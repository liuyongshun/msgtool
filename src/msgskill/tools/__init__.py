"""
MsgSkill Tools - News fetching tools for MCP server
"""

from .news_scraper import fetch_ai_news
from .arxiv_fetcher import fetch_arxiv_papers
from .rss_reader import fetch_rss_feeds
from .github_fetcher import fetch_github_trending

__all__ = [
    "fetch_ai_news",
    "fetch_arxiv_papers",
    "fetch_rss_feeds",
    "fetch_github_trending"
]
