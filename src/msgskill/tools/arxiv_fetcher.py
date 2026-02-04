"""
arXiv论文获取工具 (ArXiv Fetcher)

功能: 从arXiv获取AI相关研究论文
数据源: arXiv API (7个分类)
配置文件: config/sources.json -> sources.arxiv.*

工具函数:
    - fetch_arxiv_papers(): 主入口函数，支持按分类和关键词搜索
    - search_arxiv(): 跨分类搜索（可选）

映射关系:
    category="cs.AI"  -> config.arxiv.cs_ai
    category="cs.LG"  -> config.arxiv.cs_lg
    category="cs.CL"  -> config.arxiv.cs_cl
    category="cs.CV"  -> config.arxiv.cs_cv
    category="cs.NE"  -> config.arxiv.cs_ne
    category="cs.RO"  -> config.arxiv.cs_ro
    category="stat.ML" -> config.arxiv.stat_ml
"""

import asyncio
from datetime import datetime
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor

import arxiv

from ..utils.cache import get_cache
from ..utils.logger import logger
from ..utils.translator import translate_article_item
from ..config import get_config


# Supported arXiv categories for AI research
ARXIV_CATEGORIES = {
    "cs.AI": "Artificial Intelligence",
    "cs.LG": "Machine Learning",
    "cs.CL": "Computation and Language (NLP)",
    "cs.CV": "Computer Vision and Pattern Recognition",
    "cs.NE": "Neural and Evolutionary Computing",
    "cs.RO": "Robotics",
    "stat.ML": "Machine Learning (Statistics)",
    "cs.IR": "Information Retrieval",
    "cs.SE": "Software Engineering",
    "cs.MA": "Multiagent Systems",
    "cs.HC": "Human-Computer Interaction",
    "cs.DC": "Distributed Computing",
    "eess.AS": "Audio and Speech Processing",
}


