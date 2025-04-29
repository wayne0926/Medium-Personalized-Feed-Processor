import feedparser
import logging
import time
import datetime
from urllib.parse import urlparse
from utils import clean_html
from config import config # Import the already loaded config

# Configure logging for this module
logger = logging.getLogger(__name__)

def _extract_source_tag_from_url(url):
    """Extracts a usable tag/name from a Medium feed URL."""
    try:
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part] # Split path and remove empty parts
        if len(path_parts) >= 2:
            # Prioritize 'tag', then 'publication', then user, then last part
            if path_parts[-2] == 'tag':
                return path_parts[-1]
            elif path_parts[-2] == 'publication':
                 return path_parts[-1]
            elif path_parts[-2] == 'feed' and path_parts[-1].startswith('@'):
                 return path_parts[-1][1:] # Username without @
            elif path_parts[-2] == 'feed':
                 return path_parts[-1] # Publication name or tag after /feed/
            else:
                return path_parts[-1] # Fallback to the last part
        elif len(path_parts) == 1:
            return path_parts[0] # Fallback if only one part
    except Exception as e:
        logger.warning(f"Could not parse source tag from URL {url}: {e}")
    return "unknown_source" # Default if parsing fails

def fetch_feeds(feed_urls):
    """Fetches and parses multiple RSS feeds, including source tags."""
    all_entries_with_source = []
    if not feed_urls:
        logger.warning("No feed URLs provided in configuration.")
        return []

    logger.info(f"Starting to fetch {len(feed_urls)} feeds...")
    for url in feed_urls:
        source_tag = _extract_source_tag_from_url(url)
        try:
            logger.debug(f"Fetching feed: {url} (Source Tag: {source_tag})")
            # Add a user-agent for politeness
            feed = feedparser.parse(url, agent='MediumPersonalizedFeedFetcher/1.0')

            # Check the bozo flag (indicates potential parsing issues)
            if feed.bozo:
                bozo_reason = feed.bozo_exception
                # Sometimes it's just a character encoding issue handled by feedparser
                if isinstance(bozo_reason, feedparser.CharacterEncodingOverride):
                    logger.warning(f"Feed encoding issue detected for {url}, but parsed successfully.")
                else:
                    logger.warning(f"Feed may be ill-formed: {url} - Error: {bozo_reason}")

            # Check if entries exist and are valid
            if not hasattr(feed, 'entries') or not feed.entries:
                logger.warning(f"No entries found in feed: {url}. Status: {getattr(feed, 'status', 'N/A')}")
                continue

            # Filter out entries without links (essential)
            valid_entries = [entry for entry in feed.entries if hasattr(entry, 'link') and entry.link]

            if len(valid_entries) < len(feed.entries):
                logger.warning(f"Excluded {len(feed.entries) - len(valid_entries)} entries without links from {url}")

            # Add source tag to each entry
            for entry in valid_entries:
                entry.source_tag = source_tag # Add the tag to the entry object

            all_entries_with_source.extend(valid_entries)
            logger.info(f"Successfully fetched and parsed {len(valid_entries)} valid entries from {url}")

        except Exception as e:
            logger.error(f"Failed to fetch or parse feed {url}: {e}", exc_info=True) # Include traceback

    logger.info(f"Total valid entries fetched from all feeds: {len(all_entries_with_source)}")
    return all_entries_with_source

def extract_entry_data(entry):
    """Extracts and cleans data from a single feedparser entry, including source tag."""
    try:
        link = getattr(entry, 'link', None)
        if not link:
            logger.warning("Entry missing link attribute, skipping.")
            return None

        # Extract title, use link as fallback if missing (unlikely for valid entries)
        title = getattr(entry, 'title', link)

        # Extract and clean summary/description
        summary_html = getattr(entry, 'summary', getattr(entry, 'description', ''))
        summary_text = clean_html(summary_html)

        # Parse published time, handling potential errors
        published_iso = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
             try:
                published_time = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
                published_iso = published_time.isoformat()
             except (TypeError, ValueError, OverflowError) as time_err:
                logger.warning(f"Could not parse published time for entry {link}: {time_err}. Original value: {entry.published_parsed}")
                published_iso = None

        # Use entry ID, fallback to link
        entry_id = getattr(entry, 'id', link)
        source_tag = getattr(entry, 'source_tag', 'unknown_source') # Get the source tag added earlier

        # Basic check for very short summaries that might indicate poor feed quality
        if len(summary_text) < 50:
             logger.debug(f"Summary for entry {link} is very short (length {len(summary_text)}). May affect filtering accuracy.")

        return {
            'title': title,
            'link': link,
            'summary': summary_text,
            'published_iso': published_iso,
            'id': entry_id,
            'source_tag': source_tag # Include source_tag in the dictionary
        }
    except Exception as e:
        entry_link_for_log = getattr(entry, 'link', '[Link Missing]')
        logger.error(f"Failed to extract data for entry {entry_link_for_log}: {e}", exc_info=True)
        return None

def get_articles_from_config_feeds():
    """Fetches all feeds from config and extracts data for each entry."""
    feed_urls = config.get('medium_feeds', [])
    if not feed_urls:
        logger.warning("No RSS feeds configured in config.yaml.")
        return []

    # fetch_feeds now returns entries with source_tag attached
    raw_entries = fetch_feeds(feed_urls)
    article_data_list = []
    processed_links = set() # Avoid duplicates if an article appears in multiple feeds

    for entry in raw_entries:
        article_data = extract_entry_data(entry)
        if article_data and article_data['link'] not in processed_links:
            article_data_list.append(article_data)
            processed_links.add(article_data['link'])
        elif article_data:
             logger.debug(f"Skipping duplicate entry from a different feed: {article_data['link']}")

    logger.info(f"Extracted data for {len(article_data_list)} unique articles.")
    return article_data_list