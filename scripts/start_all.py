#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestAgent完整启动脚本
同时启动后端API服务器和前端开发服务器
"""

import os
import sys
import subprocess
import time
import signal
import threading
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

def print_banner():
    """打印启动横幅"""
    print("=" * 60)
    print("🚀 TestAgent 完整启动脚本")
    print("=" * 60)
    print("📍 项目目录:", PROJECT_ROOT)
    print("🔧 后端服务: http://localhost:8000")
    print("🌐 前端服务: http://localhost:3000")
    print("=" * 60)

def find_node_npm_paths():
    """查找Node.js和npm的路径"""
    node_path = None
    npm_path = None
    
    # 常见的Node.js安装路径
    possible_paths = [
        # nvm路径
        os.path.expanduser("~/.nvm/versions/node/v18.20.7/bin"),
        os.path.expanduser("~/.nvm/versions/node/*/bin"),
        # 系统路径
        "/usr/bin",
        "/usr/local/bin",
        # 其他可能的路径
        "/opt/node/bin",
    ]
    
    # 首先尝试直接调用（如果在PATH中）
    try:
        result = subprocess.run(["which", "node"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            node_path = result.stdout.strip()
    except:
        pass
    
    try:
        result = subprocess.run(["which", "npm"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            npm_path = result.stdout.strip()
    except:
        pass
    
    # 如果直接调用失败，尝试在常见路径中查找
    if not node_path or not npm_path:
        import glob
        for path_pattern in possible_paths:
            if "*" in path_pattern:
                # 处理通配符路径
                for expanded_path in glob.glob(path_pattern):
                    if not node_path and os.path.exists(os.path.join(expanded_path, "node")):
                        node_path = os.path.join(expanded_path, "node")
                    if not npm_path and os.path.exists(os.path.join(expanded_path, "npm")):
                        npm_path = os.path.join(expanded_path, "npm")
            else:
                if not node_path and os.path.exists(os.path.join(path_pattern, "node")):
                    node_path = os.path.join(path_pattern, "node")
                if not npm_path and os.path.exists(os.path.join(path_pattern, "npm")):
                    npm_path = os.path.join(path_pattern, "npm")
    
    return node_path, npm_path

def check_dependencies():
    """检查依赖"""
    print("🔍 检查依赖...")
    
    # 检查Python
    if sys.version_info < (3, 9):
        print("❌ Python版本过低，需要Python 3.9+")
        return False
    print("✅ Python版本:", sys.version.split()[0])
    
    # 查找Node.js和npm路径
    node_path, npm_path = find_node_npm_paths()
    
    # 检查Node.js
    if node_path:
        try:
            result = subprocess.run([node_path, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                node_version = result.stdout.strip()
                print(f"✅ Node.js版本: {node_version} (路径: {node_path})")
            else:
                print("❌ Node.js无法正常运行")
                return False
        except Exception as e:
            print(f"❌ Node.js检查失败: {e}")
            return False
    else:
        print("❌ 未找到Node.js，请确保已安装Node.js")
        print("💡 提示: 如果使用nvm，请确保已激活Node.js版本")
        return False
    
    # 检查npm
    if npm_path:
        try:
            result = subprocess.run([npm_path, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                npm_version = result.stdout.strip()
                print(f"✅ npm版本: {npm_version} (路径: {npm_path})")
            else:
                print("❌ npm无法正常运行")
                return False
        except Exception as e:
            print(f"❌ npm检查失败: {e}")
            return False
    else:
        print("❌ 未找到npm，请确保已安装npm")
        return False
    
    # 将找到的路径存储为全局变量，供后续使用
    global FOUND_NODE_PATH, FOUND_NPM_PATH
    FOUND_NODE_PATH = node_path
    FOUND_NPM_PATH = npm_path
    
    return True

def setup_backend():
    """设置后端环境"""
    print("\n📦 设置后端环境...")
    
    # 检查虚拟环境
    venv_path = PROJECT_ROOT / "venv"
    if not venv_path.exists():
        print("创建Python虚拟环境...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    
    # 激活虚拟环境并安装依赖
    if os.name == 'nt':  # Windows
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
    
    # 只安装核心依赖
    print("安装核心Python依赖...")
    core_deps = [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0", 
        "pydantic>=2.5.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "PyYAML>=6.0.0"
    ]
    
    try:
        subprocess.run([str(pip_path), "install"] + core_deps, check=True, timeout=300)
        print("✅ 核心依赖安装完成")
    except subprocess.TimeoutExpired:
        print("⚠️ 依赖安装超时，尝试使用系统Python")
        python_path = sys.executable
    except subprocess.CalledProcessError as e:
        print(f"⚠️ 依赖安装失败: {e}, 尝试使用系统Python")
        python_path = sys.executable
    
    # 创建必要的目录
    directories = ["data/vectordb", "data/documents", "data/cache", "logs", "config", "backups"]
    for directory in directories:
        dir_path = PROJECT_ROOT / directory
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # 初始化配置文件
    setup_config_files()
    
    return python_path


def setup_config_files():
    """设置配置文件"""
    print("🔧 初始化配置文件...")
    
    # 复制示例配置文件
    config_files = [
        (".env.example", ".env"),
        ("config/config.example.yaml", "config/config.yaml"),
        ("config/mcp_servers.example.json", "config/mcp_servers.json")
    ]
    
    for example_file, target_file in config_files:
        example_path = PROJECT_ROOT / example_file
        target_path = PROJECT_ROOT / target_file
        
        if example_path.exists() and not target_path.exists():
            try:
                import shutil
                shutil.copy2(example_path, target_path)
                print(f"✅ 创建配置文件: {target_file}")
            except Exception as e:
                print(f"⚠️ 无法创建配置文件 {target_file}: {e}")
    
    # 验证配置
    try:
        # 添加项目路径到Python路径
        sys.path.insert(0, str(PROJECT_ROOT))
        
        # 尝试导入和验证配置
        from src.config import validate_config, auto_fix_config, get_settings
        
        print("🔍 验证配置...")
        settings = get_settings()
        validation_results = validate_config(settings)
        
        if validation_results:
            errors = [r for r in validation_results if r.severity == "error"]
            warnings = [r for r in validation_results if r.severity == "warning"]
            
            if warnings:
                print(f"⚠️ 发现 {len(warnings)} 个配置警告")
                # 尝试自动修复
                fixed_issues, remaining_errors = auto_fix_config(settings)
                if fixed_issues:
                    print(f"✅ 自动修复了 {len(fixed_issues)} 个问题")
            
            if errors:
                print(f"❌ 发现 {len(errors)} 个配置错误，请检查配置文件")
                for error in errors[:3]:  # 只显示前3个错误
                    print(f"   - {error}")
        else:
            print("✅ 配置验证通过")
    
    except ImportError:
        print("⚠️ 配置模块未安装，跳过配置验证")
    except Exception as e:
        print(f"⚠️ 配置验证失败: {e}")

def setup_frontend():
    """设置前端环境"""
    print("\n🌐 设置前端环境...")
    
    frontend_path = PROJECT_ROOT / "frontend"
    if not frontend_path.exists():
        print("❌ 前端目录不存在")
        return False
    
    # 检查node_modules
    node_modules = frontend_path / "node_modules"
    if not node_modules.exists():
        print("安装前端依赖...")
        # 使用之前找到的npm路径
        try:
            subprocess.run([FOUND_NPM_PATH, "install"], cwd=frontend_path, check=True, timeout=300)
            print("✅ 前端依赖安装完成")
        except subprocess.TimeoutExpired:
            print("⚠️ 前端依赖安装超时")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ 前端依赖安装失败: {e}")
            return False
        except Exception as e:
            print(f"❌ npm安装过程出错: {e}")
            return False
    else:
        print("✅ 前端依赖已安装")
    
    return True

def start_backend(python_path):
    """启动后端服务"""
    print("\n🔧 启动后端服务...")
    
    # 优先使用简化版本
    simple_script = PROJECT_ROOT / "run_simple_server.py"
    api_script = PROJECT_ROOT / "run_api_server.py"
    
    if simple_script.exists():
        print("使用简化版API服务器...")
        script_to_use = simple_script
    elif api_script.exists():
        print("使用完整版API服务器...")
        script_to_use = api_script
    else:
        print("❌ API服务器脚本不存在")
        return None
    
    # 启动后端服务
    backend_process = subprocess.Popen([
        str(python_path), str(script_to_use)
    ], cwd=PROJECT_ROOT)
    
    # 等待后端服务启动
    print("等待后端服务启动...")
    for i in range(30):  # 最多等待30秒
        try:
            import requests
            response = requests.get("http://localhost:8000/health", timeout=1)
            if response.status_code == 200:
                print("✅ 后端服务启动成功")
                return backend_process
        except:
            pass
        time.sleep(1)
        print(f"等待中... ({i+1}/30)")
    
    print("❌ 后端服务启动超时")
    return backend_process

def start_frontend():
    """启动前端服务"""
    print("\n🌐 启动前端服务...")
    
    frontend_path = PROJECT_ROOT / "frontend"
    
    # 使用之前找到的npm路径启动前端服务
    try:
        frontend_process = subprocess.Popen([
            FOUND_NPM_PATH, "run", "dev"
        ], cwd=frontend_path)
        print("✅ 前端服务启动中...")
        return frontend_process
    except Exception as e:
        print(f"❌ 前端服务启动失败: {e}")
        return None

def wait_for_services(backend_process, frontend_process):
    """等待服务运行"""
    print("\n🎉 服务启动完成！")
    print("📖 访问地址:")
    print("   - 后端API: http://localhost:8000")
    print("   - API文档: http://localhost:8000/docs")
    print("   - 前端界面: http://localhost:3000")
    print("\n按 Ctrl+C 停止所有服务")
    
    try:
        # 等待进程结束
        while True:
            if backend_process.poll() is not None:
                print("❌ 后端服务已停止")
                break
            if frontend_process.poll() is not None:
                print("❌ 前端服务已停止")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
        
        # 停止进程
        try:
            backend_process.terminate()
            frontend_process.terminate()
            
            # 等待进程结束
            backend_process.wait(timeout=5)
            frontend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # 强制杀死进程
            backend_process.kill()
            frontend_process.kill()
        
        print("✅ 所有服务已停止")

def main():
    """主函数"""
    print_banner()
    
    try:
        # 检查依赖
        if not check_dependencies():
            print("\n❌ 依赖检查失败，请安装必要的依赖")
            sys.exit(1)
        
        # 设置环境
        python_path = setup_backend()
        if not setup_frontend():
            print("\n❌ 前端环境设置失败")
            sys.exit(1)
        
        # 启动服务
        backend_process = start_backend(python_path)
        if not backend_process:
            print("\n❌ 后端服务启动失败")
            sys.exit(1)
        
        frontend_process = start_frontend()
        if not frontend_process:
            print("\n❌ 前端服务启动失败")
            backend_process.terminate()
            sys.exit(1)
        
        # 等待服务运行
        wait_for_services(backend_process, frontend_process)
        
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 