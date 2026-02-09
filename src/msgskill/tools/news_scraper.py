"""
新闻抓取工具 (News Scraper)

功能: 从科技新闻网站抓取AI相关新闻
数据源: Hacker News (API)
配置文件: config/sources.json -> sources.news.*

工具函数:
    - fetch_ai_news(): 主入口函数，根据source参数选择数据源
    - _fetch_hackernews(): Hacker News API实现

映射关系:
    source="hackernews" -> _fetch_hackernews() -> config.news.hackernews

注意: Techmeme 和 TechCrunch 已迁移到 RSS 源 (sources.rss.*)
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

import httpx

from ..utils.cache import get_cache
from ..utils.parser import clean_text
from ..utils.translator import translate_article_item, has_chinese
from ..utils.logger import logger
from ..utils.ai_filter import classify_titles_batch
from ..models import ArticleItem, FetchResult, truncate_summary, classify_article_tag
from ..config import get_config
from ..output import get_output_manager

# 支持的新闻源列表（用于MCP服务器）
NEWS_SOURCES = {
    "hackernews": "Hacker News - Tech news community"
}


async def fetch_ai_news(
    source: str = "hackernews",
    limit: int = 10,
    keywords: Optional[list[str]] = None
) -> FetchResult:
    """
    Fetch AI-related news from specified source.
    
    Args:
        source: News source (hackernews)
        limit: Maximum number of news items
        keywords: Optional additional keywords to filter by
        
    Returns:
        FetchResult with standardized article items
    """
    # 从配置加载数据源
    config = get_config()
    source_config = config.get_news_source(source)
    
    if not source_config:
        available_sources = list(config.get_news_sources().keys())
        error_msg = f"Unknown source: {source}. Available: {', '.join(available_sources)}"
        logger.source_error(source, error_msg)
        return FetchResult(
            success=False,
            source_name=source,
            source_type=source,
            total_count=0,
            fetched_at=datetime.now().isoformat(),
            items=[],
            error=error_msg
        )
    
    if not source_config.enabled:
        error_msg = f"Source '{source}' is disabled in configuration"
        logger.source_skipped(source_config.name, "配置中已禁用")
        return FetchResult(
            success=False,
            source_name=source_config.name,
            source_type=source,
            total_count=0,
            fetched_at=datetime.now().isoformat(),
            items=[],
            error=error_msg
        )
    
    # 根据源类型调用相应的函数
    if source == "hackernews":
        return await _fetch_hackernews(source_config, limit, keywords)
    else:
        return FetchResult(
            success=False,
            source_name=source_config.name,
            source_type=source,
            total_count=0,
            fetched_at=datetime.now().isoformat(),
            items=[],
            error=f"Source '{source}' not implemented. Note: Techmeme and TechCrunch have been moved to RSS sources."
        )


async def _fetch_hackernews(
    source_config: Any,  # NewsSourceConfig
    limit: int,
    keywords: Optional[list[str]] = None
) -> FetchResult:
    """
    Fetch AI-related stories from Hacker News API.
    
    Uses the official Firebase API:
    - /v0/topstories.json - Top stories (热门)
    - /v0/newstories.json - New stories (最新)
    - /v0/beststories.json - Best stories (高分)
    - /v0/item/{id}.json - Story details
    
    使用AI模型批量判断标题是否与AI相关，替代关键词过滤。
    """
    cache = get_cache()
    cache_key = f"hn_ai_news_{limit}"
    
    cached = cache.get(cache_key)
    if cached:
        # 确保返回 FetchResult 对象
        if isinstance(cached, dict):
            return FetchResult(**cached)
        return cached
    
    # 从配置获取 API URL
    base_url = source_config.api_base_url
    
    # 定义三类故事类型
    story_types = [
        ("topstories", "top"),
        ("newstories", "new"),
        ("beststories", "best")
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 第一步：抓取三类列表的ID
            all_story_data = []  # [(story_id, story_type), ...]
            
            for endpoint, story_type in story_types:
                try:
                    response = await client.get(f"{base_url}/{endpoint}.json")
                    response.raise_for_status()
                    story_ids = response.json()[:100]  # 每类取前100条
                    
                    for sid in story_ids:
                        all_story_data.append((sid, story_type))
                except Exception as e:
                    logger.warning(f"获取 {endpoint} 失败: {str(e)}")
                    continue
            
            if not all_story_data:
                return FetchResult(
                    success=False,
                    source_name="Hacker News",
                    source_type="hackernews",
                    total_count=0,
                    fetched_at=datetime.now().isoformat(),
                    items=[],
                    error="无法获取任何故事列表"
                )
            
            # 去重（同一个ID可能出现在多个列表中，保留第一个类型）
            seen_ids = set()
            unique_story_data = []
            for sid, stype in all_story_data:
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    unique_story_data.append((sid, stype))
            
            # 第二步：批量获取故事详情
            all_stories = []  # 存储所有故事数据
            
            for i in range(0, len(unique_story_data), 20):
                batch_data = unique_story_data[i:i+20]
                tasks = [
                    client.get(f"{base_url}/item/{sid}.json")
                    for sid, _ in batch_data
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                for idx, resp in enumerate(responses):
                    if isinstance(resp, Exception):
                        continue
                    if resp.status_code != 200:
                        continue
                    
                    story = resp.json()
                    if not story or story.get("type") != "story":
                        continue
                    
                    sid, stype = batch_data[idx]
                    all_stories.append({
                        "id": sid,
                        "story_type": stype,
                        "data": story
                    })
            
            if not all_stories:
                return FetchResult(
                    success=False,
                    source_name="Hacker News",
                    source_type="hackernews",
                    total_count=0,
                    fetched_at=datetime.now().isoformat(),
                    items=[],
                    error="无法获取故事详情"
                )
            
            # 第三步：使用AI批量筛选标题
            # 准备标题列表：[(临时id, title), ...]
            title_batch = []
            story_map = {}  # {临时id: story_info}
            
            for idx, story_info in enumerate(all_stories):
                story = story_info["data"]
                title = story.get("title", "").strip()
                if not title:
                    continue
                
                temp_id = str(story_info["id"])
                title_batch.append((temp_id, title))
                story_map[temp_id] = story_info
            
            # 调用AI筛选
            logger.info(f"开始AI筛选 {len(title_batch)} 个标题...")
            classification_results = await classify_titles_batch(title_batch, batch_size=25)
            
            # 创建结果映射 {id: classification_result}
            result_map = {r["id"]: r for r in classification_results}
            
            # 【关键改进】第四步：分批翻译+增量输出
            # 先收集所有需要处理的stories
            filtered_story_data = []
            for temp_id, title in title_batch:
                if temp_id not in result_map:
                    continue
                
                classification = result_map[temp_id]
                if not classification["keep"]:
                    continue
                
                story_info = story_map[temp_id]
                filtered_story_data.append((temp_id, story_info, classification))
            
            # 分批处理并增量输出
            output_manager = get_output_manager()
            BATCH_SIZE = 20  # 每批处理20条新闻
            total_stories = len(filtered_story_data)
            total_batches = (total_stories + BATCH_SIZE - 1) // BATCH_SIZE
            
            ai_stories = []
            output_file = None
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min((batch_idx + 1) * BATCH_SIZE, total_stories)
                batch_data = filtered_story_data[start_idx:end_idx]
                
                logger.info(f"处理批次 {batch_idx + 1}/{total_batches} ({len(batch_data)} 条新闻)...")
                
                batch_items = []
                for temp_id, story_info, classification in batch_data:
                    story = story_info["data"]
                    story_type = story_info["story_type"]
                    
                    original_title = story.get("title", "")
                    original_summary = original_title
                    
                    # 翻译标题和摘要
                    if source_config.translation_enabled:
                        translated_title, translated_summary = await translate_article_item(
                            original_title,
                            original_summary
                        )
                    else:
                        translated_title = original_title
                        translated_summary = original_summary
                    
                    # 创建标准化的 ArticleItem
                    article = ArticleItem(
                        title=translated_title,
                        summary=translated_summary,
                        source_url=story.get("url") or f"https://news.ycombinator.com/item?id={story.get('id')}",
                        published_date=datetime.fromtimestamp(
                            story.get("time", 0)
                        ).isoformat() if story.get("time") else None,
                        source_type="hackernews",
                        article_tag=classify_article_tag(
                            title=original_title,
                            summary=original_summary,
                            source_type="hackernews"
                        ),
                        author=story.get("by"),
                        score=story.get("score", 0),
                        comments_count=story.get("descendants", 0),
                        tags=[],
                        story_type=story_type,
                        ai_score=classification["score"]
                    )
                    batch_items.append(article)
                
                # 【增量输出】立即保存这一批
                try:
                    output_file = output_manager.append_items_batch(
                        source_type="hackernews",
                        items=batch_items,
                        batch_info={
                            "batch": batch_idx + 1,
                            "total_batches": total_batches,
                            "batch_size": len(batch_items)
                        }
                    )
                    logger.info(f"✅ 批次 {batch_idx + 1}/{total_batches} 已保存到: {output_file.name}")
                except Exception as save_error:
                    logger.error(f"⚠️ 批次 {batch_idx + 1} 保存失败: {save_error}，继续处理...")
                
                ai_stories.extend(batch_items)
            
            # 按AI评分和原始评分综合排序
            ai_stories.sort(
                key=lambda x: (x.ai_score or 0.0, x.score or 0),
                reverse=True
            )
            
            # 构建标准化结果
            result = FetchResult(
                success=True,
                source_name="Hacker News",
                source_type="hackernews",
                total_count=len(ai_stories),
                fetched_at=datetime.now().isoformat(),
                items=ai_stories,
                error=None
            )
            
            # 缓存时转换为字典
            cache.set(cache_key, result.model_dump(), ttl=300)  # Cache for 5 minutes
            logger.source_success("Hacker News", f"{len(ai_stories)}/{len(title_batch)} (AI筛选后)")
            return result
            
        except httpx.HTTPError as e:
            error_msg = f"HTTP error: {str(e)}"
            logger.source_error("Hacker News", error_msg)
            return FetchResult(
                success=False,
                source_name="Hacker News",
                source_type="hackernews",
                total_count=0,
                fetched_at=datetime.now().isoformat(),
                items=[],
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.source_error("Hacker News", error_msg)
            return FetchResult(
                success=False,
                source_name="Hacker News",
                source_type="hackernews",
                total_count=0,
                fetched_at=datetime.now().isoformat(),
                items=[],
                error=error_msg
            )
