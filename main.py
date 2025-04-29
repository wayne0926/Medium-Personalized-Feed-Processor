import logging
import json # Used to store filter result strings in the database
import os # Needed for saving locally
import re # Needed for filename cleanup

# Import project modules
from config import config # Ensure config is loaded first and logging is set up
from rss_fetcher import get_articles_from_config_feeds
from ai_processor import filter_article_with_ai, filter_article_content_with_ai, process_content_with_ai
from content_fetcher import get_and_extract_article_text
from api_pusher import push_to_api # Use the pusher again
import state_manager as sm # Use an alias for the state manager

logger = logging.getLogger(__name__)

# OUTPUT_DIR = 'output_markdown' # No longer needed

# Helper function to sanitize filenames
def sanitize_filename(filename):
    # Remove or replace characters not allowed in filenames
    # Remove: / ? < > \ : * | "
    sanitized = re.sub(r'[\\/*?:"<>|]', '', filename)
    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    # Limit filename length (e.g., 200 characters)
    max_len = 200
    if len(sanitized) > max_len:
        # Try to preserve the extension (although ours is .md)
        name, ext = os.path.splitext(sanitized)
        name = name[:max_len - len(ext) - 1] # -1 for the dot
        sanitized = name + ext
    # Prevent filenames ending with dots or spaces (Windows)
    sanitized = sanitized.rstrip('. ')
    # Handle reserved filenames (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    reserved_names = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if sanitized.upper() in reserved_names:
        sanitized = "_" + sanitized # Prepend underscore
    if not sanitized:
        sanitized = "untitled" # If empty after cleaning
    return sanitized

def save_to_local(article_data, processed_markdown, base_output_dir):
    """Saves the processed Markdown to a local file."""
    try:
        title = article_data.get('title', 'No Title Provided')
        source_folder_base = article_data.get('source_tag', 'uncategorized')

        # Build directory structure similar to API pusher
        target_subfolder = f"medium/{source_folder_base}"
        full_output_dir = os.path.join(base_output_dir, target_subfolder)

        # Create directory (if it doesn't exist)
        os.makedirs(full_output_dir, exist_ok=True)

        # Create a safe filename
        safe_title = sanitize_filename(title)
        filename = f"{safe_title}.md"
        target_filepath = os.path.join(full_output_dir, filename)

        # Write the file
        with open(target_filepath, 'w', encoding='utf-8') as f:
            f.write(processed_markdown)

        logger.info(f"Successfully saved article '{title}' locally to: {target_filepath}")
        return True, target_filepath # Return success status and file path

    except IOError as e:
        logger.error(f"IO Error saving article '{title}' to local file {target_filepath}: {e}")
    except OSError as e:
         logger.error(f"OS Error creating directory {full_output_dir}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error saving article '{title}' locally: {e}", exc_info=True)

    return False, None # Return False for any failure

