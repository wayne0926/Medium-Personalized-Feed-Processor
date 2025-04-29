import logging
import sys
from bs4 import BeautifulSoup
import http.cookiejar
import io

def setup_logging(level_str='INFO', log_file=None):
    """Configures logging for the application."""
    level = getattr(logging, level_str.upper(), logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Root logger configuration
    logger = logging.getLogger()
    logger.setLevel(level)

    # Console handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # File handler (optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logging.info(f"Logging initialized. Level: {level_str}. Log file: {log_file}")
        except Exception as e:
            logging.error(f"Failed to set up file handler for {log_file}: {e}")
            # Continue with console logging
    else:
        logging.info(f"Logging initialized. Level: {level_str}. Console output only.")

def clean_html(html_content):
    """Removes HTML tags from a string, returning plain text."""
    if not html_content:
        return ""
    try:
        # Use lxml if available for better performance, otherwise use html.parser
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except ImportError:
            soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        logging.warning(f"HTML cleaning failed: {e}. Returning original content.")
        # If an unexpected error occurs during parsing, return original content
        # This can happen with severely malformed snippets in RSS feeds
        if isinstance(html_content, str):
            return html_content
        else:
            # If it's a byte string, try decoding, otherwise return an empty string
            try:
                return html_content.decode('utf-8', errors='ignore')
            except:
                return ""


def parse_netscape_cookie_file(cookie_file_path):
    """Parses a Netscape cookie file into a dictionary suitable for requests."""
    cookies = {}
    cj = http.cookiejar.MozillaCookieJar()
    try:
        # First read the file content to handle potential encoding issues
        with open(cookie_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Load into cookiejar from string content
        cj._really_load(io.StringIO(content), cookie_file_path, ignore_discard=True, ignore_expires=True)

        for cookie in cj:
            cookies[cookie.name] = cookie.value
        if not cookies:
             logging.warning(f"Failed to parse any cookies from {cookie_file_path}. The file might be empty, invalid, or cookies expired.")
        else:
             logging.info(f"Successfully parsed {len(cookies)} cookies from {cookie_file_path}")
        return cookies
    except FileNotFoundError:
        logging.error(f"Cookie file not found: {cookie_file_path}")
        return None
    except Exception as e:
        logging.error(f"Failed to parse cookie file {cookie_file_path}: {e}")
        return None

# Example function to extract main content, might need refinement based on Medium's structure
def extract_main_content_from_html(html_content, url):
    """Extracts the main article body from Medium HTML."""
    if not html_content:
        return None
    try:
        # Use lxml if available for better performance
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except ImportError:
            soup = BeautifulSoup(html_content, 'html.parser')

        # Try common Medium article selectors. This is fragile and needs monitoring.
        # Prioritize <article> tags, then specific section attributes.
        article_body = soup.find('article')

        if not article_body:
            # Medium often uses sections with specific roles or data-field attributes
            # Search for sections likely containing the main body
            potential_bodies = soup.find_all('section', attrs={'data-field': lambda x: x and 'body' in x.lower()})
            if potential_bodies:
                # Usually the longest section is the main content, but this is a heuristic
                article_body = max(potential_bodies, key=lambda tag: len(tag.get_text()))
            else:
                # Fallback: look for role="main" which might be used
                article_body = soup.find(attrs={'role': 'main'})

        if not article_body:
            logging.warning(f"Could not find the main article body container for {url}. Structure might have changed. Returning full body text as fallback.")
            # As a last resort, return the text of the entire body, minus script/style
            body_tag = soup.find('body')
            if body_tag:
                for tag in body_tag(['script', 'style', 'nav', 'header', 'footer']):
                    tag.decompose()
                return body_tag.get_text(separator='\n', strip=True)
            else:
                 logging.error(f"Could not even find the body tag for {url}. HTML might be malformed.")
                 return None # Give up if no body tag is found

        # Clean the found article body
        # Remove elements we might not want, e.g., headers, footers, sidebars within the article tag (if any)
        # Keep figure/figcaption for now as they often contain images
        # Also remove script and style tags just in case they are inside the main article body
        for unwanted_tag in article_body(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            # unwanted_tag.decompose() # Keep figure/figcaption for now
            unwanted_tag.decompose()

        # Get HTML content including tags like images, not just plain text
        # Use .prettify() or str() to get the HTML string
        # prettify() adds newlines and indentation, might help AI parsing but also increases tokens
        # str() is more compact
        # return article_body.get_text(separator='\n', strip=True) # Previous logic
        return str(article_body) # Return the HTML string

    except Exception as e:
        logging.error(f"Error extracting main content for {url}: {e}")
        return None 