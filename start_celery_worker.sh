#!/bin/bash

# Celery Worker启动脚本
# 用于解决异步分析任务阻塞主线程的问题
# 使用方法：在79014382源码目录下运行 ./start_celery_worker.sh

echo "🚀 启动Celery Worker服务..."

# 确保在正确的目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📍 当前工作目录: $(pwd)"

# 检查必要文件
if [[ ! -f "src/celery_app.py" ]]; then
    echo "❌ 错误: 找不到 src/celery_app.py，请确保在项目根目录运行"
    exit 1
fi

# 检查conda环境
if [[ "$CONDA_DEFAULT_ENV" != "xinghuo" ]]; then
    echo "⚠️  请先激活conda环境: conda activate xinghuo"
    echo "   然后再运行此脚本"
    exit 1
fi

# 检查Redis是否运行
if ! pgrep redis-server > /dev/null; then
    echo "🔍 Redis未运行，正在启动..."
    if command -v redis-server >/dev/null 2>&1; then
        redis-server --daemonize yes --port 6379
        sleep 2
    else
        echo "❌ 未找到redis-server，请先安装Redis"
        echo "   macOS: brew install redis"
        exit 1
    fi
fi

# 检查Redis连接
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis连接失败，请检查Redis服务"
    exit 1
fi

echo "✅ Redis服务正常"

# 设置环境变量
export PYTHONPATH="$(pwd):${PYTHONPATH}"
echo "📦 PYTHONPATH设置为: $PYTHONPATH"

# 启动Celery Worker
echo "🔥 启动Celery Worker..."
echo "   队列: analysis, profile"
echo "   并发数: 2"
echo "   池类型: solo (兼容性更好)"

celery -A src.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --queues=analysis,profile \
    --pool=solo \
    --hostname=worker@%h

echo "🛑 Celery Worker已停止"
