#!/bin/bash
#
# 缓存清理脚本
# 功能：删除30天前的缓存文件
# 使用：./scripts/cleanup_cache.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CACHE_DIR="$PROJECT_ROOT/.cache"

echo "================================================"
echo "缓存清理脚本"
echo "================================================"
echo ""

# 检查缓存目录是否存在
if [ ! -d "$CACHE_DIR" ]; then
    echo "⚠️  缓存目录不存在: $CACHE_DIR"
    exit 0
fi

cd "$CACHE_DIR"

# 统计清理前的文件数量和大小
BEFORE_COUNT=$(find . -type f | wc -l)
BEFORE_SIZE=$(du -sh . 2>/dev/null | cut -f1)

echo "清理前统计:"
echo "  缓存目录: $CACHE_DIR"
echo "  缓存文件数: $BEFORE_COUNT"
echo "  目录大小: $BEFORE_SIZE"
echo ""

# 分类统计缓存类型
echo "缓存类型分布:"
GITHUB_COUNT=$(find . -name "github_*" -type f | wc -l)
ARXIV_COUNT=$(find . -name "arxiv_*" -type f | wc -l)
OTHER_COUNT=$((BEFORE_COUNT - GITHUB_COUNT - ARXIV_COUNT))

echo "  GitHub 白名单: $GITHUB_COUNT 个"
echo "  arXiv 翻译: $ARXIV_COUNT 个"
echo "  其他缓存: $OTHER_COUNT 个"
echo ""

# 删除30天前的缓存文件
echo "正在删除30天前的缓存文件..."
DELETED_COUNT=$(find . -type f -mtime +30 -print -delete | wc -l)

# 统计清理后的文件数量和大小
AFTER_COUNT=$(find . -type f | wc -l)
AFTER_SIZE=$(du -sh . 2>/dev/null | cut -f1)

echo ""
echo "清理完成!"
echo "  删除文件数: $DELETED_COUNT"
echo "  剩余文件数: $AFTER_COUNT"
echo "  当前大小: $AFTER_SIZE"
echo ""

if [ $DELETED_COUNT -gt 0 ]; then
    echo "✅ 已删除 $DELETED_COUNT 个过期缓存文件"
else
    echo "✅ 没有需要清理的缓存文件"
fi

echo ""
echo "💡 提示: 缓存会自动过期，通常不需要手动清理"
echo "   - GitHub 白名单: 30天过期"
echo "   - arXiv 翻译: 24小时过期"
echo "   - API 结果: 10分钟到1小时过期"
echo ""
echo "================================================"