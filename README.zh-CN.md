[English](README.md) | **(简体中文)**

---

# Medium 个性化 Feed 处理器

本项目提供了一个自动化工作流，用于从 Medium RSS 源获取文章，使用 AI 根据您的兴趣进行筛选，将内容处理为带注释的 Markdown，并最终通过推送到特定 API 端点或保存为本地文件来输出结果。

它专为希望从 Medium 获取精选阅读列表，并以首选格式和位置自动处理和交付的用户而设计。

## 功能特性

*   **可配置的 RSS 源：** 通过 `config.yaml` 指定多个 Medium 标签、作者或出版物。
*   **两阶段 AI 过滤：**
    1.  **初步筛选：** 使用 AI 模型（例如 Gemini、GPT）根据您定义的兴趣、不喜欢的内容和质量标准，基于标题和摘要过滤文章。
    2.  **基于内容的过滤：** 对完整的文章内容进行第二次 AI 分析，以进行更深入的质量和相关性评估。
*   **付费墙处理：** 使用提供的浏览器 Cookie (`medium.com_cookies.txt`) 获取会员专享文章的完整内容。
*   **AI 内容处理：**
    *   将获取的文章 HTML 转换为干净的 Markdown 格式。
    *   根据可配置的 CEFR 等级，为可能有挑战性的英语词汇添加中文翻译注释。
*   **可配置的输出：** 选择接收已处理文章的方式：
    *   **API 推送：** 将 Markdown 内容和元数据发送到指定的 API 端点（例如，您的个人知识库或网站）。
    *   **本地保存：** 将文章另存为 `.md` 文件，存储在结构化目录中 (`output_markdown/medium/<source_tag>/article_title.md`)。
*   **状态管理：** 使用 SQLite 数据库 (`processed_articles.db`) 跟踪已处理的文章，防止重复处理。
*   **灵活配置：** 使用 `config.yaml` 进行常规设置，使用 `.env` 存储敏感的 API 密钥。支持自定义 AI API 端点（例如 OpenRouter）。
*   **详细日志记录：** 向控制台提供信息性日志，并可选择记录到文件 (`app.log`)。

## 工作原理

脚本 (`main.py`) 执行以下步骤：

1.  **加载配置：** 从 `config.yaml` 读取设置，从 `.env` 读取敏感数据。
2.  **获取 RSS 源：** 从 `config.yaml` 中指定的所有 RSS URL 检索文章。
3.  **检查历史记录：** 对每篇获取的文章，检查 `processed_articles.db` 以查看是否已处理。如果已存在则跳过。
4.  **AI 过滤器 - 阶段 1 (标题/摘要)：** 将文章的标题和摘要发送到配置的 AI 模型，进行相关性和初步质量评估 (`filter_article_with_ai`)。如果被拒绝，则标记为 `filtered_out_stage1` 并跳过。
5.  **获取完整内容：** 如果阶段 1 通过，则使用保存的浏览器 Cookie 获取完整的文章 HTML (`content_fetcher.fetch_full_article_content`)。如果获取失败，则标记为 `failed_fetch`。
6.  **AI 过滤器 - 阶段 2 (完整内容)：** 将获取的 HTML 内容发送到 AI 模型，进行更严格的质量和相关性检查 (`filter_article_content_with_ai`)。如果被拒绝，则标记为 `filtered_out_stage2` 并跳过。
7.  **AI 内容处理：** 如果阶段 2 通过，则将 HTML 内容发送到 AI 模型，将其转换为 Markdown 并添加词汇注释 (`process_content_with_ai`)。如果处理失败，则标记为 `failed_ai_processing`。
8.  **输出文章：** 根据 `config.yaml` 中的 `output.method` 设置：
    *   **`api`：** 调用 `api_pusher.push_to_api` 将处理后的 Markdown 和元数据发送到配置的 `target_api.endpoint`。将状态更新为 `pushed` 或 `failed_push`。
    *   **`local`：** 调用 `main.save_to_local` 将处理后的 Markdown 另存为 `.md` 文件，保存在配置的 `output.local_dir` 中，按源标签组织。将状态更新为 `saved_local` 或 `failed_save_local`。
9.  **日志摘要：** 打印运行摘要（获取、过滤、处理、输出、失败的文章数量）。

## 项目结构

