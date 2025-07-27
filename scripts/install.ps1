# TestAgent Windows PowerShell 安装脚本
param(
    [string]$Mode = "interactive",
    [switch]$Force,
    [switch]$SkipDependencyCheck
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
    Write-Host "    TestAgent Windows PowerShell 安装脚本" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

# 检测系统信息
function Get-SystemInfo {
    $arch = $env:PROCESSOR_ARCHITECTURE
    $osVersion = [System.Environment]::OSVersion.Version
    $psVersion = $PSVersionTable.PSVersion
    
    Write-Info "系统架构: $arch"
    Write-Info "操作系统版本: $osVersion"
    Write-Info "PowerShell版本: $psVersion"
    
    return @{
        Architecture = $arch
        OSVersion = $osVersion
        PSVersion = $psVersion
    }
}

# 检查管理员权限
function Test-AdminRights {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# 检查依赖
function Test-Dependencies {
    Write-Info "检查系统依赖..."
    
    $dependencies = @{
        Python = $false
        NodeJS = $false
        NPM = $false
        Git = $false
        Docker = $false
    }
    
    # 检查Python
    try {
        $pythonVersion = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dependencies.Python = $true
            Write-Success "Python版本: $pythonVersion"
        }
    }
    catch {
        Write-Error "Python未安装，请先安装Python 3.11+"
        Write-Info "下载地址: https://www.python.org/downloads/"
    }
    
    # 检查Node.js
    try {
        $nodeVersion = node --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dependencies.NodeJS = $true
            Write-Success "Node.js版本: $nodeVersion"
        }
    }
    catch {
        Write-Error "Node.js未安装，请先安装Node.js 18+"
        Write-Info "下载地址: https://nodejs.org/"
    }
    
    # 检查npm
    try {
        $npmVersion = npm --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dependencies.NPM = $true
            Write-Success "npm版本: $npmVersion"
        }
    }
    catch {
        Write-Error "npm未安装"
    }
    
    # 检查Git (可选)
    try {
        $gitVersion = git --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dependencies.Git = $true
            Write-Success "Git版本: $gitVersion"
        }
    }
    catch {
        Write-Warning "Git未安装，建议安装以获得更好的开发体验"
    }
    
    # 检查Docker (可选)
    try {
        $dockerVersion = docker --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dependencies.Docker = $true
            Write-Success "Docker版本: $dockerVersion"
        }
    }
    catch {
        Write-Warning "Docker未安装，将使用本地模式"
    }
    
    return $dependencies
}

# 创建项目目录
function New-ProjectDirectories {
    Write-Info "创建项目目录..."
    
    $directories = @(
        "data\vectordb",
        "data\documents", 
        "data\cache",
        "logs",
        "config",
        "backups",
        "temp"
    )
    
    foreach ($dir in $directories) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Success "创建目录: $dir"
        }
    }
}

# 设置配置文件
function Set-ConfigFiles {
    Write-Info "设置配置文件..."
    
    $configFiles = @(
        @{ Source = ".env.example"; Target = ".env" },
        @{ Source = "config\config.example.yaml"; Target = "config\config.yaml" },
        @{ Source = "config\mcp_servers.example.json"; Target = "config\mcp_servers.json" }
    )
    
    foreach ($config in $configFiles) {
        if (!(Test-Path $config.Target)) {
            if (Test-Path $config.Source) {
                Copy-Item $config.Source $config.Target
                Write-Success "创建配置文件: $($config.Target)"
            } else {
                Write-Warning "示例配置文件不存在: $($config.Source)"
            }
        } else {
            Write-Info "配置文件已存在: $($config.Target)"
        }
    }
    
    # 创建默认.env文件（如果示例文件不存在）
    if (!(Test-Path ".env") -and !(Test-Path ".env.example")) {
        $defaultEnv = @"
# TestAgent Windows 配置
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
REDIS_URL=redis://localhost:6379/0
VECTOR_DB_PATH=./data/vectordb
LOG_FILE=./logs/testagent.log
"@
        $defaultEnv | Out-File -FilePath ".env" -Encoding UTF8
        Write-Success "创建默认 .env 配置文件"
    }
}

# 创建Python虚拟环境
function New-PythonVirtualEnv {
    Write-Info "创建Python虚拟环境..."
    
    if (!(Test-Path "venv")) {
        python -m venv venv
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Python虚拟环境创建成功"
        } else {
            throw "Python虚拟环境创建失败"
        }
    } else {
        Write-Warning "Python虚拟环境已存在"
    }
}

# 安装Python依赖
function Install-PythonDependencies {
    Write-Info "安装Python依赖..."
    
    # 激活虚拟环境
    & "venv\Scripts\Activate.ps1"
    
    # 升级pip
    python -m pip install --upgrade pip
    
    # 安装核心依赖
    $coreDeps = @(
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "PyYAML>=6.0.0"
    )
    
    python -m pip install $coreDeps
    if ($LASTEXITCODE -eq 0) {
        Write-Success "核心Python依赖安装完成"
    } else {
        throw "Python依赖安装失败"
    }
    
    # 尝试安装完整依赖
    if (Test-Path "requirements.txt") {
        Write-Info "安装完整依赖包..."
        python -m pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Success "完整依赖安装成功"
        } else {
            Write-Warning "部分依赖安装失败，但核心功能可用"
        }
    }
}

