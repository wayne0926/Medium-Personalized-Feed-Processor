import requests
import json
import logging
from config import config # Import the loaded config

logger = logging.getLogger(__name__)

def _get_nested_value(data, key_path):
    """Helper to get a value from a nested dict using a dot-separated key path."""
    keys = key_path.split('.')
    value = data
    try:
        for key in keys:
            if isinstance(value, list):
                # Handle list index if specified like 'items[0]'
                # This is a basic implementation, could be extended
                if '[' in key and key.endswith(']'):
                    base_key, index_str = key[:-1].split('[')
                    index = int(index_str)
                    value = value[index].get(base_key) if isinstance(value, list) and len(value) > index and isinstance(value[index], dict) else None
                else:
                     # Cannot traverse dict keys into a list directly without index
                    return None
            elif isinstance(value, dict):
                value = value.get(key)
            else:
                return None # Cannot traverse further
            if value is None:
                return None
        return value
    except (KeyError, IndexError, TypeError, ValueError):
        return None

def push_to_api(article_data, processed_markdown):
    """Pushes processed article data to a generically configured API endpoint."""
    api_config = config.get('target_api', {})
    output_config = config.get('output', {})

    # Ensure this function is only called if output method is 'api'
    if output_config.get('method', 'api').lower() != 'api':
        logger.debug("API push skipped: output method is not 'api'.")
        return False # Should not happen if called from main.py logic

    # --- Get required configurations ---
    endpoint = api_config.get('endpoint')
    http_method = api_config.get('method', 'POST').upper()
    timeout = api_config.get('push_timeout', 30)
    auth_config = api_config.get('authentication', {})
    auth_type = auth_config.get('type', 'none').lower()
    custom_headers = api_config.get('headers', {})
    payload_mapping = api_config.get('payload_mapping', {})
    success_check_config = api_config.get('success_check', {})
    success_check_type = success_check_config.get('type', 'status_code').lower()

    # --- Basic validation ---
    if not endpoint or endpoint.startswith('YOUR_'):
        logger.error("Target API endpoint URL is not configured or is a placeholder. Cannot push article.")
        return False

    # --- Prepare data placeholders ---
    placeholders = {
        'title': article_data.get('title', 'No Title Provided'),
        'link': article_data.get('link', 'No Source URL Provided'),
        'summary': article_data.get('summary', ''), # Original summary
        'published_iso': article_data.get('published_iso'),
        'source_tag': article_data.get('source_tag', 'uncategorized'),
        'content_markdown': processed_markdown,
    }

    # --- Prepare Headers ---
    headers = {
        # Default Content-Type if sending payload
        'Content-Type': 'application/json',
        'Accept': 'application/json', # Expect JSON back by default
    }
    # Apply custom headers (overwriting defaults if specified)
    if isinstance(custom_headers, dict):
        headers.update(custom_headers)
    else:
        logger.warning("Custom headers in config are not a valid dictionary. Ignoring.")

    # --- Handle Authentication ---
    api_key_env = config.get('target_api', {}).get('api_key') # Fetched from env var during config load

    if auth_type != 'none' and not api_key_env:
        logger.error(f"Authentication type is '{auth_type}' but TARGET_API_KEY environment variable is not set. Cannot authenticate.")
        return False

    if auth_type == 'bearer':
        header_name = auth_config.get('header_name', 'Authorization')
        headers[header_name] = f"Bearer {api_key_env}"
        logger.debug(f"Using Bearer authentication in header '{header_name}'.")
    elif auth_type == 'header_key':
        header_name = auth_config.get('header_name')
        if not header_name:
            logger.error("Authentication type is 'header_key' but 'header_name' is not specified in config. Cannot authenticate.")
            return False
        headers[header_name] = api_key_env
        logger.debug(f"Using API Key authentication in header '{header_name}'.")
    elif auth_type == 'body_key':
        # Key will be added to payload later
        logger.debug(f"API Key will be added to payload body.")
    elif auth_type != 'none':
        logger.error(f"Invalid authentication type specified in config: '{auth_type}'. Valid types: none, bearer, header_key, body_key.")
        return False

    # --- Prepare Payload --- # Default to None
    payload = None
    if payload_mapping and isinstance(payload_mapping, dict):
        payload = {}
        for key, template in payload_mapping.items():
            if isinstance(template, str):
                # Replace placeholders in the template string
                value = template
                for placeholder, data_val in placeholders.items():
                    # Ensure data_val is stringifiable
                    str_data_val = str(data_val) if data_val is not None else ''
                    value = value.replace(f'{{{placeholder}}}', str_data_val)
                payload[key] = value
            else:
                # Keep static values as they are (e.g., numbers, booleans)
                payload[key] = template

        # Add API key to payload if required by auth type
        if auth_type == 'body_key':
            body_key_name = auth_config.get('body_key_name')
            if not body_key_name:
                logger.error("Authentication type is 'body_key' but 'body_key_name' is not specified in config. Cannot authenticate.")
                return False
            payload[body_key_name] = api_key_env
            logger.debug(f"Added API key to payload under key '{body_key_name}'.")
    elif payload_mapping:
         logger.warning("Payload mapping in config is not a valid dictionary. Sending request without payload.")


    # --- Make API Request --- #
    article_title_log = placeholders['title']
    logger.debug(f"Sending {http_method} request to {endpoint} for article '{article_title_log}'.")
    # logger.debug(f"Headers: {headers}")
    # logger.debug(f"Payload: {json.dumps(payload, indent=2) if payload else 'None'}")

    response = None
    try:
        request_args = {
            'method': http_method,
            'url': endpoint,
            'headers': headers,
            'timeout': timeout
        }
        # Add JSON payload only if it exists and method allows a body
        if payload is not None and http_method not in ['GET', 'HEAD', 'DELETE']: # Common methods with bodies
             request_args['json'] = payload

        response = requests.request(**request_args)
        response.raise_for_status() # Check for 4xx/5xx HTTP errors first

        # --- Check Success Criteria ---
        push_successful = False
        if success_check_type == 'status_code':
            expected_codes = success_check_config.get('expected_status_codes', [200, 201])
            if response.status_code in expected_codes:
                push_successful = True
                logger.info(f"API push successful for '{article_title_log}' (Status Code: {response.status_code}).")
            else:
                logger.error(f"API push failed for '{article_title_log}'. Unexpected status code: {response.status_code} (Expected: {expected_codes}).")
        elif success_check_type == 'json_field':
            field_name = success_check_config.get('json_field_name')
            expected_value = success_check_config.get('expected_json_value')
            if not field_name:
                logger.error(f"API push success check failed for '{article_title_log}': Success type is 'json_field' but 'json_field_name' is missing in config.")
            else:
                try:
                    response_json = response.json()
                    actual_value = _get_nested_value(response_json, field_name) # Use helper for nested keys
                    # Explicitly check type of expected_value if it's not None, compare accordingly
                    if actual_value is not None and expected_value is not None and isinstance(expected_value, type(actual_value)) and actual_value == expected_value:
                         push_successful = True
                         logger.info(f"API push successful for '{article_title_log}' (JSON field '{field_name}' matched value '{expected_value}').")
                    elif actual_value is not None and expected_value is None:
                        # If expected value is null/None, just checking existence might be enough? Or require explicit None match?
                        # Current logic: only matches if actual_value is also None.
                         if actual_value is None:
                            push_successful = True
                            logger.info(f"API push successful for '{article_title_log}' (JSON field '{field_name}' is null/None as expected)." )
                         else:
                            logger.error(f"API push failed for '{article_title_log}'. JSON field '{field_name}' has value '{actual_value}', expected null/None.")
                    elif expected_value is not None and (actual_value is None or not isinstance(expected_value, type(actual_value))):
                        logger.error(f"API push failed for '{article_title_log}'. JSON field '{field_name}' type mismatch or not found. Expected type {type(expected_value)}, Got value: {actual_value}")
                    elif actual_value != expected_value:
                        logger.error(f"API push failed for '{article_title_log}'. JSON field '{field_name}' has value '{actual_value}', expected '{expected_value}'.")
                except json.JSONDecodeError:
                    logger.error(f"API push success check failed for '{article_title_log}': Could not decode JSON response to check field '{field_name}'. Response text: {response.text[:500]}")
                except Exception as e:
                     logger.error(f"API push success check failed for '{article_title_log}' while checking JSON field '{field_name}': {e}")
        else:
            logger.error(f"Invalid success_check type specified in config: '{success_check_type}'. Defaulting to failure.")

        if not push_successful:
             # Log response details on failure if not already logged by status check
             if success_check_type != 'status_code':
                 try:
                      logger.error(f"API Response Body on Failure: {response.text[:1000]}") # Limit length
                 except Exception: pass # Ignore errors during logging
        return push_successful

    except requests.exceptions.Timeout:
        logger.error(f"Timeout error ({timeout}s) pushing article '{article_title_log}' to {endpoint}.")
    except requests.exceptions.HTTPError as e:
        # Error already logged by raise_for_status usually, but log details here
        logger.error(f"HTTP error pushing article '{article_title_log}' to {endpoint}: {e}")
        if e.response is not None:
            logger.error(f"API Response Status: {e.response.status_code}")
            try: logger.error(f"API Response Body: {e.response.text[:1000]}") # Limit length
            except Exception: pass
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error pushing article '{article_title_log}' to {endpoint}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during API push for '{article_title_log}': {e}", exc_info=True)

    return False # Any exception leads to failure 