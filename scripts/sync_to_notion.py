#!/usr/bin/env python3
"""
Notion同步脚本 - 将output数据同步到Notion数据库

使用方法:
    # 同步指定日期的所有文件
    python scripts/sync_to_notion.py --date 2026-02-10
    
    # 同步指定文件
    python scripts/sync_to_notion.py --file output/daily/2026-02-10/github_20260210_000031.json
    
    # 同步今天的所有文件
    python scripts/sync_to_notion.py
    
    # 同步所有日期的文件（谨慎使用）
    python scripts/sync_to_notion.py --all
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.msgskill.utils.notion_sync import get_notion_sync
from src.msgskill.output import get_output_manager
from src.msgskill.utils.logger import logger


def sync_file(file_path: Path, notion_sync) -> dict:
    """同步单个文件"""
    logger.info(f"📄 同步文件: {file_path.name}")
    result = notion_sync.sync_json_file(file_path)
    
    if result["success"]:
        logger.info(
            f"✅ 完成: 总计{result['total']}条, "
            f"已同步{result['synced']}条, "
            f"跳过{result['skipped']}条, "
            f"失败{result['failed']}条"
        )
    else:
        logger.error(f"❌ 失败: {result.get('reason', '未知错误')}")
    
    return result


def sync_date(date_str: str, notion_sync) -> dict:
    """同步指定日期的所有文件"""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logger.error(f"❌ 日期格式错误: {date_str}，请使用 YYYY-MM-DD 格式")
        return {"success": False}
    
    output_manager = get_output_manager()
    daily_dir = output_manager.get_daily_dir(date)
    
    if not daily_dir.exists():
        logger.warning(f"⚠️ 目录不存在: {daily_dir}")
        return {"success": False}
    
    json_files = list(daily_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"⚠️ 目录中没有JSON文件: {daily_dir}")
        return {"success": False}
    
    logger.info(f"📅 同步日期: {date_str}，找到 {len(json_files)} 个文件")
    
    total_stats = {
        "total": 0,
        "synced": 0,
        "skipped": 0,
        "failed": 0
    }
    
    for json_file in json_files:
        result = sync_file(json_file, notion_sync)
        if result.get("success"):
            total_stats["total"] += result.get("total", 0)
            total_stats["synced"] += result.get("synced", 0)
            total_stats["skipped"] += result.get("skipped", 0)
            total_stats["failed"] += result.get("failed", 0)
    
    logger.info(
        f"\n📊 日期 {date_str} 汇总:\n"
        f"   总计: {total_stats['total']} 条\n"
        f"   已同步: {total_stats['synced']} 条\n"
        f"   跳过: {total_stats['skipped']} 条\n"
        f"   失败: {total_stats['failed']} 条"
    )
    
    return {"success": True, **total_stats}


def sync_all(notion_sync) -> dict:
    """同步所有日期的文件"""
    output_manager = get_output_manager()
    base_dir = output_manager.base_dir / "daily"
    
    if not base_dir.exists():
        logger.warning(f"⚠️ 目录不存在: {base_dir}")
        return {"success": False}
    
    date_dirs = [d for d in base_dir.iterdir() if d.is_dir()]
    if not date_dirs:
        logger.warning(f"⚠️ 没有找到日期目录")
        return {"success": False}
    
    logger.info(f"📦 同步所有日期，找到 {len(date_dirs)} 个日期目录")
    
    total_stats = {
        "total": 0,
        "synced": 0,
        "skipped": 0,
        "failed": 0
    }
    
    for date_dir in sorted(date_dirs):
        date_str = date_dir.name
        result = sync_date(date_str, notion_sync)
        if result.get("success"):
            total_stats["total"] += result.get("total", 0)
            total_stats["synced"] += result.get("synced", 0)
            total_stats["skipped"] += result.get("skipped", 0)
            total_stats["failed"] += result.get("failed", 0)
    
    logger.info(
        f"\n🎉 全部完成汇总:\n"
        f"   总计: {total_stats['total']} 条\n"
        f"   已同步: {total_stats['synced']} 条\n"
        f"   跳过: {total_stats['skipped']} 条\n"
        f"   失败: {total_stats['failed']} 条"
    )
    
    return {"success": True, **total_stats}


def main():
    parser = argparse.ArgumentParser(
        description="将output数据同步到Notion数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--date",
        type=str,
        help="同步指定日期 (格式: YYYY-MM-DD)，默认为今天"
    )
    
    parser.add_argument(
        "--file",
        type=str,
        help="同步指定文件路径"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="同步所有日期的文件（谨慎使用）"
    )
    
    args = parser.parse_args()
    
    # 获取Notion同步器
    notion_sync = get_notion_sync()
    if not notion_sync:
        logger.error("❌ Notion同步未配置或未启用")
        logger.info("💡 请在 config/sources.json 中配置 notion_sync:")
        logger.info("   1. enabled: true")
        logger.info("   2. api_token: 你的Notion Integration Token")
        logger.info("   3. database_id: 你的Notion数据库ID")
        sys.exit(1)
    
    if not notion_sync.enabled:
        logger.error("❌ Notion同步已禁用")
        sys.exit(1)
    
    # 执行同步
    if args.file:
        # 同步指定文件
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error(f"❌ 文件不存在: {file_path}")
            sys.exit(1)
        result = sync_file(file_path, notion_sync)
        sys.exit(0 if result.get("success") else 1)
    
    elif args.all:
        # 同步所有日期
        result = sync_all(notion_sync)
        sys.exit(0 if result.get("success") else 1)
    
    else:
        # 同步指定日期或今天
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        result = sync_date(date_str, notion_sync)
        sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