def main():
    logger.info("--- Starting Medium Personalized Feed Run ---")
    # Counters
    passed_stage1_filter_count = 0
    passed_stage2_filter_count = 0
    pushed_count = 0 # Counter for successfully pushed via API
    saved_local_count = 0 # Counter for successfully saved locally
    filtered_out_stage1_count = 0
    filtered_out_stage2_count = 0
    failed_count = 0 # General failures (fetch, AI, output)
    skipped_processed_count = 0

    # Get output configuration
    output_config = config.get('output', {})
    output_method = output_config.get('method', 'api').lower() # Default to 'api', ensure lowercase
    local_output_dir = output_config.get('local_dir', 'output_markdown')
    logger.info(f"Configured output method: {output_method}")
    if output_method == 'local':
        logger.info(f"Local save directory: {local_output_dir}")
    elif output_method != 'api':
        logger.warning(f"Invalid output method '{output_method}' in config. Falling back to 'api'.")
        output_method = 'api' # Fallback to api

    # 1. Get articles from RSS feeds specified in config
    try:
        articles = get_articles_from_config_feeds()
        if not articles:
            logger.info("No new articles found in the configured feeds.")
            logger.info("--- Run Finished ---")
            return
        total_articles_fetched = len(articles)
        logger.info(f"Found {total_articles_fetched} unique articles from RSS feeds.")
    except Exception as e:
         logger.critical(f"Failed to fetch or parse RSS feeds: {e}", exc_info=True)
         logger.info("--- Run Terminated Due to Critical Error ---")
         return

    # Get AI filter configuration
    ai_conf = config.get('ai_filter', {})
    accepted_relevance = ai_conf.get('accepted_relevance', ['High', 'Medium'])
    # Ensure accepted_quality is a list
    accepted_quality_raw = ai_conf.get('accepted_quality', ['In-depth', 'Opinion', 'Overview'])
    accepted_quality = list(accepted_quality_raw) if isinstance(accepted_quality_raw, (list, tuple)) else ['In-depth', 'Opinion', 'Overview']

    # Add specific accepted quality for content filtering if needed, else reuse first pass
    accepted_content_quality_raw = ai_conf.get('accepted_content_quality', accepted_quality)
    accepted_content_quality = list(accepted_content_quality_raw) if isinstance(accepted_content_quality_raw, (list, tuple)) else accepted_quality

    # 2. Process each article
    for article_data in articles:
        link = article_data['link']
        title = article_data['title']
        logger.info(f"[{articles.index(article_data) + 1}/{total_articles_fetched}] Processing article: '{title}' ({link})")

        # 3. Check if article has already been processed (using state manager)
        if sm.is_article_processed(link):
            logger.info(f"Skipping already processed article: {link}")
            skipped_processed_count += 1
            continue

        # 4. AI Filter Stage 1 (Based on title/summary)
        ai_filter_result_stage1 = filter_article_with_ai(article_data)
        filter_result_stage1_str = json.dumps(ai_filter_result_stage1) if ai_filter_result_stage1 else None

        if not ai_filter_result_stage1:
            logger.error(f"AI filtering Stage 1 failed for {link}. Skipping article.")
            sm.mark_article_status(link, 'failed_filter_stage1', title, filter_result_stage1_str)
            failed_count += 1
            continue

        relevance_s1 = ai_filter_result_stage1.get('relevance')
        quality_s1 = ai_filter_result_stage1.get('quality_type')

        if relevance_s1 not in accepted_relevance or quality_s1 not in accepted_quality:
            logger.info(f"Article rejected by AI filter Stage 1: {link} (Relevance: {relevance_s1}, Quality: {quality_s1})")
            sm.mark_article_status(link, 'filtered_out_stage1', title, filter_result_stage1_str)
            filtered_out_stage1_count += 1
            continue

        logger.info(f"Article passed AI filter Stage 1: {link} (Relevance: {relevance_s1}, Quality: {quality_s1})")
        sm.mark_article_status(link, 'passed_filter_stage1', title, filter_result_stage1_str) # Mark intermediate state
        passed_stage1_filter_count += 1

        # 5. Fetch full article HTML content
        full_article_html = get_and_extract_article_text(link) # Now returns HTML
        if not full_article_html:
            logger.error(f"Failed to fetch or extract full HTML content for {link}. Skipping.")
            # Use the result string from stage 1 filter for marking status
            sm.mark_article_status(link, 'failed_fetch', title, filter_result_stage1_str)
            failed_count += 1
            continue

        # 6. AI Filter Stage 2 (Based on full HTML content)
        ai_filter_result_stage2 = filter_article_content_with_ai(full_article_html, link)
        # We might want to store stage 2 results too, but let's keep using stage 1 for now

        if not ai_filter_result_stage2:
            logger.error(f"AI filtering Stage 2 (content) failed for {link}. Skipping article.")
            sm.mark_article_status(link, 'failed_filter_stage2', title, filter_result_stage1_str)
            failed_count += 1
            continue

        relevance_s2 = ai_filter_result_stage2.get('relevance')
        quality_s2 = ai_filter_result_stage2.get('quality_type')

        # Use potentially different quality criteria for content stage
        if relevance_s2 not in accepted_relevance or quality_s2 not in accepted_content_quality:
            logger.info(f"Article rejected by AI filter Stage 2 (content): {link} (Relevance: {relevance_s2}, Quality: {quality_s2})")
            sm.mark_article_status(link, 'filtered_out_stage2', title, filter_result_stage1_str) # Still use stage 1 result for simplicity
            filtered_out_stage2_count += 1
            continue

        logger.info(f"Article passed AI filter Stage 2 (content): {link} (Relevance: {relevance_s2}, Quality: {quality_s2})")
        sm.mark_article_status(link, 'passed_filter_stage2', title, filter_result_stage1_str) # Mark intermediate state
        passed_stage2_filter_count += 1

        # 7. AI Content Processing (Markdown and Vocabulary) - Input is still the HTML
        processed_markdown = process_content_with_ai(full_article_html, link)
        if not processed_markdown or processed_markdown.startswith("[Error:") or processed_markdown.startswith("[错误:"): # Check both English and potential leftover Chinese error prefix
             logger.error(f"AI content processing failed for {link}. Error: {processed_markdown}")
             sm.mark_article_status(link, 'failed_ai_processing', title, filter_result_stage1_str)
             failed_count += 1
             continue # Skip saving/pushing if processing failed

        sm.mark_article_status(link, 'processed', title, filter_result_stage1_str) # Mark as processed before attempting output

        # 8. Output Article (API or Local)
        output_successful = False
        output_target = None # Can store API response details or local filepath

        if output_method == 'api':
            logger.debug(f"Attempting to push article {link} to API")
            push_successful = push_to_api(article_data, processed_markdown)
            if push_successful:
                output_successful = True
                output_target = "API" # Or capture filename from API response if needed later
                logger.info(f"Successfully processed and pushed to API: {link}")
                sm.mark_article_status(link, 'pushed', title, filter_result_stage1_str)
                pushed_count += 1
            else:
                # Error is logged within push_to_api
                logger.error(f"Failed to push article {link} to API. See previous logs for details.")
                sm.mark_article_status(link, 'failed_push', title, filter_result_stage1_str)
                failed_count += 1
        elif output_method == 'local':
            logger.debug(f"Attempting to save article {link} to local directory {local_output_dir}")
            save_successful, saved_filepath = save_to_local(article_data, processed_markdown, local_output_dir)
            if save_successful:
                output_successful = True
                output_target = saved_filepath
                # Logger message already inside save_to_local
                sm.mark_article_status(link, 'saved_local', title, filter_result_stage1_str)
                saved_local_count += 1
            else:
                # Error is logged within save_to_local
                logger.error(f"Failed to save article {link} locally. See previous logs for details.")
                sm.mark_article_status(link, 'failed_save_local', title, filter_result_stage1_str)
                failed_count += 1
        # else case is already handled by the initial check and fallback

    # --- Run Summary --- #
    logger.info("--- Medium Personalized Feed Run Summary ---")
    logger.info(f"Total unique articles found in feeds: {total_articles_fetched}")
    logger.info(f"Articles previously processed (skipped): {skipped_processed_count}")
    attempted_count = total_articles_fetched - skipped_processed_count
    logger.info(f"Articles attempted for processing: {attempted_count}")
    logger.info(f"--- AI Filter Stage 1 (Title/Summary) ---")
    logger.info(f"   Articles filtered out: {filtered_out_stage1_count}")
    logger.info(f"   Articles passed: {passed_stage1_filter_count}")
    logger.info(f"--- AI Filter Stage 2 (Full Content) ---")
    logger.info(f"   Articles filtered out: {filtered_out_stage2_count}")
    logger.info(f"   Articles passed (proceeded to processing): {passed_stage2_filter_count}")

    # Adjust summary based on output method
    processed_successfully_count = pushed_count + saved_local_count # Count of articles that made it through processing and output
    logger.info(f"--- Content Processing & Output ---")
    logger.info(f"   Articles successfully processed (AI): {processed_successfully_count + failed_count - filtered_out_stage1_count - filtered_out_stage2_count}") # Approximation might be slightly off if AI processing fails but content filter passed
    if output_method == 'api':
        logger.info(f"   Articles successfully pushed to API: {pushed_count}")
    elif output_method == 'local':
        logger.info(f"   Articles successfully saved locally: {saved_local_count}")
    logger.info(f"   Articles failed during fetch, AI processing, or output: {failed_count}")
    logger.info(f"--- Run Finished ---")


if __name__ == "__main__":
    # Ensure the state manager initializes the database if it doesn't exist
    sm.initialize_database()
    main()