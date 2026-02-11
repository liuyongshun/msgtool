# AI开发指南 - MsgSkill

本文档为 AI Agent 提供快速理解和扩展 MsgSkill 项目的完整指南。

---

## 1. 项目架构

### 1.1 目录结构

```
msgskill/
├── config/                    # 配置文件
│   ├── sources.json          # 数据源配置（核心）
│   └── sources_schema.json   # 配置JSON Schema
├── src/msgskill/             # 核心代码
│   ├── tools/                # 数据获取工具
│   │   ├── arxiv_fetcher.py      # arXiv论文
│   │   ├── github_fetcher.py     # GitHub项目
│   │   ├── news_scraper.py       # HackerNews
│   │   ├── rss_reader.py         # RSS订阅
│   │   └── registry.py           # 工具注册表
│   ├── utils/                # 工具模块
│   │   ├── ai_filter.py          # AI筛选
│   │   ├── translator.py          # 翻译
│   │   ├── cache.py               # 缓存
│   │   ├── logger.py              # 日志
│   │   ├── parser.py              # 文本解析
│   │   ├── github_db_new.py       # GitHub数据库管理
│   │   └── notion_sync.py         # Notion同步
│   ├── config.py             # 配置管理
│   ├── models.py             # 数据模型
│   ├── output.py             # 输出管理
│   ├── multi_scheduler.py    # 调度器
│   └── preview_server.py     # 预览服务器
├── output/                   # 输出目录
│   ├── daily/                # 按日期存储（RSS/HackerNews/arXiv）
│   └── github/               # GitHub项目数据库（持久化）
│       └── github_projects.json
├── templates/                # HTML模板
│   └── output_preview.html   # 数据预览页面
├── static/                   # 静态资源
│   ├── css/
│   └── js/
├── scripts/                  # 工具脚本
│   ├── cleanup_logs.sh       # 日志清理
│   └── sync_to_notion.py     # Notion手动同步
├── test/                     # 测试脚本
└── docs/                     # 文档
```

### 1.2 数据流

```
配置加载 → 数据获取 → 时间过滤 → AI筛选 → 翻译 → 输出保存 → Notion同步（可选）
   ↓          ↓         ↓          ↓        ↓        ↓            ↓
sources.json  tools/  recent_days  ai_filter  translator  output/  notion_sync
```

**关键流程说明**：
1. **配置加载**: 从 `sources.json` 读取数据源配置
2. **数据获取**: 各工具模块从API/RSS抓取原始数据
3. **时间过滤**: 仅处理最近 N 天内的数据（`llm.recent_days`，默认7天）
4. **AI筛选**: 使用LLM批量判断内容相关性（可选）
5. **翻译**: 将标题/摘要翻译为中文（可选，各数据源独立控制）
6. **输出保存**: 保存到 `output/daily/` 或 `output/github/`
7. **Notion同步**: 自动或手动同步到Notion数据库（可选）

---

## 2. 核心概念

### 2.1 数据源类型

项目支持 4 种数据源类型：

| 类型 | 配置路径 | 工具函数 | 用途 |
|------|---------|---------|------|
| arXiv | `sources.arxiv.*` | `fetch_arxiv_papers()` | 学术论文 |
| HackerNews | `sources.news.hackernews` | `fetch_ai_news()` | 技术新闻 |
| RSS | `sources.rss.*` | `fetch_rss_feeds()` | 媒体订阅 |
| GitHub | `sources.github.trending_daily` | `fetch_github_trending()` | 开源项目 |

### 2.2 统一数据模型

所有数据源输出统一为 `ArticleItem` 模型：

```python
class ArticleItem(BaseModel):
    title: str                    # 标题（必需）
    summary: str                  # 摘要（≤300字，必需）
    source_url: str              # 来源URL（必需）
    published_date: Optional[str] # 发布日期（ISO 8601，可选）
    source_type: Literal["hackernews", "techmeme", "arxiv", "rss", "github"]  # 来源类型
    article_tag: Literal["AI资讯", "AI工具", "AI论文", "技术博客"]  # 分类标签
    
    # 可选字段
    author: Optional[str]        # 作者
    score: Optional[int]         # 评分/热度
    comments_count: Optional[int] # 评论数
    tags: list[str]             # 关键词标签
    story_type: Optional[Literal["top", "new", "best", "pushed", "created", "stars"]]  # 数据源类型
    ai_score: Optional[float]    # AI相关性（0.0-1.0）
```

