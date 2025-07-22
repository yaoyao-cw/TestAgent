@echo off
REM TestAgent前端启动脚本 (Windows)

echo 🚀 启动TestAgent前端开发服务器
echo ==================================

REM 检查Node.js是否安装
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js未安装，请先安装Node.js 16+
    pause
    exit /b 1
)

REM 检查npm是否安装
npm --version >nul 2>&1
if errorlevel 1 (
    echo ❌ npm未安装，请先安装npm
    pause
    exit /b 1
)

REM 进入前端目录
cd /d "%~dp0..\frontend"

echo 📍 当前目录: %cd%

REM 检查package.json是否存在
if not exist "package.json" (
    echo ❌ package.json不存在，请确认在正确的目录
    pause
    exit /b 1
)

REM 检查node_modules是否存在
if not exist "node_modules" (
    echo 📦 安装依赖包...
    npm install
) else (
    echo ✅ 依赖包已安装
)

REM 检查后端服务是否运行
echo 🔍 检查后端服务...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ⚠️  后端服务未运行，请先启动后端服务
    echo    运行: python run_api_server.py
) else (
    echo ✅ 后端服务运行正常
)

REM 启动开发服务器
echo 🌐 启动前端开发服务器...
echo    地址: http://localhost:3000
echo    按 Ctrl+C 停止服务器
echo.

npm run dev

pause