"""
MsgSkill MCP Server - Main entry point

A Model Context Protocol server providing AI news fetching capabilities.
"""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
)

from .tools.news_scraper import fetch_ai_news, NEWS_SOURCES
from .tools.arxiv_fetcher import fetch_arxiv_papers, ARXIV_CATEGORIES
from .tools.rss_reader import fetch_rss_feeds, DEFAULT_AI_FEEDS
from .tools.github_fetcher import fetch_github_trending
from .utils.logger import logger


# Create the MCP server instance
server = Server("msgskill")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="fetch_ai_news",
            description="Fetch AI-related news from tech websites like Hacker News, TechCrunch, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": f"News source to fetch from. Available: {', '.join(NEWS_SOURCES.keys())}",
                        "enum": list(NEWS_SOURCES.keys()),
                        "default": "hackernews"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of news items to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional keywords to filter news (e.g., ['LLM', 'GPT', 'Claude'])",
                        "default": []
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="fetch_arxiv_papers",
            description="Fetch latest AI research papers from arXiv",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": f"arXiv category. Available: {', '.join(ARXIV_CATEGORIES.keys())}",
                        "enum": list(ARXIV_CATEGORIES.keys()),
                        "default": "cs.AI"
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional search query to filter papers",
                        "default": ""
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of papers to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="fetch_rss_feeds",
            description="Fetch and aggregate AI news from RSS feeds",
            inputSchema={
                "type": "object",
                "properties": {
                    "feed_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"List of RSS feed URLs. If empty, uses default AI news feeds: {', '.join(DEFAULT_AI_FEEDS.keys())}",
                        "default": []
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items per feed",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="fetch_github_trending",
            description="Fetch AI-related trending projects from GitHub",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Programming language filter (e.g., 'python', 'javascript'). Optional.",
                        "default": None
                    },
                    "since": {
                        "type": "string",
                        "description": "Time range: 'daily', 'weekly', or 'monthly'",
                        "enum": ["daily", "weekly", "monthly"],
                        "default": "daily"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of projects to return",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="search_ai_news",
            description="Search for AI news across multiple sources",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'large language models', 'GPT-5')"
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"Sources to search. Available: hackernews, arxiv, rss, github. Default: all",
                        "default": ["hackernews", "arxiv", "rss", "github"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results per source",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["query"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls"""
    logger.info(f"执行工具: {name}")
    try:
        if name == "fetch_ai_news":
            result = await fetch_ai_news(
                source=arguments.get("source", "hackernews"),
                limit=arguments.get("limit", 10),
                keywords=arguments.get("keywords", [])
            )
        elif name == "fetch_arxiv_papers":
            result = await fetch_arxiv_papers(
                category=arguments.get("category", "cs.AI"),
                query=arguments.get("query", ""),
                max_results=arguments.get("max_results", 10)
            )
        elif name == "fetch_rss_feeds":
            result = await fetch_rss_feeds(
                feed_urls=arguments.get("feed_urls", []),
                limit=arguments.get("limit", 10)
            )
        elif name == "fetch_github_trending":
            result = await fetch_github_trending(
                language=arguments.get("language"),
                since=arguments.get("since", "daily"),
                limit=arguments.get("limit", 20)
            )
            # Convert FetchResult to dict for JSON serialization
            if hasattr(result, "model_dump"):
                result = result.model_dump()
        elif name == "search_ai_news":
            result = await search_ai_news(
                query=arguments["query"],
                sources=arguments.get("sources", ["hackernews", "arxiv", "rss", "github"]),
                limit=arguments.get("limit", 5)
            )
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
        
        # 检查结果中的错误并输出
        if isinstance(result, dict):
            # RSS和arXiv返回dict格式
            if result.get("error"):
                logger.error(f"工具 {name} 执行失败: {result.get('error')}")
            elif result.get("errors"):
                for error in result.get("errors", []):
                    logger.error(f"工具 {name} 部分失败: {error}")
        elif hasattr(result, "success"):
            # FetchResult格式
            if not result.success:
                logger.error(f"工具 {name} 执行失败: {result.error}")
            else:
                logger.success(f"工具 {name} 执行成功，获取 {result.total_count} 条数据")
        
        # Format result as JSON
        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]
        
    except Exception as e:
        error_msg = f"Error executing {name}: {str(e)}"
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=error_msg
        )]


async def search_ai_news(
    query: str,
    sources: list[str],
    limit: int = 5
) -> dict[str, Any]:
    """
    Search for AI news across multiple sources.
    
    Args:
        query: Search query
        sources: List of sources to search
        limit: Maximum results per source
        
    Returns:
        Dictionary with results from each source
    """
    results = {
        "query": query,
        "sources": {}
    }
    
    tasks = []
    source_names = []
    
    if "hackernews" in sources:
        tasks.append(fetch_ai_news(
            source="hackernews",
            limit=limit,
            keywords=query.split()
        ))
        source_names.append("hackernews")
    
    if "arxiv" in sources:
        tasks.append(fetch_arxiv_papers(
            category="cs.AI",
            query=query,
            max_results=limit
        ))
        source_names.append("arxiv")
    
    if "rss" in sources:
        tasks.append(fetch_rss_feeds(
            feed_urls=[],
            limit=limit
        ))
        source_names.append("rss")
    
    if "github" in sources:
        tasks.append(fetch_github_trending(
            language=None,
            since="daily",
            limit=limit
        ))
        source_names.append("github")
    
    if tasks:
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for source_name, task_result in zip(source_names, task_results):
            if isinstance(task_result, Exception):
                results["sources"][source_name] = {
                    "error": str(task_result),
                    "items": []
                }
            else:
                # Filter RSS results by query if applicable
                if source_name == "rss" and query:
                    query_lower = query.lower()
                    filtered_items = []
                    for feed_name, feed_data in task_result.get("feeds", {}).items():
                        for item in feed_data.get("items", []):
                            title = item.get("title", "").lower()
                            summary = item.get("summary", "").lower()
                            if query_lower in title or query_lower in summary:
                                item["feed_source"] = feed_name
                                filtered_items.append(item)
                    results["sources"][source_name] = {
                        "count": len(filtered_items),
                        "items": filtered_items[:limit]
                    }
                elif source_name == "github":
                    # GitHub returns FetchResult format, convert to dict if needed
                    if hasattr(task_result, "model_dump"):
                        github_data = task_result.model_dump()
                    else:
                        github_data = task_result
                    
                    # Filter by query if applicable
                    if query:
                        query_lower = query.lower()
                        filtered_items = []
                        for item in github_data.get("items", []):
                            title = item.get("title", "").lower()
                            summary = item.get("summary", "").lower()
                            if query_lower in title or query_lower in summary:
                                filtered_items.append(item)
                        results["sources"][source_name] = {
                            "count": len(filtered_items),
                            "items": filtered_items[:limit],
                            "total_count": github_data.get("total_count", 0)
                        }
                    else:
                        results["sources"][source_name] = github_data
                else:
                    results["sources"][source_name] = task_result
    
    return results


async def run_server():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def main():
    """Main entry point"""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
