#!/usr/bin/env python3
"""
arXiv 数据获取脚本
从 arXiv 获取 AI 相关论文，输出精简 JSON 格式
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List

# 添加 agent_skill 路径以导入本地 tools 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.arxiv_fetcher import fetch_arxiv_papers, ARXIV_CATEGORIES

# 导入 Skill 配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.skill_config import get_config

# 导入 Markdown 转换工具
sys.path.insert(0, str(Path(__file__).parent))
from json_to_markdown import convert_json_to_markdown


def simplify_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """
    精简论文数据，只保留核心字段
    
    Args:
        paper: 原始论文数据
    
    Returns:
        精简后的论文数据
    """
    return {
        "title": paper.get("title", ""),
        "summary": paper.get("summary", "")[:300],  # 限制摘要长度
        "source_url": paper.get("pdf_url") or paper.get("arxiv_url", ""),
        "published_date": paper.get("published"),
        "source_type": "arxiv",
        "article_tag": "AI论文",
        "author": ", ".join(paper.get("authors", [])[:3]),  # 最多3个作者
        "tags": paper.get("categories", [])[:5],  # 最多5个标签
    }


async def fetch_arxiv_data(max_results: int = None, config_path: str = None) -> Dict[str, Any]:
    """
    获取 arXiv 论文数据
    
    Args:
        max_results: 每个分类最多获取的论文数
        config_path: 配置文件路径
    
    Returns:
        包含论文数据的字典
    """
    try:
        # 加载配置
        config = get_config(config_path)
        arxiv_config = config.get_arxiv_config()
        
        if not arxiv_config.get("enabled", False):
            return {
                "success": False,
                "error": "arXiv 数据源未启用",
                "source": "arxiv"
            }
        
        # 获取配置参数
        if max_results is None:
            max_results = arxiv_config.get("max_results", 20)
        
        categories = config.get_arxiv_categories(enabled_only=True)
        
        if not categories:
            return {
                "success": False,
                "error": "没有启用的 arXiv 分类",
                "source": "arxiv"
            }
        
        # 并发获取所有分类的论文（最多 5 个并发，避免限流）
        enabled_categories = [c for c in categories if c.get("key")]

        semaphore = asyncio.Semaphore(5)

        async def fetch_one(category_info):
            category_key = category_info.get("key")
            async with semaphore:
                try:
                    result = await fetch_arxiv_papers(
                        category=category_key,
                        max_results=max_results
                    )
                    if "error" in result:
                        return []
                    return [simplify_paper(p) for p in (result.get("papers") or [])]
                except Exception:
                    return []

        results = await asyncio.gather(*[fetch_one(c) for c in enabled_categories])
        all_papers = [paper for batch in results for paper in batch]
        
        # 去重（基于 source_url）
        seen_urls = set()
        unique_papers = []
        for paper in all_papers:
            url = paper.get("source_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_papers.append(paper)
        
        return {
            "success": True,
            "source": "arXiv",
            "fetched_at": datetime.now().isoformat(),
            "total_count": len(unique_papers),
            "data": unique_papers
        }
        
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"配置文件未找到: {str(e)}",
            "source": "arxiv"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取数据失败: {str(e)}",
            "source": "arxiv"
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="获取 arXiv 论文数据")
    parser.add_argument("--config-path", type=str, help="配置文件路径（可选）")
    parser.add_argument("--max-results", type=int, help="每个分类最多获取的论文数")
    parser.add_argument("--output-format", choices=["json", "markdown"], default="markdown", help="输出格式（默认：markdown）")
    parser.add_argument("--output-file", type=str, help="输出文件路径（可选，默认写入 output/ 目录）")

    args = parser.parse_args()

    # 获取数据
    result = asyncio.run(fetch_arxiv_data(
        max_results=args.max_results,
        config_path=args.config_path
    ))

    # 确定默认输出路径：output/arxiv_<时间戳>.<ext>
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "md" if args.output_format == "markdown" else "json"
    default_path = output_dir / f"arxiv_{timestamp}.{ext}"
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
