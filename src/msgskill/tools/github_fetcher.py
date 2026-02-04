"""
GitHub项目获取工具 (GitHub Fetcher)

功能: 从GitHub获取AI相关热门项目
数据源: GitHub API (Trending)
配置文件: config/sources.json -> sources.github.*

工具函数:
    - fetch_github_trending(): 获取GitHub趋势项目

映射关系:
    source="trending_daily" -> fetch_github_trending() -> config.github.trending_daily
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from ..utils.cache import get_cache
from ..utils.logger import logger
from ..utils.ai_filter import classify_titles_batch
from ..models import ArticleItem, FetchResult, truncate_summary, classify_article_tag
from ..utils.translator import translate_article_item
from ..utils.parser import clean_text
from ..config import get_config
from ..output import get_output_manager


async def fetch_github_trending(
    language: Optional[str] = None,
    since: str = "daily",
    limit: int = 20
) -> FetchResult:
    """
    获取GitHub趋势项目（AI相关）
    
    支持多维度抓取：
    - pushed: 最近推送的项目（最近7天有更新）
    - created: 最近创建的项目（最近7天创建）
    - stars: 高热度项目（star数>100）
    
    支持语言过滤：Python, JavaScript, TypeScript, Rust
    
    使用AI模型批量判断项目是否与AI相关。
    
    Args:
        language: 编程语言过滤（可选，支持：python, javascript, typescript, rust）
        since: 时间范围（daily, weekly, monthly）- 当前未使用
        limit: 最大返回数量
        
    Returns:
        FetchResult: 标准化的抓取结果
    """
    cache = get_cache()
    cache_key = f"github_trending_{language}_{since}_{limit}"
    
    cached = cache.get(cache_key)
    if cached:
        if isinstance(cached, dict):
            return FetchResult(**cached)
        return cached
    
    config = get_config()
    github_config = config._config.get("sources", {}).get("github", {}).get("trending_daily", {})
    
    # 获取配置的语言列表（默认四种）
    supported_languages = github_config.get("languages", ["python", "javascript", "typescript", "rust"])
    trending_types = github_config.get("trending_types", ["pushed", "created", "stars"])
    ai_filter_enabled = github_config.get("ai_filter_enabled", True)
    
    # 获取 star 限制配置
    star_limits = github_config.get("star_limits", {
        "pushed": 500,
        "created": 100,
        "stars": 500
    })
    
    # 获取 topics 配置（用于扩展查询范围）
    topics = github_config.get("topics", ["ai"])
    
    # 如果指定了语言，使用指定语言；否则使用配置的语言列表
    if language:
        languages_to_fetch = [language.lower()]
    else:
        languages_to_fetch = supported_languages
    
    try:
        # 减少超时时间，提高响应速度
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 修复：使用正确的 Accept 头以获取 topics
            headers = {
                "Accept": "application/vnd.github.mercy-preview+json",
                "User-Agent": "MsgSkill/1.0"
            }
            
            all_repos = []  # 存储所有抓取到的仓库数据
            
            # 第一步：多维度抓取（类似 Hacker News 的三类）
            # 使用所有配置的语言进行查询
            languages_to_query = languages_to_fetch
            total_queries = len(trending_types) * len(languages_to_query)
            query_count = 0
            
            for trend_type in trending_types:
                # 为每种语言分别查询（限制为前2种语言）
                for lang in languages_to_query:
                    try:
                        query_parts = []
                        
                        # 语言过滤
                        query_parts.append(f"language:{lang}")
                        
                        # AI关键词：使用配置的 topics，优先使用 "ai" 作为主要关键词
                        # GitHub API 会自动匹配相关词，使用 "ai" 可以覆盖大部分相关项目
                        query_parts.append("ai")
                        
                        # 根据类型构建不同的查询
                        if trend_type == "pushed":
                            # 最近7天有推送的项目（保持原逻辑）
                            pushed_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                            query_parts.append(f"pushed:>={pushed_date}")
                            query_parts.append(f"stars:>{star_limits.get('pushed', 500)}")  # 从配置读取star限制
                            sort_by = "updated"
                        elif trend_type == "created":
                            # 最近180天（约半年）创建的项目
                            created_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
                            query_parts.append(f"created:>={created_date}")
                            query_parts.append(f"stars:>{star_limits.get('created', 100)}")  # 从配置读取star限制
                            sort_by = "stars"
                        else:  # stars
                            # 高热度项目（最近半年创建或推送）
                            date_limit = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
                            query_parts.append(f"created:>={date_limit}")
                            query_parts.append(f"stars:>{star_limits.get('stars', 500)}")  # 从配置读取star限制
                            sort_by = "stars"
                        
                        # GitHub API 查询使用空格分隔
                        query = " ".join(query_parts)
                        
                        url = "https://api.github.com/search/repositories"
                        params = {
                            "q": query,
                            "sort": sort_by,
                            "order": "desc",
                            "per_page": min(100, limit * 3)  # 多抓取一些，后续AI筛选
                        }
                        
                        query_count += 1
                        logger.info(f"发送查询 {query_count}/{total_queries}: {trend_type}/{lang}")
                        logger.info(f"查询字符串: {query}")
                        
                        response = await client.get(url, headers=headers, params=params)
                        
                        # 检查 rate limit
                        if response.status_code == 403:
                            rate_limit_remaining = response.headers.get("X-RateLimit-Remaining", "0")
                            rate_limit_reset = response.headers.get("X-RateLimit-Reset", "0")
                            error_msg = (
                                f"GitHub API rate limit exceeded. "
                                f"Remaining: {rate_limit_remaining}, "
                                f"Reset at: {datetime.fromtimestamp(int(rate_limit_reset)).isoformat() if rate_limit_reset != '0' else 'N/A'}"
                            )
                            logger.warning(f"{trend_type}/{lang}: {error_msg}")
                            # 如果还有已抓取的数据，继续处理；否则跳过这个语言
                            if all_repos:
                                logger.warning("已部分抓取数据，继续处理其他语言...")
                                break  # 跳出语言循环，继续下一个trend_type
                            else:
                                continue  # 跳过这个语言，继续下一个
                        
                        response.raise_for_status()
                        data = response.json()
                        
                        total_count = data.get("total_count", 0)
                        items_count = len(data.get("items", []))
                        logger.info(f"查询结果: 总计 {total_count} 个，返回 {items_count} 个")
                        
                        # 为每个仓库添加元数据
                        for repo in data.get("items", []):
                            repo["_trend_type"] = trend_type
                            # 从仓库的language字段获取语言
                            repo["_language"] = repo.get("language", "").lower() or lang
                            all_repos.append(repo)
                        
                        # 增加延迟，避免触发 rate limit（每个请求后延迟）
                        await asyncio.sleep(1.0)  # 减少到1秒延迟，提高速度
                        
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 403:
                            logger.warning(f"抓取 {trend_type}/{lang} 时遇到 rate limit，跳过")
                            # 如果遇到 rate limit，跳出语言循环，继续下一个trend_type
                            break
                        else:
                            logger.warning(f"抓取 {trend_type}/{lang} 失败: {str(e)}")
                            continue  # 继续下一个语言
                    except Exception as e:
                        logger.warning(f"抓取 {trend_type}/{lang} 失败: {str(e)}")
                        continue  # 继续下一个语言
            
            if not all_repos:
                return FetchResult(
                    success=False,
                    source_name="GitHub Trending",
                    source_type="github",
                    total_count=0,
                    fetched_at=datetime.now().isoformat(),
                    items=[],
                    error="无法获取任何仓库数据"
                )
            
            # 去重（同一个仓库可能出现在多个查询结果中）
            seen_ids = set()
            unique_repos = []
            for repo in all_repos:
                repo_id = repo.get("id")
                if repo_id not in seen_ids:
                    seen_ids.add(repo_id)
                    unique_repos.append(repo)
            
            logger.info(f"抓取到 {len(unique_repos)} 个唯一仓库")
            
            # 【优化】第二步：利用白名单缓存，减少AI筛选
            if ai_filter_enabled:
                # 分离：白名单项目 vs 新项目
                whitelisted_repos = []
                new_repos = []
                
                for repo in unique_repos:
                    repo_id = str(repo.get("id"))
                    whitelist_key = f"github_whitelist_{repo_id}"
                    cached_classification = cache.get(whitelist_key)
                    
                    if cached_classification:
                        # 白名单中的项目，直接保留并恢复AI评分
                        repo["_ai_score"] = cached_classification.get("ai_score", 0.8)
                        whitelisted_repos.append(repo)
                    else:
                        # 新项目，需要AI筛选
                        new_repos.append(repo)
                
                logger.info(
                    f"白名单命中: {len(whitelisted_repos)} 个 | "
                    f"需要AI筛选: {len(new_repos)} 个"
                )
                
                filtered_repos = list(whitelisted_repos)  # 先加入白名单项目
            else:
                # 不使用AI筛选时，所有项目都视为新项目
                new_repos = unique_repos
                filtered_repos = []
            
            # 第三步：对新项目进行AI筛选
            if ai_filter_enabled and new_repos:
                logger.info(f"开始AI筛选 {len(new_repos)} 个新项目...")
                # 准备标题列表：[(临时id, title), ...]
                title_batch = []
                repo_map = {}
                
                for repo in new_repos:
                    repo_name = repo.get("name", "")
                    description = repo.get("description", "") or ""
                    # 构建标题：项目名 + 描述前50字符
                    title = f"{repo.get('full_name', '')}: {description[:50]}"
                    
                    temp_id = str(repo.get("id"))
                    title_batch.append((temp_id, title))
                    repo_map[temp_id] = repo
                
                # 调用AI筛选：使用较小的批次大小，避免JSON截断
                classification_results = await classify_titles_batch(title_batch, batch_size=25)
                result_map = {r["id"]: r for r in classification_results}
                
                # 根据AI筛选结果过滤，并更新白名单
                for temp_id, _ in title_batch:
                    if temp_id not in result_map:
                        continue
                    
                    classification = result_map[temp_id]
                    if not classification["keep"]:
                        continue
                    
                    repo = repo_map[temp_id]
                    ai_score = classification["score"]
                    repo["_ai_score"] = ai_score
                    filtered_repos.append(repo)
                    
                    # 【关键优化】将通过筛选的项目加入白名单（缓存30天）
                    whitelist_key = f"github_whitelist_{temp_id}"
                    cache.set(whitelist_key, {
                        "repo_id": temp_id,
                        "full_name": repo.get("full_name", ""),
                        "ai_score": ai_score,
                        "reason": classification.get("reason", ""),
                        "cached_at": datetime.now().isoformat()
                    }, ttl=30*24*3600)  # 30天
                
                logger.info(
                    f"AI筛选完成: {len(filtered_repos)} 个仓库 "
                    f"(白名单 {len(whitelisted_repos)} + 新通过 {len(filtered_repos) - len(whitelisted_repos)})"
                )
            else:
                # 不使用AI筛选，使用关键词匹配（向后兼容）
                filtered_repos = []
                ai_keywords = [
                    "ai", "artificial intelligence", "machine learning", "ml",
                    "llm", "gpt", "claude", "transformer", "neural", "deep learning"
                ]
                
                for repo in unique_repos:
                    repo_name = repo.get("name", "").lower()
                    description = repo.get("description", "").lower()
                    topics = [t.lower() for t in repo.get("topics", [])]
                    
                    is_ai_related = any(
                        kw in repo_name or kw in description or any(kw in t for t in topics)
                        for kw in ai_keywords
                    )
                    
                    if is_ai_related:
                        filtered_repos.append(repo)
            
            # 【关键改进】第三步：分批翻译+增量输出
            # 每翻译一批就立即保存，避免中途异常导致全部丢失
            output_manager = get_output_manager()
            
            BATCH_SIZE = 20  # 每批处理20个项目
            total_repos = len(filtered_repos)
            total_batches = (total_repos + BATCH_SIZE - 1) // BATCH_SIZE
            
            all_items = []
            output_file = None
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min((batch_idx + 1) * BATCH_SIZE, total_repos)
                batch_repos = filtered_repos[start_idx:end_idx]
                
                logger.info(f"处理批次 {batch_idx + 1}/{total_batches} ({len(batch_repos)} 个项目)...")
                
                batch_items = []
                for repo in batch_repos:
                    # 清理摘要：去除HTML标签和URL
                    raw_description = repo.get("description", "") or f"GitHub项目: {repo.get('name', '')}"
                    cleaned_summary = clean_text(raw_description, max_length=300)
                    cleaned_summary = re.sub(r'https?://\S+', '', cleaned_summary).strip()
                    summary = truncate_summary(cleaned_summary, 300)
                    
                    title = f"{repo.get('full_name', '')}: {repo.get('name', '')}"
                    
                    # 翻译标题和摘要
                    try:
                        translated_title, translated_summary = await translate_article_item(title, summary)
                    except Exception:
                        translated_title = title
                        translated_summary = truncate_summary(summary, 300)
                    
                    topics = repo.get("topics", [])[:5]
                    
                    # 创建 ArticleItem
                    article = ArticleItem(
                        title=translated_title,
                        summary=translated_summary,
                        source_url=repo.get("html_url", ""),
                        published_date=repo.get("created_at", "").replace("Z", "+00:00") if repo.get("created_at") else None,
                        source_type="github",
                        article_tag=classify_article_tag(title=title, summary=summary, source_type="github"),
                        author=repo.get("owner", {}).get("login"),
                        score=repo.get("stargazers_count", 0),
                        tags=topics,
                        story_type=repo.get("_trend_type"),
                        ai_score=repo.get("_ai_score")
                    )
                    batch_items.append(article)
                
                # 【增量输出】立即保存这一批
                try:
                    output_file = output_manager.append_items_batch(
                        source_type="github",
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
                
                all_items.extend(batch_items)
            
            # 按AI评分和star数综合排序
            all_items.sort(
                key=lambda x: (x.ai_score or 0.0, x.score or 0),
                reverse=True
            )
            
            items = all_items
            
            result = FetchResult(
                success=True,
                source_name="GitHub Trending",
                source_type="github",
                total_count=len(items),
                fetched_at=datetime.now().isoformat(),
                items=items,
                error=None
            )
            
            cache.set(cache_key, result.model_dump(), ttl=github_config.get("cache_ttl", 3600))
            logger.source_success("GitHub Trending", f"{len(items)}/{len(unique_repos)} (AI筛选后)")
            return result
            
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {str(e)}"
        logger.source_error("GitHub Trending", error_msg)
        return FetchResult(
            success=False,
            source_name="GitHub Trending",
            source_type="github",
            total_count=0,
            fetched_at=datetime.now().isoformat(),
            items=[],
            error=error_msg
        )
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.source_error("GitHub Trending", error_msg)
        return FetchResult(
            success=False,
            source_name="GitHub Trending",
            source_type="github",
            total_count=0,
            fetched_at=datetime.now().isoformat(),
            items=[],
            error=error_msg
        )
