**(English)** | [简体中文](README.zh-CN.md)

---

# Medium Personalized Feed Processor

This project provides an automated workflow to fetch articles from Medium RSS feeds, filter them based on your interests using AI, process the content into annotated Markdown, and finally output the results either by pushing to a specific API endpoint or saving them as local files.

It's designed for users who want a curated reading list from Medium, automatically processed and delivered in a preferred format and location.

## Features

*   **Configurable RSS Feeds:** Specify multiple Medium tags, authors, or publications via `config.yaml`.
*   **Two-Stage AI Filtering:**
    1.  **Initial Screening:** Filters articles based on title and summary using an AI model (e.g., Gemini, GPT) against your defined interests, dislikes, and quality criteria.
    2.  **Content-Based Filtering:** Performs a second AI analysis on the full article content for deeper quality and relevance assessment.
*   **Paywall Handling:** Uses provided browser cookies (`medium.com_cookies.txt`) to fetch full content of member-only articles.
*   **AI Content Processing:**
    *   Converts fetched article HTML into clean Markdown format.
    *   Annotates potentially challenging English vocabulary with Chinese translations based on a configurable CEFR level.
*   **Configurable Output:** Choose how to receive processed articles:
    *   **API Push:** Send Markdown content and metadata to a designated API endpoint (e.g., your personal knowledge base or website).
    *   **Local Save:** Save articles as `.md` files in a structured directory (`output_markdown/medium/<source_tag>/article_title.md`).
*   **State Management:** Uses an SQLite database (`processed_articles.db`) to track processed articles, preventing duplicates.
*   **Flexible Configuration:** Uses `config.yaml` for general settings and `.env` for sensitive API keys. Supports custom AI API endpoints (e.g., OpenRouter).
*   **Detailed Logging:** Provides informative logs to console and optionally to a file (`app.log`).

## How It Works

The script (`main.py`) executes the following steps:

1.  **Load Configuration:** Reads settings from `config.yaml` and sensitive data from `.env`.
2.  **Fetch RSS Feeds:** Retrieves articles from all RSS URLs specified in `config.yaml`.
3.  **Check History:** For each fetched article, checks the `processed_articles.db` to see if it has already been processed. Skips if already present.
4.  **AI Filter - Stage 1 (Title/Summary):** Sends the article's title and summary to the configured AI model for relevance and initial quality assessment (`filter_article_with_ai`). If rejected, marks as `filtered_out_stage1` and skips.
5.  **Fetch Full Content:** If Stage 1 passes, fetches the full article HTML using saved browser cookies (`content_fetcher.fetch_full_article_content`). If fetching fails, marks as `failed_fetch`.
6.  **AI Filter - Stage 2 (Full Content):** Sends the fetched HTML content to the AI model for a more rigorous quality and relevance check (`filter_article_content_with_ai`). If rejected, marks as `filtered_out_stage2` and skips.
7.  **AI Content Processing:** If Stage 2 passes, sends the HTML content to the AI model to convert it to Markdown and add vocabulary annotations (`process_content_with_ai`). If processing fails, marks as `failed_ai_processing`.
8.  **Output Article:** Based on the `output.method` setting in `config.yaml`:
    *   **`api`:** Calls `api_pusher.push_to_api` to send the processed Markdown and metadata to the configured `target_api.endpoint`. Updates status to `pushed` or `failed_push`.
    *   **`local`:** Calls `main.save_to_local` to save the processed Markdown as a `.md` file in the configured `output.local_dir`, organized by source tag. Updates status to `saved_local` or `failed_save_local`.
9.  **Log Summary:** Prints a summary of the run (articles fetched, filtered, processed, outputted, failed).

## Project Structure

