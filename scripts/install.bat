@echo off
REM TestAgent Windows 安装脚本
setlocal enabledelayedexpansion

echo ========================================
echo TestAgent Windows 安装脚本
echo ========================================

REM 设置颜色
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM 检测系统架构
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set ARCH=x64
) else if "%PROCESSOR_ARCHITECTURE%"=="ARM64" (
    set ARCH=arm64
) else (
    set ARCH=x86
)

echo %BLUE%[INFO]%NC% 检测到系统架构: %ARCH%

REM 检查管理员权限
net session >nul 2>&1
if %errorLevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% 管理员权限检查通过
) else (
    echo %YELLOW%[WARNING]%NC% 建议以管理员身份运行以获得最佳体验
)

REM 检查依赖
echo %BLUE%[INFO]%NC% 检查系统依赖...

REM 检查Python
python --version >nul 2>&1
if %errorLevel% == 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo %GREEN%[SUCCESS]%NC% Python版本: !PYTHON_VERSION!
) else (
    echo %RED%[ERROR]%NC% Python未安装，请先安装Python 3.11+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查Node.js
node --version >nul 2>&1
if %errorLevel% == 0 (
    for /f %%i in ('node --version') do set NODE_VERSION=%%i
    echo %GREEN%[SUCCESS]%NC% Node.js版本: !NODE_VERSION!
) else (
    echo %RED%[ERROR]%NC% Node.js未安装，请先安装Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

REM 检查npm
npm --version >nul 2>&1
if %errorLevel% == 0 (
    for /f %%i in ('npm --version') do set NPM_VERSION=%%i
    echo %GREEN%[SUCCESS]%NC% npm版本: !NPM_VERSION!
) else (
    echo %RED%[ERROR]%NC% npm未安装
    pause
    exit /b 1
)

REM 检查Docker (可选)
docker --version >nul 2>&1
if %errorLevel% == 0 (
    for /f "tokens=3" %%i in ('docker --version') do set DOCKER_VERSION=%%i
    echo %GREEN%[SUCCESS]%NC% Docker版本: !DOCKER_VERSION!
    set DOCKER_AVAILABLE=true
) else (
    echo %YELLOW%[WARNING]%NC% Docker未安装，将使用本地模式
    set DOCKER_AVAILABLE=false
)

REM 创建必要目录
echo %BLUE%[INFO]%NC% 创建项目目录...
if not exist "data" mkdir data
if not exist "data\vectordb" mkdir data\vectordb
if not exist "data\documents" mkdir data\documents
if not exist "data\cache" mkdir data\cache
if not exist "logs" mkdir logs
if not exist "config" mkdir config
if not exist "backups" mkdir backups
if not exist "temp" mkdir temp

echo %GREEN%[SUCCESS]%NC% 目录创建完成

REM 设置配置文件
echo %BLUE%[INFO]%NC% 设置配置文件...

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo %GREEN%[SUCCESS]%NC% 已创建 .env 配置文件
    ) else (
        echo # TestAgent Windows 配置 > .env
        echo ENVIRONMENT=development >> .env
        echo DEBUG=true >> .env
        echo LOG_LEVEL=INFO >> .env
        echo API_HOST=0.0.0.0 >> .env
        echo API_PORT=8000 >> .env
        echo REDIS_URL=redis://localhost:6379/0 >> .env
        echo VECTOR_DB_PATH=./data/vectordb >> .env
        echo LOG_FILE=./logs/testagent.log >> .env
        echo %GREEN%[SUCCESS]%NC% 已创建默认 .env 配置文件
    )
)

if not exist "config\config.yaml" (
    if exist "config\config.example.yaml" (
        copy "config\config.example.yaml" "config\config.yaml" >nul
        echo %GREEN%[SUCCESS]%NC% 已创建 config.yaml 配置文件
    )
)

if not exist "config\mcp_servers.json" (
    if exist "config\mcp_servers.example.json" (
        copy "config\mcp_servers.example.json" "config\mcp_servers.json" >nul
        echo %GREEN%[SUCCESS]%NC% 已创建 MCP服务器配置文件
    )
)

REM 创建Python虚拟环境
echo %BLUE%[INFO]%NC% 创建Python虚拟环境...
if not exist "venv" (
    python -m venv venv
    if %errorLevel% == 0 (
        echo %GREEN%[SUCCESS]%NC% Python虚拟环境创建成功
    ) else (
        echo %RED%[ERROR]%NC% Python虚拟环境创建失败
        pause
        exit /b 1
    )
) else (
    echo %YELLOW%[WARNING]%NC% Python虚拟环境已存在
)

