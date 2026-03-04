#!/bin/bash

# MsgSkill 统一启动脚本
# 同时启动定时任务和预览服务

echo "================================================"
echo "🚀 MsgSkill - AI信息聚合专家"
echo "================================================"
echo ""

# 检查依赖
echo "检查依赖..."
if ! python3 -c "import flask" 2>/dev/null; then
    echo "安装依赖..."
    pip3 install -r requirements.txt
fi

# 检查 Docker（如果需要 RSSHub）
echo ""
echo "检查 Docker 环境..."
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "  ✓ Docker 和 Docker Compose 已安装"
    # 检查是否有使用 RSSHub 的配置
    if grep -q "localhost:8878" config/sources.json 2>/dev/null; then
        echo "  ✓ 检测到 RSSHub 配置，将在启动时自动启动 RSSHub 容器"
    fi
else
    if grep -q "localhost:8878" config/sources.json 2>/dev/null; then
        echo "  ⚠ 警告: 检测到 RSSHub 配置，但未安装 Docker"
        echo "    请安装 Docker 和 Docker Compose，或手动启动 RSSHub 服务"
        echo "    安装指南: https://docs.docker.com/get-docker/"
    fi
fi

echo ""
echo "================================================"
echo "启动服务"
echo "================================================"
echo ""

# 启动定时任务（前台运行，显示执行进度）
echo "▶ 启动定时任务调度器..."
echo "  调度器将立即执行一次所有任务，然后按计划定期执行"
echo "  预览服务将在任务执行完成后启动"
echo ""
echo "================================================"
echo "执行中 - 请等待首次同步完成..."
echo "================================================"
echo ""

# 先执行一次所有任务（前台运行，显示进度）
echo "执行首次同步..."
# python3 src/msgskill/multi_scheduler.py --once

echo ""
echo "================================================"
echo "✅ 首次同步完成"
echo "================================================"
echo ""

# 创建 logs 目录（如果不存在）
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo "  ✓ 创建 logs 目录"
fi

# 启动定时任务（后台运行，日志同时输出到控制台和文件）
echo "▶ 启动后台定时调度器..."
# 使用 tee 同时输出到终端和文件，-a 表示追加模式
# 注意：后台进程的输出会同时显示在终端和写入文件
python3 src/msgskill/multi_scheduler.py 2>&1 | tee -a logs/scheduler.log &
SCHEDULER_PID=$!
echo "  ✓ 调度器PID: $SCHEDULER_PID"
echo "  ✓ 日志同时输出到控制台和文件: logs/scheduler.log"

# 等待一下确保调度器启动
sleep 2

# 检查并杀掉占用5001端口的进程
echo "▶ 检查端口5001..."
PORT_PID=$(lsof -ti:5001 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "  ⚠ 发现端口5001被占用 (PID: $PORT_PID)，正在终止..."
    kill -9 $PORT_PID 2>/dev/null
    sleep 1
    echo "  ✓ 端口5001已释放"
else
    echo "  ✓ 端口5001可用"
fi

# 启动预览服务（前台运行）
echo ""
echo "▶ 启动数据预览服务..."
echo "  访问地址: http://localhost:5001"
echo ""
echo "================================================"
echo "按 Ctrl+C 停止所有服务"
echo "================================================"
echo ""

# 捕获退出信号，清理后台进程
trap "echo ''; echo '正在停止服务...'; kill $SCHEDULER_PID 2>/dev/null; exit" INT TERM

# 启动预览服务（前台）
python3 src/msgskill/preview_server.py

# 如果预览服务退出，也停止调度器
kill $SCHEDULER_PID 2>/dev/null
