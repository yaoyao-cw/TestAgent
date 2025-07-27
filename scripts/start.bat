@echo off
REM TestAgent Windows 启动脚本
setlocal enabledelayedexpansion

REM 设置颜色
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM 获取脚本参数
set "COMMAND=%~1"
if "%COMMAND%"=="" set "COMMAND=dev"

echo ========================================
echo TestAgent Windows 启动脚本
echo ========================================

REM 检查项目目录
if not exist "venv" (
    echo %RED%[ERROR]%NC% 虚拟环境不存在，请先运行 install.bat
    pause
    exit /b 1
)

if not exist ".env" (
    echo %RED%[ERROR]%NC% 配置文件不存在，请先运行 install.bat
    pause
    exit /b 1
)

REM 根据命令执行不同操作
if "%COMMAND%"=="dev" goto :start_dev
if "%COMMAND%"=="prod" goto :start_prod
if "%COMMAND%"=="stop" goto :stop_services
if "%COMMAND%"=="status" goto :check_status
if "%COMMAND%"=="logs" goto :show_logs
if "%COMMAND%"=="help" goto :show_help
goto :show_help

:start_dev
echo %BLUE%[INFO]%NC% 启动开发环境...

REM 检查端口占用
netstat -an | find "8000" | find "LISTENING" >nul
if %errorLevel% == 0 (
    echo %YELLOW%[WARNING]%NC% 端口8000已被占用，请先停止相关服务
    goto :stop_services
)

netstat -an | find "3000" | find "LISTENING" >nul
if %errorLevel% == 0 (
    echo %YELLOW%[WARNING]%NC% 端口3000已被占用，请先停止相关服务
    goto :stop_services
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 启动后端服务
echo %BLUE%[INFO]%NC% 启动后端服务...
if exist "run_simple_server.py" (
    start "TestAgent Backend" /min python run_simple_server.py
) else if exist "run_api_server.py" (
    start "TestAgent Backend" /min python run_api_server.py
) else (
    echo %RED%[ERROR]%NC% 找不到服务器启动脚本
    pause
    exit /b 1
)

REM 等待后端服务启动
echo %BLUE%[INFO]%NC% 等待后端服务启动...
timeout /t 5 /nobreak >nul

REM 检查后端服务状态
for /l %%i in (1,1,30) do (
    curl -s http://localhost:8000/health >nul 2>&1
    if !errorLevel! == 0 (
        echo %GREEN%[SUCCESS]%NC% 后端服务启动成功
        goto :start_frontend
    )
    timeout /t 1 /nobreak >nul
    echo 等待后端服务... (%%i/30^)
)

echo %RED%[ERROR]%NC% 后端服务启动超时
goto :stop_services

:start_frontend
REM 启动前端服务
if exist "frontend" (
    echo %BLUE%[INFO]%NC% 启动前端服务...
    cd frontend
    start "TestAgent Frontend" /min npm run dev
    cd ..
    
    REM 等待前端服务启动
    timeout /t 10 /nobreak >nul
    echo %GREEN%[SUCCESS]%NC% 前端服务启动中...
) else (
    echo %YELLOW%[WARNING]%NC% 前端目录不存在，仅启动后端服务
)

REM 显示访问信息
echo.
echo %GREEN%========================================%NC%
echo %GREEN%        服务启动完成！%NC%
echo %GREEN%========================================%NC%
echo.
echo 访问地址:
echo   - 后端API: http://localhost:8000
echo   - API文档: http://localhost:8000/docs
if exist "frontend" (
    echo   - 前端界面: http://localhost:3000
)
echo.
echo 管理命令:
echo   - 查看状态: start.bat status
echo   - 查看日志: start.bat logs
echo   - 停止服务: start.bat stop
echo.
echo %BLUE%按任意键停止服务...%NC%
pause >nul
goto :stop_services

:start_prod
echo %BLUE%[INFO]%NC% 启动生产环境...

REM 检查Docker
docker --version >nul 2>&1
if %errorLevel% neq 0 (
    echo %RED%[ERROR]%NC% Docker未安装，无法启动生产环境
    echo 请安装Docker Desktop或使用开发模式: start.bat dev
    pause
    exit /b 1
)

REM 检查docker-compose文件
if not exist "docker-compose.yml" (
    echo %RED%[ERROR]%NC% docker-compose.yml文件不存在
    pause
    exit /b 1
)

REM 启动Docker服务
echo %BLUE%[INFO]%NC% 启动Docker容器...
docker-compose up -d

if %errorLevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% 生产环境启动成功
    echo.
    echo 访问地址:
    echo   - 主应用: http://localhost:8000
    echo   - API文档: http://localhost:8000/docs
    echo   - 监控面板: http://localhost:3000
    echo.
    echo 管理命令:
    echo   - 查看状态: docker-compose ps
    echo   - 查看日志: docker-compose logs -f
    echo   - 停止服务: docker-compose down
) else (
    echo %RED%[ERROR]%NC% 生产环境启动失败
)
pause
exit /b 0

:stop_services
echo %BLUE%[INFO]%NC% 停止所有服务...

REM 停止Python进程
taskkill /f /im python.exe /t >nul 2>&1
if %errorLevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% 后端服务已停止
)

REM 停止Node.js进程
taskkill /f /im node.exe /t >nul 2>&1
if %errorLevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% 前端服务已停止
)

REM 停止Docker容器
docker-compose down >nul 2>&1
if %errorLevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% Docker容器已停止
)

echo %GREEN%[SUCCESS]%NC% 所有服务已停止
if "%COMMAND%"=="stop" pause
exit /b 0

:check_status
echo %BLUE%[INFO]%NC% 检查服务状态...

REM 检查后端服务
curl -s http://localhost:8000/health >nul 2>&1
if %errorLevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% 后端服务运行正常 (http://localhost:8000)
) else (
    echo %RED%[ERROR]%NC% 后端服务未运行
)

REM 检查前端服务
curl -s http://localhost:3000 >nul 2>&1
if %errorLevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% 前端服务运行正常 (http://localhost:3000)
) else (
    echo %YELLOW%[WARNING]%NC% 前端服务未运行或未安装
)

REM 检查Docker容器
docker-compose ps >nul 2>&1
if %errorLevel% == 0 (
    echo %BLUE%[INFO]%NC% Docker容器状态:
    docker-compose ps
)

pause
exit /b 0

:show_logs
echo %BLUE%[INFO]%NC% 显示服务日志...

if exist "logs\testagent.log" (
    echo %BLUE%[INFO]%NC% 应用日志:
    type logs\testagent.log | more
)

REM 显示Docker日志
docker-compose logs --tail=50 >nul 2>&1
if %errorLevel% == 0 (
    echo %BLUE%[INFO]%NC% Docker日志:
    docker-compose logs --tail=50
)

pause
exit /b 0

:show_help
echo 用法: start.bat [命令]
echo.
echo 命令:
echo   dev      - 启动开发环境 (默认)
echo   prod     - 启动生产环境 (需要Docker)
echo   stop     - 停止所有服务
echo   status   - 检查服务状态
echo   logs     - 查看服务日志
echo   help     - 显示帮助信息
echo.
echo 示例:
echo   start.bat dev     # 启动开发环境
echo   start.bat prod    # 启动生产环境
echo   start.bat stop    # 停止服务
echo.
pause
exit /b 0