### 2.3 配置管理

**核心配置文件**: `config/sources.json`

```json
{
  "sources": {
    "arxiv": { ... },      // 论文配置
    "news": { ... },       // 新闻配置
    "rss": { ... },        // RSS配置
    "github": { ... }      // GitHub配置
  },
  "global_settings": {
    "scheduler": {
      "enabled": true,
      "tasks": {
        "arxiv": { "enabled": true, "time": "09:00", "max_results": 20 }
      }
    }
  },
  "llm": {
    "api_key": "sk-xxx",   // DeepSeek API密钥
    "model_name": "deepseek-chat"
  }
}
```

### 2.4 缓存策略

| 缓存类型 | TTL | 用途 |
|---------|-----|------|
| 数据缓存 | 5分钟 | 避免重复API调用 |
| 翻译缓存 | 24小时 | arXiv论文翻译结果 |
| GitHub数据库 | 持久化 | GitHub项目全量存储和智能去重 |

**GitHub数据库结构**：
- `output/github/github_projects.json`：**单一权威文件**，存储所有GitHub项目
  - 使用 `source_url` 作为主键
  - 包含 `is_ai_project` 和 `ai_score` 标记
  - 新项目进行LLM分析，已存在项目仅更新状态（stars、comments等）
  - 支持增量AI筛选，批量保存防止数据丢失

---

## 3. 开发规范

### 3.1 文件组织

```
新增数据源工具：src/msgskill/tools/新工具_fetcher.py
新增工具函数：src/msgskill/utils/新功能.py
输出文件：
  - RSS/HackerNews/arXiv: output/daily/YYYY-MM-DD/source_timestamp.json
  - GitHub: output/github/github_projects.json（持久化全量数据库）
```

### 3.1.1 测试脚本规范

- **测试脚本位置**: `test/` 目录
- **测试输出**: `output/` 目录，文件名格式：`标识_时间戳.json`
- **命名规范**: `test_功能描述.py`

### 3.2 函数签名规范

**数据获取函数**：

```python
def fetch_xxx_data(
    limit: int = 10,
    **kwargs
) -> FetchResult:
    """
    获取XXX数据源内容
    
    Args:
        limit: 返回条目数量限制
        **kwargs: 其他参数（如category、language等）
    
    Returns:
        FetchResult: 统一的抓取结果格式
    """
    # 注意：当前实现为同步函数，如需异步请使用 asyncio
```

**关键开发规范**：
1. **时间过滤**: 在LLM处理前，先过滤掉超过 `llm.recent_days` 的旧数据
2. **错误处理**: 所有网络请求必须包含 try-except，失败时返回 `FetchResult(success=False)`
3. **日志记录**: 使用 `logger.info/warning/error` 记录关键操作
4. **缓存使用**: 合理使用 `get_cache()` 避免重复API调用

### 3.3 错误处理

```python
try:
    result = fetch_data()
    if result.success:
        logger.info(f"✅ 获取成功: {result.total_count}条")
    else:
        logger.error(f"❌ 获取失败: {result.error}")
except Exception as e:
    logger.error(f"❌ 异常: {str(e)}")
    return FetchResult(
        success=False,
        source_name="数据源名称",
        source_type="数据源类型",
        total_count=0,
        fetched_at=datetime.now().isoformat(),
        items=[],
        error=str(e)
    )
```

### 3.4 时间过滤规范

**所有数据源在LLM处理前必须进行时间过滤**：

```python
from datetime import datetime, timedelta

# 获取配置的时间窗口
config = get_config()
llm_cfg = config.get_llm_config()
recent_days = max(1, int(getattr(llm_cfg, "recent_days", 7) or 7))
cutoff_dt = datetime.utcnow() - timedelta(days=recent_days)

# 过滤数据
filtered_items = []
for item in items:
    pub_date = parse_date(item.published_date)
    if pub_date and pub_date >= cutoff_dt:
        filtered_items.append(item)
    
logger.info(f"时间过滤：最近 {recent_days} 天内 {len(filtered_items)} 条，跳过过期 {len(items) - len(filtered_items)} 条")
```

---

