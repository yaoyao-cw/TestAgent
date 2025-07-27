# TestAgent Windows PowerShell 启动脚本
param(
    [string]$Command = "dev",
    [string]$Service = "",
    [switch]$Background,
    [switch]$Verbose
)

# 设置错误处理
$ErrorActionPreference = "Stop"

# 颜色函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    
    $colorMap = @{
        "Red" = "Red"
        "Green" = "Green"
        "Yellow" = "Yellow"
        "Blue" = "Blue"
        "Cyan" = "Cyan"
        "Magenta" = "Magenta"
    }
    
    Write-Host $Message -ForegroundColor $colorMap[$Color]
}

function Write-Info { param([string]$Message) Write-ColorOutput "[INFO] $Message" "Blue" }
function Write-Success { param([string]$Message) Write-ColorOutput "[SUCCESS] $Message" "Green" }
function Write-Warning { param([string]$Message) Write-ColorOutput "[WARNING] $Message" "Yellow" }
function Write-Error { param([string]$Message) Write-ColorOutput "[ERROR] $Message" "Red" }

# 显示横幅
function Show-Banner {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "    TestAgent Windows PowerShell 启动脚本" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

# 检查项目环境
function Test-ProjectEnvironment {
    if (!(Test-Path "venv")) {
        Write-Error "虚拟环境不存在，请先运行 install.ps1"
        return $false
    }
    
    if (!(Test-Path ".env")) {
        Write-Error "配置文件不存在，请先运行 install.ps1"
        return $false
    }
    
    return $true
}

# 检查端口占用
function Test-PortAvailable {
    param([int]$Port)
    
    try {
        $listener = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        $portInUse = $listener | Where-Object { $_.Port -eq $Port }
        return $portInUse.Count -eq 0
    }
    catch {
        return $true
    }
}

# 等待服务启动
function Wait-ForService {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30,
        [string]$ServiceName = "服务"
    )
    
    Write-Info "等待 $ServiceName 启动..."
    
    for ($i = 1; $i -le $TimeoutSeconds; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 1 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                Write-Success "$ServiceName 启动成功"
                return $true
            }
        }
        catch {
            # 忽略连接错误，继续等待
        }
        
        Write-Host "等待 $ServiceName... ($i/$TimeoutSeconds)" -ForegroundColor Gray
        Start-Sleep -Seconds 1
    }
    
    Write-Error "$ServiceName 启动超时"
    return $false
}

# 启动开发环境
function Start-DevEnvironment {
    Write-Info "启动开发环境..."
    
    # 检查端口占用
    if (!(Test-PortAvailable -Port 8000)) {
        Write-Warning "端口8000已被占用，尝试停止相关服务..."
        Stop-AllServices
        Start-Sleep -Seconds 2
    }
    
    if (!(Test-PortAvailable -Port 3000)) {
        Write-Warning "端口3000已被占用，尝试停止相关服务..."
        Stop-AllServices
        Start-Sleep -Seconds 2
    }
    
    # 激活虚拟环境
    & "venv\Scripts\Activate.ps1"
    
    # 启动后端服务
    Write-Info "启动后端服务..."
    $backendScript = $null
    if (Test-Path "run_simple_server.py") {
        $backendScript = "run_simple_server.py"
        Write-Info "使用简化版API服务器..."
    } elseif (Test-Path "run_api_server.py") {
        $backendScript = "run_api_server.py"
        Write-Info "使用完整版API服务器..."
    } else {
        Write-Error "找不到服务器启动脚本"
        return $false
    }
    
    if ($Background) {
        Start-Process -FilePath "python" -ArgumentList $backendScript -WindowStyle Hidden
    } else {
        Start-Process -FilePath "python" -ArgumentList $backendScript -WindowStyle Minimized
    }
    
    # 等待后端服务启动
    if (!(Wait-ForService -Url "http://localhost:8000/health" -ServiceName "后端服务")) {
        return $false
    }
    
    # 启动前端服务
    if (Test-Path "frontend") {
        Write-Info "启动前端服务..."
        Push-Location "frontend"
        try {
            if ($Background) {
                Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WindowStyle Hidden
            } else {
                Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WindowStyle Minimized
            }
            
            # 等待前端服务启动
            Start-Sleep -Seconds 10
            Write-Success "前端服务启动中..."
        }
        finally {
            Pop-Location
        }
    } else {
        Write-Warning "前端目录不存在，仅启动后端服务"
    }
    
    # 显示访问信息
    Show-AccessInfo
    
    if (!$Background) {
        Write-Host ""
        Write-ColorOutput "按任意键停止服务..." "Yellow"
        Read-Host
        Stop-AllServices
    }
    
    return $true
}