```
.
├── .env                # 存储敏感的 API 密钥 (git 会忽略)
├── .gitignore          # 指定 git 忽略的文件
├── config.yaml         # 主要配置文件
├── main.py             # 协调工作流的主脚本
├── medium.com_cookies.txt # 你的 Medium 浏览器 Cookie (git 会忽略)
├── requirements.txt    # Python 依赖项
├── processed_articles.db # 跟踪已处理文章的 SQLite 数据库 (git 会忽略)
├── app.log             # 日志文件 (如果配置了, git 会忽略)
├── utils.py            # 工具函数 (日志记录, HTML 清理, Cookie 解析, 内容提取)
├── config.py           # 从 yaml 和 .env 加载配置
├── state_manager.py    # 管理 SQLite 数据库状态
├── rss_fetcher.py      # 获取并解析 RSS 源
├── ai_processor.py     # 处理与 AI API 的交互以进行过滤和处理
├── content_fetcher.py  # 使用 Cookie 获取完整的文章 HTML
├── api_pusher.py       # 将处理后的内容推送到目标 API (如果输出方法是 'api')
├── README.md           # 英文版 README 文件
└── README.zh-CN.md     # 此文件的中文翻译
```

*(注意：如果提供了 `.env.example` 文件，您可能需要基于它创建 `.env` 文件，或者手动创建。)*

## 先决条件

*   Python 3.7+
*   `pip` (Python 包安装器)
*   访问 AI API (OpenAI 兼容，例如 OpenAI、OpenRouter，或具有 OpenAI 兼容接口的本地模型)
*   一个 Medium 帐户 (用于通过 Cookie 访问会员专享内容)
*   (可选) 如果使用 `api` 输出方法，需要一个目标 API 端点。

## 安装

1.  **克隆仓库 (如果尚未克隆)：**
    ```bash
    git clone https://github.com/wayne0926/Medium-Personalized-Feed-Processor
    cd Medium-Personalized-Feed-Processor
    ```

2.  **创建虚拟环境 (推荐)：**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # 在 Windows 上使用 `.venv\Scripts\activate`
    ```

3.  **安装依赖项：**
    ```bash
    pip install -r requirements.txt
    ```

## 配置

配置分为 `config.yaml` (常规设置) 和 `.env` (敏感密钥)。

### 1. `.env` 文件

在项目根目录中创建一个名为 `.env` 的文件。在此处添加您的 API 密钥：

```dotenv
# .env

# 你的 AI API 密钥 (例如 OpenAI, OpenRouter)
# 确保此密钥有权访问 config.yaml 中指定的模型
OPENAI_API_KEY="sk-..."

# 你的目标 API 密钥/令牌 (如果你的 API 端点需要)
# 仅当 output.method 为 'api' 且你的 API 需要身份验证时才需要
TARGET_API_KEY="your_target_api_secret_key"
```

*   **`OPENAI_API_KEY`**: **必需。** 您的 AI 服务密钥。
*   **`TARGET_API_KEY`**: **可选。** 仅当 `output.method` 为 `api` 且您的目标端点需要 API 密钥时才需要 (示例 `api_pusher.py` 会将其发送到 JSON 正文中)。

### 2. `medium.com_cookies.txt` 文件

*   **访问会员专享内容的关键。** 您 *必须* 在项目根目录中提供此文件 (或在 `config.yaml` 中更新路径)。
*   它需要包含您 **当前有效** 的 Medium 登录 Cookie，格式为 **Netscape 格式**。
*   **如何获取 Cookie：**
    1.  在您的网页浏览器中登录 Medium.com。
    2.  使用旨在导出 Cookie 的浏览器扩展程序 (例如，适用于 Chrome/Firefox 的 "Get cookies.txt")。
    3.  **仅** 导出 `medium.com` 域的 Cookie。
    4.  将导出的内容另存为项目根目录中的 `medium.com_cookies.txt`。
*   **安全性：** 此文件包含敏感的会话信息。确保它已列在您的 `.gitignore` 中，并且 **切勿将其提交到版本控制**。
*   **过期：** Cookie 会过期！您需要定期 (例如，每周或每月) 更新此文件，脚本才能继续访问付费内容。

### 3. `config.yaml` 文件

编辑 `config.yaml` 以自定义行为：

```yaml
# config.yaml

# 日志配置
logging:
  level: INFO # DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_file: app.log # 设置为 null 或删除以仅记录到控制台

# 要监控的 RSS 源
medium_feeds:
  - https://medium.com/feed/tag/artificial-intelligence
  - https://medium.com/feed/tag/programming
  # 添加更多 Medium 标签、作者 (例如 https://medium.com/feed/@username)
  # 或出版物 (例如 https://medium.com/feed/publication-name) 源

