#!/bin/bash
#
# 日志清理脚本
# 功能：清理过期日志文件
# 使用：./scripts/cleanup_all.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "MsgSkill 日志清理工具"
echo "================================================"
echo ""

# 清理日志
echo "清理日志文件..."
echo ""
bash "$SCRIPT_DIR/cleanup_logs.sh"

echo ""
echo "================================================"
echo "✅ 日志清理完成"
echo "================================================"