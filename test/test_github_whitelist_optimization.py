"""
测试 GitHub 白名单缓存优化效果

测试场景：
1. 第一次运行：所有项目都需要AI筛选
2. 第二次运行：白名单项目跳过AI筛选，只筛选新项目
3. Token消耗对比
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.msgskill.tools.github_fetcher import fetch_github_trending
from src.msgskill.utils.cache import get_cache


async def test_github_whitelist():
    """测试 GitHub 白名单缓存优化"""
    print("=" * 80)
    print("GitHub 白名单缓存优化测试")
    print("=" * 80)
    print()
    
    cache = get_cache()
    
    # 清空GitHub相关缓存（模拟首次运行）
    print("清空缓存，模拟首次运行...")
    # 注意：这里只清空结果缓存，保留白名单缓存
    cache_keys_to_clear = []
    # 实际使用中cache没有list_keys方法，这里仅作演示
    print("  ⚠️  提示：实际运行时，第一次会进行完整AI筛选")
    print()
    
    # ===== 第一次运行 =====
    print("【第一次运行】- 模拟首次查询（需要AI筛选所有项目）")
    print("-" * 80)
    
    start_time1 = datetime.now()
    result1 = await fetch_github_trending(limit=20)
    end_time1 = datetime.now()
    
    duration1 = (end_time1 - start_time1).total_seconds()
    
    if result1.success:
        items1 = result1.items
        print(f"  ✅ 抓取成功: {len(items1)} 个项目")
        print(f"  ⏱️  耗时: {duration1:.2f} 秒")
        print()
        
        # 统计白名单
        whitelist_count = 0
        for item in items1:
            repo_id = item.source_url.split('/')[-1] if item.source_url else None
            if repo_id:
                whitelist_key = f"github_whitelist_{repo_id}"
                # 这里无法直接统计，实际在代码中已缓存
                whitelist_count += 1
        
        print(f"  📝 预计加入白名单: {len(items1)} 个项目")
    else:
        print(f"  ❌ 抓取失败: {result1.error}")
        return
    
    print()
    print("=" * 80)
    
    # ===== 第二次运行 =====
    print("【第二次运行】- 模拟1天后查询（利用白名单缓存）")
    print("-" * 80)
    print("  等待3秒后执行第二次查询...")
    await asyncio.sleep(3)
    
    start_time2 = datetime.now()
    result2 = await fetch_github_trending(limit=20)
    end_time2 = datetime.now()
    
    duration2 = (end_time2 - start_time2).total_seconds()
    
    if result2.success:
        items2 = result2.items
        print(f"  ✅ 抓取成功: {len(items2)} 个项目")
        print(f"  ⏱️  耗时: {duration2:.2f} 秒")
        print()
        
        # 计算加速比
        if duration1 > 0:
            speedup = ((duration1 - duration2) / duration1 * 100)
            print(f"  ⚡ 速度提升: {speedup:.1f}%")
    else:
        print(f"  ❌ 抓取失败: {result2.error}")
    
    print()
    print("=" * 80)
    print("Token 消耗估算")
    print("=" * 80)
    print()
    
    # Token 消耗估算
    tokens_per_batch = 1500  # 每批25个标题约1500 tokens
    
    # 假设第一次424个项目，全部需要AI筛选
    first_run_projects = 424
    first_run_batches = (first_run_projects + 25 - 1) // 25
    first_run_tokens = first_run_batches * tokens_per_batch
    
    # 假设第二次同样424个项目，但80%在白名单中
    second_run_projects = 424
    whitelist_rate = 0.80  # 80%命中白名单
    new_projects = int(second_run_projects * (1 - whitelist_rate))
    second_run_batches = (new_projects + 25 - 1) // 25
    second_run_tokens = second_run_batches * tokens_per_batch
    
    saved_tokens = first_run_tokens - second_run_tokens
    saved_percentage = (saved_tokens / first_run_tokens * 100) if first_run_tokens > 0 else 0
    
    print("假设场景（424个项目，80%白名单命中率）:")
    print()
    print(f"【第一次运行】")
    print(f"  总项目数: {first_run_projects}")
    print(f"  需AI筛选: {first_run_projects} (100%)")
    print(f"  AI批次数: {first_run_batches} 批")
    print(f"  Token消耗: ~{first_run_tokens:,} tokens")
    print()
    
    print(f"【第二次运行】")
    print(f"  总项目数: {second_run_projects}")
    print(f"  白名单命中: {second_run_projects - new_projects} ({whitelist_rate*100:.0f}%)")
    print(f"  需AI筛选: {new_projects} ({(1-whitelist_rate)*100:.0f}%)")
    print(f"  AI批次数: {second_run_batches} 批")
    print(f"  Token消耗: ~{second_run_tokens:,} tokens")
    print()
    
    print(f"【优化效果】")
    print(f"  💰 节省Token: ~{saved_tokens:,} tokens")
    print(f"  📊 节省比例: {saved_percentage:.1f}%")
    print()
    
    # 长期效果估算
    print("=" * 80)
    print("长期效果估算（假设每天查询1次，持续30天）")
    print("=" * 80)
    print()
    
    # 假设白名单命中率逐步提升
    days = 30
    total_tokens_without_whitelist = first_run_tokens * days
    
    # 白名单命中率提升曲线：第1天0%，逐步提升到第30天90%
    total_tokens_with_whitelist = 0
    for day in range(1, days + 1):
        # 命中率从0%线性增长到90%
        daily_whitelist_rate = min(0.9, (day - 1) / days * 0.9)
        daily_new_projects = int(second_run_projects * (1 - daily_whitelist_rate))
        daily_batches = (daily_new_projects + 25 - 1) // 25
        daily_tokens = daily_batches * tokens_per_batch
        total_tokens_with_whitelist += daily_tokens
    
    saved_tokens_30days = total_tokens_without_whitelist - total_tokens_with_whitelist
    saved_percentage_30days = (saved_tokens_30days / total_tokens_without_whitelist * 100)
    
    print(f"无白名单（30天）: ~{total_tokens_without_whitelist:,} tokens")
    print(f"有白名单（30天）: ~{total_tokens_with_whitelist:,} tokens")
    print(f"30天节省: ~{saved_tokens_30days:,} tokens ({saved_percentage_30days:.1f}%)")
    print()
    
    # 成本估算
    price_per_million = 0.14  # DeepSeek价格
    cost_without = (total_tokens_without_whitelist / 1_000_000) * price_per_million
    cost_with = (total_tokens_with_whitelist / 1_000_000) * price_per_million
    saved_cost = cost_without - cost_with
    
    print(f"成本对比 (DeepSeek $0.14/1M tokens):")
    print(f"  无白名单: ${cost_without:.2f} (30天)")
    print(f"  有白名单: ${cost_with:.2f} (30天)")
    print(f"  💵 节省: ${saved_cost:.2f}")
    print()
    
    print("=" * 80)
    print("优化方案总结")
    print("=" * 80)
    print()
    print("✅ GitHub 白名单缓存优化")
    print("   - 通过AI筛选的项目自动加入白名单")
    print("   - 白名单缓存30天，避免重复筛选")
    print("   - 白名单命中率随时间提升（最终可达80-90%）")
    print("   - 预计节省70-85%的AI筛选token消耗")
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_github_whitelist())