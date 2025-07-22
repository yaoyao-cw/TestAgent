#!/bin/bash

# TestAgent前端启动脚本

set -e

echo "🚀 启动TestAgent前端开发服务器"
echo "=================================="

# 检查Node.js是否安装
if ! command -v node &> /dev/null; then
    echo "❌ Node.js未安装，请先安装Node.js 16+"
    exit 1
fi

# 检查npm是否安装
if ! command -v npm &> /dev/null; then
    echo "❌ npm未安装，请先安装npm"
    exit 1
fi

# 进入前端目录
cd "$(dirname "$0")/../frontend"

echo "📍 当前目录: $(pwd)"

# 检查package.json是否存在
if [ ! -f "package.json" ]; then
    echo "❌ package.json不存在，请确认在正确的目录"
    exit 1
fi

# 检查node_modules是否存在
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖包..."
    npm install
else
    echo "✅ 依赖包已安装"
fi

# 检查后端服务是否运行
echo "🔍 检查后端服务..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ 后端服务运行正常"
else
    echo "⚠️  后端服务未运行，请先启动后端服务"
    echo "   运行: python run_api_server.py"
fi

# 启动开发服务器
echo "🌐 启动前端开发服务器..."
echo "   地址: http://localhost:3000"
echo "   按 Ctrl+C 停止服务器"
echo ""

npm run dev