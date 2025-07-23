#!/bin/bash
# 职面星火系统启动脚本

echo "🔥 职面星火 - 智能面试评测系统启动脚本"
echo "=================================================="

# 检查Python版本
echo "📋 检查系统环境..."
python --version

# 检查是否存在配置文件
if [ ! -f "config.env" ]; then
    echo "⚠️ 配置文件不存在，复制模板文件..."
    cp config.env.template config.env
    echo "✅ 请编辑 config.env 文件并填写必要配置（如讯飞星火API密钥）"
    echo "   配置文件位置: ./config.env"
    echo ""
    echo "📝 必填配置项："
    echo "   - SPARK_APP_ID: 讯飞星火应用ID"
    echo "   - SPARK_API_SECRET: 讯飞星火API密钥"
    echo ""
    read -p "配置完成后按任意键继续..."
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python -m venv venv
fi

echo "🔧 激活虚拟环境..."
source venv/bin/activate

echo "📥 安装依赖..."
pip install -r requirements.txt

echo "📁 创建必要的目录..."
mkdir -p data/interviews data/cache data/chroma_db data/resumes logs

echo "🚀 启动职面星火系统..."
echo "   访问地址: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"  
echo "   测试页面: http://localhost:8000/frontend/api-test.html"
echo "=================================================="
echo ""

python main.py 