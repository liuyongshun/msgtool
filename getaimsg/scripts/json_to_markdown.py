#!/usr/bin/env python3
"""
JSON 转 Markdown 转换工具
将精简的 JSON 数据转换为结构化的 Markdown 格式
支持四种数据源格式：arXiv、HackerNews、RSS、GitHub
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime


def format_date(date_str: str) -> str:
    """
    格式化日期字符串
    
    Args:
        date_str: ISO 格式日期字符串
    
    Returns:
        格式化后的日期字符串
    """
    if not date_str:
        return ""
    
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str


def convert_arxiv_to_markdown(data: Dict[str, Any]) -> str:
    """
    将 arXiv 数据转换为 Markdown
    
    Args:
        data: arXiv JSON 数据
    
    Returns:
        Markdown 字符串
    """
    if not data.get("success"):
        return f"# arXiv 数据获取失败\n\n错误: {data.get('error', '未知错误')}\n"
    
    papers = data.get("data", [])
    fetched_at = data.get("fetched_at", "")
    
    md = f"# arXiv 论文\n\n"
    if fetched_at:
        md += f"**获取时间**: {format_date(fetched_at)}\n\n"
    md += f"**总数**: {len(papers)} 篇\n\n"
    md += "---\n\n"
    
    for idx, paper in enumerate(papers, 1):
        md += f"## {idx}. {paper.get('title', '无标题')}\n\n"
        
        if paper.get("summary"):
            md += f"**摘要**: {paper.get('summary')}\n\n"
        
        if paper.get("author"):
            md += f"**作者**: {paper.get('author')}\n\n"
        
        if paper.get("published_date"):
            md += f"**发布日期**: {format_date(paper.get('published_date'))}\n\n"
        
        if paper.get("source_url"):
            md += f"**链接**: [{paper.get('source_url')}]({paper.get('source_url')})\n\n"
        
        if paper.get("tags"):
            tags_str = ", ".join([f"`{tag}`" for tag in paper.get("tags", [])])
            md += f"**标签**: {tags_str}\n\n"
        
        md += "---\n\n"
    
    return md


def convert_hackernews_to_markdown(data: Dict[str, Any]) -> str:
    """
    将 HackerNews 数据转换为 Markdown
    
    Args:
        data: HackerNews JSON 数据
    
    Returns:
        Markdown 字符串
    """
    if not data.get("success"):
        return f"# HackerNews 数据获取失败\n\n错误: {data.get('error', '未知错误')}\n"
    
    items = data.get("data", [])
    fetched_at = data.get("fetched_at", "")
    
    md = f"# HackerNews 新闻\n\n"
    if fetched_at:
        md += f"**获取时间**: {format_date(fetched_at)}\n\n"
    md += f"**总数**: {len(items)} 条\n\n"
    md += "---\n\n"
    
    for idx, item in enumerate(items, 1):
        md += f"## {idx}. {item.get('title', '无标题')}\n\n"
        
        if item.get("summary"):
            md += f"**摘要**: {item.get('summary')}\n\n"
        
        if item.get("author"):
            md += f"**作者**: {item.get('author')}\n\n"
        
        if item.get("score") is not None:
            md += f"**评分**: {item.get('score')}\n\n"
        
        if item.get("published_date"):
            md += f"**发布日期**: {format_date(item.get('published_date'))}\n\n"
        
        if item.get("source_url"):
            md += f"**链接**: [{item.get('source_url')}]({item.get('source_url')})\n\n"
        
        if item.get("ai_score") is not None:
            md += f"**AI相关性**: {item.get('ai_score'):.2f}\n\n"
        
        md += "---\n\n"
    
    return md


def convert_rss_to_markdown(data: Dict[str, Any]) -> str:
    """
    将 RSS 数据转换为 Markdown
    
    Args:
        data: RSS JSON 数据
    
    Returns:
        Markdown 字符串
    """
    if not data.get("success"):
        return f"# RSS 数据获取失败\n\n错误: {data.get('error', '未知错误')}\n"
    
    data_content = data.get("data", {})
    feeds = data_content.get("feeds", {})
    all_items = data_content.get("all_items", [])
    fetched_at = data.get("fetched_at", "")
    
    md = f"# RSS 订阅内容\n\n"
    if fetched_at:
        md += f"**获取时间**: {format_date(fetched_at)}\n\n"
    md += f"**总数**: {len(all_items)} 条\n"
    md += f"**订阅源数**: {len(feeds)} 个\n\n"
    md += "---\n\n"
    
    # 按订阅源分组显示
    for feed_name, feed_data in feeds.items():
        items = feed_data.get("items", [])
        if not items:
            continue
        
        md += f"## {feed_name}\n\n"
        md += f"**URL**: {feed_data.get('url', '')}\n\n"
        md += f"**条目数**: {len(items)} 条\n\n"
        
        for idx, item in enumerate(items, 1):
            md += f"### {idx}. {item.get('title', '无标题')}\n\n"
            
            if item.get("summary"):
                md += f"**摘要**: {item.get('summary')}\n\n"
            
            if item.get("author"):
                md += f"**作者**: {item.get('author')}\n\n"
            
            if item.get("published_date"):
                md += f"**发布日期**: {format_date(item.get('published_date'))}\n\n"
            
            if item.get("source_url"):
                md += f"**链接**: [{item.get('source_url')}]({item.get('source_url')})\n\n"
            
            if item.get("tags"):
                tags_str = ", ".join([f"`{tag}`" for tag in item.get("tags", [])])
                md += f"**标签**: {tags_str}\n\n"
            
            md += "\n"
        
        md += "---\n\n"
    
    return md


def convert_github_to_markdown(data: Dict[str, Any]) -> str:
    """
    将 GitHub 数据转换为 Markdown
    
    Args:
        data: GitHub JSON 数据
    
    Returns:
        Markdown 字符串
    """
    if not data.get("success"):
        return f"# GitHub 数据获取失败\n\n错误: {data.get('error', '未知错误')}\n"
    
    items = data.get("data", [])
    fetched_at = data.get("fetched_at", "")
    
    md = f"# GitHub 趋势项目\n\n"
    if fetched_at:
        md += f"**获取时间**: {format_date(fetched_at)}\n\n"
    md += f"**总数**: {len(items)} 个\n\n"
    md += "---\n\n"
    
    for idx, item in enumerate(items, 1):
        md += f"## {idx}. {item.get('title', '无标题')}\n\n"
        
        if item.get("summary"):
            md += f"**描述**: {item.get('summary')}\n\n"
        
        if item.get("author"):
            md += f"**作者**: {item.get('author')}\n\n"
        
        if item.get("score") is not None:
            md += f"**Stars**: {item.get('score')}\n\n"
        
        if item.get("published_date"):
            md += f"**创建日期**: {format_date(item.get('published_date'))}\n\n"
        
        if item.get("source_url"):
            md += f"**链接**: [{item.get('source_url')}]({item.get('source_url')})\n\n"
        
        if item.get("tags"):
            tags_str = ", ".join([f"`{tag}`" for tag in item.get("tags", [])])
            md += f"**标签**: {tags_str}\n\n"
        
        if item.get("ai_score") is not None:
            md += f"**AI相关性**: {item.get('ai_score'):.2f}\n\n"
        
        md += "---\n\n"
    
    return md


def convert_json_to_markdown(json_data: Dict[str, Any]) -> str:
    """
    将 JSON 数据转换为 Markdown（自动识别数据源类型）
    
    Args:
        json_data: JSON 数据字典
    
    Returns:
        Markdown 字符串
    """
    source = json_data.get("source", "").lower()
    
    if "arxiv" in source:
        return convert_arxiv_to_markdown(json_data)
    elif "hackernews" in source or "hacker" in source:
        return convert_hackernews_to_markdown(json_data)
    elif "rss" in source:
        return convert_rss_to_markdown(json_data)
    elif "github" in source:
        return convert_github_to_markdown(json_data)
    else:
        # 未知数据源，尝试通用格式
        return f"# {json_data.get('source', '数据')}\n\n" + \
               f"**获取时间**: {json_data.get('fetched_at', '')}\n\n" + \
               f"**总数**: {json_data.get('total_count', 0)}\n\n" + \
               f"```json\n{json.dumps(json_data, ensure_ascii=False, indent=2)}\n```\n"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="将 JSON 数据转换为 Markdown 格式")
    parser.add_argument("input_file", nargs="?", help="输入 JSON 文件路径（可选，默认从 stdin 读取）")
    parser.add_argument("-o", "--output", type=str, help="输出 Markdown 文件路径（可选，默认输出到 stdout）")
    
    args = parser.parse_args()
    
    # 读取 JSON 数据
    try:
        if args.input_file:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        else:
            # 从 stdin 读取
            json_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 读取数据失败: {str(e)}", file=sys.stderr)
        sys.exit(1)
    
    # 转换为 Markdown
    try:
        markdown = convert_json_to_markdown(json_data)
    except Exception as e:
        print(f"错误: 转换失败: {str(e)}", file=sys.stderr)
        sys.exit(1)
    
    # 输出结果
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(markdown)
    else:
        print(markdown)


if __name__ == "__main__":
    main()