# AI 过滤和处理配置
ai_filter:
  # 你的兴趣 (请具体说明)
  interests:
    - "深度学习应用"
    - "python 编程最佳实践"
    - "系统设计"
  # 要过滤掉的主题/类型
  dislikes:
    - "加密货币价格投机"
    - "快速致富计划"
    - "营销流行语"
  # 词汇注释的英语水平 (例如 CEFR B2, C1, Native)
  english_level: "CEFR C1"
  # 用于阶段 1 和 2 过滤 (标题/摘要和完整内容) 的 AI 模型
  filtering_model: "google/gemini-1.5-flash-preview" # 或例如 "gpt-3.5-turbo"
  # 用于内容处理 (HTML -> Markdown + 注释) 的 AI 模型
  # 需要良好的指令遵循能力和可能更大的上下文窗口
  processing_model: "google/gemini-1.5-pro-preview" # 或例如 "gpt-4-turbo"
  # 可选: 为 OpenAI 兼容的 API 指定不同的基础 URL (例如，用于 OpenRouter、本地模型)
  # 如果设置了环境变量 OPENAI_API_BASE_URL，则优先使用该变量。
  api_base_url: "https://openrouter.ai/api/v1" # OpenRouter 示例
  # 可选: 为 AI API 请求指定代理 URL (例如 http://127.0.0.1:7890, socks5://user:pass@host:port)
  # 如果设置，这将覆盖 AI 调用的 HTTP_PROXY/HTTPS_PROXY 环境变量。
  proxy: null
  # 接受的相关性级别 (High, Medium, Low, None)
  accepted_relevance: ["High", "Medium"]
  # 接受的质量/类型级别 (In-depth, Opinion, Overview, Shallow, Promotional, Low-Quality)
  # 根据您希望过滤的严格程度进行调整
  accepted_quality: ["In-depth", "Opinion"] # 更严格的示例
  # 可选: 阶段 2 (基于内容) 过滤的不同质量标准
  # accepted_content_quality: ["In-depth"] # 更严格的示例

# 完整内容获取配置
fetch_config:
  # Netscape cookie 文件的路径
  cookie_file: "medium.com_cookies.txt"
  # 获取完整文章 HTML 的超时时间 (秒)
  fetch_timeout: 30
  # 可选: 为获取文章 HTML 内容指定代理 URL (例如 http://127.0.0.1:7890, socks5://user:pass@host:port)
  # 如果设置，这将覆盖内容获取调用的 HTTP_PROXY/HTTPS_PROXY 环境变量。
  proxy: null

# --- 目标 API 配置 (通用 - 仅当 output.method 为 'api' 时使用) ---
target_api:
  # 必需: 目标 API 端点的完整 URL。
  endpoint: "YOUR_API_ENDPOINT_URL" # 示例: "https://your-api.com/v1/articles"

  # 可选: 要使用的 HTTP 方法 (例如 POST, PUT, PATCH)。默认为 "POST"。
  method: "POST"

  # 可选: 目标 API 的身份验证详细信息。
  authentication:
    # 身份验证类型。选项:
    # - "none": 无身份验证 (默认)。
    # - "bearer": 在 'Authorization' 标头中发送 API 密钥，格式为 "Bearer <key>"。
    # - "header_key": 在自定义标头中发送 API 密钥。
    # - "body_key": 在 JSON 有效负载中将 API 密钥作为字段发送。
    # **重要提示**: 实际的 API 密钥/令牌值必须存储在 `.env` 文件中的
    #              `TARGET_API_KEY` 环境变量中。
    type: "none"

    # 如果类型是 'header_key' 或 'bearer'，则为必需。
    # 指定 HTTP 标头的名称。
    # 对于 'bearer'，如果省略，则默认为 "Authorization"。
    # 'header_key' 示例: "X-Api-Key"
    header_name: null

    # 如果类型是 'body_key'，则为必需。
    # 指定 JSON 有效负载中将放置 `TARGET_API_KEY` 的键名。
    # 示例: "apiKey"
    body_key_name: null

  # 可选: 与请求一起发送的自定义 HTTP 标头。
  # 如果发送了有效负载，默认 'Content-Type' 是 'application/json'。
  # 默认 'Accept' 是 'application/json'。这些可以在此处覆盖。
  headers:
    # 示例:
    # User-Agent: "MyMediumProcessor/1.0"
    # X-Custom-ID: "some-value"
    Content-Type: "application/json" # 保留或覆盖

  # 可选: 定义发送到 API 的 JSON 有效负载的结构。
  # 如果省略或为 null/空，则不发送 JSON 有效负载 (对于 GET/DELETE 或期望无正文的 API 很有用)。
  # 使用占位符: {title}, {link}, {summary}, {published_iso}, {source_tag}, {content_markdown}
  # 这些将被实际的文章数据替换。
  # 您可以包含静态值 (字符串、数字、布尔值) 或嵌套结构。
  payload_mapping:
    # --- 示例结构 --- #
    article_title: "{title}"          # 映射文章标题
    source_url: "{link}"            # 映射文章链接
    body: "{content_markdown}"       # 映射处理后的 Markdown 内容
    published: "{published_iso}"    # 映射发布日期 (ISO 格式)
    category: "medium/{source_tag}" # 结合静态文本和占位符的示例
    metadata:
      source: "medium-importer"
      processed_at: "{now_iso}" # 当前时间的占位符 (如果支持，否则在 API 中处理)
    tags: ["medium", "imported", "{source_tag}"] # 带有占位符的示例列表
    is_draft: true                  # 示例静态布尔值
    # 注意: 如果 authentication.type 是 'body_key'，则在
    #       authentication.body_key_name 中定义的键将自动添加到此处。

  # 可选: 如何确定 API 调用是否成功。
  success_check:
    # 类型: 'status_code' 或 'json_field'。默认为 'status_code'。
    type: "status_code"

    # 如果类型是 'status_code'，则为必需。可接受的 HTTP 状态代码列表。
    # 默认为 [200, 201]。
    expected_status_codes: [200, 201]

    # 如果类型是 'json_field'，则为必需。要在 JSON 响应中检查的键路径 (嵌套使用点分隔)。
    # 示例: "status", "result.code", "data[0].id"
    json_field_name: null
    # 如果类型是 'json_field'，则为必需。指定字段的预期值。
    # 可以是字符串、数字、布尔值或 null。
    expected_json_value: null # 示例: "success", 200, true

  # 可选: API 请求的超时时间 (秒)。默认为 30。
  push_timeout: 30

