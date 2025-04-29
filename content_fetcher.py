import requests
import logging
from config import config # Import the already loaded config
from utils import parse_netscape_cookie_file, extract_main_content_from_html
# Optional: newspaper3k as a fallback
# try:
#     from newspaper import Article
#     NEWSPAPER_AVAILABLE = True
# except ImportError:
#     NEWSPAPER_AVAILABLE = False
NEWSPAPER_AVAILABLE = False # Keeping it simple for now

logger = logging.getLogger(__name__)

def fetch_full_article_content(url):
    """Fetches the full HTML content of an article using cookies."""
    fetch_conf = config.get('fetch_config', {})
    cookie_file = fetch_conf.get('cookie_file')
    timeout = fetch_conf.get('fetch_timeout', 30)
    proxy = fetch_conf.get('proxy') # Get proxy setting
    # use_newspaper = fetch_conf.get('use_newspaper_fallback', False) and NEWSPAPER_AVAILABLE
    use_newspaper = False # Keep it simple

    if not cookie_file:
        logger.error("Cookie file path not configured in fetch_config. Cannot fetch full content.")
        return None

    # Parse cookies from Netscape format file
    cookies_dict = parse_netscape_cookie_file(cookie_file)
    if cookies_dict is None:
        logger.error(f"Could not parse cookies from {cookie_file}. Cannot proceed with authenticated fetching.")
        return None # Critical error if cookies cannot be parsed
    if not cookies_dict:
         logger.warning(f"Could not load any cookies from {cookie_file}. Fetching might fail or hit paywalls.")
         # Still continue, maybe some articles are public

    # Prepare proxies dictionary if proxy is set
    proxies = None
    if proxy:
        proxies = {
            'http': proxy,
            'https': proxy
        }
        logger.info(f"Using proxy for fetching: {proxy}")

    headers = {
        # Use a realistic User-Agent
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1', # Do Not Track
        'Upgrade-Insecure-Requests': '1',
        # Referer might help sometimes, but can be omitted
        # 'Referer': 'https://medium.com/',
    }

    logger.debug(f"Attempting to fetch full content for URL: {url}")
    try:
        response = requests.get(
            url,
            headers=headers,
            cookies=cookies_dict, # requests library handles dict format
            timeout=timeout,
            allow_redirects=True, # Allow redirects
            proxies=proxies # Add proxies here
        )
        response.raise_for_status() # Check for HTTP errors (4xx, 5xx)

        # Basic paywall check (very heuristic, might need improvement)
        # Look for common phrases indicating member-only content when *not* logged in properly
        # This check might need adjustment based on Medium's current wording
        html_content = response.text
        if "Member-only story" in html_content and "Upgrade" in html_content and "membership" in html_content:
             # If possible, check for presence of user-specific elements (hard without knowing structure)
             # For now, log a warning if common paywall hints are seen
             logger.warning(f"Potentially encountered a paywall for {url}. Cookies might be invalid/expired or lack permissions.")
             # Consider returning None or a specific marker if paywall is strongly suspected

        logger.info(f"Successfully fetched HTML content for URL: {url} (Size: {len(html_content)} bytes)")
        return html_content # Return the full HTML

    except requests.exceptions.Timeout:
        logger.error(f"Timeout error fetching full content for {url} after {timeout} seconds.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching full content for {url}: {e.response.status_code} {e.response.reason}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching full content for {url}: {e}")
    except Exception as e:
         logger.error(f"Unexpected error during full content fetch for {url}: {e}", exc_info=True)

    return None # Return None on any failure

def get_and_extract_article_text(url):
    """Fetches HTML and extracts the main text content."""
    html_content = fetch_full_article_content(url)
    if not html_content:
        logger.error(f"Failed to fetch HTML for {url}, cannot extract text.")
        return None

    extracted_text = extract_main_content_from_html(html_content, url)

    # --- Optional Newspaper3k fallback --- #
    # fetch_conf = config.get('fetch_config', {})
    # use_newspaper = fetch_conf.get('use_newspaper_fallback', False) and NEWSPAPER_AVAILABLE
    # if not extracted_text and use_newspaper:
    #     logger.warning(f"BeautifulSoup failed to extract main content for {url}. Trying newspaper3k fallback.")
    #     try:
    #         article = Article(url)
    #         # Feed the already downloaded HTML to newspaper
    #         article.download(input_html=html_content)
    #         article.parse()
    #         extracted_text = article.text
    #         if extracted_text:
    #             logger.info(f"Successfully extracted text using newspaper3k fallback: {url}")
    #         else:
    #             logger.error(f"Newspaper3k fallback also failed to extract text: {url}")
    #     except Exception as newspaper_e:
    #         logger.error(f"Newspaper3k fallback failed for {url}: {newspaper_e}")

    if not extracted_text:
        logger.error(f"Failed to extract main text content for {url} after trying main method.")
        return None

    logger.info(f"Successfully extracted main text content for: {url} (Approx. size: {len(extracted_text)} chars)")
    return extracted_text 