async def fetch_arxiv_papers(
    category: str = "cs.AI",
    query: str = "",
    max_results: int = 10
) -> dict[str, Any]:
    """
    Fetch latest AI research papers from arXiv.
    
    Args:
        category: arXiv category (cs.AI, cs.LG, cs.CL, etc.)
        query: Optional search query to filter papers
        max_results: Maximum number of papers to return
        
    Returns:
        Dictionary with paper information
    """
    if category not in ARXIV_CATEGORIES:
        return {
            "error": f"Unknown category: {category}. Available: {', '.join(ARXIV_CATEGORIES.keys())}",
            "papers": []
        }
    
    cache = get_cache()
    cache_key = f"arxiv_{category}_{query}_{max_results}"
    
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        # Build search query
        if query:
            # Search within category with additional query
            search_query = f"cat:{category} AND ({query})"
        else:
            # Just search by category
            search_query = f"cat:{category}"
        
        # Create search client
        search = arxiv.Search(
            query=search_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        # Run the synchronous arxiv API in a thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            papers = await loop.run_in_executor(
                executor,
                lambda: list(search.results())
            )
        
        # Format results
        paper_list = []
        for paper in papers:
            paper_list.append({
                "id": paper.entry_id.split("/")[-1],
                "title": paper.title,
                "authors": [author.name for author in paper.authors[:5]],  # Limit authors
                "author_count": len(paper.authors),
                "summary": _truncate_text(paper.summary, 500),
                "categories": paper.categories,
                "primary_category": paper.primary_category,
                "published": paper.published.isoformat() if paper.published else None,
                "updated": paper.updated.isoformat() if paper.updated else None,
                "pdf_url": paper.pdf_url,
                "arxiv_url": paper.entry_id,
                "comment": paper.comment,
            })
        
        # 【方案A+B+C】智能翻译策略：选择性翻译 + 缓存
        if paper_list:
            config = get_config()
            scheduler_config = config._config.get("global_settings", {}).get("scheduler", {})
            arxiv_config = scheduler_config.get("arxiv", {})
            translation_strategy = arxiv_config.get("translation_strategy", {})
            
            # 获取翻译策略配置
            selective_enabled = translation_strategy.get("selective_translation", True)
            min_authors = translation_strategy.get("min_authors", 2)
            
            # 筛选需要翻译的论文
            papers_to_translate = []
            papers_to_skip = []
            
            for paper in paper_list:
                paper_id = paper.get("id", "")
                author_count = paper.get("author_count", 0)
                
                # 【方案B】检查翻译缓存
                translation_cache_key = f"arxiv_translation_{paper_id}"
                cached_translation = cache.get(translation_cache_key)
                
                if cached_translation:
                    # 使用缓存的翻译
                    paper["title"] = cached_translation.get("title", paper["title"])
                    paper["summary"] = cached_translation.get("summary", paper["summary"])
                    papers_to_skip.append(paper_id)
                    continue
                
                # 【方案A】选择性翻译：只翻译高质量论文
                if selective_enabled and author_count < min_authors:
                    # 单作者或低质量论文，跳过翻译
                    papers_to_skip.append(paper_id)
                    continue
                
                papers_to_translate.append(paper)
            
            if papers_to_skip:
                logger.info(f"跳过翻译: {len(papers_to_skip)} 篇论文（{len([p for p in papers_to_skip if cache.get(f'arxiv_translation_{p}')])} 篇使用缓存）")
            
            if papers_to_translate:
                logger.info(f"开始翻译 {len(papers_to_translate)} 篇高质量论文...")
                translation_tasks = []
                for paper in papers_to_translate:
                    title = paper.get("title", "")
                    summary = paper.get("summary", "")
                    translation_tasks.append(translate_article_item(title, summary))
                
                # 并发翻译所有论文
                translation_results = await asyncio.gather(*translation_tasks, return_exceptions=True)
                
                # 更新论文标题和摘要，并缓存翻译结果
                for paper, result in zip(papers_to_translate, translation_results):
                    if isinstance(result, Exception):
                        # 翻译失败，保持原文
                        logger.warning(f"论文 {paper.get('id')} 翻译失败: {str(result)}")
                        continue
                    
                    translated_title, translated_summary = result
                    paper["title"] = translated_title
                    paper["summary"] = translated_summary
                    
                    # 【方案B】缓存翻译结果（缓存24小时）
                    paper_id = paper.get("id", "")
                    if paper_id:
                        translation_cache_key = f"arxiv_translation_{paper_id}"
                        cache.set(translation_cache_key, {
                            "title": translated_title,
                            "summary": translated_summary
                        }, ttl=86400)  # 24小时
                
                logger.info(f"翻译完成: {len(papers_to_translate)} 篇论文")
            
            logger.info(f"论文处理统计: 总计{len(paper_list)}篇，翻译{len(papers_to_translate)}篇，跳过{len(papers_to_skip)}篇")
        
        result = {
            "source": "arXiv",
            "category": category,
            "category_name": ARXIV_CATEGORIES[category],
            "query": query or None,
            "count": len(paper_list),
            "fetched_at": datetime.now().isoformat(),
            "papers": paper_list
        }
        
        cache.set(cache_key, result, ttl=600)  # Cache for 10 minutes
        category_name = ARXIV_CATEGORIES.get(category, category)
        logger.source_success(f"arXiv {category_name}", len(paper_list))
        return result
        
    except Exception as e:
        error_msg = f"Error fetching papers: {str(e)}"
        category_name = ARXIV_CATEGORIES.get(category, category)
        logger.source_error(f"arXiv {category_name}", error_msg)
        return {
            "source": "arXiv",
            "category": category,
            "error": error_msg,
            "papers": []
        }


def _truncate_text(text: str, max_length: int) -> str:
    """Truncate text to max length, ending at word boundary"""
    if not text or len(text) <= max_length:
        return text
    
    # Clean up whitespace
    text = " ".join(text.split())
    
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated + "..."


async def search_arxiv(
    query: str,
    categories: Optional[list[str]] = None,
    max_results: int = 10
) -> dict[str, Any]:
    """
    Search arXiv across multiple categories.
    
    Args:
        query: Search query
        categories: List of categories to search (default: all AI categories)
        max_results: Maximum results per category
        
    Returns:
        Dictionary with search results
    """
    if categories is None:
        categories = list(ARXIV_CATEGORIES.keys())
    
    # Validate categories
    valid_categories = [c for c in categories if c in ARXIV_CATEGORIES]
    if not valid_categories:
        return {
            "error": "No valid categories specified",
            "results": {}
        }
    
    # Fetch from all categories in parallel
    tasks = [
        fetch_arxiv_papers(
            category=cat,
            query=query,
            max_results=max_results
        )
        for cat in valid_categories
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    combined = {
        "query": query,
        "categories_searched": valid_categories,
        "fetched_at": datetime.now().isoformat(),
        "results": {}
    }
    
    for cat, result in zip(valid_categories, results):
        if isinstance(result, Exception):
            combined["results"][cat] = {
                "error": str(result),
                "papers": []
            }
        else:
            combined["results"][cat] = result
    
    return combined