## 4. 添加新数据源

### 4.1 步骤概览

1. 在 `config/sources.json` 添加配置
2. 在 `src/msgskill/tools/` 创建 fetcher
3. 在 `multi_scheduler.py` 注册任务
4. 测试和验证

### 4.2 配置示例

在 `config/sources.json` 添加：

```json
{
  "sources": {
    "new_source": {
      "example_site": {
        "enabled": true,
        "name": "示例网站",
        "type": "api",
        "api_base_url": "https://api.example.com",
        "description": "示例数据源",
        "fetch_limit": {
          "default": 10,
          "max": 50
        },
        "cache_ttl": 300,
        "ai_filter_enabled": true
      }
    }
  }
}
```

### 4.3 Fetcher 实现

创建 `src/msgskill/tools/example_fetcher.py`：

```python
"""
示例数据源获取工具
"""
import asyncio
from typing import Optional
import httpx

from ..models import ArticleItem, FetchResult
from ..utils.cache import get_cache
from ..utils.logger import logger
from ..utils.ai_filter import classify_titles_batch
from ..config import get_config

async def fetch_example_data(limit: int = 10) -> FetchResult:
    """获取示例数据"""
    logger.info(f"📡 开始获取示例数据 - 最多{limit}条")
    
    try:
        # 1. 检查缓存
        cache = get_cache()
        cache_key = f"example_data_{limit}"
        cached = cache.get(cache_key)
        if cached:
            logger.info("✅ 使用缓存数据")
            return FetchResult(**cached)
        
        # 2. 获取配置
        config = get_config()
        source_config = config.config.get("sources", {}).get("new_source", {}).get("example_site")
        
        # 3. 请求数据
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{source_config['api_base_url']}/data",
                params={"limit": limit}
            )
            data = response.json()
        
        # 4. 转换为统一模型
        items = []
        for item in data["results"]:
            article = ArticleItem(
                title=item["title"],
                summary=item["description"][:300],
                source_url=item["url"],
                published_date=item["created_at"],
                source_type="example",
                article_tag="AI资讯"
            )
            items.append(article)
        
        # 5. AI筛选（如果启用）
        if source_config.get("ai_filter_enabled"):
            titles = [item.title for item in items]
            classifications = await classify_titles_batch(
                titles=titles,
                source_type="example"
            )
            
            filtered_items = []
            for item, (is_relevant, score) in zip(items, classifications):
                if is_relevant:
                    item.ai_score = score
                    filtered_items.append(item)
            items = filtered_items
        
        # 6. 构建结果
        result = FetchResult(
            success=True,
            source_name="示例网站",
            source_type="example",
            total_count=len(items),
            fetched_at=datetime.now().isoformat(),
            items=items
        )
        
        # 7. 缓存结果
        cache.set(cache_key, result.model_dump(), ttl=300)
        
        logger.info(f"✅ 获取完成: {len(items)}条")
        return result
        
    except Exception as e:
        logger.error(f"❌ 获取失败: {str(e)}")
        return FetchResult(
            success=False,
            source_name="示例网站",
            source_type="example",
            total_count=0,
            fetched_at=datetime.now().isoformat(),
            items=[],
            error=str(e)
        )
```

### 4.4 注册调度任务

在 `multi_scheduler.py` 添加：

```python
# 1. 添加同步方法（同步函数，非异步）
def sync_example(self, max_results: int = 10):
    """同步示例数据"""
    logger.info(f"📡 开始同步示例数据 - 最多{max_results}条")
    
    try:
        result = fetch_example_data(limit=max_results)
        
        if result.success:
            # 保存到文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_manager.get_daily_dir() / f"example_{timestamp}.json"
            self.output_manager._write_json(output_file, result.model_dump())
            
            # Notion自动同步（如果启用）
            try:
                config_manager = get_config()
                notion_cfg = config_manager.get_notion_config() or {}
                auto_sync_cfg = notion_cfg.get("auto_sync", {})
                if bool(auto_sync_cfg.get("example", False)):
                    self._sync_example_items_to_notion(result.items)
            except Exception as notion_error:
                logger.debug(f"Notion自动同步检查失败: {notion_error}")
            
            logger.info(f"✅ 同步完成: {result.total_count}条")
            self.sync_stats["success_count"] += 1
        else:
            logger.error(f"❌ 同步失败: {result.error}")
            self.sync_stats["failed_sources"].append("example")
            
    except Exception as e:
        logger.error(f"❌ 同步异常: {str(e)}")
        self.sync_stats["failed_sources"].append("example")

# 2. 在 start 方法中添加调度
def start(self):
    scheduler_config = self.config.global_settings.get("scheduler", {})
    tasks_config = scheduler_config.get("tasks", {})
    
    example_config = tasks_config.get("example")
    if example_config and example_config.get("enabled"):
        time_str = example_config.get("time", "12:00")
        max_results = example_config.get("max_results", 10)
        
        # 支持单个时间或时间数组
        times = [time_str] if isinstance(time_str, str) else time_str
        for time_str in times:
            schedule.every().day.at(time_str).do(self.sync_example, max_results=max_results)
            logger.info(f"📅 已注册示例数据同步任务: {time_str}, max_results={max_results}")
```

