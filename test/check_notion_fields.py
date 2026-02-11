#!/usr/bin/env python3
"""
检查Notion数据库的字段名称
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from src.msgskill.config import get_config

def check_database_fields():
    """检查数据库字段"""
    config = get_config()
    notion_config = config.get_notion_config()
    
    if not notion_config or not notion_config.get("enabled"):
        print("❌ Notion同步未配置")
        return
    
    api_token = notion_config.get("api_token")
    databases_config = notion_config.get("databases", {})
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    for source_type, db_config in databases_config.items():
        if isinstance(db_config, dict):
            database_id = db_config.get("database_id", "")
        else:
            database_id = db_config if isinstance(db_config, str) else ""
        
        if not database_id:
            continue
        
        print(f"\n{'='*60}")
        print(f"📊 {source_type.upper()} 数据库字段")
        print(f"{'='*60}")
        print(f"Database ID: {database_id}\n")
        
        try:
            response = httpx.get(
                f"https://api.notion.com/v1/databases/{database_id}",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                db_info = response.json()
                title = db_info.get('title', [{}])[0].get('plain_text', 'N/A')
                print(f"数据库标题: {title}\n")
                
                properties = db_info.get('properties', {})
                print(f"字段列表（共 {len(properties)} 个）:")
                print("-" * 60)
                
                for prop_name, prop_info in properties.items():
                    prop_type = prop_info.get('type', 'unknown')
                    print(f"  • {prop_name:20s} ({prop_type})")
                
                print("\n💡 代码期望的字段名称:")
                print("  • Title (title类型)")
                print("  • Source URL (url类型)")
                print("  • Summary (rich_text类型)")
                
            else:
                print(f"❌ 获取失败 (HTTP {response.status_code})")
                print(f"错误: {response.text[:200]}")
        except Exception as e:
            print(f"❌ 错误: {e}")

if __name__ == "__main__":
    check_database_fields()
