---
name: AI数据源聚合
description: >
  获取 AI 领域的学术论文、技术新闻和开源项目。
  当用户想看论文/研究，调用 fetch_arxiv.py；
  当用户想看新闻/资讯，同时调用 fetch_hackernews.py 和 fetch_rss.py；
  当用户想看 AI 开源项目/GitHub 趋势，调用 fetch_github.py。
  所有脚本默认输出 Markdown 格式。
license: MIT
metadata:
  author: MsgSkill Team
  version: "1.1.0"
  category: data-fetching
  tags: [arxiv, hackernews, rss, github, ai, news, papers, open-source]
dependencies: python>=3.10, pyyaml, feedparser, arxiv, httpx
---

# AI数据源聚合 Skill

## 意图识别 → 脚本映射

这是 Agent 调用本 Skill 时最重要的判断逻辑：

| 用户意图 | 示例表述 | 调用脚本 |
|----------|----------|----------|
| 看论文 / 学术研究 | "最新的 AI 论文"、"有什么新研究"、"帮我找 NLP 相关论文"、"机器学习最新进展" | `fetch_arxiv.py` |
| 看新闻 / 资讯 | "最新 AI 新闻"、"今天有啥科技新闻"、"帮我看看 AI 动态"、"技术博客有什么更新" | `fetch_hackernews.py` + `fetch_rss.py` |
| 看开源项目 | "有什么火的 AI 项目"、"GitHub 上有什么新的 Python AI 库"、"推荐开源工具"、"最近有什么值得关注的项目" | `fetch_github.py` |

> **说明**：新闻类需求同时运行 HackerNews 和 RSS 两个脚本，合并结果后呈现，覆盖社区讨论和媒体报道两个维度。

---

## 快速调用

```bash
# 切换到 skill 目录（所有脚本均在此目录下执行）
cd getaimsg

# 📚 论文
python scripts/fetch_arxiv.py --max-results 10

# 📰 新闻（同时跑两个）
python scripts/fetch_hackernews.py --max-results 15
python scripts/fetch_rss.py --max-results 10

# 💻 开源项目
python scripts/fetch_github.py --max-results 20
```

---

## 数据源详情

### 📚 arXiv 论文 — `fetch_arxiv.py`

- **来源**：arXiv 学术预印本平台
- **默认启用分类（5个）**：cs.AI / cs.LG / cs.CL / cs.CV / cs.NE（其余 8 个分类在 `config.yaml` 中可按需启用）
- **AI 筛选**：❌ 不启用（分类已足够精确）
- **翻译**：✅ 启用（摘要自动翻译为中文）
- **输出**：论文标题、摘要、作者、发布日期、PDF 链接、分类标签

```bash
python scripts/fetch_arxiv.py --max-results 10
python scripts/fetch_arxiv.py --max-results 20 --output-format json
```

### 📰 HackerNews — `fetch_hackernews.py`

- **来源**：Hacker News Firebase API（top / new / best 三类故事）
- **时间范围**：最近 7 天（可在 `config.yaml` 的 `hackernews.recent_days` 调整）
- **AI 筛选**：✅ 启用（内容混杂，由 DeepSeek 筛选 AI 相关条目）
- **翻译**：✅ 启用（标题和摘要翻译为中文）
- **输出**：标题、摘要、评分、作者、发布日期、原文链接

```bash
python scripts/fetch_hackernews.py --max-results 15
```

### 📡 RSS 订阅 — `fetch_rss.py`

- **来源**：28 个 AI 相关 Feed，覆盖：
  - 国际媒体：MIT Technology Review、TechCrunch AI、Ars Technica
  - 公司博客：OpenAI、Google AI、Microsoft AI、LangChain
  - 中文媒体：量子位、机器之心、少数派、36氪AI、IT之家
  - 技术社区：InfoQ、V2EX、掘金
- **AI 筛选**：✅ 启用（来源多样，由 DeepSeek 过滤 AI 相关内容）
- **翻译**：✅ 启用（英文内容自动翻译）
- **输出**：按 Feed 分组，含标题、摘要、发布日期、来源链接

```bash
python scripts/fetch_rss.py --max-results 10
```

### 💻 GitHub 项目 — `fetch_github.py`

- **来源**：GitHub Search API
- **查询条件**（API 层过滤，不依赖关键词）：
  - 语言：Python / JavaScript / TypeScript / Rust
  - 时间：最近 15 天内创建（`created_days: 15`）
  - Stars：> 300（`star_limits.created: 300`）
- **AI 相关性筛选**：内置关键词匹配（ai / llm / gpt / transformer / neural 等）
- **AI 筛选**：❌ 不启用（直接关键词匹配，减少 LLM 调用）
- **翻译**：✅ 启用（项目名称和描述翻译为中文）
- **输出**：项目名、描述、Stars 数、创建日期、语言标签、仓库链接

```bash
python scripts/fetch_github.py --max-results 20
python scripts/fetch_github.py --max-results 20 --output-format json
```

---

## 命令行参数