# 输出配置
output:
  method: "api" # 或 "local"
  local_dir: "output_markdown" # 如果 method 是 "local" 则使用

# 状态管理配置
state_database:
  db_file: "processed_articles.db"

```

**关键 `config.yaml` 部分：**

*   **`logging`:** 设置日志详细程度 (`level`) 和可选的输出文件 (`log_file`)。
*   **`medium_feeds`:** 列出您要处理的 Medium RSS 源的 URL。
*   **`ai_filter`:**
    *   `interests`/`dislikes`: 定义您对 AI 过滤器的偏好。
    *   `english_level`: 设置词汇注释的目标级别。
    *   `filtering_model`/`processing_model`: 指定要使用的 AI 模型。确保您的 `OPENAI_API_KEY` 有权访问这些模型。
    *   `api_base_url`: 如果您的 AI 提供商不是 OpenAI 或者您正在使用代理/本地模型，请使用此项。
    *   `proxy`: **(新增)** 可选地指定用于 AI API 请求的完整代理 URL (例如 `http://localhost:7890`, `socks5://user:pass@host:port`)。如果设置，它将覆盖这些特定请求的 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量。需要 `httpx` 库 (已添加到 `requirements.txt`)。
    *   `accepted_relevance`/`accepted_quality`: 定义哪些 AI 分类可以通过过滤器。
*   **`fetch_config`:**
    *   `cookie_file`: 指向您的 `medium.com_cookies.txt` 的路径。**确保此文件存在且有效。**
    *   `fetch_timeout`: 获取文章的网络超时时间。
    *   `proxy`: **(新增)** 可选地指定用于获取文章 HTML 内容的完整代理 URL (例如 `http://localhost:7890`, `socks5://user:pass@host:port`)。如果设置，它将覆盖这些特定请求的 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量。
*   **`target_api`:** (仅当 `output.method: api` 时使用) - **此部分现在高度可配置！**
    *   `endpoint`: **必需。** 您的 API 端点的完整 URL。
    *   `method`: HTTP 方法 (例如 `POST`, `PUT`)。默认为 `POST`。
    *   `authentication`:
        *   `type`: 选择 `none`, `bearer`, `header_key`, 或 `body_key`。
        *   `header_name`: `bearer` (默认为 `Authorization`) 和 `header_key` 必需。
        *   `body_key_name`: `body_key` 必需。
        *   **请记住：** 实际的密钥/令牌应放在 `.env` 文件中，作为 `TARGET_API_KEY`。
    *   `headers`: 添加您的 API 可能需要的任何自定义 HTTP 标头。
    *   `payload_mapping`: 定义您的 API 期望的确切 JSON 结构。使用 `{title}`, `{content_markdown}` 等占位符，它们将被文章数据填充。您可以创建嵌套 JSON 并包含静态值。
    *   `success_check`:
        *   `type`: 选择 `status_code` (检查 HTTP 状态) 或 `json_field` (检查 API 的 JSON 响应中的值)。
        *   `expected_status_codes`: 指示成功的 HTTP 代码列表 (如果类型是 `status_code`)。
        *   `json_field_name`: 响应 JSON 中要检查的键 (嵌套用点分隔，例如 `data.status`) (如果类型是 `json_field`)。
        *   `expected_json_value`: `json_field_name` 应具有的值，以便请求被视为成功。
    *   `push_timeout`: API 请求的网络超时时间。
