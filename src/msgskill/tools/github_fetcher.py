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
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Dict, List

import httpx

from ..utils.cache import get_cache
from ..utils.logger import logger
from ..utils.ai_filter import classify_titles_batch
from ..models import ArticleItem, FetchResult, truncate_summary, classify_article_tag
from ..utils.translator import translate_article_item
from ..utils.parser import clean_text
from ..config import get_config
from ..utils.github_db_new import get_github_db


def _load_existing_github_items() -> Dict[str, ArticleItem]:
    """
    从output/github/目录加载已存在的GitHub项目数据
    
    Returns:
        Dict[str, ArticleItem]: 以source_url为key的已存在项目字典
    """
    # 获取output/github目录
    github_output_dir = Path(__file__).parent.parent.parent.parent / "output" / "github"
    github_output_dir.mkdir(parents=True, exist_ok=True)
    
    existing_items: Dict[str, ArticleItem] = {}
    
    # 查找所有JSON文件（可能是github_projects.json或其他格式）
    json_files = list(github_output_dir.glob("*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 处理不同的数据格式
            items = []
            if isinstance(data, dict):
                # 如果是FetchResult格式
                if "items" in data:
                    items = data["items"]
                # 如果是项目数据库格式（github_projects.json）
                else:
                    # 检查格式：可能是ArticleItem格式（有source_url）或项目元数据格式（有html_url和status）
                    for project_data in data.values():
                        if not isinstance(project_data, dict):
                            continue
                        
                        # 判断格式：ArticleItem格式有source_url，项目元数据格式有html_url和status
                        source_url = project_data.get("source_url") or project_data.get("html_url", "")
                        if not source_url:
                            continue
                        
                        # 如果是ArticleItem格式（已有title和summary），直接使用
                        if project_data.get("title") and project_data.get("summary"):
                            try:
                                # 修正可能不合法的 article_tag（保证符合 ArticleItem 的 Literal 限制）
                                valid_tags = {"AI资讯", "AI工具", "AI论文", "技术博客"}
                                tag = project_data.get("article_tag") or "AI工具"
                                if tag not in valid_tags:
                                    project_data["article_tag"] = "AI工具"
                                if project_data.get("summary"):
                                    project_data["summary"] = truncate_summary(project_data["summary"], 300)
                                item = ArticleItem(**project_data)
                                items.append(item)
                            except Exception as e:
                                logger.debug(f"跳过无效ArticleItem数据: {e}")
                                continue
                        # 如果是项目元数据格式（有html_url和status），需要转换为ArticleItem
                        elif project_data.get("html_url") and "status" in project_data:
                            try:
                                item = ArticleItem(
                                    title=project_data.get("title", project_data.get("full_name", "")),
                                    summary=truncate_summary(project_data.get("summary") or project_data.get("description", ""), 300),
                                    source_url=source_url,
                                    published_date=project_data.get("published_date") or (project_data.get("created_at", "").replace("Z", "+00:00") if project_data.get("created_at") else None),
                                    source_type="github",
                                    article_tag=project_data.get("article_tag", "AI工具"),
                                    author=project_data.get("author") or (project_data.get("owner", {}).get("login") if isinstance(project_data.get("owner"), dict) else None),
                                    score=project_data.get("score") or project_data.get("stargazers_count", 0),
                                    comments_count=project_data.get("comments_count"),
                                    tags=project_data.get("tags") or project_data.get("topics", []),
                                    story_type=project_data.get("story_type") or project_data.get("trend_type"),
                                    ai_score=project_data.get("ai_score")
                                )
                                items.append(item)
                            except Exception as e:
                                logger.debug(f"跳过无效项目元数据: {e}")
                                continue
                        # 如果是“简化的项目元数据格式”（只有 html_url / topics / ai_score 等），也需要转换
                        # 该格式常见于历史版本/清理脚本之后：没有 status/title/source_url 字段
                        elif project_data.get("html_url"):
                            try:
                                full_name = project_data.get("full_name", "")
                                name = project_data.get("name", "")
                                title = project_data.get("title") or (f"{full_name}: {name}" if full_name or name else source_url)
                                summary = project_data.get("summary") or project_data.get("description", "") or f"GitHub项目: {name}"
                                ai_score = project_data.get("ai_score", 0.0) or 0.0
                                item = ArticleItem(
                                    title=title,
                                    summary=truncate_summary(clean_text(summary, max_length=300), 300),
                                    source_url=source_url,
                                    published_date=project_data.get("published_date") or (project_data.get("created_at", "").replace("Z", "+00:00") if project_data.get("created_at") else None),
                                    source_type="github",
                                    # 归一化 article_tag，避免非法枚举值导致后续加载失败
                                    article_tag=project_data.get("article_tag", "AI工具") if project_data.get("article_tag") in {"AI资讯", "AI工具", "AI论文", "技术博客"} else "AI工具",
                                    author=project_data.get("author"),
                                    score=project_data.get("score") or project_data.get("stargazers_count", 0),
                                    tags=project_data.get("tags") or project_data.get("topics", []),
                                    story_type=project_data.get("story_type") or project_data.get("trend_type"),
                                    ai_score=ai_score
                                )
                                items.append(item)
                            except Exception as e:
                                logger.debug(f"跳过无效简化项目元数据: {e}")
                                continue
            elif isinstance(data, list):
                items = data
            
            # 将items转换为字典，以source_url为key（兼容dict和ArticleItem）
            for item_data in items:
                try:
                    item: Optional[ArticleItem] = None
                    source_url: str = ""
                    
                    if isinstance(item_data, ArticleItem):
                        # 已经是ArticleItem对象
                        item = item_data
                        source_url = item.source_url
                    elif isinstance(item_data, dict):
                        # 还未转换的dict数据
                        source_url = item_data.get("source_url") or item_data.get("html_url", "")
                        if not source_url:
                            continue
                        if item_data.get("summary"):
                            item_data["summary"] = truncate_summary(item_data["summary"], 300)
                        item = ArticleItem(**item_data)
                    else:
                        # 其他类型直接跳过
                        continue
                    
                    if source_url and source_url not in existing_items:
                        existing_items[source_url] = item
                except Exception as e:
                    logger.debug(f"跳过无效item: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"加载文件 {json_file} 失败: {e}")
            continue
    
    logger.info(f"📂 从output/github/加载了 {len(existing_items)} 个已存在的项目")
    return existing_items


def _save_github_repos_to_file(repos: List[Dict], is_ai_project_map: Optional[Dict[str, bool]] = None) -> Path:
    """
    保存GitHub项目数据到output/github/目录（全量数据）
    
    Args:
        repos: GitHub项目原始数据列表
        is_ai_project_map: 项目URL到是否为AI项目的映射 {url: is_ai}
        
    Returns:
        Path: 保存的文件路径
    """
    github_output_dir = Path(__file__).parent.parent.parent.parent / "output" / "github"
    github_output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = github_output_dir / "github_projects.json"
    
    # 加载已有数据
    existing_data = {}
    if output_file.exists():
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            logger.warning(f"加载已有数据失败: {e}，将创建新文件")
    
    def _normalize_existing_record(value: Dict, source_url: str) -> Dict:
        """
        将历史格式/简化格式/github_db_new格式 统一归一化为可被增量逻辑和预览服务识别的格式。
        核心约束：
        - key 使用 source_url（html_url）
        - 必须包含 title/summary/source_url/published_date/score/tags/ai_score 等字段
        """
        normalized = dict(value) if isinstance(value, dict) else {}
        normalized["source_url"] = normalized.get("source_url") or source_url
        normalized["html_url"] = normalized.get("html_url") or normalized["source_url"]

        full_name = normalized.get("full_name", "")
        name = normalized.get("name", "")
        description = normalized.get("description", "") or normalized.get("summary", "") or ""

        # 核心展示字段
        normalized["title"] = normalized.get("title") or (f"{full_name}: {name}" if full_name or name else normalized["source_url"])
        normalized["summary"] = normalized.get("summary") or description or (f"GitHub项目: {name}" if name else "GitHub项目")
        normalized["source_type"] = normalized.get("source_type") or "github"
        normalized["article_tag"] = normalized.get("article_tag") or "AI工具"

        # 时间字段：published_date 优先，其次 created_at
        created_at = normalized.get("created_at") or ""
        normalized["published_date"] = normalized.get("published_date") or (created_at.replace("Z", "+00:00") if created_at else None)
        normalized["created_at"] = created_at

        # 热度字段
        normalized["stargazers_count"] = normalized.get("stargazers_count") or normalized.get("score") or 0
        normalized["score"] = normalized.get("score") or normalized["stargazers_count"]

        # 标签字段：同时保留 tags（标准化）与 topics（GitHub原始语义）
        topics = normalized.get("topics") or normalized.get("tags") or []
        if not isinstance(topics, list):
            topics = []
        normalized["topics"] = topics[:5]
        normalized["tags"] = (normalized.get("tags") or normalized["topics"])[:5]

        # AI字段：统一用 ai_score + is_ai_project
        ai_score = normalized.get("ai_score", 0.0) or 0.0
        normalized["ai_score"] = ai_score
        if "is_ai_project" not in normalized:
            normalized["is_ai_project"] = bool(ai_score and ai_score > 0)
        normalized["ai_reason"] = normalized.get("ai_reason", "") or normalized.get("_ai_reason", "") or ""

        # 其他常用字段
        normalized["language"] = normalized.get("language", "") or ""
        normalized["updated_at"] = normalized.get("updated_at") or datetime.now().isoformat()

        # 删除冗余字段（历史状态/调度字段）
        for redundant_field in [
            "repo_id", "trend_type", "language_query", "crawled_at",
            "last_screened_at", "last_seen", "status", "whitelisted_until",
            "comments_count", "id", "added_at"
        ]:
            normalized.pop(redundant_field, None)

        return normalized

    # 统一使用source_url作为key
    projects_data: Dict[str, Dict] = {}

    # 先保留并归一化已有数据（自动迁移旧key/旧格式）
    for key, value in existing_data.items():
        if not isinstance(value, dict):
            continue

        source_url = ""
        if isinstance(key, str) and key.startswith("https://github.com/"):
            source_url = key
        else:
            source_url = value.get("source_url") or value.get("html_url", "")

        if not source_url:
            continue

        projects_data[source_url] = _normalize_existing_record(value, source_url)
    
    # 更新或添加新项目（全量保存）
    for repo in repos:
        source_url = repo.get("html_url", "")
        if not source_url:
            continue
        
        # 判断是否为AI项目
        is_ai = False
        ai_score = 0.0
        if is_ai_project_map and source_url in is_ai_project_map:
            is_ai = is_ai_project_map[source_url]
            # 从repo中获取ai_score（如果有）
            ai_score = repo.get("_ai_score", 0.0) if is_ai else 0.0
        elif repo.get("_ai_score", 0.0) > 0:
            is_ai = True
            ai_score = repo.get("_ai_score", 0.0)
        
        # 如果已存在，只更新状态字段，同时确保格式归一化
        if source_url in projects_data:
            existing = _normalize_existing_record(projects_data[source_url], source_url)
            # 更新状态字段
            existing["score"] = repo.get("stargazers_count", existing.get("score", 0))
            if repo.get("topics"):
                existing["topics"] = repo.get("topics", [])[:5]
                existing["tags"] = repo.get("topics", [])[:5]
            if repo.get("_trend_type"):
                existing["story_type"] = repo.get("_trend_type")
            # 更新AI标记
            existing["is_ai_project"] = is_ai
            existing["ai_score"] = ai_score
            if repo.get("_ai_reason"):
                existing["ai_reason"] = repo.get("_ai_reason")
            # 更新元数据
            existing["stargazers_count"] = repo.get("stargazers_count", existing.get("stargazers_count", 0))
            existing["language"] = repo.get("language", existing.get("language", ""))
            existing["updated_at"] = datetime.now().isoformat()
            projects_data[source_url] = existing
        else:
            # 新项目，创建完整记录（只保留必要字段）
            title = f"{repo.get('full_name', '')}: {repo.get('name', '')}"
            description = repo.get("description", "") or f"GitHub项目: {repo.get('name', '')}"
            
            projects_data[source_url] = {
                # 核心显示字段
                "title": title,
                "summary": description,
                "source_url": source_url,
                "published_date": (repo.get("created_at", "").replace("Z", "+00:00") if repo.get("created_at") else None),
                "source_type": "github",
                "article_tag": "AI工具" if is_ai else "工具",
                "author": repo.get("owner", {}).get("login", "") if isinstance(repo.get("owner"), dict) else "",
                "score": repo.get("stargazers_count", 0),
                "tags": repo.get("topics", [])[:5],
                "story_type": repo.get("_trend_type", ""),
                "language": repo.get("language", ""),
                # AI相关字段
                "ai_score": ai_score,
                "is_ai_project": is_ai,
                "ai_reason": repo.get("_ai_reason", ""),
                # 元数据字段（用于构建显示）
                "full_name": repo.get("full_name", ""),
                "name": repo.get("name", ""),
                "description": description,
                "html_url": source_url,
                "stargazers_count": repo.get("stargazers_count", 0),
                "topics": repo.get("topics", [])[:5],
                "created_at": repo.get("created_at", ""),
                # 更新时间
                "updated_at": datetime.now().isoformat()
            }
    
    # 保存到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(projects_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"💾 保存了 {len(projects_data)} 个项目到 {output_file} (AI项目: {sum(1 for p in projects_data.values() if p.get('is_ai_project', False))} 个)")
    return output_file


def _save_github_items_to_file(items: List[ArticleItem], all_repos: Optional[List[Dict]] = None) -> Path:
    """
    保存GitHub项目数据到output/github/目录（兼容旧接口）
    
    Args:
        items: ArticleItem列表
        all_repos: 所有原始项目数据（用于全量保存）
        
    Returns:
        Path: 保存的文件路径
    """
    github_output_dir = Path(__file__).parent.parent.parent.parent / "output" / "github"
    github_output_dir.mkdir(parents=True, exist_ok=True)
    
    # 使用统一的文件名：github_projects.json
    output_file = github_output_dir / "github_projects.json"
    
    # 加载已有数据（如果存在）
    existing_data = {}
    if output_file.exists():
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            logger.warning(f"加载已有数据失败: {e}，将创建新文件")
    
    # 转换为字典格式保存（包含所有ArticleItem字段）
    # 统一使用source_url作为key，确保唯一性
    projects_data = {}
    
    # 先保留已有数据（统一转换为source_url为key）
    for key, value in existing_data.items():
        if not isinstance(value, dict):
            continue
        
        # 获取source_url（可能在不同字段中）
        source_url = value.get("source_url") or value.get("html_url", "")
        
        # 如果key本身就是URL格式，直接使用
        if key.startswith("https://github.com/"):
            source_url = key
        
        # 如果value中有source_url，使用它作为key（统一格式）
        if source_url:
            # 如果数据格式是github_db_new格式（有status字段），转换为ArticleItem格式
            if "status" in value and "title" not in value:
                # 这是github_db_new格式，需要转换
                projects_data[source_url] = {
                    "title": f"{value.get('full_name', '')}: {value.get('name', '')}",
                    "summary": value.get("description", "") or f"GitHub项目: {value.get('name', '')}",
                    "source_url": source_url,
                    "published_date": (value.get("created_at", "").replace("Z", "+00:00") if value.get("created_at") else None) or value.get("published_date"),
                    "source_type": "github",
                    "article_tag": value.get("article_tag", "AI工具"),
                    "author": value.get("owner", {}).get("login", "") if isinstance(value.get("owner"), dict) else value.get("author", ""),
                    "score": value.get("stargazers_count", 0) or value.get("score", 0),
                    "comments_count": value.get("comments_count"),
                    "tags": value.get("topics", []) or value.get("tags", []),
                    "story_type": value.get("trend_type") or value.get("story_type", ""),
                    "ai_score": value.get("ai_score", 0.0),
                    "updated_at": value.get("updated_at", datetime.now().isoformat())
                }
            else:
                # 已经是ArticleItem格式，直接使用
                projects_data[source_url] = value
    
    # 更新或添加新项目
    for item in items:
        source_url = item.source_url
        if not source_url:
            continue
        
        projects_data[source_url] = {
            "title": item.title,
            "summary": item.summary,
            "source_url": item.source_url,
            "published_date": item.published_date,
            "source_type": item.source_type,
            "article_tag": item.article_tag,
            "author": item.author,
            "score": item.score,
            "comments_count": item.comments_count,
            "tags": item.tags,
            "story_type": item.story_type,
            "ai_score": item.ai_score,
            "updated_at": datetime.now().isoformat()
        }
    
    # 保存到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(projects_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"💾 保存了 {len(projects_data)} 个项目到 {output_file}")
    return output_file


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
    translation_enabled = github_config.get("translation_enabled", True)
    
    # 获取 star 限制配置
    star_limits = github_config.get("star_limits", {
        "pushed": 500,
        "created": 300,
        "stars": 500
    })
    
    # 获取 created 时间范围（天数），默认15天
    created_days = github_config.get("created_days", 15)
    
    # 如果指定了语言，使用指定语言；否则使用配置的语言列表
    if language:
        languages_to_fetch = [language.lower()]
    else:
        languages_to_fetch = supported_languages
    
    try:
        logger.info("🔄 开始获取GitHub趋势项目...")
        logger.info(f"使用语言: {languages_to_fetch}")
        logger.info(f"查询类型: {trending_types}")
        
        # 减少超时时间，提高响应速度
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 使用正确的 Accept 头以获取 topics
            headers = {
                "Accept": "application/vnd.github.mercy-preview+json",
                "User-Agent": "MsgSkill/1.0"
            }
            
            all_repos = []  # 存储所有抓取到的仓库数据
            
            # 第一步：多维度抓取（类似 Hacker News 的三类）
            # 使用所有配置的语言进行查询
            total_queries = len(trending_types) * len(languages_to_fetch)
            query_count = 0
            
            for trend_type in trending_types:
                # 为每种语言分别查询
                for lang in languages_to_fetch:
                    try:
                        query_parts = []
                        
                        # 语言过滤
                        query_parts.append(f"language:{lang}")
                        
                        # 不使用关键词过滤，改为通过 language + created_days + stars 控制范围
                        # AI 相关性通过后续 AI 筛选或本地关键词匹配完成
                        
                        # 根据类型构建不同的查询
                        if trend_type == "pushed":
                            # 最近7天有推送的项目
                            pushed_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                            query_parts.append(f"pushed:>={pushed_date}")
                            query_parts.append(f"stars:>{star_limits.get('pushed', 500)}")
                            sort_by = "updated"
                        elif trend_type == "created":
                            # 使用配置的 created_days（默认15天）
                            created_date = (datetime.now() - timedelta(days=created_days)).strftime("%Y-%m-%d")
                            query_parts.append(f"created:>={created_date}")
                            query_parts.append(f"stars:>{star_limits.get('created', 300)}")
                            sort_by = "stars"
                        else:  # stars
                            # 高热度项目
                            date_limit = (datetime.now() - timedelta(days=created_days)).strftime("%Y-%m-%d")
                            query_parts.append(f"created:>={date_limit}")
                            query_parts.append(f"stars:>{star_limits.get('stars', 500)}")
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
                        logger.info(f"📡 发送查询 {query_count}/{total_queries}: {trend_type}/{lang}")
                        logger.info(f"🔍 查询字符串: {query}")
                        
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
                        logger.info(f"📊 查询结果: 总计 {total_count} 个，返回 {items_count} 个")
                        
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
            
            logger.info(f"🔍 抓取到 {len(unique_repos)} 个唯一仓库")
            
            # 【核心功能】第一步：加载本地已存在的项目数据
            existing_items = _load_existing_github_items()
            
            # 获取GitHub数据库实例（用于状态管理）
            github_db = get_github_db()
            
            # 【核心功能】第二步：分离新项目和已存在项目
            new_repos = []  # 需要AI筛选和翻译的新项目
            existing_repos = []  # 已存在，只需更新状态的项目
            
            for repo in unique_repos:
                repo_url = repo.get("html_url", "")
                if repo_url in existing_items:
                    # 已存在的项目，只更新状态信息
                    existing_repos.append(repo)
                else:
                    # 新项目，需要AI筛选和翻译
                    new_repos.append(repo)
            
            logger.info(
                f"📋 项目分类: 新项目 {len(new_repos)} 个 | "
                f"已存在项目 {len(existing_repos)} 个"
            )
            
            # 【核心功能】第三步：处理已存在项目 - 只更新状态，保留原有标题
            updated_existing_items = []
            for repo in existing_repos:
                repo_url = repo.get("html_url", "")
                existing_item = existing_items[repo_url]
                
                # 只更新状态字段，保留原有标题和摘要
                existing_item.score = repo.get("stargazers_count", existing_item.score or 0)
                existing_item.comments_count = repo.get("comments_count", existing_item.comments_count)
                # 更新tags（如果有新tags）
                if repo.get("topics"):
                    existing_item.tags = repo.get("topics", [])[:5]
                # 更新story_type（如果有）
                if repo.get("_trend_type"):
                    existing_item.story_type = repo.get("_trend_type")
                
                updated_existing_items.append(existing_item)
                
                # 更新数据库状态（使用add_project会自动保存）
                project_id = github_db._generate_project_id(repo)
                existing_project = github_db.get_project(project_id)
                if existing_project:
                    # 保留原有状态和AI评分
                    status = existing_project.get("status", "crawled")
                    ai_score = existing_project.get("ai_score", 0.0)
                    ai_reason = existing_project.get("ai_reason", "")
                    # 使用add_project更新，会自动保存数据库
                    github_db.add_project(repo, status=status, ai_score=ai_score, ai_reason=ai_reason)
                    logger.debug(f"📊 更新已存在项目状态: {repo.get('full_name')} (stars: {repo.get('stargazers_count', 0)})")
            
            # 【核心功能】第四步：处理新项目 - 进行AI筛选和翻译
            filtered_repos = []
            whitelisted_projects = []  # 在外层定义，确保所有分支都能访问
            need_ai_screening = []
            
            logger.info(f"🔧 AI筛选配置: enabled={ai_filter_enabled}, 新项目数={len(new_repos)}")
            
            if ai_filter_enabled and new_repos:
                # 分离：数据库中的AI项目 vs 新项目
                reused_ai_screened = 0  # 复用历史AI结果的项目数
                
                # 检测每个新项目的状态
                for repo in new_repos:
                    project_id = github_db._generate_project_id(repo)
                    existing_project = github_db.get_project(project_id)
                    
                    if existing_project:
                        status = existing_project.get("status", "crawled")
                        
                        # 1. 白名单项目：直接使用缓存数据，完全跳过AI筛选
                        if status == "whitelisted" and github_db.is_whitelisted(repo):
                            repo["_ai_score"] = existing_project.get("ai_score", 0.8)
                            whitelisted_projects.append(repo)
                            logger.debug(f"📋 项目 {repo.get('full_name')} 在白名单中，跳过AI筛选")
                            # 更新项目的最后访问时间，但不改变状态
                            github_db.add_project(repo, status="whitelisted")
                        
                        # 2. 已经AI筛选通过的项目：复用上次的AI结果，不再调用LLM
                        elif status == "ai_screened":
                            ai_score = existing_project.get("ai_score", 0.0)
                            ai_reason = existing_project.get("ai_reason", "")
                            repo["_ai_score"] = ai_score
                            repo["_ai_reason"] = ai_reason
                            filtered_repos.append(repo)
                            reused_ai_screened += 1
                            logger.debug(f"📋 项目 {repo.get('full_name')} 已AI筛选，复用结果，跳过AI筛选")
                            # 更新last_seen等状态
                            github_db.add_project(repo, status="ai_screened", ai_score=ai_score, ai_reason=ai_reason)
                        
                        # 3. 其他状态（crawled 等）：需要AI筛选
                        else:
                            need_ai_screening.append(repo)
                            logger.debug(f"📋 项目 {repo.get('full_name')} 状态={status}，需要AI筛选")
                    else:
                        # 完全新项目：先写入数据库，再进入AI筛选队列
                        github_db.add_project(repo, status="crawled")
                        need_ai_screening.append(repo)
                        logger.debug(f"📋 新项目 {repo.get('full_name')} 需要AI筛选")
                
                # 关键统计日志：直观看到节省了多少 LLM 调用
                logger.info(
                    f"📋 新项目分类: 总新项目 {len(new_repos)} 个 | "
                    f"白名单命中 {len(whitelisted_projects)} 个 | "
                    f"复用AI结果 {reused_ai_screened} 个 | "
                    f"需要AI筛选 {len(need_ai_screening)} 个"
                )
                
                filtered_repos = list(whitelisted_projects)  # 加入白名单项目
            else:
                # 不使用AI筛选时，所有新项目都需要处理
                need_ai_screening = new_repos
                filtered_repos = []
            
            # 【核心功能】第五步：先保存所有新项目到文件（标记为非AI），避免数据丢失
            # 这样即使后续AI筛选中断，新项目也已经保存了
            if new_repos:
                logger.info(f"💾 先保存 {len(new_repos)} 个新项目到文件（标记为非AI）...")
                try:
                    # 先保存所有新项目，标记为非AI（is_ai_project=False）
                    _save_github_repos_to_file(new_repos, is_ai_project_map={})
                    logger.info(f"✅ 已保存 {len(new_repos)} 个新项目到文件（待AI筛选）")
                except Exception as save_error:
                    logger.error(f"⚠️ 保存新项目失败: {save_error}")
            
            # 第六步：对新项目进行AI筛选（批量处理，每批完成后立即保存）
            # 全局的is_ai_project_map，用于记录所有项目的AI标记
            is_ai_project_map = {}
            
            # 白名单项目标记为AI
            for repo in whitelisted_projects:
                repo_url = repo.get("html_url", "")
                if repo_url:
                    is_ai_project_map[repo_url] = True
            
            if ai_filter_enabled and need_ai_screening:
                logger.info(f"🤖 开始AI筛选 {len(need_ai_screening)} 个新项目...")
                
                # 分批进行AI筛选，每批完成后立即保存
                AI_BATCH_SIZE = 25  # AI筛选批次大小
                total_ai_batches = (len(need_ai_screening) + AI_BATCH_SIZE - 1) // AI_BATCH_SIZE
                
                for ai_batch_idx in range(total_ai_batches):
                    start_idx = ai_batch_idx * AI_BATCH_SIZE
                    end_idx = min((ai_batch_idx + 1) * AI_BATCH_SIZE, len(need_ai_screening))
                    batch_repos = need_ai_screening[start_idx:end_idx]
                    
                    logger.info(f"🤖 AI筛选批次 {ai_batch_idx + 1}/{total_ai_batches} ({len(batch_repos)} 个项目)...")
                    
                    # 准备标题列表
                    title_batch = []
                    repo_map = {}
                    
                    for repo in batch_repos:
                        description = repo.get("description", "") or ""
                        title = f"{repo.get('full_name', '')}: {description[:50]}"
                        temp_id = str(repo.get("id"))
                        title_batch.append((temp_id, title))
                        repo_map[temp_id] = repo
                    
                    # 调用AI筛选
                    classification_results = await classify_titles_batch(title_batch, batch_size=20)
                    result_map = {r["id"]: r for r in classification_results}
                    
                    # 处理AI筛选结果
                    batch_ai_repos = []
                    for temp_id, _ in title_batch:
                        if temp_id not in result_map:
                            continue
                        
                        classification = result_map[temp_id]
                        repo = repo_map[temp_id]
                        repo_url = repo.get("html_url", "")
                        
                        if classification["keep"]:
                            # 通过AI筛选
                            ai_score = classification["score"]
                            repo["_ai_score"] = ai_score
                            repo["_ai_reason"] = classification.get("reason", "")
                            is_ai_project_map[repo_url] = True
                            filtered_repos.append(repo)
                            batch_ai_repos.append(repo)
                            
                            # 更新数据库状态
                            github_db.mark_as_ai_screened(repo, ai_score=ai_score)
                        else:
                            # 未通过AI筛选
                            is_ai_project_map[repo_url] = False
                            repo["_ai_score"] = 0.0
                    
                    # 【关键】每批AI筛选完成后立即保存，避免数据丢失
                    if batch_repos:
                        try:
                            _save_github_repos_to_file(batch_repos, is_ai_project_map)
                            logger.info(f"💾 已保存批次 {ai_batch_idx + 1} 的 {len(batch_repos)} 个项目（AI项目: {len(batch_ai_repos)} 个）")
                        except Exception as save_error:
                            logger.error(f"⚠️ 保存批次 {ai_batch_idx + 1} 失败: {save_error}")
                
                logger.info(
                    f"✅ AI筛选完成: {len(filtered_repos)} 个AI仓库 "
                    f"(白名单命中 {len(whitelisted_projects)} + 新通过 {len(filtered_repos) - len(whitelisted_projects)})"
                )
            elif not ai_filter_enabled:
                logger.warning(f"⚠️ AI筛选已禁用，将使用关键词匹配（配置: ai_filter_enabled=False）")
            elif not need_ai_screening:
                logger.warning(f"⚠️ 没有需要AI筛选的项目（所有新项目可能都在白名单中）")
            else:
                # 不使用AI筛选，使用关键词匹配（向后兼容）- 只处理新项目
                filtered_repos = []
                ai_keywords = [
                    "ai", "artificial intelligence", "machine learning", "ml",
                    "llm", "gpt", "claude", "transformer", "neural", "deep learning"
                ]
                
                for repo in new_repos:
                    repo_name = repo.get("name", "").lower()
                    description = repo.get("description", "").lower()
                    topics = [t.lower() for t in repo.get("topics", [])]
                    
                    is_ai_related = any(
                        kw in repo_name or kw in description or any(kw in t for t in topics)
                        for kw in ai_keywords
                    )
                    
                    if is_ai_related:
                        filtered_repos.append(repo)
            
            # 【核心功能】第六步：对新项目进行翻译和创建ArticleItem
            # 每翻译一批就立即保存，避免中途异常导致全部丢失
            BATCH_SIZE = 20  # 每批处理20个项目
            total_repos = len(filtered_repos)
            total_batches = (total_repos + BATCH_SIZE - 1) // BATCH_SIZE if total_repos > 0 else 0
            
            new_items = []
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min((batch_idx + 1) * BATCH_SIZE, total_repos)
                batch_repos = filtered_repos[start_idx:end_idx]
                
                logger.info(f"📦 处理新项目批次 {batch_idx + 1}/{total_batches} ({len(batch_repos)} 个项目)...")
                
                batch_items = []
                for repo in batch_repos:
                    # 清理摘要：去除HTML标签和URL
                    raw_description = repo.get("description", "") or f"GitHub项目: {repo.get('name', '')}"
                    cleaned_summary = clean_text(raw_description, max_length=300)
                    cleaned_summary = re.sub(r'https?://\S+', '', cleaned_summary).strip()
                    summary = truncate_summary(cleaned_summary, 300)
                    
                    title = f"{repo.get('full_name', '')}: {repo.get('name', '')}"
                    
                    # 翻译标题和摘要（只对新项目进行翻译）
                    if translation_enabled:
                        try:
                            translated_title, translated_summary = await translate_article_item(title, summary)
                        except Exception:
                            translated_title = title
                            translated_summary = truncate_summary(summary, 300)
                    else:
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
                
                new_items.extend(batch_items)
            
            # 【核心功能】第七步：最终保存所有项目到output/github/（全量数据）
            # 合并所有项目（新项目+已存在项目），统一保存
            all_repos_to_save = existing_repos + new_repos
            
            # 从已有数据中加载已存在项目的AI标记（保留历史标记）
            for repo_url, item in existing_items.items():
                if repo_url not in is_ai_project_map:
                    # 如果已有数据中标记为AI项目，保留标记
                    if item.ai_score and item.ai_score > 0:
                        is_ai_project_map[repo_url] = True
                    else:
                        is_ai_project_map[repo_url] = False
            
            # 最终保存所有项目（全量数据，包括已存在项目的更新）
            try:
                _save_github_repos_to_file(all_repos_to_save, is_ai_project_map)
                ai_count = sum(1 for is_ai in is_ai_project_map.values() if is_ai)
                logger.info(f"💾 最终保存 {len(all_repos_to_save)} 个项目到output/github/ (AI项目: {ai_count} 个)")
            except Exception as save_error:
                logger.error(f"⚠️ 最终保存到output/github/失败: {save_error}")
            
            # 为了返回FetchResult，只返回AI项目（用于预览显示）
            items = updated_existing_items + new_items
            
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
            logger.info("✅ GitHub趋势项目获取完成!")
            logger.info(
                f"📊 最终结果: {len(items)} 个AI相关项目 "
                f"(新项目: {len(new_items)} 个, 已存在项目: {len(updated_existing_items)} 个, "
                f"从 {len(unique_repos)} 个仓库中筛选)"
            )
            logger.source_success("GitHub Trending", f"{len(items)}/{len(unique_repos)} (新:{len(new_items)},已存在:{len(updated_existing_items)})")
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