# 安装前端依赖
function Install-FrontendDependencies {
    Write-Info "安装前端依赖..."
    
    if (Test-Path "frontend") {
        Push-Location "frontend"
        try {
            npm install
            if ($LASTEXITCODE -eq 0) {
                Write-Success "前端依赖安装完成"
            } else {
                throw "前端依赖安装失败"
            }
        }
        finally {
            Pop-Location
        }
    } else {
        Write-Warning "前端目录不存在，跳过前端依赖安装"
    }
}

# 创建启动脚本
function New-StartupScripts {
    Write-Info "创建启动脚本..."
    
    # 创建开发环境启动脚本
    $devScript = @"
# TestAgent 开发环境启动脚本
Write-Host "启动TestAgent开发环境..." -ForegroundColor Green

# 激活虚拟环境
& "venv\Scripts\Activate.ps1"

# 启动后端服务
if (Test-Path "run_simple_server.py") {
    Start-Process -FilePath "python" -ArgumentList "run_simple_server.py" -WindowStyle Minimized
} elseif (Test-Path "run_api_server.py") {
    Start-Process -FilePath "python" -ArgumentList "run_api_server.py" -WindowStyle Minimized
} else {
    Write-Error "找不到服务器启动脚本"
    exit 1
}

# 等待后端服务启动
Start-Sleep -Seconds 5

# 启动前端服务
if (Test-Path "frontend") {
    Push-Location "frontend"
    Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WindowStyle Minimized
    Pop-Location
}

Write-Host "服务已启动:" -ForegroundColor Green
Write-Host "  - 后端API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  - 前端界面: http://localhost:3000" -ForegroundColor Cyan
Write-Host "按任意键停止服务..." -ForegroundColor Yellow
Read-Host

# 停止服务
Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force
"@
    $devScript | Out-File -FilePath "start-dev.ps1" -Encoding UTF8
    
    # 创建生产环境启动脚本（如果Docker可用）
    try {
        docker --version | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $prodScript = @"
# TestAgent 生产环境启动脚本
Write-Host "启动TestAgent生产环境..." -ForegroundColor Green

docker-compose up -d

if (`$LASTEXITCODE -eq 0) {
    Write-Host "服务已启动:" -ForegroundColor Green
    Write-Host "  - 主应用: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "  - API文档: http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host "  - 监控面板: http://localhost:3000" -ForegroundColor Cyan
} else {
    Write-Error "生产环境启动失败"
}

Read-Host "按回车键继续"
"@
            $prodScript | Out-File -FilePath "start-prod.ps1" -Encoding UTF8
        }
    }
    catch {
        Write-Info "Docker不可用，跳过生产环境脚本创建"
    }
    
    # 创建停止脚本
    $stopScript = @"
# TestAgent 停止脚本
Write-Host "停止TestAgent服务..." -ForegroundColor Yellow

Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force

try {
    docker-compose down 2>`$null
}
catch {
    # Docker不可用，忽略错误
}

Write-Host "所有服务已停止" -ForegroundColor Green
"@
    $stopScript | Out-File -FilePath "stop.ps1" -Encoding UTF8
    
    Write-Success "启动脚本创建完成"
}

# 主安装函数
function Install-TestAgent {
    try {
        Show-Banner
        
        # 检测系统信息
        $systemInfo = Get-SystemInfo
        
        # 检查管理员权限
        if (Test-AdminRights) {
            Write-Success "管理员权限检查通过"
        } else {
            Write-Warning "建议以管理员身份运行以获得最佳体验"
        }
        
        # 检查依赖
        if (!$SkipDependencyCheck) {
            $deps = Test-Dependencies
            if (!$deps.Python -or !$deps.NodeJS -or !$deps.NPM) {
                if (!$Force) {
                    throw "必要依赖缺失，请安装后重试，或使用 -Force 参数强制继续"
                }
            }
        }
        
        # 创建目录
        New-ProjectDirectories
        
        # 设置配置文件
        Set-ConfigFiles
        
        # 创建Python虚拟环境
        New-PythonVirtualEnv
        
        # 安装Python依赖
        Install-PythonDependencies
        
        # 安装前端依赖
        Install-FrontendDependencies
        
        # 创建启动脚本
        New-StartupScripts
        
        # 显示完成信息
        Write-Host ""
        Write-Success "========================================"
        Write-Success "        安装完成！"
        Write-Success "========================================"
        Write-Host ""
        Write-Info "使用方法:"
        Write-Info "  - 开发环境: .\start-dev.ps1"
        if (Test-Path "start-prod.ps1") {
            Write-Info "  - 生产环境: .\start-prod.ps1"
        }
        Write-Info "  - 停止服务: .\stop.ps1"
        Write-Host ""
        Write-Info "访问地址:"
        Write-Info "  - 后端API: http://localhost:8000"
        Write-Info "  - API文档: http://localhost:8000/docs"
        Write-Info "  - 前端界面: http://localhost:3000"
        Write-Host ""
        Write-Info "配置文件:"
        Write-Info "  - 主配置: .env"
        Write-Info "  - 应用配置: config\config.yaml"
        Write-Info "  - MCP配置: config\mcp_servers.json"
        Write-Host ""
        
        if ($Mode -eq "interactive") {
            Read-Host "按回车键退出"
        }
        
    }
    catch {
        Write-Error "安装失败: $($_.Exception.Message)"
        if ($Mode -eq "interactive") {
            Read-Host "按回车键退出"
        }
        exit 1
    }
}

# 执行安装
Install-TestAgent