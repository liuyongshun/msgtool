#!/usr/bin/env python3
"""
测试各数据源各2条数据同步到Notion（统一英文字段）
"""

import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.msgskill.models import ArticleItem
from src.msgskill.utils.notion_sync import get_notion_sync

def create_test_items():
    """创建测试数据"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    items = []
    
    # RSS测试数据（2条）
    for i in range(1, 3):
        items.append(ArticleItem(
            title=f"RSS测试文章 {i} - {timestamp}",
            source_url=f"https://test-rss.example.com/article_{i}_{timestamp}",
            summary=f"这是RSS测试文章{i}的摘要内容，用于测试Notion同步功能。",
            source_type="rss",
            article_tag="AI资讯",
            published_date=datetime.now().isoformat()
        ))
    
    # HackerNews测试数据（2条）
    for i in range(1, 3):
        items.append(ArticleItem(
            title=f"HackerNews测试新闻 {i} - {timestamp}",
            source_url=f"https://test-hn.example.com/news_{i}_{timestamp}",
            summary=f"这是HackerNews测试新闻{i}的摘要内容，用于测试Notion同步功能。",
            source_type="hackernews",
            article_tag="AI资讯",
            published_date=datetime.now().isoformat()
        ))
    
    # GitHub测试数据（2条）
    for i in range(1, 3):
        items.append(ArticleItem(
            title=f"GitHub测试项目 {i} - {timestamp}",
            source_url=f"https://test-github.example.com/project_{i}_{timestamp}",
            summary=f"这是GitHub测试项目{i}的摘要内容，用于测试Notion同步功能。",
            source_type="github",
            article_tag="AI工具",
            published_date=datetime.now().isoformat()
        ))
    
    return items

def main():
    """主函数"""
    print("=" * 60)
    print("🔧 Notion同步器已初始化")
    sync = get_notion_sync()
    print(f"   已配置数据库: {list(sync.databases.keys())}")
    print()
    
    # 创建测试数据
    test_items = create_test_items()
    
    print("=" * 60)
    print("📝 测试数据（各2条）")
    print("=" * 60)
    
    for i, item in enumerate(test_items, 1):
        print(f"\n{i}. {item.source_type.upper()}:")
        print(f"   标题: {item.title}")
        print(f"   链接: {item.source_url}")
        print(f"   日期: {item.published_date}")
    
    print("\n" + "=" * 60)
    print("🔄 开始同步到Notion...")
    print("=" * 60)
    
    # 按数据源分组同步
    results = {
        "rss": {"success": 0, "failed": 0, "skipped": 0},
        "hackernews": {"success": 0, "failed": 0, "skipped": 0},
        "github": {"success": 0, "failed": 0, "skipped": 0}
    }
    
    for item in test_items:
        source_type = item.source_type
        print(f"\n📤 同步 {source_type.upper()} 数据...")
        
        try:
            # 先检查是否已存在
            database_id = sync.get_database_id(source_type)
            existing_page_id = sync._check_page_exists(item.source_url, database_id, source_type)
            
            if existing_page_id:
                results[source_type]["skipped"] += 1
                print(f"   ⏭️  已存在，跳过: {item.title}...")
            else:
                # 同步数据
                success = sync.sync_item(item, skip_existing=False)
                if success:
                    results[source_type]["success"] += 1
                    print(f"   ✅ 成功同步: {item.title}...")
                else:
                    results[source_type]["failed"] += 1
                    print(f"   ❌ 同步失败: {item.title}...")
        except Exception as e:
            results[source_type]["failed"] += 1
            print(f"   ❌ 同步失败: {item.title}...")
            print(f"      错误: {str(e)}")
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 同步结果汇总")
    print("=" * 60)
    
    all_success = True
    for source_type, stats in results.items():
        total = stats["success"] + stats["failed"] + stats["skipped"]
        status = "✅" if stats["failed"] == 0 else "❌"
        print(f"   {source_type.upper()}: {status} 成功:{stats['success']} 失败:{stats['failed']} 跳过:{stats['skipped']} (共{total}条)")
        if stats["failed"] > 0:
            all_success = False
    
    if all_success:
        print("\n✅ 所有测试数据同步成功！")
        print("\n💡 请到Notion数据库查看：")
        print("   - RSS数据库：应看到2条测试数据（使用英文字段：Title, Source URL, Summary, Published Date）")
        print("   - HackerNews数据库：应看到2条测试数据（使用英文字段：Title, Source URL, Summary, Published Date）")
        print("   - GitHub数据库：应看到2条测试数据（使用英文字段：Title, Source URL, Summary, Published Date）")
    else:
        print("\n⚠️ 部分测试数据同步失败")

if __name__ == "__main__":
    main()
