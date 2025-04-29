import openai
import json
import logging
import time
import os
import httpx # Import httpx to support proxies with the openai library
from config import config # Import the already loaded config

logger = logging.getLogger(__name__)

# Initialize OpenAI client
ai_conf = config.get('ai_filter', {})
api_key = ai_conf.get('api_key')
api_base_url_from_config = ai_conf.get('api_base_url')
api_base_url = os.getenv('OPENAI_API_BASE_URL', api_base_url_from_config) # Env var takes precedence
proxy = ai_conf.get('proxy') # Get proxy setting from loaded config

client = None # Initialize client to None

if api_key:
    try:
        # Configure httpx client with proxy if provided
        http_client = None
        if proxy:
            try:
                # Check if socks5h or socks5 specified for specific handling if needed
                # Basic proxy setup for httpx
                proxies = {
                    "http://": proxy,
                    "https://": proxy,
                }
                http_client = httpx.Client(proxies=proxies)
                logger.info(f"Configuring OpenAI client with proxy: {proxy}")
            except Exception as proxy_err:
                logger.error(f"Failed to configure httpx client with proxy '{proxy}': {proxy_err}. Proceeding without proxy.")
                http_client = None # Fallback to no proxy

        # Recommended: use openai.OpenAI() for client initialization
        client_params = {
            'api_key': api_key,
            'http_client': http_client # Pass the configured httpx client
        }
        if api_base_url:
            client_params['base_url'] = api_base_url
            logger.info(f"Using API Base URL: {api_base_url}")

        client = openai.OpenAI(**client_params)
        logger.info("OpenAI client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        client = None
else:
    logger.warning("OpenAI API key not found. AI processing features will be disabled.")
    client = None

def filter_article_with_ai(article_data):
    """Filters an article based on title and summary using AI."""
    if not client:
        logger.error("OpenAI client not initialized. Cannot perform AI filtering.")
        return None

    ai_conf = config.get('ai_filter', {})
    interests = ai_conf.get('interests', [])
    dislikes = ai_conf.get('dislikes', [])
    model = ai_conf.get('filtering_model', 'gpt-3.5-turbo')

    if not interests:
        logger.warning("AI filtering interests not defined in config. Filtering may be ineffective.")

    prompt = f"""
    Analyze the following article based ONLY on its title and summary. Assess its relevance to my interests and rigorously evaluate its potential quality and depth.

    My interests are: {interests}
    I want to filter out articles that are primarily about: {dislikes}, OR articles that appear superficial, promotional, clickbaity, or lack substantial content based on this initial information.

    Title: "{article_data['title']}"
    Summary: "{article_data['summary'][:1500]}" # Limit summary length

    Evaluate the following:
    1. Relevance: Is the topic highly relevant to my interests? (Answer: High / Medium / Low / None)
    2. Quality/Type: Based ONLY on the title and summary, estimate the **likely depth and quality**. Does it seem like:
       - In-depth: Likely contains deep analysis, original research, or rigorous technical detail.
       - Opinion: Likely a well-reasoned, potentially insightful opinion piece.
       - Overview: Likely a general summary, possibly lacking depth.
       - Shallow: Likely superficial, a listicle without substance, generic advice, or philosophical platitudes.
       - Promotional: Likely marketing, sales-oriented, or primarily promoting a product/service.
       - Low-Quality: Likely clickbait, poorly written, or lacking credible information.
       (Answer: In-depth / Opinion / Overview / Shallow / Promotional / Low-Quality)

    Be critical in your quality assessment. Prioritize potential depth and substance. Err on the side of caution; if it looks shallow or promotional, classify it as such.

    Output your evaluation strictly as a JSON object with keys "relevance" and "quality_type".
    Example: {{"relevance": "High", "quality_type": "In-depth"}}
    """

    logger.debug(f"Sending filtering request to AI for article: {article_data['link']}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2 # Lower temperature for more deterministic classification
        )
        result_content = response.choices[0].message.content
        logger.debug(f"Received AI filtering response: {result_content}")
        result_json = json.loads(result_content)

        # Basic validation of the returned JSON structure
        if not isinstance(result_json, dict) or 'relevance' not in result_json or 'quality_type' not in result_json:
             logger.error(f"AI filtering returned unexpected JSON format for {article_data['link']}: {result_content}")
             return None

        return result_json

    except openai.APIError as e:
         logger.error(f"OpenAI API error during filtering for {article_data['link']}: {e}. Status={e.status_code}, Message={e.message}")
         # Implement retry logic if needed, e.g., for rate limits or temporary server errors
         # time.sleep(5) # Simple backoff
         # return filter_article_with_ai(article_data) # Beware of recursion depth
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode AI filtering JSON response for {article_data['link']}: {e}. Response: {result_content}")
    except Exception as e:
        logger.error(f"Unexpected error during AI filtering for {article_data['link']}: {e}", exc_info=True)

    return None # Return None on failure

def filter_article_content_with_ai(full_html_content, article_url):
    """Filters an article based on its full HTML content using AI."""
    if not client:
        logger.error("OpenAI client not initialized. Cannot perform AI content filtering.")
        return None

    ai_conf = config.get('ai_filter', {})
    interests = ai_conf.get('interests', [])
    dislikes = ai_conf.get('dislikes', [])
    # Use the same filtering model as the first pass, unless a specific one is defined
    model = ai_conf.get('content_filtering_model', ai_conf.get('filtering_model', 'gpt-3.5-turbo'))

    if not interests:
        logger.warning("AI filtering interests not defined in config. Content filtering may be ineffective.")

    # Basic check for empty or very short content
    if not full_html_content or len(full_html_content) < 50:
        logger.warning(f"Content for {article_url} is too short or empty for meaningful content filtering.")
        # Return a neutral/default result or None? Let's return None to indicate failure.
        return None

    # Consider potential token limits - maybe truncate the input?
    # For now, send the whole HTML, but be aware of potential context length errors.
    # A simple truncation might be: max_len = 16000 # Adjust based on model limits
    # truncated_content = full_html_content[:max_len]
    # if len(full_html_content) > max_len:
    #     logger.warning(f"Content for {article_url} truncated to {max_len} chars for AI content filtering.")

    prompt = f"""
    Critically analyze the following article based on its **full HTML content**. Focus on the main substance, ignoring boilerplate/ads.
    My interests are: {interests}
    I want to filter out articles that are primarily about: {dislikes}, AND articles that lack **depth, originality, or rigorous analysis**, even if related to my interests.

    Article HTML Content (from {article_url}):
    ```html
    {full_html_content[:16000]} 
    ```
    { "... (content truncated)" if len(full_html_content) > 16000 else "" }

    Evaluate the following based on the **actual substance, depth, and originality demonstrated in the content**:
    1. Relevance: Is the core topic highly relevant to my interests? (Answer: High / Medium / Low / None)
    2. Quality/Type: Assess the **true quality and depth**. Is this:
       - In-depth: Provides significant depth, rigorous analysis, original insights, or substantial technical detail.
       - Opinion: Presents a well-reasoned, substantiated, and potentially insightful opinion.
       - Overview: A general summary or survey; lacks significant depth or original analysis.
       - Shallow: Lacks substance, offers generic advice, philosophical platitudes, superficial analysis, or is mainly a listicle.
       - Promotional: Primarily focused on marketing, selling, or promoting something.
       - Low-Quality: Poorly written, contains errors, lacks credibility, is clickbait, or is unoriginal/rehashed.
       (Answer: In-depth / Opinion / Overview / Shallow / Promotional / Low-Quality)

    Be very strict in your quality assessment. Only classify as 'In-depth' or 'Opinion' if the article genuinely demonstrates these qualities. If it is superficial, generic, promotional, or poorly substantiated, classify it accordingly (Shallow, Promotional, Low-Quality).

    Output your evaluation strictly as a JSON object with keys "relevance" and "quality_type".
    Example: {{"relevance": "Medium", "quality_type": "Opinion"}}
    """

    logger.debug(f"Sending content filtering request to AI for article: {article_url}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2 # Low temperature for consistent classification
        )
        result_content = response.choices[0].message.content
        logger.debug(f"Received AI content filtering response: {result_content}")
        result_json = json.loads(result_content)

        # Basic validation
        if not isinstance(result_json, dict) or 'relevance' not in result_json or 'quality_type' not in result_json:
            logger.error(f"AI content filtering returned unexpected JSON format for {article_url}: {result_content}")
            return None

        return result_json

    except openai.APIError as e:
        # Handle context length error specifically if possible
        if hasattr(e, 'code') and e.code == 'context_length_exceeded':
             logger.error(f"AI content filtering failed for {article_url} due to context length exceeded ({model}). Consider implementing smarter truncation or chunking in code.")
             # Return a specific error or None?
             return None # Indicate failure
        else:
            logger.error(f"OpenAI API error during content filtering for {article_url}: {e}. Status={getattr(e, 'status_code', 'N/A')}, Message={getattr(e, 'message', str(e))}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode AI content filtering JSON response for {article_url}: {e}. Response: {result_content}")
    except Exception as e:
        logger.error(f"Unexpected error during AI content filtering for {article_url}: {e}", exc_info=True)

    return None # Indicate failure

def process_content_with_ai(full_text, article_url):
    """Uses AI to convert text to Markdown and add vocabulary annotations."""
    if not client:
        logger.error("OpenAI client not initialized. Cannot perform AI processing.")
        return "[Error: AI client not initialized]"

    ai_conf = config.get('ai_filter', {})
    english_level = ai_conf.get('english_level', 'CEFR C1')
    model = ai_conf.get('processing_model', 'gpt-4-turbo') # Use a model suitable for long text
    # Read new config options
    enable_annotation = ai_conf.get('enable_vocabulary_annotation', False) # Default to False if not set
    annotation_language = ai_conf.get('annotation_language', None)

    # Simple check if text is empty or too short
    if not full_text or len(full_text) < 100:
        logger.warning(f"Content for {article_url} is too short or empty. Skipping AI processing.")
        return full_text # Return original text if too short

    # --- Build the prompt dynamically ---
    prompt_base = f"""
    You are an expert text processor specializing in converting HTML to Markdown.
    Your primary task is to convert the following English article HTML into well-structured Markdown format.

    Instructions:
    1. Convert the input HTML into clean Markdown. Use appropriate Markdown syntax for headings (derived from <h1>-<h6> tags), lists (<ul>, <ol>, <li>), blockquotes (<blockquote>), paragraphs (<p>), and code blocks (<pre>, <code>). Ensure paragraphs are separated by a blank line.
    2. **Image Handling:** Convert `<img>` HTML tags to Markdown image syntax: `![alt text](src)`. Use the `alt` attribute from the `<img>` tag as the alt text. If the `alt` attribute is missing or empty, use a generic placeholder like 'image'.
    3. Preserve the original meaning and structure of the article as much as possible. Do not summarize or add external information.
    4. Output ONLY the processed Markdown text.
    """

    prompt_annotation_instructions = "" # Initialize as empty
    if enable_annotation and annotation_language:
        prompt_annotation_instructions = f"""

    **Additional Task: Vocabulary Annotation**
    Besides Markdown conversion, your *secondary* task is to annotate potentially difficult vocabulary for a user whose English level is approximately {english_level}.

    Annotation Instructions:
    A. Identify specific words or short technical phrases (1-4 words) in the *text content* that might be challenging for a {english_level} learner reading a technical article. Examples: 'idempotent', 'concurrency control', 'distributed ledger', 'gradient descent'.
    B. Immediately after each identified challenging word/phrase, add its concise translation into **{annotation_language}** in parentheses. Example (if target language is Chinese): "...a very sophisticated (复杂的) approach...", "...implementing concurrency control (并发控制)..." Ensure the translation fits naturally.
    C. Do NOT annotate common English words (e.g., 'the', 'is', 'and', 'but', 'article', 'content', 'system'). Focus on domain-specific terms, advanced vocabulary, or idioms that hinder understanding for the target level.
    D. Annotations should ONLY be applied to the text content, not within image tags, code blocks, or other Markdown syntax elements.
    E. If performing annotations, ensure the final output is still valid Markdown with the inline ({annotation_language}) annotations.
    """
        # Modify the base instruction about the output format if annotation is enabled
        prompt_base = prompt_base.replace(
            "4. Output ONLY the processed Markdown text.",
            f"4. Output ONLY the processed Markdown text, potentially including inline {annotation_language} annotations as per the instructions below."
        )

    # Combine prompts
    prompt = f"""{prompt_base}{prompt_annotation_instructions}

    Article HTML (from {article_url}):
    ---
    {full_text}
    ---
    """
    if enable_annotation and annotation_language:
         logger.info(f"AI processing for {article_url}: Markdown conversion and {annotation_language} annotations requested.")
    else:
         logger.info(f"AI processing for {article_url}: Markdown conversion ONLY requested.")

    logger.debug(f"Sending content processing request to AI for article: {article_url}")
    try:
        # Consider potential context length limits. Very long articles might need chunking.
        # A simplified check (adjust based on model limits and typical article lengths):
        # if len(full_text) > 30000: # Rough estimate for character limit
        #     logger.warning(f"Article {article_url} is very long ({len(full_text)} characters). Processing may fail or be truncated. Consider implementing chunking.")
        #     # return process_large_article_in_chunks(full_text, english_level, model) # Placeholder

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            # max_tokens=... # Optional: can limit output tokens, but might truncate content
            temperature=0.3 # Keep creativity low for formatting/annotation task
        )
        processed_markdown = response.choices[0].message.content
        logger.info(f"AI content processing successful for article: {article_url}")
        return processed_markdown

    except openai.APIError as e:
         # Specific check for context length exceeded
        if hasattr(e, 'code') and e.code == 'context_length_exceeded':
             logger.error(f"AI processing failed for {article_url} due to context length exceeding model limit ({model}). Article too long for single call. Chunking needed.")
             return f"[Error: Article too long for model '{model}'. Chunking needed.]"
        else:
            logger.error(f"OpenAI API error during processing for {article_url}: {e}. Status={getattr(e, 'status_code', 'N/A')}, Message={getattr(e, 'message', str(e))}")

    except json.JSONDecodeError as e:
        # This shouldn't happen unless the API response format changes drastically
        logger.error(f"Failed to decode (unexpected) AI processing JSON response for {article_url}: {e}. Raw response: {response.choices[0].message.content if response and response.choices else 'No response'}")
    except Exception as e:
        logger.error(f"Unexpected error during AI processing for {article_url}: {e}", exc_info=True)

    return f"[Error: AI processing failed for {article_url}. See logs.]"

# TODO (Optional): Implement chunking for very long articles
# def process_large_article_in_chunks(full_text, english_level, model, chunk_size=10000): # Adjust chunk size
#     logger.warning(f"Attempting to chunk large article...")
#     # Basic text splitting (could be improved by splitting at paragraph boundaries)
#     chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
#     processed_chunks = []
#     for i, chunk in enumerate(chunks):
#         logger.debug(f"Processing chunk {i+1}/{len(chunks)}")
#         # Modify prompt slightly for chunk?
#         processed_chunk = process_content_with_ai(chunk, f"[Chunk {i+1}/{len(chunks)}]", english_level, model) # Need to adjust call
#         if "[Error:" in processed_chunk: # Use Chinese error marker check
#              logger.error(f"Error in chunk {i+1}. Stopping chunking.")
#              return "[Error: Failed during chunking]"
#         processed_chunks.append(processed_chunk)
#         time.sleep(1) # If processing many chunks quickly, avoid hitting rate limit
#     return "\n\n".join(processed_chunks) 