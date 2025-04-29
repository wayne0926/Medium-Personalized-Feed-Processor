import yaml
import os
import logging
from dotenv import load_dotenv
from utils import setup_logging # Import from our utils module

CONFIG_FILE = 'config.yaml'

def load_config():
    """Loads configuration from YAML file and environment variables."""
    # First, load environment variables from .env file
    load_dotenv()

    # Load base configuration from YAML file
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file '{CONFIG_FILE}' not found. Please create it.")
        raise
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file '{CONFIG_FILE}': {e}")
        raise

    # Set up logging based on the configuration
    log_config = config.get('logging', {})
    setup_logging(log_config.get('level', 'INFO'), log_config.get('log_file'))
    logging.info("Configuration loading started.")


    # --- Validate required sections and values ---
    required_sections = ['medium_feeds', 'ai_filter', 'fetch_config', 'target_api', 'state_database']
    for section in required_sections:
        if section not in config:
            logging.error(f"Missing required configuration section: '{section}'")
            raise ValueError(f"Missing config section: '{section}'")

    if not isinstance(config['medium_feeds'], list) or not config['medium_feeds']:
        logging.warning("'medium_feeds' list in config.yaml is empty or invalid. No feeds to process.")
        # Allow empty list to proceed, but log warning

    if 'cookie_file' not in config['fetch_config']:
         logging.error("Missing 'cookie_file' path in 'fetch_config' section.")
         raise ValueError("Missing 'cookie_file' in fetch_config")

    if 'url' not in config['target_api']:
         logging.error("Missing 'url' in 'target_api' section.")
         raise ValueError("Missing API URL in target_api config")

    # --- Supplement configuration with environment variables (sensitive data) ---
    config['ai_filter']['api_key'] = os.getenv('OPENAI_API_KEY')
    config['target_api']['api_key'] = os.getenv('TARGET_API_KEY')

    # --- Load optional proxy settings from config ---
    # AI Filter Proxy
    ai_proxy = config.get('ai_filter', {}).get('proxy')
    if ai_proxy:
        config['ai_filter']['proxy'] = ai_proxy
        logging.info(f"Using AI filter proxy: {ai_proxy}")
    else:
        # Check environment variables as fallback
        http_proxy_env = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy_env = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        if https_proxy_env:
            config['ai_filter']['proxy'] = https_proxy_env # Prefer HTTPS
            logging.info(f"Using AI filter proxy from environment HTTPS_PROXY: {https_proxy_env}")
        elif http_proxy_env:
            config['ai_filter']['proxy'] = http_proxy_env
            logging.info(f"Using AI filter proxy from environment HTTP_PROXY: {http_proxy_env}")
        else:
            config['ai_filter']['proxy'] = None # Explicitly set to None if not found

    # Fetch Config Proxy
    fetch_proxy = config.get('fetch_config', {}).get('proxy')
    if fetch_proxy:
        config['fetch_config']['proxy'] = fetch_proxy
        logging.info(f"Using content fetching proxy: {fetch_proxy}")
    else:
        # Check environment variables as fallback (independent check)
        http_proxy_env = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy_env = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        if https_proxy_env:
            config['fetch_config']['proxy'] = https_proxy_env # Prefer HTTPS
            logging.info(f"Using content fetching proxy from environment HTTPS_PROXY: {https_proxy_env}")
        elif http_proxy_env:
            config['fetch_config']['proxy'] = http_proxy_env
            logging.info(f"Using content fetching proxy from environment HTTP_PROXY: {http_proxy_env}")
        else:
            config['fetch_config']['proxy'] = None # Explicitly set to None if not found

    if not config['ai_filter'].get('api_key'):
        logging.warning("OPENAI_API_KEY not found in environment variables. AI features will fail.")
        # Decide if this should be a fatal error based on usage
        # raise ValueError("Missing OPENAI_API_KEY")

    if config['target_api'].get('url') and config['target_api'][ 'url'].startswith('YOUR_'):
        logging.warning("Target API URL in config.yaml seems to be a placeholder. Please update it.")

    if config['target_api'].get('url') and not config['target_api'].get('api_key'):
        # Only warn if URL is set, maybe the API doesn't need a key
        logging.warning("TARGET_API_KEY not found in environment variables, but target_api.url is set. API push might fail if authentication is required.")

    logging.info("Configuration loaded successfully.")
    return config

# Load config globally on import to make it accessible
config = load_config() 