# 启动生产环境
function Start-ProdEnvironment {
    Write-Info "启动生产环境..."
    
    # 检查Docker
    try {
        docker --version | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Docker命令执行失败"
        }
    }
    catch {
        Write-Error "Docker未安装，无法启动生产环境"
        Write-Info "请安装Docker Desktop或使用开发模式: start.ps1 dev"
        return $false
    }
    
    # 检查docker-compose文件
    if (!(Test-Path "docker-compose.yml")) {
        Write-Error "docker-compose.yml文件不存在"
        return $false
    }
    
    # 启动Docker服务
    Write-Info "启动Docker容器..."
    docker-compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "生产环境启动成功"
        Write-Host ""
        Write-Info "访问地址:"
        Write-Info "  - 主应用: http://localhost:8000"
        Write-Info "  - API文档: http://localhost:8000/docs"
        Write-Info "  - 监控面板: http://localhost:3000"
        Write-Host ""
        Write-Info "管理命令:"
        Write-Info "  - 查看状态: docker-compose ps"
        Write-Info "  - 查看日志: docker-compose logs -f"
        Write-Info "  - 停止服务: docker-compose down"
        return $true
    } else {
        Write-Error "生产环境启动失败"
        return $false
    }
}

# 停止所有服务
function Stop-AllServices {
    Write-Info "停止所有服务..."
    
    # 停止Python进程
    try {
        Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force
        Write-Success "后端服务已停止"
    }
    catch {
        # 忽略错误
    }
    
    # 停止Node.js进程
    try {
        Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force
        Write-Success "前端服务已停止"
    }
    catch {
        # 忽略错误
    }
    
    # 停止Docker容器
    try {
        docker-compose down 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Docker容器已停止"
        }
    }
    catch {
        # 忽略错误
    }
    
    Write-Success "所有服务已停止"
}

# 检查服务状态
function Get-ServiceStatus {
    Write-Info "检查服务状态..."
    
    # 检查后端服务
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -Method GET -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Success "后端服务运行正常 (http://localhost:8000)"
        }
    }
    catch {
        Write-Error "后端服务未运行"
    }
    
    # 检查前端服务
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -Method GET -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Success "前端服务运行正常 (http://localhost:3000)"
        }
    }
    catch {
        Write-Warning "前端服务未运行或未安装"
    }
    
    # 检查Docker容器
    try {
        $containers = docker-compose ps 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Docker容器状态:"
            docker-compose ps
        }
    }
    catch {
        Write-Info "Docker服务未运行"
    }
}

# 显示日志
function Show-Logs {
    Write-Info "显示服务日志..."
    
    if (Test-Path "logs\testagent.log") {
        Write-Info "应用日志:"
        Get-Content "logs\testagent.log" -Tail 50
    }
    
    # 显示Docker日志
    try {
        docker-compose logs --tail=50 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Docker日志:"
            docker-compose logs --tail=50
        }
    }
    catch {
        Write-Info "Docker日志不可用"
    }
}

# 显示访问信息
function Show-AccessInfo {
    Write-Host ""
    Write-Success "========================================"
    Write-Success "        服务启动完成！"
    Write-Success "========================================"
    Write-Host ""
    Write-Info "访问地址:"
    Write-Info "  - 后端API: http://localhost:8000"
    Write-Info "  - API文档: http://localhost:8000/docs"
    if (Test-Path "frontend") {
        Write-Info "  - 前端界面: http://localhost:3000"
    }
    Write-Host ""
    Write-Info "管理命令:"
    Write-Info "  - 查看状态: .\start.ps1 status"
    Write-Info "  - 查看日志: .\start.ps1 logs"
    Write-Info "  - 停止服务: .\start.ps1 stop"
}

# 显示帮助信息
function Show-Help {
    Write-Host "用法: .\start.ps1 [命令] [选项]"
    Write-Host ""
    Write-Host "命令:"
    Write-Host "  dev      - 启动开发环境 (默认)"
    Write-Host "  prod     - 启动生产环境 (需要Docker)"
    Write-Host "  stop     - 停止所有服务"
    Write-Host "  status   - 检查服务状态"
    Write-Host "  logs     - 查看服务日志"
    Write-Host "  help     - 显示帮助信息"
    Write-Host ""
    Write-Host "选项:"
    Write-Host "  -Background  - 后台运行服务"
    Write-Host "  -Verbose     - 显示详细输出"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\start.ps1 dev              # 启动开发环境"
    Write-Host "  .\start.ps1 dev -Background  # 后台启动开发环境"
    Write-Host "  .\start.ps1 prod             # 启动生产环境"
    Write-Host "  .\start.ps1 stop             # 停止服务"
    Write-Host ""
}

# 主函数
function Main {
    try {
        Show-Banner
        
        # 检查项目环境
        if (!(Test-ProjectEnvironment)) {
            return
        }
        
        # 根据命令执行不同操作
        switch ($Command.ToLower()) {
            "dev" {
                Start-DevEnvironment
            }
            "prod" {
                Start-ProdEnvironment
            }
            "stop" {
                Stop-AllServices
            }
            "status" {
                Get-ServiceStatus
            }
            "logs" {
                Show-Logs
            }
            "help" {
                Show-Help
            }
            default {
                Write-Error "未知命令: $Command"
                Show-Help
            }
        }
    }
    catch {
        Write-Error "执行失败: $($_.Exception.Message)"
        if ($Verbose) {
            Write-Host $_.Exception.StackTrace -ForegroundColor Red
        }
    }
}

# 执行主函数
Main