```
.
├── .env                # Stores sensitive API keys (ignored by git)
├── .gitignore          # Specifies files ignored by git
├── config.yaml         # Main configuration file
├── main.py             # Main script orchestrating the workflow
├── medium.com_cookies.txt # Your Medium browser cookies (ignored by git)
├── requirements.txt    # Python dependencies
├── processed_articles.db # SQLite database tracking processed articles (ignored by git)
├── app.log             # Log file (if configured, ignored by git)
├── utils.py            # Utility functions (logging, HTML cleaning, cookie parsing, content extraction)
├── config.py           # Loads configuration from yaml and .env
├── state_manager.py    # Manages SQLite database state
├── rss_fetcher.py      # Fetches and parses RSS feeds
├── ai_processor.py     # Handles interactions with AI APIs for filtering and processing
├── content_fetcher.py  # Fetches full article HTML using cookies
├── api_pusher.py       # Pushes processed content to the target API (if output method is 'api')
└── README.md           # This file
```

*(Note: You might need to create the `.env` file from `.env.example` if provided, or create it manually.)*

## Prerequisites

*   Python 3.7+
*   `pip` (Python package installer)
*   Access to an AI API (OpenAI compatible, e.g., OpenAI, OpenRouter, local models with an OpenAI-compatible interface)
*   A Medium account (for accessing member-only content via cookies)
*   (Optional) A target API endpoint if using the `api` output method.

## Installation

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone https://github.com/wayne0926/Medium-Personalized-Feed-Processor
    cd Medium-Personalized-Feed-Processor
    ```

2.  **Create a virtual environment (Recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Configuration is split between `config.yaml` (general settings) and `.env` (sensitive keys).

### 1. `.env` File

Create a file named `.env` in the project root directory. Add your API keys here:

```dotenv
# .env

# Your AI API Key (e.g., OpenAI, OpenRouter)
# Ensure this key has access to the models specified in config.yaml
OPENAI_API_KEY="sk-..."

# Your Target API Key/Token (if required by your API endpoint)
# Only needed if output.method is 'api' and your API requires authentication
TARGET_API_KEY="your_target_api_secret_key"
```

*   **`OPENAI_API_KEY`**: **Required.** Your key for the AI service.
*   **`TARGET_API_KEY`**: **Optional.** Only needed if `output.method` is `api` and your target endpoint requires an API key (the example `api_pusher.py` sends this in the JSON body).

### 2. `medium.com_cookies.txt` File

*   **Crucial for accessing member-only content.** You *must* provide this file in the project root (or update the path in `config.yaml`).
*   It needs to contain your **currently valid** Medium login cookies in **Netscape format**.
*   **How to get cookies:**
    1.  Log in to Medium.com in your web browser.
    2.  Use a browser extension designed to export cookies (e.g., "Get cookies.txt" for Chrome/Firefox).
    3.  Export cookies **only** for the `medium.com` domain.
    4.  Save the exported content as `medium.com_cookies.txt` in the project root.
*   **Security:** This file contains sensitive session information. Ensure it's listed in your `.gitignore` and **never commit it to version control**.
*   **Expiration:** Cookies expire! You will need to update this file periodically (e.g., weekly or monthly) for the script to continue accessing paywalled content.

### 3. `config.yaml` File

Edit `config.yaml` to customize the behavior:

```yaml
# config.yaml

# Logging configuration
logging:
  level: INFO # DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_file: app.log # Set to null or remove to log only to console

# RSS feeds to monitor
medium_feeds:
  - https://medium.com/feed/tag/artificial-intelligence
  - https://medium.com/feed/tag/programming
  # Add more Medium tag, author (e.g., https://medium.com/feed/@username),
  # or publication (e.g., https://medium.com/feed/publication-name) feeds

