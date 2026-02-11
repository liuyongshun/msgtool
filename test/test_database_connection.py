#!/usr/bin/env python3
"""
测试Notion数据库连接
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from src.msgskill.config import get_config

def test_databases():
    """测试所有数据库连接"""
    config = get_config()
    notion_config = config.get_notion_config()
    
    if not notion_config or not notion_config.get("enabled"):
        print("❌ Notion同步未配置或未启用")
        return False
    
    api_token = notion_config.get("api_token")
    databases_config = notion_config.get("databases", {})
    
    print(f"🔑 API Token: {api_token[:20]}...\n")
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    all_success = True
    
    for source_type, db_config in databases_config.items():
        if isinstance(db_config, dict):
            database_id = db_config.get("database_id", "")
        else:
            database_id = db_config if isinstance(db_config, str) else ""
        
        if not database_id:
            print(f"⚠️ {source_type}: 未配置数据库ID")
            continue
        
        print(f"📊 测试 {source_type} 数据库...")
        print(f"   Database ID: {database_id}")
        
        try:
            response = httpx.get(
                f"https://api.notion.com/v1/databases/{database_id}",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                db_info = response.json()
                title = db_info.get('title', [{}])[0].get('plain_text', 'N/A')
                print(f"   ✅ 连接成功！")
                print(f"   数据库标题: {title}")
                print()
            else:
                print(f"   ❌ 连接失败 (HTTP {response.status_code})")
                print(f"   错误: {response.text[:200]}")
                print()
                all_success = False
        except Exception as e:
            print(f"   ❌ 连接失败: {e}")
            print()
            all_success = False
    
    return all_success

if __name__ == "__main__":
    success = test_databases()
    sys.exit(0 if success else 1)
