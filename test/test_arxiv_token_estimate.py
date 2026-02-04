"""
arXiv 论文 Token 消耗估算

计算优化前后的 token 消耗对比
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.msgskill.config import get_config

def estimate_token_consumption():
    """估算优化前后的 token 消耗"""
    print("=" * 80)
    print("arXiv 论文 Token 消耗估算")
    print("=" * 80)
    print()
    
    # 获取配置
    config = get_config()
    scheduler_config = config._config.get("global_settings", {}).get("scheduler", {})
    arxiv_config = scheduler_config.get("tasks", {}).get("arxiv", {})
    
    # 当前配置
    max_results = arxiv_config.get("max_results", 20)
    translation_strategy = arxiv_config.get("translation_strategy", {})
    selective_enabled = translation_strategy.get("selective_translation", True)
    min_authors = translation_strategy.get("min_authors", 2)
    
    print("当前配置:")
    print(f"  - 每分类论文数: {max_results} 篇")
    print(f"  - 选择性翻译: {'启用' if selective_enabled else '禁用'}")
    print(f"  - 最小作者数: {min_authors}")
    print()
    
    # 统计启用的分类数量
    arxiv_sources = config._config.get("sources", {}).get("arxiv", {})
    enabled_categories = [cat for cat, cfg in arxiv_sources.items() if cfg.get("enabled", True)]
    category_count = len(enabled_categories)
    
    print(f"启用的论文分类: {category_count} 个")
    print(f"分类列表: {', '.join(enabled_categories)}")
    print()
    
    # Token 消耗估算
    tokens_per_paper = 800  # 每篇论文翻译约800 tokens
    
    print("=" * 80)
    print("Token 消耗对比")
    print("=" * 80)
    print()
    
    # 优化前：50篇 × 13个分类 × 全部翻译
    old_max = 50
    old_total_papers = old_max * category_count
    old_tokens = old_total_papers * tokens_per_paper
    
    print("【优化前】")
    print(f"  论文数量: {old_max} 篇/分类 × {category_count} 分类 = {old_total_papers} 篇")
    print(f"  翻译策略: 全部翻译")
    print(f"  Token 消耗: ~{old_tokens:,} tokens/天")
    print()
    
    # 优化后：20篇 × 13个分类 × 选择性翻译（假设60%论文是多作者）
    new_total_papers = max_results * category_count
    
    if selective_enabled:
        # 假设60%的论文作者数>=2
        translation_rate = 0.6
        papers_to_translate = int(new_total_papers * translation_rate)
        new_tokens = papers_to_translate * tokens_per_paper
        
        print("【优化后】")
        print(f"  论文数量: {max_results} 篇/分类 × {category_count} 分类 = {new_total_papers} 篇")
        print(f"  翻译策略: 选择性翻译（作者数>={min_authors}）")
        print(f"  预估翻译: {papers_to_translate} 篇 ({translation_rate*100:.0f}%)")
        print(f"  Token 消耗: ~{new_tokens:,} tokens/天")
    else:
        new_tokens = new_total_papers * tokens_per_paper
        
        print("【优化后】")
        print(f"  论文数量: {max_results} 篇/分类 × {category_count} 分类 = {new_total_papers} 篇")
        print(f"  翻译策略: 全部翻译")
        print(f"  Token 消耗: ~{new_tokens:,} tokens/天")
    
    print()
    print("=" * 80)
    print("优化效果")
    print("=" * 80)
    print()
    
    saved_tokens = old_tokens - new_tokens
    saved_percentage = (saved_tokens / old_tokens * 100) if old_tokens > 0 else 0
    
    print(f"  💰 节省 Token: ~{saved_tokens:,} tokens/天")
    print(f"  📊 节省比例: {saved_percentage:.1f}%")
    print()
    
    # 成本估算（假设 DeepSeek 价格：1M tokens = $0.14）
    price_per_million = 0.14
    old_cost = (old_tokens / 1_000_000) * price_per_million
    new_cost = (new_tokens / 1_000_000) * price_per_million
    saved_cost = old_cost - new_cost
    
    print("成本估算 (DeepSeek 价格: $0.14/1M tokens):")
    print(f"  优化前: ${old_cost:.2f}/天 ≈ ${old_cost * 30:.2f}/月")
    print(f"  优化后: ${new_cost:.2f}/天 ≈ ${new_cost * 30:.2f}/月")
    print(f"  💵 月节省: ${saved_cost * 30:.2f}")
    print()
    
    print("=" * 80)
    print("优化方案总结")
    print("=" * 80)
    print()
    print("✅ 方案A: 选择性翻译")
    print(f"   - 只翻译作者数>={min_authors}的高质量论文")
    print(f"   - 预估节省: ~{(1-0.6)*100:.0f}% 翻译量")
    print()
    print("✅ 方案B: 翻译缓存")
    print(f"   - 相同论文24小时内不重复翻译")
    print(f"   - 节省重复调用的token消耗")
    print()
    print("✅ 方案C: 减少论文数量")
    print(f"   - 从每分类50篇减少到{max_results}篇")
    print(f"   - 减少{((old_max - max_results) / old_max * 100):.0f}%的抓取量")
    print()
    print("=" * 80)


if __name__ == "__main__":
    estimate_token_consumption()