#!/usr/bin/env python3
"""
HackerNews 数据获取脚本
从 HackerNews 获取 AI 相关新闻，输出精简 JSON 格式
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

# 添加 agent_skill 路径以导入本地 tools 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.news_scraper import fetch_ai_news

# 导入 Skill 配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.skill_config import get_config

# 导入 Markdown 转换工具
sys.path.insert(0, str(Path(__file__).parent))
from json_to_markdown import convert_json_to_markdown


def simplify_item(item: Any) -> Dict[str, Any]:
    """
    精简新闻项数据，只保留核心字段
    
    Args:
        item: 原始新闻项（ArticleItem 或 dict）
    
    Returns:
        精简后的新闻项数据
    """
    if hasattr(item, 'model_dump'):
        # ArticleItem 对象
        data = item.model_dump()
    elif isinstance(item, dict):
        data = item
    else:
        return {}
    
    return {
        "title": data.get("title", ""),
        "summary": data.get("summary", "")[:300],
        "source_url": data.get("source_url", ""),
        "published_date": data.get("published_date"),
        "source_type": "hackernews",
        "article_tag": data.get("article_tag", "AI资讯"),
        "author": data.get("author"),
        "score": data.get("score"),
        "tags": data.get("tags", [])[:5],
        "ai_score": data.get("ai_score"),
    }


async def fetch_hackernews_data(max_results: int = None, config_path: str = None) -> Dict[str, Any]:
    """
    获取 HackerNews 新闻数据
    
    Args:
        max_results: 最多获取的新闻数
        config_path: 配置文件路径
    
    Returns:
        包含新闻数据的字典
    """
    try:
        # 加载配置
        config = get_config(config_path)
        hn_config = config.get_hackernews_config()
        
        if not hn_config.get("enabled", False):
            return {
                "success": False,
                "error": "HackerNews 数据源未启用",
                "source": "hackernews"
            }
        
        # 获取配置参数
        if max_results is None:
            max_results = hn_config.get("max_results", 15)
        
        # 获取数据
        result = await fetch_ai_news(
            source="hackernews",
            limit=max_results
        )
        
        if not result.success:
            return {
                "success": False,
                "error": result.error or "获取数据失败",
                "source": "hackernews"
            }
        
        # 精简数据
        simplified_items = []
        for item in result.items:
            simplified = simplify_item(item)
            if simplified:
                simplified_items.append(simplified)
        
        return {
            "success": True,
            "source": "HackerNews",
            "fetched_at": datetime.now().isoformat(),
            "total_count": len(simplified_items),
            "data": simplified_items
        }
        
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"配置文件未找到: {str(e)}",
            "source": "hackernews"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取数据失败: {str(e)}",
            "source": "hackernews"
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="获取 HackerNews 新闻数据")
    parser.add_argument("--config-path", type=str, help="配置文件路径（可选）")
    parser.add_argument("--max-results", type=int, help="最多获取的新闻数")
    parser.add_argument("--output-format", choices=["json", "markdown"], default="markdown", help="输出格式（默认：markdown）")
    parser.add_argument("--output-file", type=str, help="输出文件路径（可选，默认写入 output/ 目录）")

    args = parser.parse_args()

    # 获取数据
    result = asyncio.run(fetch_hackernews_data(
        max_results=args.max_results,
        config_path=args.config_path
    ))

    # 确定默认输出路径：output/hackernews_<时间戳>.<ext>
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "md" if args.output_format == "markdown" else "json"
    default_path = output_dir / f"hackernews_{timestamp}.{ext}"
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