# AI Filtering and Processing Configuration
ai_filter:
  # Your interests (be specific)
  interests:
    - "deep learning applications"
    - "python programming best practices"
    - "systems design"
  # Topics/types to filter out
  dislikes:
    - "crypto price speculation"
    - "get rich quick schemes"
    - "marketing buzzwords"
  # English level for vocabulary annotation (e.g., CEFR B2, C1, Native)
  english_level: "CEFR C1"
  # AI model for Stage 1 & 2 filtering (title/summary & full content)
  filtering_model: "google/gemini-1.5-flash-preview" # Or e.g., "gpt-3.5-turbo"
  # AI model for content processing (HTML -> Markdown + Annotations)
  # Needs good instruction following and potentially larger context window
  processing_model: "google/gemini-1.5-pro-preview" # Or e.g., "gpt-4-turbo"
  # Optional: Specify a different base URL for the OpenAI-compatible API (e.g., for OpenRouter, local models)
  # Environment variable OPENAI_API_BASE_URL takes precedence if set.
  api_base_url: "https://openrouter.ai/api/v1" # Example for OpenRouter
  # Optional: Specify a proxy URL for AI API requests (e.g., http://127.0.0.1:7890, socks5://user:pass@host:port)
  # If set, this overrides HTTP_PROXY/HTTPS_PROXY environment variables for AI calls.
  proxy: null
  # Relevance levels to accept (High, Medium, Low, None)
  accepted_relevance: ["High", "Medium"]
  # Quality/Type levels to accept (In-depth, Opinion, Overview, Shallow, Promotional, Low-Quality)
  # Adjust based on how strict you want the filtering to be
  accepted_quality: ["In-depth", "Opinion"] # Stricter example
  # Optional: Different quality criteria for Stage 2 (content-based) filtering
  # accepted_content_quality: ["In-depth"] # Even stricter example

# Full Content Fetching Configuration
fetch_config:
  # Path to your Netscape cookie file
  cookie_file: "medium.com_cookies.txt"
  # Timeout in seconds for fetching full article HTML
  fetch_timeout: 30
  # Optional: Specify a proxy URL for fetching article HTML (e.g., http://127.0.0.1:7890, socks5://user:pass@host:port)
  # If set, this overrides HTTP_PROXY/HTTPS_PROXY environment variables for content fetching calls.
  proxy: null

# --- Target API Configuration (Generic - Used only if output.method is 'api') ---
target_api:
  # REQUIRED: Full URL of your target API endpoint.
  endpoint: "YOUR_API_ENDPOINT_URL" # Example: "https://your-api.com/v1/articles"

  # Optional: HTTP method to use (e.g., POST, PUT, PATCH). Defaults to "POST".
  method: "POST"

  # Optional: Authentication details for the target API.
  authentication:
    # Type of authentication. Options:
    # - "none": No authentication (default).
    # - "bearer": Sends API key in the 'Authorization' header as "Bearer <key>".
    # - "header_key": Sends API key in a custom header.
    # - "body_key": Sends API key as a field within the JSON payload.
    # **IMPORTANT**: The actual API Key/Token value MUST be stored in the
    #              `TARGET_API_KEY` environment variable in your `.env` file.
    type: "none"

    # Required if type is 'header_key' or 'bearer'.
    # Specifies the name of the HTTP header.
    # For 'bearer', if omitted, defaults to "Authorization".
    # Example for 'header_key': "X-Api-Key"
    header_name: null

    # Required if type is 'body_key'.
    # Specifies the key name in the JSON payload where the `TARGET_API_KEY` will be placed.
    # Example: "apiKey"
    body_key_name: null

  # Optional: Custom HTTP headers to send with the request.
  # Default 'Content-Type' is 'application/json' if a payload is sent.
  # Default 'Accept' is 'application/json'. These can be overridden here.
  headers:
    # Example:
    # User-Agent: "MyMediumProcessor/1.0"
    # X-Custom-ID: "some-value"
    Content-Type: "application/json" # Keep or override

  # Optional: Defines the structure of the JSON payload sent to the API.
  # If omitted or null/empty, no JSON payload is sent (useful for GET/DELETE or APIs expecting no body).
  # Use placeholders: {title}, {link}, {summary}, {published_iso}, {source_tag}, {content_markdown}
  # These will be replaced with actual article data.
  # You can include static values (strings, numbers, booleans) or nested structures.
  payload_mapping:
    # --- Example Structure --- #
    article_title: "{title}"          # Maps article title
    source_url: "{link}"            # Maps article link
    body: "{content_markdown}"       # Maps processed Markdown content
    published: "{published_iso}"    # Maps publication date (ISO format)
    category: "medium/{source_tag}" # Example combining static text and placeholder
    metadata:
      source: "medium-importer"
      processed_at: "{now_iso}" # Placeholder for current time (if supported, otherwise handle in API)
    tags: ["medium", "imported", "{source_tag}"] # Example list with placeholder
    is_draft: true                  # Example static boolean value
    # Note: If authentication.type is 'body_key', the key defined in
    #       authentication.body_key_name will be automatically added here.

  # Optional: How to determine if the API call was successful.
  success_check:
    # Type: 'status_code' or 'json_field'. Defaults to 'status_code'.
    type: "status_code"

    # Required if type is 'status_code'. List of acceptable HTTP status codes.
    # Defaults to [200, 201].
    expected_status_codes: [200, 201]

    # Required if type is 'json_field'. The key path (dot-separated for nested) to check in the JSON response.
    # Example: "status", "result.code", "data[0].id"
    json_field_name: null
    # Required if type is 'json_field'. The expected value for the specified field.
    # Can be a string, number, boolean, or null.
    expected_json_value: null # Example: "success", 200, true

  # Optional: Timeout in seconds for the API request. Defaults to 30.
  push_timeout: 30

