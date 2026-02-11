## GitHub 抓取与本地数据库说明

### 1. 功能概览

- **数据来源**：GitHub 搜索 API（按语言 + 趋势类型 + 关键词 `ai`）。
- **核心目标**：
  - 只对**本地不存在的新项目**做 LLM 筛选和（可选）翻译；
  - 已存在的项目只更新 star / topics 等状态，不改标题和摘要。
- **存储位置**：`output/github/github_projects.json`  
  这是 GitHub 项目的**唯一权威数据文件**，预览页和后续处理都基于它。

---

### 2. 配置入口

#### 2.1 GitHub 抓取配置

- **位置**：`config/sources.json` → `sources.github.trending_daily`
- **关键字段**：

```jsonc
"github": {
  "trending_daily": {
    "enabled": true,
    "api_base_url": "https://api.github.com",
    "languages": ["python", "javascript", "typescript", "rust"],
    "topics": ["ai"],
    "trending_types": ["pushed", "created", "stars"],
    "star_limits": {
      "pushed": 500,
      "created": 100,
      "stars": 500
    },
    "ai_filter_enabled": true,
    "translation_enabled": false
  }
}
```

- **字段含义**：
  - **`languages`**：要抓取的编程语言列表。
  - **`trending_types`**：
    - `pushed`：最近一段时间有推送的项目；
    - `created`：最近创建的项目；
    - `stars`：高 star 项目。
  - **`star_limits`**：每种类型的最小 star 数（用于过滤噪音）。
  - **`ai_filter_enabled`**：是否启用 LLM 筛选（只保留 AI 相关项目）。
  - **`translation_enabled`**：是否对标题/摘要做翻译（GitHub 一般可以设为 `false`，节省 Token）。

> **调优建议：**
> - 想多抓一些项目：降低 `star_limits` 或增加 `languages`。
> - 想结果更干净：保持 `ai_filter_enabled=true`，适当调高 `star_limits`。

#### 2.2 调度器配置

- **位置**：`config/sources.json` → `settings.scheduler.tasks.github`

```jsonc
"settings": {
  "scheduler": {
    "enabled": true,
    "tasks": {
      "github": {
        "enabled": true,
        "time": "09:30",
        "max_results": 100
      }
    }
  }
}
```

- **字段含义**：
  - **`settings.scheduler.enabled`**：调度器总开关。
  - **`tasks.github.enabled`**：是否注册 GitHub 定时任务。
  - **`tasks.github.time`**：每天执行时间（字符串或字符串数组）。
  - **`tasks.github.max_results`**：单次调用 `fetch_github_trending(limit=...)` 的上限。

> **注意**：
> - 定时任务不会在启动时自动跑一次，如需立即执行，用 `--once`。

---

### 3. 运行方式

#### 3.1 一次性执行（推荐调试 / 手动刷新）

```bash
python3 src/msgskill/multi_scheduler.py --once
```

- 会并行执行所有配置为 `enabled: true` 的任务，其中包括 GitHub。
- GitHub 流程：
  - 调用 `fetch_github_trending(limit=...)`；
  - 读取本地 `output/github/github_projects.json` 做增量判断；
  - 只对新项目调用 LLM，处理后写回同一个文件。

#### 3.2 长期定时运行

- 使用现有 `start.sh` 启动调度器后台循环：
  - 由 `settings.scheduler.enabled` + `tasks.github.enabled` 控制是否启用；
  - 按 `tasks.github.time` 指定的时间每天执行一次 GitHub 抓取。
- 启动时**不会自动执行一次 GitHub 抓取**，即时执行仍需显式加 `--once`。

---

### 4. 数据结构说明：`output/github/github_projects.json`

- **文件类型**：单个 JSON 对象。
- **key**：`source_url`（即 GitHub 仓库链接，例如 `https://github.com/user/repo`）。
- **value**：该仓库的完整元数据和 AI 标记。

示例（字段已简化，只保留核心）：

```jsonc
{
  "https://github.com/user/repo": {
    "title": "user/repo: 项目名或简短描述",
    "summary": "清洗后的简介（可选翻译）",
    "source_url": "https://github.com/user/repo",
    "published_date": "2025-01-01T12:34:56+00:00",
    "source_type": "github",
    "article_tag": "AI工具",
    "author": "user",
    "score": 1234,
    "tags": ["ai", "agent"],
    "language": "Python",
    "story_type": "pushed",
    "ai_score": 0.8,
    "is_ai_project": true,
    "ai_reason": "简要说明为什么与 AI 相关",
    "full_name": "user/repo",
    "name": "repo",
    "description": "原始 description 文本",
    "html_url": "https://github.com/user/repo",
    "topics": ["ai", "agent"],
    "created_at": "2025-01-01T12:34:56Z",
    "updated_at": "2026-02-10T11:00:00"
  }
}
```

#### 4.1 增量更新逻辑

- **判定依据**：`source_url` 是否已存在于 `github_projects.json`。
- **旧项目（已存在）**：
  - 更新：
    - `score` / `stargazers_count`
    - `tags` / `topics`
    - `story_type`（趋势类型）
    - `language`
    - `updated_at`
  - 不改变：
    - `title` / `summary`
    - 既有 `ai_score` / `is_ai_project`
- **新项目（本地不存在）**：
  - 先以“非 AI 项目”的身份写入，避免中途出错导致完全没有记录；
  - 之后按批次调用 LLM 做 AI 筛选，通过的补上：
    - `ai_score`
    - `is_ai_project=true`
    - `ai_reason`

---

### 5. 与其他组件的关系

- **Notion 同步（可选，默认关闭）**：
  - `notion_sync` 模块提供统一的 Notion 同步能力（`sync_items` / `sync_json_file`），并通过 `config/sources.json` 中的 `notion_sync` 段配置 token 和各数据源数据库。
  - 额外增加了 GitHub 专用开关：
    ```jsonc
    "notion_sync": {
      "enabled": true,
      "auto_sync": {
        "github": false
      },
      "databases": {
        "github": { "database_id": "..." }
      }
    }
    ```
  - 行为说明：
    - 当 `notion_sync.enabled = true` 且 `auto_sync.github = true` 时：
      - 每次调度器执行 `sync_github()` 并成功获取结果后，会自动调用 Notion，同步本次抓取到的 GitHub 项目（去重基于 `source_url`）。
    - 当 `auto_sync.github = false`（默认）时：
      - 不会自动同步 GitHub 到 Notion；
      - 如需同步，可单独编写脚本，基于 `github_projects.json` 调用 `notion_sync.sync_json_file(...)` 或 `sync_items(...)`。

---

### 6. 常见调整场景（简要）

- **想要更多候选项目**：
  - 降低 `star_limits`；
  - 增加 `languages`（例如加上 `go`、`java`）。
- **想结果更“精”**：
  - 保持 `ai_filter_enabled = true`；
  - 合理调高 `star_limits`，过滤低质量仓库。
- **暂时关闭 LLM 筛选**：
  - 将 `sources.github.trending_daily.ai_filter_enabled` 设为 `false`；
  - 系统会改用简单的关键词匹配（名称/描述/topics 中包含 `ai` 等）替代 LLM。

