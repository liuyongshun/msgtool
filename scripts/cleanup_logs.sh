#!/bin/bash
#
# 日志清理脚本
# 功能：删除7天前的日志文件
# 使用：./scripts/cleanup_logs.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"

echo "================================================"
echo "日志清理脚本"
echo "================================================"
echo ""

# 检查日志目录是否存在
if [ ! -d "$LOG_DIR" ]; then
    echo "⚠️  日志目录不存在: $LOG_DIR"
    exit 0
fi

cd "$LOG_DIR"

# 统计清理前的文件数量和大小
BEFORE_COUNT=$(find . -name "*.log" -type f | wc -l)
BEFORE_SIZE=$(du -sh . 2>/dev/null | cut -f1)

echo "清理前统计:"
echo "  日志目录: $LOG_DIR"
echo "  日志文件数: $BEFORE_COUNT"
echo "  目录大小: $BEFORE_SIZE"
echo ""

# 删除7天前的日志文件
echo "正在删除7天前的日志文件..."
DELETED_COUNT=$(find . -name "*.log" -type f -mtime +7 -print -delete | wc -l)

# 统计清理后的文件数量和大小
AFTER_COUNT=$(find . -name "*.log" -type f | wc -l)
AFTER_SIZE=$(du -sh . 2>/dev/null | cut -f1)

echo ""
echo "清理完成!"
echo "  删除文件数: $DELETED_COUNT"
echo "  剩余文件数: $AFTER_COUNT"
echo "  当前大小: $AFTER_SIZE"
echo ""

if [ $DELETED_COUNT -gt 0 ]; then
    echo "✅ 已删除 $DELETED_COUNT 个过期日志文件"
else
    echo "✅ 没有需要清理的日志文件"
fi

echo ""
echo "================================================"