# Output Configuration
output:
  method: "api" # Or "local"
  local_dir: "output_markdown" # Used if method is "local"

# State Management Configuration
state_database:
  db_file: "processed_articles.db"

```

**Key `config.yaml` Sections:**

*   **`logging`:** Set log verbosity (`level`) and optional output file (`log_file`).
*   **`medium_feeds`:** List the URLs of the Medium RSS feeds you want to process.
*   **`ai_filter`:**
    *   `interests`/`dislikes`: Define your preferences for the AI filters.
    *   `english_level`: Sets the target level for vocabulary annotations.
    *   `filtering_model`/`processing_model`: Specify the AI models to use. Ensure your `OPENAI_API_KEY` has access to these models.
    *   `api_base_url`: Use this if your AI provider isn't OpenAI or if you're using a proxy/local model.
    *   `proxy`: **(New)** Optionally specify a full proxy URL (e.g., `http://localhost:7890`, `socks5://user:pass@host:port`) to use for AI API requests. If set, this overrides the `HTTP_PROXY`/`HTTPS_PROXY` environment variables for these specific requests. Requires the `httpx` library (added to `requirements.txt`).
    *   `accepted_relevance`/`accepted_quality`: Define which AI classifications pass the filters.
*   **`fetch_config`:**
    *   `cookie_file`: Path to your `medium.com_cookies.txt`. **Ensure this file exists and is valid.**
    *   `fetch_timeout`: Network timeout for fetching articles.
    *   `proxy`: **(New)** Optionally specify a full proxy URL (e.g., `http://localhost:7890`, `socks5://user:pass@host:port`) to use for fetching article HTML content. If set, this overrides the `HTTP_PROXY`/`HTTPS_PROXY` environment variables for these specific requests.
