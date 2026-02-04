"""
数据模型定义 - 统一的输出格式
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, HttpUrl


class ArticleItem(BaseModel):
    """
    标准化的文章/资讯项目模型
    
    所有工具的输出都应该转换为这个统一格式
    """
    title: str = Field(..., description="文章标题")
    summary: str = Field(..., max_length=300, description="内容摘要，不超过300字")
    source_url: str = Field(..., description="来源地址URL")
    published_date: Optional[str] = Field(None, description="发布日期，ISO 8601格式")
    source_type: Literal["hackernews", "techmeme", "arxiv", "rss", "github"] = Field(
        ..., 
        description="来源类型"
    )
    article_tag: Literal["AI资讯", "AI工具", "AI论文", "技术博客"] = Field(
        ..., 
        description="文章标签分类"
    )
    
    # 可选的额外字段
    author: Optional[str] = Field(None, description="作者")
    score: Optional[int] = Field(None, description="评分/热度")
    comments_count: Optional[int] = Field(None, description="评论数")
    tags: list[str] = Field(default_factory=list, description="关键词标签")
    
    # 数据源特定字段
    story_type: Optional[Literal["top", "new", "best", "pushed", "created", "stars"]] = Field(
        None, 
        description="数据源类型：Hacker News(top/new/best) 或 GitHub(pushed/created/stars)"
    )
    ai_score: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0, 
        description="AI相关性评分，0.0-1.0，由AI模型判断"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "GPT-5 Released by OpenAI",
                "summary": "OpenAI announces the release of GPT-5, featuring improved reasoning capabilities and longer context windows...",
                "source_url": "https://openai.com/blog/gpt-5",
                "published_date": "2026-01-20T10:00:00",
                "source_type": "rss",
                "article_tag": "AI资讯",
                "author": "OpenAI Team",
                "tags": ["gpt", "llm", "openai"]
            }
        }


class FetchResult(BaseModel):
    """
    统一的抓取结果格式
    """
    success: bool = Field(..., description="是否成功")
    source_name: str = Field(..., description="数据源名称")
    source_type: str = Field(..., description="数据源类型")
    total_count: int = Field(..., description="返回的条目总数")
    fetched_at: str = Field(..., description="抓取时间，ISO 8601格式")
    items: list[ArticleItem] = Field(default_factory=list, description="文章列表")
    error: Optional[str] = Field(None, description="错误信息（如果有）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "source_name": "Hacker News",
                "source_type": "hackernews",
                "total_count": 10,
                "fetched_at": "2026-01-20T15:30:00",
                "items": [],
                "error": None
            }
        }


class SearchResult(BaseModel):
    """
    跨源搜索结果格式
    """
    success: bool = Field(..., description="是否成功")
    query: str = Field(..., description="搜索关键词")
    sources_count: int = Field(..., description="搜索的源数量")
    total_items: int = Field(..., description="总条目数")
    searched_at: str = Field(..., description="搜索时间")
    results: list[FetchResult] = Field(default_factory=list, description="各源的结果")


def truncate_summary(text: str, max_length: int = 300) -> str:
    """
    截断摘要到指定长度，在词边界处截断
    
    Args:
        text: 原始文本
        max_length: 最大长度（默认300字符）
        
    Returns:
        截断后的文本（保证不超过max_length）
    """
    if not text or len(text) <= max_length:
        return text
    
    # 清理空白字符
    text = " ".join(text.split())
    
    if len(text) <= max_length:
        return text
    
    # 【关键修复】为"..."预留3个字符，确保最终长度不超过max_length
    safe_length = max_length - 3
    
    # 在词边界处截断（对英文有效，中文会直接截断）
    truncated = text[:safe_length].rsplit(" ", 1)[0]
    
    # 确保截断后的长度 + "..." 不超过 max_length
    if len(truncated) + 3 > max_length:
        truncated = truncated[:max_length - 3]
    
    return truncated + "..."


def classify_article_tag(
    title: str, 
    summary: str, 
    source_type: str,
    tags: Optional[list[str]] = None
) -> Literal["AI资讯", "AI工具", "AI论文", "技术博客"]:
    """
    根据标题、摘要和来源自动分类文章标签
    
    Args:
        title: 文章标题
        summary: 文章摘要
        source_type: 来源类型
        tags: 额外的标签
        
    Returns:
        文章分类标签
    """
    # 转换为小写用于匹配
    text = f"{title} {summary}".lower()
    if tags:
        text += " " + " ".join(tags).lower()
    
    # arXiv 来源直接分类为论文
    if source_type == "arxiv":
        return "AI论文"
    
    # 工具相关关键词
    tool_keywords = [
        "tool", "library", "framework", "api", "sdk", "platform",
        "工具", "框架", "平台", "库", "插件", "extension",
        "github", "open source", "release", "launch"
    ]
    
    # 博客相关关键词  
    blog_keywords = [
        "blog", "tutorial", "guide", "how to", "introduction",
        "博客", "教程", "指南", "介绍"
    ]
    
    # 检查是否为工具
    if any(kw in text for kw in tool_keywords):
        return "AI工具"
    
    # 检查是否为博客
    if source_type == "rss" and any(kw in text for kw in blog_keywords):
        return "技术博客"
    
    # 默认为资讯
    return "AI资讯"
