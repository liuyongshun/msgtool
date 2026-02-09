# AI开发指南 - MsgSkill

本文档为 AI Agent 提供快速理解和扩展 MsgSkill 项目的完整指南。

---

## 1. 项目架构

### 1.1 目录结构

```
msgskill/
├── config/                    # 配置文件
│   └── sources.json          # 数据源配置（核心）
├── src/msgskill/             # 核心代码
│   ├── tools/                # 数据获取工具
│   │   ├── arxiv_fetcher.py      # arXiv论文
│   │   ├── github_fetcher.py     # GitHub项目
│   │   ├── news_scraper.py       # HackerNews
│   │   └── rss_reader.py         # RSS订阅
│   ├── utils/                # 工具模块
│   │   ├── ai_filter.py          # AI筛选
│   │   ├── translator.py         # 翻译
│   │   ├── cache.py              # 缓存
│   │   └── logger.py             # 日志
│   ├── config.py             # 配置管理
│   ├── models.py             # 数据模型
│   ├── output.py             # 输出管理
│   └── multi_scheduler.py    # 调度器
├── output/daily/             # 输出目录（按日期）
└── docs/                     # 文档
```

### 1.2 数据流

```
配置加载 → 数据获取 → AI筛选 → 翻译 → 输出保存
   ↓          ↓         ↓        ↓        ↓
sources.json  tools/  ai_filter  translator  output/
```

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
    title: str                    # 标题
    summary: str                  # 摘要（≤300字）
    source_url: str              # 来源URL
    published_date: str          # 发布日期（ISO 8601）
    source_type: Literal[...]    # 来源类型
    article_tag: Literal[...]    # 分类标签
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
| GitHub数据库 | 持久化 | GitHub项目持久化存储和智能去重 |
- `output/github/all_projects.json`：所有抓取过的GitHub项目
- `output/github/ai_projects.json`：AI筛选的GitHub项目
- `output/github/ai_whitelist.json`：AI项目白名单，30天过期 |

---

## 3. 开发规范

### 3.1 文件组织

```
新增数据源工具：src/msgskill/tools/新工具_fetcher.py
新增工具函数：src/msgskill/utils/新功能.py
输出文件：output/daily/YYYY-MM-DD/source_timestamp.json
```

### 3.2 函数签名规范

**数据获取函数**：

```python
async def fetch_xxx_data(
    limit: int = 10,
    **kwargs
) -> FetchResult:
    """
    获取XXX数据源内容
    
    Args:
        limit: 返回条目数量限制
        **kwargs: 其他参数
    
    Returns:
        FetchResult: 统一的抓取结果格式
    """
```

### 3.3 错误处理

```python
try:
    result = await fetch_data()
    if result.success:
        logger.info(f"✅ 获取成功: {result.total_count}条")
    else:
        logger.error(f"❌ 获取失败: {result.error}")
except Exception as e:
    logger.error(f"❌ 异常: {str(e)}")
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
# 1. 添加同步方法
async def sync_example(self, max_results: int = 10):
    """同步示例数据"""
    logger.info(f"📡 开始同步示例数据 - 最多{max_results}条")
    
    try:
        result = await fetch_example_data(limit=max_results)
        
        if result.success:
            # 保存到文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_manager.get_daily_dir() / f"example_{timestamp}.json"
            self.output_manager._write_json(output_file, result.model_dump())
            
            logger.info(f"✅ 同步完成: {result.total_count}条")
            self.sync_stats["success_count"] += 1
        else:
            logger.error(f"❌ 同步失败: {result.error}")
            self.sync_stats["failed_sources"].append("example")
            
    except Exception as e:
        logger.error(f"❌ 同步异常: {str(e)}")
        self.sync_stats["failed_sources"].append("example")

# 2. 在 run_all_sources_async 中添加
async def run_all_sources_async(self):
    tasks = []
    
    for source, config in self.sources_config.items():
        if config.get("enabled", False):
            max_results = config.get("max_results", 10)
            
            if source == "example":  # 新增
                tasks.append(self.sync_example(max_results))
            # ... 其他数据源
    
    if tasks:
        await asyncio.gather(*tasks)

# 3. 在 start 方法中添加调度
def start(self):
    for source, config in self.sources_config.items():
        if source == "example":  # 新增
            sync_func = lambda mr=max_results: self.sync_example(mr)
            # 设置定时任务...
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

- ✅ 使用缓存避免重复API调用
- ✅ 批量请求AI筛选（一次处理多个标题）
- ✅ 选择性翻译（只翻译高质量内容）
- ✅ 白名单机制（已筛选项目跳过AI判断）

### 9.2 错误处理

- ✅ 所有网络请求添加 try-except
- ✅ 记录详细错误日志
- ✅ 失败时返回空结果而非崩溃
- ✅ 更新 sync_stats 记录失败来源

### 9.3 性能优化

- ✅ 使用 asyncio 并发请求
- ✅ 设置合理的 cache_ttl
- ✅ 避免过快请求同一API（添加延迟）
- ✅ 限制单次获取数量（max_results）

---

## 10. 快速命令

```bash
# 启动服务（前台运行，带日志）
./start.sh

# 立即执行一次所有任务
python -m src.msgskill.multi_scheduler --once

# 查看今日输出
ls -lh output/daily/$(date +%Y-%m-%d)/

# 清理日志（7天前）
./scripts/cleanup_logs.sh

# 清理缓存（30天前）
./scripts/cleanup_cache.sh

# 查看实时日志
tail -f logs/scheduler.log
```

---

**最后更新**: 2026-02-03