*   **`target_api`:** (Used only if `output.method: api`) - **This section is now highly configurable!**
    *   `endpoint`: **Required.** The full URL your API endpoint.
    *   `method`: The HTTP method (e.g., `POST`, `PUT`). Defaults to `POST`.
    *   `authentication`:
        *   `type`: Choose `none`, `bearer`, `header_key`, or `body_key`.
        *   `header_name`: Required for `bearer` (defaults to `Authorization`) and `header_key`.
        *   `body_key_name`: Required for `body_key`.
        *   **Remember:** The actual secret key/token goes in the `.env` file as `TARGET_API_KEY`.
    *   `headers`: Add any custom HTTP headers your API requires.
    *   `payload_mapping`: Define the exact JSON structure your API expects. Use placeholders like `{title}`, `{content_markdown}`, etc., which will be filled with article data. You can create nested JSON and include static values.
    *   `success_check`:
        *   `type`: Choose `status_code` (check HTTP status) or `json_field` (check a value in the API's JSON response).
        *   `expected_status_codes`: List of HTTP codes indicating success (if type is `status_code`).
        *   `json_field_name`: The key (dot-separated for nesting, e.g., `data.status`) in the response JSON to check (if type is `json_field`).
        *   `expected_json_value`: The value the `json_field_name` should have for the request to be considered successful.
    *   `push_timeout`: Network timeout for API requests.
*   **`output`:** (As before - choose `api` or `local`)
*   **`state_database`:** (As before)

**Proxy Support Note:**

*   Proxy settings can be configured separately for AI API requests (`ai_filter.proxy`) and for fetching article content (`fetch_config.proxy`).
*   If a proxy is *not* set in `config.yaml` for either section, the script will attempt to use the standard `HTTP_PROXY` or `HTTPS_PROXY` environment variables if they are set.
*   The proxy settings in `config.yaml` take precedence over environment variables.
*   Using a proxy for AI requests (`ai_filter.proxy`) requires the `httpx` library, which has been added to `requirements.txt`.

## Usage

Once configured, run the main script from your terminal within the project directory (and with the virtual environment activated, if used):

```bash
python main.py
```

The script will execute the workflow described in "How It Works". Logs will be printed to the console (and to `app.log` if configured).

## Output

Depending on the `output.method` setting:

*   **`api`:** Processed articles are sent to the configured `target_api.endpoint` using the specified `method`, `authentication`, `headers`, and `payload_mapping`. Success is determined by the `success_check` configuration. Check the script logs for details on success or failure, including API responses on failure.
*   **`local`:** Processed articles are saved as Markdown files (`.md`) within the directory specified by `output.local_dir`. The structure will be:
    ```
    output_markdown/
    └── medium/
        ├── <source_tag_1>/
        │   ├── <article_title_1>.md
        │   └── <article_title_2>.md
        └── <source_tag_2>/
            └── <article_title_3>.md
            └── ...
    ```
    Where `<source_tag>` is derived from the RSS feed URL (e.g., `programming`, `artificial-intelligence`) and `<article_title>` is a sanitized version of the article's title. Success/failure is logged.

## State Management

The `processed_articles.db` file is an SQLite database that stores the URLs of all articles that have been processed (or attempted). This prevents the script from processing and outputting the same article multiple times if it appears in feeds again or if the script is run multiple times. The database tracks the processing status (e.g., `pushed`, `saved_local`, `filtered_out_stage1`, `failed_fetch`).

## Automation (Optional)

You can automate the script execution using task schedulers:

*   **Linux/macOS:** Use `cron`. Edit your crontab (`crontab -e`) and add a line similar to:
    ```cron
    # Run every 2 hours
    0 */2 * * * /path/to/your/project/.venv/bin/python /path/to/your/project/main.py >> /path/to/your/project/cron.log 2>&1
    ```
    *(Adjust paths, virtual environment activation, and frequency as needed.)*
*   **Windows:** Use Task Scheduler to create a task that runs `C:\path\to\your\project\.venv\Scripts\python.exe C:\path\to\your\project\main.py` periodically.

## Maintenance & Potential Issues

*   **Cookie Expiration:** **This is the most common issue.** `medium.com_cookies.txt` needs regular manual updates as cookies expire.
*   **Medium Website Changes:** Medium might change its HTML structure, breaking the content extraction logic in `utils.py` (`extract_main_content_from_html`). This may require updating the BeautifulSoup selectors.
*   **AI Model Changes/Costs:** AI APIs evolve. Models might be deprecated, or pricing might change. Monitor your AI API usage and costs. Context length limits can also be an issue for very long articles.
*   **API Changes:** If using the `api` output, changes to your target API might require updates to `api_pusher.py`.
*   **RSS Feed Issues:** Feeds can become temporarily unavailable or change format.
*   **Configuration Errors:** Ensure paths in `config.yaml` are correct and API keys in `.env` are valid.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs, feature requests, or improvements.


## License


This project is licensed under the MIT License. See the `LICENSE` file for details.