### 4.5 添加调度配置

在 `config/sources.json` 的 `global_settings.scheduler.tasks` 中添加：

```json
{
  "global_settings": {
    "scheduler": {
      "tasks": {
        "example": {
          "enabled": true,
          "time": "15:00",
          "max_results": 20,
          "note": "每天15:00执行示例数据同步"
        }
      }
    }
  }
}
```

---

## 5. 功能扩展

### 5.1 添加新的 AI 筛选逻辑

编辑 `src/msgskill/utils/ai_filter.py`：

```python
async def classify_with_custom_logic(
    items: list[dict],
    keywords: list[str]
) -> list[tuple[bool, float]]:
    """
    自定义筛选逻辑
    
    Args:
        items: 待筛选项目列表
        keywords: 关键词列表
    
    Returns:
        [(是否相关, 评分), ...]
    """
    # 实现自定义筛选逻辑
    pass
```

### 5.2 添加新的翻译策略

编辑 `src/msgskill/utils/translator.py`：

```python
async def translate_with_strategy(
    text: str,
    strategy: str = "default"
) -> str:
    """
    支持多种翻译策略
    
    Args:
        text: 待翻译文本
        strategy: 翻译策略（default/selective/none）
    
    Returns:
        翻译后的文本
    """
    if strategy == "none":
        return text
    elif strategy == "selective":
        # 选择性翻译逻辑
        pass
    else:
        # 默认翻译
        pass
```

### 5.3 自定义输出格式

编辑 `src/msgskill/output.py`：

```python
def save_result_custom_format(
    self,
    result: FetchResult,
    format_type: str = "json"
) -> Path:
    """
    支持多种输出格式
    
    Args:
        result: 抓取结果
        format_type: 输出格式（json/markdown/html）
    
    Returns:
        输出文件路径
    """
    if format_type == "markdown":
        # 生成 Markdown 格式
        pass
    elif format_type == "html":
        # 生成 HTML 格式
        pass
    else:
        # 默认 JSON 格式
        pass
```

---

## 6. 测试指南

```bash
# 立即执行一次所有任务
python -m src.msgskill.multi_scheduler --once

# 检查输出目录
ls -lh output/daily/$(date +%Y-%m-%d)/
```

---

## 7. 关键 API 参考

### 7.1 配置管理

```python
from src.msgskill.config import get_config

config = get_config()

# 获取全局设置
settings = config.global_settings

# 获取特定数据源配置
arxiv_config = config.get_arxiv_categories()
rss_urls = config.get_rss_feed_urls()
```

### 7.2 缓存操作

```python
from src.msgskill.utils.cache import get_cache

cache = get_cache()

# 设置缓存（TTL秒）
cache.set("key", {"data": "value"}, ttl=300)

# 获取缓存
data = cache.get("key")

# 删除缓存
cache.delete("key")
```

### 7.3 日志记录

```python
from src.msgskill.utils.logger import logger

logger.info("ℹ️ 信息日志")
logger.warning("⚠️ 警告日志")
logger.error("❌ 错误日志")
```

### 7.4 AI 筛选

```python
from src.msgskill.utils.ai_filter import classify_titles_batch

titles = ["AI论文标题1", "AI论文标题2"]
results = await classify_titles_batch(
    titles=titles,
    source_type="arxiv"
)
# 返回: [(是否相关, 评分), ...]
```

