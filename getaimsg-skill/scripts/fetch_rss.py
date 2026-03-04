#!/usr/bin/env python3
"""
RSS 数据获取脚本
从 RSS 订阅源获取 AI 相关文章，输出精简 JSON 格式
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

# 添加 agent_skill 路径以导入本地 tools 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.rss_reader import fetch_rss_feeds

# 导入 Skill 配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.skill_config import get_config

# 导入 Markdown 转换工具
sys.path.insert(0, str(Path(__file__).parent))
from json_to_markdown import convert_json_to_markdown


def simplify_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    精简 RSS 项数据，只保留核心字段
    
    Args:
        item: 原始 RSS 项数据
    
    Returns:
        精简后的 RSS 项数据
    """
    return {
        "title": item.get("title", ""),
        "summary": item.get("summary", "")[:300],
        "source_url": item.get("link", ""),
        "published_date": item.get("published"),
        "source_type": "rss",
        "article_tag": "AI资讯",
        "author": item.get("author"),
        "tags": item.get("tags", [])[:5],
        "ai_score": item.get("ai_score"),
    }


async def fetch_rss_data(max_results: int = None, config_path: str = None) -> Dict[str, Any]:
    """
    获取 RSS 订阅数据
    
    Args:
        max_results: 每个订阅源最多获取的条目数
        config_path: 配置文件路径
    
    Returns:
        包含 RSS 数据的字典
    """
    try:
        # 加载配置
        config = get_config(config_path)
        rss_config = config.get_rss_config()
        
        if not rss_config.get("enabled", False):
            return {
                "success": False,
                "error": "RSS 数据源未启用",
                "source": "rss"
            }
        
        # 获取配置参数
        if max_results is None:
            max_results = rss_config.get("max_results", 10)
        
        feeds = config.get_rss_feeds(enabled_only=True)
        
        if not feeds:
            return {
                "success": False,
                "error": "没有启用的 RSS 订阅源",
                "source": "rss"
            }
        
        # 获取所有订阅源的 URL
        feed_urls = [feed.get("url") for feed in feeds if feed.get("url")]
        
        if not feed_urls:
            return {
                "success": False,
                "error": "没有有效的 RSS 订阅源 URL",
                "source": "rss"
            }
        
        # 获取数据
        result = await fetch_rss_feeds(
            feed_urls=feed_urls,
            limit=max_results
        )
        
        if not isinstance(result, dict):
            return {
                "success": False,
                "error": "返回数据格式错误",
                "source": "rss"
            }
        
        # 处理 feeds 数据，精简输出
        simplified_feeds = {}
        all_items = []
        
        feeds_data = result.get("feeds", {})
        for feed_name, feed_data in feeds_data.items():
            if not isinstance(feed_data, dict):
                continue
            
            items = feed_data.get("items", [])
            simplified_items = []
            
            for item in items:
                simplified = simplify_item(item)
                if simplified:
                    simplified_items.append(simplified)
                    all_items.append(simplified)
            
            simplified_feeds[feed_name] = {
                "url": feed_data.get("url", ""),
                "title": feed_data.get("title", feed_name),
                "items_count": len(simplified_items),
                "items": simplified_items
            }
        
        return {
            "success": True,
            "source": "RSS",
            "fetched_at": datetime.now().isoformat(),
            "total_count": len(all_items),
            "feeds_count": len(simplified_feeds),
            "errors_count": result.get("errors_count", 0),
            "data": {
                "feeds": simplified_feeds,
                "all_items": all_items  # 扁平化的所有条目
            }
        }
        
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"配置文件未找到: {str(e)}",
            "source": "rss"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取数据失败: {str(e)}",
            "source": "rss"
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="获取 RSS 订阅数据")
    parser.add_argument("--config-path", type=str, help="配置文件路径（可选）")
    parser.add_argument("--max-results", type=int, help="每个订阅源最多获取的条目数")
    parser.add_argument("--output-format", choices=["json", "markdown"], default="markdown", help="输出格式（默认：markdown）")
    parser.add_argument("--output-file", type=str, help="输出文件路径（可选，默认写入 output/ 目录）")

    args = parser.parse_args()

    # 获取数据
    result = asyncio.run(fetch_rss_data(
        max_results=args.max_results,
        config_path=args.config_path
    ))

    # 确定默认输出路径：output/rss_<时间戳>.<ext>
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "md" if args.output_format == "markdown" else "json"
    default_path = output_dir / f"rss_{timestamp}.{ext}"
    output_path = Path(args.output_file) if args.output_file else default_path

    # 生成内容
    if args.output_format == "markdown":
        content = convert_json_to_markdown(result)
    else:
        content = json.dumps(result, ensure_ascii=False, indent=2)

    # 写入文件并打印路径
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(content)
    print(f"\n📄 已保存至: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