REM 激活虚拟环境并安装依赖
echo %BLUE%[INFO]%NC% 安装Python依赖...
call venv\Scripts\activate.bat

REM 升级pip
python -m pip install --upgrade pip

REM 安装核心依赖
python -m pip install fastapi uvicorn[standard] pydantic pydantic-settings python-dotenv PyYAML
if %errorLevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% 核心Python依赖安装完成
) else (
    echo %RED%[ERROR]%NC% Python依赖安装失败
    pause
    exit /b 1
)

REM 尝试安装完整依赖
if exist "requirements.txt" (
    echo %BLUE%[INFO]%NC% 安装完整依赖包...
    python -m pip install -r requirements.txt
    if %errorLevel% == 0 (
        echo %GREEN%[SUCCESS]%NC% 完整依赖安装成功
    ) else (
        echo %YELLOW%[WARNING]%NC% 部分依赖安装失败，但核心功能可用
    )
)

REM 安装前端依赖
echo %BLUE%[INFO]%NC% 安装前端依赖...
if exist "frontend" (
    cd frontend
    npm install
    if %errorLevel% == 0 (
        echo %GREEN%[SUCCESS]%NC% 前端依赖安装完成
    ) else (
        echo %RED%[ERROR]%NC% 前端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
) else (
    echo %YELLOW%[WARNING]%NC% 前端目录不存在，跳过前端依赖安装
)

REM 创建启动脚本
echo %BLUE%[INFO]%NC% 创建启动脚本...

REM 创建开发环境启动脚本
echo @echo off > start-dev.bat
echo echo 启动TestAgent开发环境... >> start-dev.bat
echo call venv\Scripts\activate.bat >> start-dev.bat
echo start /b python run_simple_server.py >> start-dev.bat
echo timeout /t 5 /nobreak ^>nul >> start-dev.bat
echo cd frontend >> start-dev.bat
echo start /b npm run dev >> start-dev.bat
echo cd .. >> start-dev.bat
echo echo 服务已启动: >> start-dev.bat
echo echo   - 后端API: http://localhost:8000 >> start-dev.bat
echo echo   - 前端界面: http://localhost:3000 >> start-dev.bat
echo echo 按任意键停止服务... >> start-dev.bat
echo pause ^>nul >> start-dev.bat
echo taskkill /f /im python.exe /t ^>nul 2^>^&1 >> start-dev.bat
echo taskkill /f /im node.exe /t ^>nul 2^>^&1 >> start-dev.bat

REM 创建生产环境启动脚本
if "%DOCKER_AVAILABLE%"=="true" (
    echo @echo off > start-prod.bat
    echo echo 启动TestAgent生产环境... >> start-prod.bat
    echo docker-compose up -d >> start-prod.bat
    echo echo 服务已启动: >> start-prod.bat
    echo echo   - 主应用: http://localhost:8000 >> start-prod.bat
    echo echo   - API文档: http://localhost:8000/docs >> start-prod.bat
    echo echo   - 监控面板: http://localhost:3000 >> start-prod.bat
    echo pause >> start-prod.bat
)

REM 创建停止脚本
echo @echo off > stop.bat
echo echo 停止TestAgent服务... >> stop.bat
echo taskkill /f /im python.exe /t ^>nul 2^>^&1 >> stop.bat
echo taskkill /f /im node.exe /t ^>nul 2^>^&1 >> stop.bat
if "%DOCKER_AVAILABLE%"=="true" (
    echo docker-compose down ^>nul 2^>^&1 >> stop.bat
)
echo echo 所有服务已停止 >> stop.bat

echo %GREEN%[SUCCESS]%NC% 启动脚本创建完成

REM 安装完成
echo.
echo %GREEN%========================================%NC%
echo %GREEN%        安装完成！%NC%
echo %GREEN%========================================%NC%
echo.
echo 使用方法:
echo   - 开发环境: start-dev.bat
if "%DOCKER_AVAILABLE%"=="true" (
    echo   - 生产环境: start-prod.bat
)
echo   - 停止服务: stop.bat
echo.
echo 访问地址:
echo   - 后端API: http://localhost:8000
echo   - API文档: http://localhost:8000/docs
echo   - 前端界面: http://localhost:3000
echo.
echo 配置文件:
echo   - 主配置: .env
echo   - 应用配置: config\config.yaml
echo   - MCP配置: config\mcp_servers.json
echo.
echo %BLUE%按任意键退出...%NC%
pause >nul