### 7.5 翻译

```python
from src.msgskill.utils.translator import translate_article_item

article = ArticleItem(...)
translated = await translate_article_item(article)
```

---

## 8. 配置参考

### 8.1 数据源配置模板

```json
{
  "sources": {
    "类型名": {
      "数据源ID": {
        "enabled": true,
        "name": "显示名称",
        "description": "描述",
        "type": "api|scrape",
        "api_base_url": "https://api.example.com",
        "fetch_limit": {
          "default": 10,
          "max": 50
        },
        "cache_ttl": 300,
        "ai_filter_enabled": true
      }
    }
  }
}
```

### 8.2 调度任务配置模板

```json
{
  "global_settings": {
    "scheduler": {
      "enabled": true,
      "tasks": {
        "数据源名": {
          "enabled": true,
          "time": "09:00",
          "max_results": 20,
          "note": "说明文字"
        }
      }
    }
  }
}
```

---

## 9. 最佳实践

### 9.1 Token 优化

- ✅ **时间过滤**: 仅处理最近 N 天内的数据（`llm.recent_days`，默认7天），节省 30-50% Token
- ✅ **缓存机制**: 使用缓存避免重复API调用
- ✅ **批量处理**: 批量请求AI筛选（一次处理多个标题）
- ✅ **选择性翻译**: arXiv 选择性翻译（只翻译多作者论文），节省 76% Token
- ✅ **GitHub去重**: GitHub项目数据库智能去重，已筛选项目跳过AI判断，节省 70-85% Token
- ✅ **增量保存**: LLM识别一批就更新一次，避免中断导致数据丢失

### 9.2 错误处理

- ✅ 所有网络请求添加 try-except
- ✅ 记录详细错误日志（使用 `logger.error`）
- ✅ 失败时返回 `FetchResult(success=False)` 而非崩溃
- ✅ 更新 `sync_stats` 记录失败来源
- ✅ 单个数据源失败不影响其他数据源

### 9.3 性能优化

- ✅ 设置合理的 `cache_ttl`（API结果5分钟，翻译24小时）
- ✅ 避免过快请求同一API（添加延迟）
- ✅ 限制单次获取数量（`max_results`）
- ✅ 使用 `httpx` 进行HTTP请求（支持异步）

### 9.4 数据存储规范

- ✅ **RSS/HackerNews/arXiv**: 保存到 `output/daily/YYYY-MM-DD/`，按日期组织
- ✅ **GitHub**: 保存到 `output/github/github_projects.json`，全量持久化存储
- ✅ **文件命名**: `source_YYYYMMDD_HHMMSS.json`（带时间戳）
- ✅ **数据格式**: 使用 `FetchResult` 或 `ArticleItem` 统一格式

---

## 10. 快速命令

```bash
# 启动服务（前台运行，带日志）
./start.sh

# 立即执行一次所有任务（不启动定时调度）
python3 src/msgskill/multi_scheduler.py --once

# 查看今日输出
ls -lh output/daily/$(date +%Y-%m-%d)/

# 查看GitHub数据库
cat output/github/github_projects.json | jq 'keys | length'  # 项目总数

# 清理日志（7天前）
./scripts/cleanup_logs.sh

# Notion手动同步
python3 scripts/sync_to_notion.py --date $(date +%Y-%m-%d)

# 查看实时日志
tail -f logs/scheduler.log
```

## 11. Notion 同步开发规范

### 11.1 自动同步

在 `multi_scheduler.py` 的同步方法中添加：

```python
# 检查是否启用自动同步
config_manager = get_config()
notion_cfg = config_manager.get_notion_config() or {}
auto_sync_cfg = notion_cfg.get("auto_sync", {})
if bool(auto_sync_cfg.get("数据源名", False)):
    self._sync_数据源_items_to_notion(result.items)
```

### 11.2 手动同步

预览页提供单条同步按钮，通过 `/api/notion/sync` API实现。

### 11.3 数据转换

确保 `ArticleItem` 字段符合 Notion 数据库字段要求：
- `title` → Title (title)
- `source_url` → Source URL (url)
- `summary` → Summary (rich_text)
- `published_date` → Published Date (date)
- `ai_score` → AI Score (number)

---

**最后更新**: 2026-02-10
**版本**: 3.3.0