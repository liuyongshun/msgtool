"""
RSS订阅聚合工具 (RSS Reader)

功能: 从多个RSS订阅源聚合AI相关文章
数据源: 7个RSS订阅源（可自定义）
配置文件: config/sources.json -> sources.rss.*

工具函数:
    - fetch_rss_feeds(): 主入口函数，并行抓取多个RSS源
    - _fetch_single_feed(): 单个RSS源抓取实现
    - get_feed_info(): 获取RSS源元信息

映射关系:
    默认使用 config.rss.* 中的所有启用源
    支持通过 feed_urls 参数自定义RSS源列表
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor
import html
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from ..utils.cache import get_cache
from ..utils.parser import clean_text
from ..utils.logger import logger
from ..utils.ai_filter import classify_titles_batch
from ..utils.translator import translate_article_item
from ..config import get_config


# Default AI-related RSS feeds
DEFAULT_AI_FEEDS = {
    "MIT Technology Review AI": "https://www.technologyreview.com/feed/",
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "The Batch (DeepLearning.AI)": "https://www.deeplearning.ai/the-batch/feed/",
    "AI News (Sebastian Raschka)": "https://magazine.sebastianraschka.com/feed",
}


async def fetch_rss_feeds(
    feed_urls: Optional[list[str]] = None,
    limit: int = 10
) -> dict[str, Any]:
    """
    Fetch and aggregate news from RSS feeds.
    
    Args:
        feed_urls: List of RSS feed URLs. If empty, uses default AI feeds.
        limit: Maximum number of items per feed
        
    Returns:
        Dictionary with aggregated feed items
    """
    # Use default feeds if none provided
    if not feed_urls:
        feeds_to_fetch = DEFAULT_AI_FEEDS
    else:
        # Create a dict with URL as both key and value for custom feeds
        feeds_to_fetch = {url: url for url in feed_urls}
    
    # 获取配置，检查每个源的AI筛选设置
    config = get_config()
    rss_sources = config.get_rss_sources(enabled_only=False)
    
    # 构建URL到配置的映射
    url_to_config = {}
    for source_key, source_config in rss_sources.items():
        if source_config.url:
            url_to_config[source_config.url] = source_config
    
    cache = get_cache()
    
    # Fetch feeds in parallel
    tasks = []
    feed_names = []
    
    for name, url in feeds_to_fetch.items():
        cache_key = f"rss_{url}_{limit}"
        cached = cache.get(cache_key)
        
        # 获取该源的AI筛选配置
        source_config = url_to_config.get(url)
        ai_filter_enabled = source_config.ai_filter_enabled if source_config else True  # 默认启用
        
        if cached:
            # Use cached result
            tasks.append(asyncio.coroutine(lambda c=cached: c)())
        else:
            # 获取翻译配置
            translation_enabled = source_config.translation_enabled if source_config else True  # 默认启用
            tasks.append(_fetch_single_feed(url, limit, ai_filter_enabled, translation_enabled))
        
        feed_names.append(name)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Organize results
    feeds_result = {}
    total_items = 0
    errors = []
    
    for name, result in zip(feed_names, results):
        url = feeds_to_fetch[name]
        
        if isinstance(result, Exception):
            error_msg = str(result)
            feeds_result[name] = {
                "url": url,
                "error": error_msg,
                "items": []
            }
            errors.append(f"{name}: {error_msg}")
            logger.source_error(name, error_msg)
        else:
            # Cache successful results
            cache_key = f"rss_{url}_{limit}"
            cache.set(cache_key, result, ttl=600)  # 10 minutes
            
            feeds_result[name] = result
            item_count = len(result.get("items", []))
            total_items += item_count
            logger.source_success(name, item_count)
    
    return {
        "source": "RSS Feeds",
        "feeds_count": len(feeds_to_fetch),
        "total_items": total_items,
        "errors_count": len(errors),
        "fetched_at": datetime.now().isoformat(),
        "feeds": feeds_result,
        "errors": errors if errors else None
    }


async def _fetch_single_feed(url: str, limit: int, ai_filter_enabled: bool = True, translation_enabled: bool = True) -> dict[str, Any]:
    """
    Fetch a single RSS feed.
    
    Args:
        url: Feed URL
        limit: Maximum items to return
        ai_filter_enabled: Whether to enable AI filtering
        translation_enabled: Whether to enable translation
        
    Returns:
        Dictionary with feed info and items
    """
    try:
        # 为有反爬机制的网站提供更好的浏览器模拟
        anti_crawler_domains = ['qbitai.com', 'jiqizhixin.com', 'ithome.com']
        needs_advanced_headers = any(domain in url for domain in anti_crawler_domains)
        
        # Fetch feed content
        timeout = httpx.Timeout(60.0, connect=30.0)  # 增加超时时间
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 基础请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            }
            
            # 对于反爬严格的网站，使用更完整的浏览器头
            if needs_advanced_headers:
                headers.update({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Upgrade-Insecure-Requests": "1"
                })
            
            # 第一次请求，处理可能的重定向
            response = await client.get(url, headers=headers, follow_redirects=True)
            
            # 如果遇到403禁止访问，尝试使用更完整的浏览器头重新请求
            if response.status_code == 403 and not needs_advanced_headers:
                logger.warning(f"检测到403禁止访问，尝试使用完整浏览器头重新请求: {url}")
                headers.update({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Upgrade-Insecure-Requests": "1"
                })
                response = await client.get(url, headers=headers, follow_redirects=True)
            
            response.raise_for_status()
            
            # 使用字节内容而非文本，让feedparser自己处理编码
            # 这样可以避免某些编码转换问题
            content_bytes = response.content
            
            # Parse feed in thread pool (feedparser is synchronous)
            # feedparser.parse 可以接受字节、字符串或URL
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                feed = await loop.run_in_executor(
                    executor,
                    feedparser.parse,
                    content_bytes  # 直接使用字节内容
                )
        
        # Check for parsing errors
        # 注意：feedparser即使XML不完美也能解析，只要有条目就继续
        if feed.bozo:
            # 只有在既有错误又没有条目时才报错
            if not feed.entries:
                raise ValueError(f"Failed to parse feed: {feed.bozo_exception}")
            else:
                # 有错误但有条目，记录警告但继续处理
                logger.warning(f"RSS feed has parsing warnings but contains entries: {url}")
                if hasattr(feed, 'bozo_exception'):
                    logger.warning(f"  Warning: {feed.bozo_exception}")
        
        # Extract feed metadata
        feed_info = {
            "url": url,
            "title": feed.feed.get("title", "Unknown"),
            "description": feed.feed.get("description", ""),
            "link": feed.feed.get("link", url),
            "updated": feed.feed.get("updated", None),
        }
        
        # Extract items
        items = []
        for entry in feed.entries[:limit]:
            # Parse published date (保留时区信息)
            published = None
            
            # 优先使用原始字符串（包含时区）
            if hasattr(entry, "published") and entry.published:
                published = entry.published
            elif hasattr(entry, "updated") and entry.updated:
                published = entry.updated
            # 如果没有字符串，使用parsed时间（UTC）
            elif hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    # published_parsed是UTC时间元组，明确标注为UTC
                    utc_time = datetime(*entry.published_parsed[:6])
                    published = utc_time.isoformat() + "Z"
                except (ValueError, TypeError):
                    pass
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                try:
                    utc_time = datetime(*entry.updated_parsed[:6])
                    published = utc_time.isoformat() + "Z"
                except (ValueError, TypeError):
                    pass
            
            # Get summary/content
            summary = ""
            if hasattr(entry, "summary"):
                summary = _clean_html(entry.summary)
            elif hasattr(entry, "content") and entry.content:
                summary = _clean_html(entry.content[0].get("value", ""))
            
            # Truncate summary
            summary = clean_text(summary, max_length=500)
            
            items.append({
                "title": entry.get("title", "No title"),
                "link": entry.get("link", ""),
                "summary": summary,
                "published": published,
                "author": entry.get("author", None),
                "tags": [tag.term for tag in entry.get("tags", [])][:5],  # Limit tags
            })
        
        # 在进行任何 LLM 请求前，先按发布时间过滤，只保留最近 N 天内的文章
        if items:
            cfg = get_config()
            llm_cfg = cfg.get_llm_config()
            recent_days = max(1, int(getattr(llm_cfg, "recent_days", 7) or 7))
            cutoff_dt = datetime.utcnow() - timedelta(days=recent_days)

            filtered_by_time: list[dict[str, Any]] = []
            skipped_by_time = 0

            for item in items:
                pub_str = item.get("published")
                if not pub_str:
                    # 没有时间信息的先保留，避免误删
                    filtered_by_time.append(item)
                    continue

                pub_dt: datetime | None = None
                # 尝试多种解析方式
                try:
                    # RSS 常见为 RFC2822，如 "Tue, 10 Feb 2026 08:00:00 GMT"
                    pub_dt = parsedate_to_datetime(pub_str)
                except Exception:
                    try:
                        # 回退到 ISO8601
                        pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    except Exception:
                        pub_dt = None

                if pub_dt is None:
                    filtered_by_time.append(item)
                    continue

                # 统一到 naive UTC 再比较
                if pub_dt.tzinfo is not None:
                    pub_dt = pub_dt.astimezone(tz=None).replace(tzinfo=None)

                if pub_dt < cutoff_dt:
                    skipped_by_time += 1
                    continue

                filtered_by_time.append(item)

            logger.info(
                f"RSS 时间过滤：最近 {recent_days} 天内 {len(filtered_by_time)} 篇，"
                f"跳过过期 {skipped_by_time} 篇，总抓取 {len(items)} 篇"
            )
            items = filtered_by_time
        
        # AI筛选：如果启用，使用AI判断文章是否与AI/科技相关（已按时间过滤）
        if ai_filter_enabled and items:
            logger.info(f"开始AI筛选 {len(items)} 篇文章（仅最近 {recent_days} 天）...")
            
            # 准备标题列表：[(临时id, title), ...]
            title_batch = []
            item_map = {}
            
            for idx, item in enumerate(items):
                title = item.get("title", "")
                # 使用索引作为临时ID
                temp_id = str(idx)
                title_batch.append((temp_id, title))
                item_map[temp_id] = item
            
            # 调用AI筛选
            classification_results = await classify_titles_batch(title_batch, batch_size=25)
            result_map = {r["id"]: r for r in classification_results}
            
            # 根据AI筛选结果过滤
            filtered_items = []
            for temp_id, _ in title_batch:
                if temp_id not in result_map:
                    continue
                
                classification = result_map[temp_id]
                
                # 只保留AI判断为相关的文章
                if not classification["keep"]:
                    continue
                
                item = item_map[temp_id]
                # 添加AI评分
                item["ai_score"] = classification["score"]
                filtered_items.append(item)
            
            logger.info(f"AI筛选完成: {len(items)} -> {len(filtered_items)} 篇文章")
            items = filtered_items
        
        # 翻译：对筛选后的文章进行翻译（标题和摘要，已按时间过滤）
        if items and translation_enabled:
            logger.info(f"开始翻译 {len(items)} 篇文章（仅最近 {recent_days} 天）...")
            translation_tasks = []
            for item in items:
                title = item.get("title", "")
                summary = item.get("summary", "")
                translation_tasks.append(translate_article_item(title, summary))
            
            # 并发翻译所有文章
            translation_results = await asyncio.gather(*translation_tasks, return_exceptions=True)
            
            # 更新文章标题和摘要
            for item, result in zip(items, translation_results):
                if isinstance(result, Exception):
                    # 翻译失败，保持原文
                    continue
                
                translated_title, translated_summary = result
                item["title"] = translated_title
                item["summary"] = translated_summary
            
            logger.info(f"翻译完成: {len(items)} 篇文章")
        else:
            logger.info(f"翻译已禁用或不需要翻译")
        
        return {
            **feed_info,
            "items_count": len(items),
            "items": items
        }
        
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code} error fetching feed: {e.response.url}"
        if e.response.status_code == 403:
            error_msg += " (可能被拒绝访问，需要检查网络或代理设置)"
        elif e.response.status_code == 404:
            error_msg += " (RSS地址不存在)"
        elif e.response.status_code >= 500:
            error_msg += " (服务器错误)"
        raise RuntimeError(error_msg)
    except httpx.TimeoutException as e:
        raise RuntimeError(f"请求超时: {str(e)}")
    except httpx.ConnectError as e:
        raise RuntimeError(f"连接失败: {str(e)} (可能无法访问该地址，需要检查网络或使用代理)")
    except httpx.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching feed: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error processing feed: {type(e).__name__}: {str(e)}")


def _clean_html(text: str) -> str:
    """
    Remove HTML tags and decode entities from text.
    
    Args:
        text: HTML text
        
    Returns:
        Plain text
    """
    if not text:
        return ""
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Simple HTML tag removal (basic approach)
    import re
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text


async def get_feed_info(url: str) -> dict[str, Any]:
    """
    Get metadata about an RSS feed without fetching all items.
    
    Args:
        url: Feed URL
        
    Returns:
        Feed metadata
    """
    try:
        result = await _fetch_single_feed(url, limit=1)
        return {
            "url": result.get("url"),
            "title": result.get("title"),
            "description": result.get("description"),
            "link": result.get("link"),
            "updated": result.get("updated"),
            "available": True
        }
    except Exception as e:
        return {
            "url": url,
            "available": False,
            "error": str(e)
        }
