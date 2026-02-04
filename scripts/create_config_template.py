#!/usr/bin/env python3
"""
创建配置文件模板
从 sources.json 中移除敏感信息（API密钥），生成 sources.json.example
"""

import json
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "sources.json"
TEMPLATE_FILE = PROJECT_ROOT / "config" / "sources.json.example"


def mask_api_key(api_key: str) -> str:
    """掩码API密钥"""
    if not api_key or len(api_key) < 10:
        return "your-api-key-here"
    return "your-api-key-here"


def create_template():
    """创建配置模板"""
    print("🔧 创建配置文件模板...")
    print(f"   源文件: {CONFIG_FILE}")
    print(f"   目标文件: {TEMPLATE_FILE}")
    print()
    
    if not CONFIG_FILE.exists():
        print(f"❌ 错误: 配置文件不存在 {CONFIG_FILE}")
        sys.exit(1)
    
    # 读取原始配置
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 移除敏感信息
    if "llm" in config and "api_key" in config["llm"]:
        original_key = config["llm"]["api_key"]
        config["llm"]["api_key"] = mask_api_key(original_key)
        print(f"✓ 已掩码 LLM API 密钥")
    
    # 写入模板文件
    with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"✅ 配置模板已创建: {TEMPLATE_FILE}")
    print()
    print("📝 使用方法:")
    print("   1. 复制 sources.json.example 为 sources.json")
    print("   2. 在 sources.json 中填入真实的 API 密钥")
    print("   3. 或者使用 .env 文件配置环境变量")


if __name__ == "__main__":
    create_template()