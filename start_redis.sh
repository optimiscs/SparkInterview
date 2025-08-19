#!/bin/bash

# Redis启动脚本

echo "🚀 启动Redis服务器..."

# 检查Redis是否已运行
if pgrep redis-server > /dev/null; then
    echo "✅ Redis已在运行"
    redis-cli ping
    exit 0
fi

# 启动Redis
if command -v redis-server >/dev/null 2>&1; then
    redis-server --daemonize yes --port 6379
    sleep 2
    
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis启动成功"
        echo "📍 Redis运行在: localhost:6379"
    else
        echo "❌ Redis启动失败"
        exit 1
    fi
else
    echo "❌ 未找到redis-server，请先安装Redis:"
    echo "   macOS: brew install redis"
    echo "   Ubuntu: sudo apt-get install redis-server"
    exit 1
fi