所有 fetch 脚本支持统一参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--max-results` | 最大返回数量 | 配置文件中的值 |
| `--output-format` | 输出格式：`markdown` / `json` | `markdown` |
| `--output-file` | 指定输出文件路径（不填则自动写入 `output/<来源>_<时间戳>.md`） | `output/<来源>_<时间戳>.md` |
| `--config-path` | 自定义配置文件路径 | `config.yaml` |

---

## 输出格式

### Markdown（默认）

所有脚本默认输出可读的 Markdown，可直接展示给用户：

```markdown
# arXiv 论文

**获取时间**: 2026-02-25
**总数**: 10 篇

---

## 1. 论文标题（中文翻译）
**摘要**: 摘要内容...
**作者**: A, B, C
**发布日期**: 2026-02-20
**链接**: [https://arxiv.org/abs/xxxx](...)
**标签**: `cs.AI`, `cs.LG`
```

### JSON（可选）

使用 `--output-format json` 输出结构化数据，字段统一：

```json
{
  "success": true,
  "source": "arXiv",
  "fetched_at": "2026-02-25T10:00:00",
  "total_count": 10,
  "data": [
    {
      "title": "论文标题",
      "summary": "摘要（最多300字）",
      "source_url": "https://...",
      "published_date": "2026-02-20",
      "source_type": "arxiv",
      "article_tag": "AI论文",
      "author": "作者",
      "tags": ["cs.AI"],
      "score": null,
      "ai_score": null
    }
  ]
}
```

### 错误格式

脚本执行失败时返回统一结构，Markdown 模式下也会输出友好提示：

```json
{
  "success": false,
  "error": "具体错误描述",
  "source": "数据源名称"
}
```

---

## 配置说明

配置文件：`getaimsg/config.yaml`

| 数据源 | AI筛选 | 翻译 | 关键说明 |
|--------|--------|------|----------|
| arXiv | ❌ | ✅ | 分类精确，无需筛选 |
| HackerNews | ✅ DeepSeek | ✅ | `recent_days` 控制时间范围 |
| RSS | ✅ DeepSeek | ✅ | 多来源混合，需筛选 |
| GitHub | ❌（关键词匹配） | ✅ | `created_days` + `star_limits` 控制范围 |

**可调节的关键配置项：**

```yaml
hackernews:
  max_results: 15
  recent_days: 7        # 查近几天的数据

github:
  created_days: 15      # 近几天创建的项目
  star_limits:
    created: 300        # 最低 star 数

llm:
  enabled: true
  api_key: "your-key"   # DeepSeek API Key
  recent_days: 7        # HackerNews/RSS 的兜底时间范围
```

---

## 典型场景

### 场景 1：用户想看论文

> "最近有什么 AI 相关的新论文？"、"帮我看看机器学习最新进展"

```bash
python scripts/fetch_arxiv.py --max-results 10
```

### 场景 2：用户想看新闻

> "今天 AI 圈有什么新动态？"、"帮我看下最新技术资讯"

```bash
# 同时运行两个，覆盖社区 + 媒体两个维度
python scripts/fetch_hackernews.py --max-results 15
python scripts/fetch_rss.py --max-results 10
```

### 场景 3：用户想看开源项目

> "GitHub 上最近有什么新的 AI 项目？"、"推荐一些开源工具"

```bash
python scripts/fetch_github.py --max-results 20
```

### 场景 4：准备技术周报

> "帮我收集本周的 AI 动态，整理成周报"

```bash
# 同时收集三类数据
python scripts/fetch_arxiv.py --max-results 5 --output-file arxiv.json
python scripts/fetch_hackernews.py --max-results 10 --output-file hn.json
python scripts/fetch_rss.py --max-results 10 --output-file rss.json
python scripts/fetch_github.py --max-results 5 --output-file github.json

# 各自转换为 Markdown 后聚合
python scripts/json_to_markdown.py arxiv.json -o papers.md
python scripts/json_to_markdown.py hn.json -o news_hn.md
python scripts/json_to_markdown.py rss.json -o news_rss.md
python scripts/json_to_markdown.py github.json -o projects.md
```

---

## 技术架构

```
getaimsg/
├── config.yaml              # 独立配置，不依赖主项目
├── scripts/
│   ├── fetch_arxiv.py       # arXiv 入口脚本
│   ├── fetch_hackernews.py  # HackerNews 入口脚本
│   ├── fetch_rss.py         # RSS 入口脚本
│   ├── fetch_github.py      # GitHub 入口脚本
│   └── json_to_markdown.py  # JSON → Markdown 转换工具
├── tools/                   # 核心数据获取逻辑
│   ├── arxiv_fetcher.py
│   ├── news_scraper.py
│   ├── rss_reader.py
│   └── github_fetcher.py
└── utils/                   # 工具类
    ├── ai_filter.py         # DeepSeek AI 筛选
    ├── translator.py        # 翻译
    ├── cache.py             # 内存缓存
    ├── logger.py            # 日志
    ├── github_db_new.py     # GitHub 内存数据库
    └── skill_config.py      # Skill 配置加载
```

**设计原则：**
- **独立运行**：不依赖主项目配置，`config.yaml` 完全自包含
- **内存缓存**：GitHub 使用内存数据库，无文件副作用
- **错误隔离**：单个数据源失败不影响其他脚本
- **默认可用**：开箱即用，配置好 `llm.api_key` 即可启用 AI 筛选
