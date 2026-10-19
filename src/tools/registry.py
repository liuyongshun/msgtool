"""
工具注册表 - 维护工具与数据源的映射关系
"""

from typing import TypedDict, Literal, Optional


class SourceMapping(TypedDict):
    """数据源映射定义"""
    config_key: str  # 配置键路径，如 "news.hackernews"
    function: str    # 实现函数名
    type: Literal["api", "scrape", "rss", "arxiv"]  # 数据源类型


class ToolMapping(TypedDict):
    """工具映射定义"""
    module: str  # 模块名
    description: str  # 工具描述
    sources: dict[str, SourceMapping]  # 数据源映射


# 工具与数据源映射表
TOOL_REGISTRY: dict[str, ToolMapping] = {
    "fetch_ai_news": {
        "module": "news_scraper",
        "description": "从科技新闻网站抓取AI相关新闻",
        "sources": {
            "hackernews": {
                "config_key": "news.hackernews",
                "function": "_fetch_hackernews",
                "type": "api"
            }
        }
    },
    "fetch_arxiv_papers": {
        "module": "arxiv_fetcher",
        "description": "从arXiv获取AI研究论文",
        "sources": {
            "cs_ai": {
                "config_key": "arxiv.cs_ai",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_lg": {
                "config_key": "arxiv.cs_lg",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_cl": {
                "config_key": "arxiv.cs_cl",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_cv": {
                "config_key": "arxiv.cs_cv",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_ne": {
                "config_key": "arxiv.cs_ne",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_ro": {
                "config_key": "arxiv.cs_ro",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "stat_ml": {
                "config_key": "arxiv.stat_ml",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_ir": {
                "config_key": "arxiv.cs_ir",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_se": {
                "config_key": "arxiv.cs_se",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_ma": {
                "config_key": "arxiv.cs_ma",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_hc": {
                "config_key": "arxiv.cs_hc",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "cs_dc": {
                "config_key": "arxiv.cs_dc",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            },
            "eess_as": {
                "config_key": "arxiv.eess_as",
                "function": "fetch_arxiv_papers",
                "type": "arxiv"
            }
        }
    },
    "fetch_rss_feeds": {
        "module": "rss_reader",
        "description": "从RSS订阅源聚合AI相关文章",
        "sources": {
            "mit_tech_review": {
                "config_key": "rss.mit_tech_review",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "openai_blog": {
                "config_key": "rss.openai_blog",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "google_ai": {
                "config_key": "rss.google_ai",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "huggingface": {
                "config_key": "rss.huggingface",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "deeplearning_ai": {
                "config_key": "rss.deeplearning_ai",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "sebastian_raschka": {
                "config_key": "rss.sebastian_raschka",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "anthropic_blog": {
                "config_key": "rss.anthropic_blog",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "deepseek_blog": {
                "config_key": "rss.deepseek_blog",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "meta_ai": {
                "config_key": "rss.meta_ai",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "microsoft_ai": {
                "config_key": "rss.microsoft_ai",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "langchain_blog": {
                "config_key": "rss.langchain_blog",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "llamaindex_blog": {
                "config_key": "rss.llamaindex_blog",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "techmeme": {
                "config_key": "rss.techmeme",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "techcrunch": {
                "config_key": "rss.techcrunch",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "sequoia_blog": {
                "config_key": "rss.sequoia_blog",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "a16z_blog": {
                "config_key": "rss.a16z_blog",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "thoughtworks": {
                "config_key": "rss.thoughtworks",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "gartner": {
                "config_key": "rss.gartner",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "product_hunt": {
                "config_key": "rss.product_hunt",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "futurepedia": {
                "config_key": "rss.futurepedia",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "sspai": {
                "config_key": "rss.sspai",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "arstechnica": {
                "config_key": "rss.arstechnica",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "36kr": {
                "config_key": "rss.36kr",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "36kr_article": {
                "config_key": "rss.36kr_article",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "36kr_newsflash": {
                "config_key": "rss.36kr_newsflash",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "36kr_moment": {
                "config_key": "rss.36kr_moment",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "infoq": {
                "config_key": "rss.infoq",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "ithome": {
                "config_key": "rss.ithome",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "huggingface_daily_papers": {
                "config_key": "rss.huggingface_daily_papers",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "qbitai": {
                "config_key": "rss.qbitai",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "jiqizhixin": {
                "config_key": "rss.jiqizhixin",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "huxiu": {
                "config_key": "rss.huxiu",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "tmtpost": {
                "config_key": "rss.tmtpost",
                "function": "_fetch_single_feed",
                "type": "rss"
            },
            "v2ex": {
                "config_key": "rss.v2ex",
                "function": "_fetch_single_feed",
                "type": "rss"
            }
        }
    },
    "fetch_github_trending": {
        "module": "github_fetcher",
        "description": "从GitHub获取AI相关热门项目",
        "sources": {
            "trending_daily": {
                "config_key": "github.trending_daily",
                "function": "fetch_github_trending",
                "type": "api"
            }
        }
    }
}


def get_tool_mapping(tool_name: str) -> Optional[ToolMapping]:
    """
    获取工具的映射信息
    
    Args:
        tool_name: 工具名称
        
    Returns:
        工具映射信息或None
    """
    return TOOL_REGISTRY.get(tool_name)


def list_all_tools() -> list[str]:
    """
    列出所有注册的工具
    
    Returns:
        工具名称列表
    """
    return list(TOOL_REGISTRY.keys())


def get_tool_sources(tool_name: str) -> Optional[dict[str, SourceMapping]]:
    """
    获取工具支持的数据源
    
    Args:
        tool_name: 工具名称
        
    Returns:
        数据源映射字典或None
    """
    mapping = get_tool_mapping(tool_name)
    return mapping.get("sources") if mapping else None


def get_source_info(tool_name: str, source_key: str) -> Optional[SourceMapping]:
    """
    获取特定工具和数据源的映射信息
    
    Args:
        tool_name: 工具名称
        source_key: 数据源键
        
    Returns:
        数据源映射信息或None
    """
    sources = get_tool_sources(tool_name)
    return sources.get(source_key) if sources else None


def get_tools_by_type(source_type: Literal["api", "scrape", "rss", "arxiv"]) -> list[str]:
    """
    根据数据源类型查找工具
    
    Args:
        source_type: 数据源类型
        
    Returns:
        工具名称列表
    """
    tools = []
    for tool_name, mapping in TOOL_REGISTRY.items():
        for source_mapping in mapping["sources"].values():
            if source_mapping["type"] == source_type:
                tools.append(tool_name)
                break
    return tools
