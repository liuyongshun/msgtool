## RSS 抓取与本地数据库说明

### 1. 功能概览

- **数据来源**：`config/sources.json` 中配置的一组 RSS 源（科技媒体、公司博客、Newsletter 等）。
- **核心目标**：
  - 聚合多源 AI / 科技相关文章；
  - 通过 LLM 对文章标题做相关性筛选；
  - 可选对标题/摘要做翻译；
  - 将结果按天写入 `output/daily/YYYY-MM-DD/rss_*.json`。

---

### 2. 配置入口

#### 2.1 RSS 源配置

- **位置**：`config/sources.json` → `sources.rss`
- **单个源配置示例**：

```jsonc
"rss": {
  "mit_tech_review": {
    "enabled": true,
    "name": "MIT Technology Review AI",
    "url": "https://www.technologyreview.com/feed/",
    "description": "MIT科技评论AI频道",
    "category": "technology_news",
    "tags": ["AI资讯", "技术博客"],
    "ai_filter_enabled": true,
    "translation_enabled": false
  }
}
```

- **字段含义**：
  - **`enabled`**：是否启用该 RSS 源。
  - **`name`**：用于前端展示和日志输出的名称。
  - **`url`**：RSS 订阅地址。
  - **`category`**：自定义分类标签（如 `news` / `newsletter` / `trends` 等，主要用于文档和后续扩展）。
  - **`tags`**：对该源的固定标签（例如 `["AI资讯","技术博客"]`），会附加在文章上。
  - **`ai_filter_enabled`**：
    - `true`：对该源抓到的文章标题使用 LLM 做一次「是否与 AI / 科技相关」的筛选；
    - `false`：不调用 LLM，所有抓到的文章都保留。
  - **`translation_enabled`**：
    - `true`：对筛选后的文章标题和摘要调用翻译；
    - `false`：只保留原文。

> **推荐策略：**
> - 对信噪比较高、专注 AI 的源，可以考虑 `ai_filter_enabled=false`，节省 Token；
> - 对综合科技媒体（TechCrunch、Techmeme 等），建议保持 `ai_filter_enabled=true`；
> - 中国区 / 中文源可以按需要关闭 `translation_enabled`。

#### 2.2 调度配置

- **位置**：`config/sources.json` → `settings.scheduler.tasks.rss`

```jsonc
"settings": {
  "scheduler": {
    "enabled": true,
    "tasks": {
      "rss": {
        "enabled": true,
        "time": ["10:20", "14:05", "17:20", "20:40"],
        "max_results": 20
      }
    }
  }
}
```

- **字段含义**：
  - **`settings.scheduler.enabled`**：调度器总开关。
  - **`tasks.rss.enabled`**：是否启用 RSS 定时任务。
  - **`tasks.rss.time`**：每天执行的时间点（可以是字符串或字符串数组）。
  - **`tasks.rss.max_results`**：单次每个源最多抓取多少条文章。

> **说明**：
> - 定时任务不会在启动时自动执行一次，若要立即执行，仍需使用 `--once`。

---

### 3. 运行方式

#### 3.1 一次性执行（手动刷新）

```bash
python3 src/multi_scheduler.py --once
```

- 会执行所有 `enabled=true` 的任务，其中包括 RSS。
- RSS 流程：
  - 从配置中读取所有启用源的 URL；
  - 对每个源调用 `fetch_rss_feeds` 抓取 + LLM 筛选 + 翻译；
  - 按天写入/追加到 `output/daily/YYYY-MM-DD/rss_*.json`；
  - 结果写入当天的 RSS JSON 文件。

#### 3.2 长期定时运行

- 使用 `start.sh` 启动调度器后台循环：
  - 由 `settings.scheduler.enabled` + `tasks.rss.enabled` 控制是否启用；
  - 每天在 `tasks.rss.time` 指定的时间点执行一次 RSS 同步。

---

### 4. 数据结构说明：`output/daily/YYYY-MM-DD/rss_*.json`

- **文件命名**：`rss_YYYYMMDD_HHMMSS.json`
- **结构示例（精简版）**：

```jsonc
{
  "source": "RSS Feeds",
  "feeds_count": 27,
  "total_items": 247,
  "errors_count": 3,
  "fetched_at": "2026-02-10T10:20:53",
  "feeds": {
    "https://www.technologyreview.com/feed/": {
      "url": "https://www.technologyreview.com/feed/",
      "title": "MIT Technology Review AI",
      "description": "...",
      "link": "https://www.technologyreview.com/",
      "updated": "...",
      "items_count": 20,
      "items": [
        {
          "title": "...",
          "link": "https://www.technologyreview.com/...",
          "summary": "...",
          "published": "Mon, 10 Feb 2026 02:28:48 GMT",
          "author": "作者名",
          "tags": ["AI资讯"],
          "ai_score": 0.87
        }
      ]
    }
  },
  "errors": [
    "某些源的抓取/解析错误信息（可选）"
  ]
}
```

#### 4.1 追加与去重逻辑

- 同一天多次同步时：
  - 始终在同一个 `rss_*.json` 文件内追加；
  - 对**同一个 feed** 下的文章，按 `link` 去重（同一链接只保留一条）。
- `preview_server` 的 `/api/data/<date>/rss` 会：
  - 合并同一天的所有 `rss_*.json`；
  - 按 feed 聚合，统计 `feeds_count` 与 `total_items`；
  - 提供给前端 `renderRssData` 渲染。

---

### 5. LLM 与翻译行为

- **AI 筛选（`ai_filter_enabled`）**：
  - 当某个源启用 AI 筛选时，本轮抓到的文章标题会打包送入 `classify_titles_batch`；
  - 只保留 `keep=true` 的文章，并在条目上写入 `ai_score`；
  - 日志中可见：
    - `开始AI筛选 N 篇文章...`
    - `AI筛选完成: N -> M 篇文章`。
- **翻译（`translation_enabled`）**：
  - 对通过 AI 筛选的文章（或未启用 AI 筛选时的所有文章）并发调用 `translate_article_item`；
  - 用翻译后的标题与摘要覆盖原始值；
  - 若翻译失败，会保留原文。
- **缓存机制**：
  - 每个源按 `rss_{url}_{limit}_t{0/1}` 做 10 分钟缓存（`t1` 表示开启翻译，`t0` 表示关闭翻译）；
  - 缓存 key 区分 `translation_enabled` 状态，避免翻译结果和未翻译结果相互污染；
  - 10 分钟内重复调用，不会再次请求 HTTP 和 LLM，而是直接使用缓存结果。

> 当前 RSS 暂未像 GitHub 那样做「跨天 LLM 结果复用」，所以同一篇文章跨天再次抓取时，会重新跑一次 AI 筛选（但每次只对“新抓到”的 N 条文章调用一次 LLM）。

---

### 6. 调整与优化建议（简要）

- **想多一点 RSS 内容**：
  - 提高 `tasks.rss.max_results`；
  - 启用更多源（`sources.rss.*.enabled=true`）。
- **想减少 Token 消耗**：
  - 对纯 AI 源（例如 deep-learning Newsletter）关闭 `ai_filter_enabled`；
  - 只对“泛科技新闻”类源保留 AI 筛选；
  - 按需关闭 `translation_enabled`，改为只保留原文。
- **调试问题时**：
  - 查看 `logs/scheduler_clean.log` 中的 RSS 日志：
    - 抓取：`📺 开始同步RSS订阅 - 最多...`、`同步 N 个RSS源`
    - AI：`开始AI筛选...`、`AI筛选完成...`
    - 落盘：`✅/⚠️ RSS同步完成/部分失败: ... | 输出: rss_*.json`