*   **`output`:** (同前 - 选择 `api` 或 `local`)
*   **`state_database`:** (同前)

**代理支持说明：**

*   可以分别为 AI API 请求 (`ai_filter.proxy`) 和获取文章内容 (`fetch_config.proxy`) 配置代理设置。
*   如果 `config.yaml` 中未为任一部分设置代理，脚本将尝试使用标准的 `HTTP_PROXY` 或 `HTTPS_PROXY` 环境变量 (如果已设置)。
*   `config.yaml` 中的代理设置优先于环境变量。
*   为 AI 请求使用代理 (`ai_filter.proxy`) 需要 `httpx` 库，该库已添加到 `requirements.txt`。

## 使用方法

配置完成后，在项目目录中 (如果使用虚拟环境，请先激活) 从终端运行主脚本：

```bash
python main.py
```

脚本将执行"工作原理"中描述的工作流。日志将打印到控制台 (如果配置了，也会记录到 `app.log`)。

## 输出

根据 `output.method` 设置：

*   **`api`：** 处理后的文章将使用指定的 `method`, `authentication`, `headers`, 和 `payload_mapping` 发送到配置的 `target_api.endpoint`。成功与否由 `success_check` 配置确定。检查脚本日志以获取成功或失败的详细信息，包括失败时的 API 响应。
*   **`local`：** 处理后的文章将另存为 Markdown 文件 (`.md`)，存储在 `output.local_dir` 指定的目录中。结构如下：
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
    其中 `<source_tag>` 来自 RSS 源 URL (例如 `programming`, `artificial-intelligence`)，`<article_title>` 是文章标题的净化版本。成功/失败会被记录。

## 状态管理

`processed_articles.db` 文件是一个 SQLite 数据库，用于存储所有已处理 (或尝试处理) 文章的 URL。这可以防止在文章再次出现在源中或脚本多次运行时重复处理和输出同一篇文章。数据库跟踪处理状态 (例如 `pushed`, `saved_local`, `filtered_out_stage1`, `failed_fetch`)。

## 自动化 (可选)

您可以使用任务计划程序自动执行脚本：

*   **Linux/macOS:** 使用 `cron`。编辑您的 crontab (`crontab -e`) 并添加类似以下行：
    ```cron
    # 每 2 小时运行一次
    0 */2 * * * /path/to/your/project/.venv/bin/python /path/to/your/project/main.py >> /path/to/your/project/cron.log 2>&1
    ```
    *(根据需要调整路径、虚拟环境激活和频率。)*
*   **Windows:** 使用"任务计划程序"创建一个任务，定期运行 `C:\path\to\your\project\.venv\Scripts\python.exe C:\path\to\your\project\main.py`。

## 维护和潜在问题

*   **Cookie 过期：** **这是最常见的问题。** `medium.com_cookies.txt` 需要定期手动更新，因为 Cookie 会过期。
*   **Medium 网站更改：** Medium 可能会更改其 HTML 结构，从而破坏 `utils.py` 中的内容提取逻辑 (`extract_main_content_from_html`)。这可能需要更新 BeautifulSoup 选择器。
*   **AI 模型更改/成本：** AI API 会不断发展。模型可能会被弃用，或者定价可能会发生变化。监控您的 AI API 使用情况和成本。对于非常长的文章，上下文长度限制也可能是一个问题。
*   **API 更改：** 如果使用 `api` 输出，对目标 API 的更改可能需要更新 `api_pusher.py`。
*   **RSS 源问题：** 源可能会暂时不可用或更改格式。
*   **配置错误：** 确保 `config.yaml` 中的路径正确，并且 `.env` 中的 API 密钥有效。

## 贡献

欢迎贡献！请随时提交拉取请求或为错误、功能请求或改进提出问题。


## 许可证


本项目根据 MIT 许可证授权。有关详细信息，请参阅 `LICENSE` 文件。
