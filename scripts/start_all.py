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
    """查找Node.js和npm的路径（跨平台兼容）"""
    node_path = None
    npm_path = None

    # 首先尝试直接执行命令来验证是否在PATH中
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            # 如果可以直接执行，就使用命令名
            node_path = "node"
    except:
        pass

    # 对于 npm，在 Windows 上需要特殊处理
    try:
        if os.name == "nt":  # Windows
            # 在 Windows 上，npm 可能是 .ps1 脚本，需要通过 PowerShell 执行
            result = subprocess.run(
                ["powershell", "-Command", "npm --version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        else:
            result = subprocess.run(
                ["npm", "--version"], capture_output=True, text=True, timeout=5
            )

        if result.returncode == 0:
            # 如果可以直接执行，就使用命令名
            npm_path = "npm"
    except:
        pass

    # 如果直接执行成功，就不需要查找具体路径了
    if node_path and npm_path:
        return node_path, npm_path

    # 如果直接执行失败，尝试使用which/where命令查找路径
    if os.name == "nt":  # Windows
        node_exe = "node.exe"
        npm_exe = "npm.cmd"
        which_cmd = "where"
    else:  # Unix/Linux/macOS
        node_exe = "node"
        npm_exe = "npm"
        which_cmd = "which"

    if not node_path:
        try:
            result = subprocess.run(
                [which_cmd, "node"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                node_path = result.stdout.strip().split("\n")[0]
        except:
            pass

    if not npm_path:
        try:
            result = subprocess.run(
                [which_cmd, "npm"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                npm_path = result.stdout.strip().split("\n")[0]
        except:
            pass

    # 如果还是找不到，尝试在常见路径中查找
    if not node_path or not npm_path:
        import glob

        # 根据操作系统定义可能的安装路径
        if os.name == "nt":  # Windows
            possible_paths = [
                # Node.js官方安装路径
                "C:/Program Files/nodejs",
                "C:/Program Files (x86)/nodejs",
                # nvm-windows路径
                os.path.expanduser("~/AppData/Roaming/nvm/*/"),
                # Chocolatey路径
                "C:/ProgramData/chocolatey/lib/nodejs/tools",
                # Scoop路径
                os.path.expanduser("~/scoop/apps/nodejs/current"),
                # 用户本地安装
                os.path.expanduser("~/nodejs"),
            ]
        else:  # Unix/Linux/macOS
            possible_paths = [
                # nvm路径
                os.path.expanduser("~/.nvm/versions/node/*/bin"),
                # 系统路径
                "/usr/bin",
                "/usr/local/bin",
                # Homebrew路径 (macOS)
                "/opt/homebrew/bin",
                "/usr/local/Cellar/node/*/bin",
                # 其他可能的路径
                "/opt/node/bin",
                os.path.expanduser("~/node/bin"),
            ]

        for path_pattern in possible_paths:
            if "*" in path_pattern:
                # 处理通配符路径
                try:
                    for expanded_path in glob.glob(path_pattern):
                        if not node_path and os.path.exists(
                            os.path.join(expanded_path, node_exe)
                        ):
                            node_path = os.path.join(expanded_path, node_exe)
                        if not npm_path and os.path.exists(
                            os.path.join(expanded_path, npm_exe)
                        ):
                            npm_path = os.path.join(expanded_path, npm_exe)
                except:
                    continue
            else:
                if not node_path and os.path.exists(
                    os.path.join(path_pattern, node_exe)
                ):
                    node_path = os.path.join(path_pattern, node_exe)
                if not npm_path and os.path.exists(os.path.join(path_pattern, npm_exe)):
                    npm_path = os.path.join(path_pattern, npm_exe)

    return node_path, npm_path


def check_dependencies():
    """检查Node.js和npm依赖"""
    print("🔍 检查Node.js依赖...")

    # 查找Node.js和npm路径
    node_path, npm_path = find_node_npm_paths()

    # 检查Node.js
    if node_path:
        try:
            if node_path == "node":
                # 直接使用命令名
                result = subprocess.run(
                    ["node", "--version"], capture_output=True, text=True, timeout=5
                )
            else:
                # 使用完整路径
                result = subprocess.run(
                    [node_path, "--version"], capture_output=True, text=True, timeout=5
                )

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
        print("❌ 未找到Node.js")
        print("💡 提示: 请安装Node.js以启用前端服务")
        print("   - 下载地址: https://nodejs.org/")
        if os.name != "nt":
            print(
                "   - 或使用nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
            )
        return False

    # 检查npm
    if npm_path:
        try:
            if npm_path == "npm":
                # 直接使用命令名，在Windows上通过PowerShell执行
                if os.name == "nt":
                    result = subprocess.run(
                        ["powershell", "-Command", "npm --version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                else:
                    result = subprocess.run(
                        ["npm", "--version"], capture_output=True, text=True, timeout=5
                    )
            else:
                # 使用完整路径
                result = subprocess.run(
                    [npm_path, "--version"], capture_output=True, text=True, timeout=5
                )

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
        print("❌ 未找到npm")
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
    if os.name == "nt":  # Windows
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"

    # 检查并安装依赖
    print("检查Python依赖...")
    requirements_file = PROJECT_ROOT / "requirements.txt"

    if requirements_file.exists():
        print("安装完整项目依赖...")
        try:
            # 先升级pip
            subprocess.run(
                [str(pip_path), "install", "--upgrade", "pip"], check=True, timeout=120
            )

            # 安装项目依赖
            subprocess.run(
                [str(pip_path), "install", "-r", str(requirements_file)],
                check=True,
                timeout=600,
            )  # 10分钟超时
            print("✅ 项目依赖安装完成")
        except subprocess.TimeoutExpired:
            print("⚠️ 依赖安装超时，尝试安装核心依赖")
            # 回退到核心依赖
            core_deps = [
                "fastapi>=0.104.0",
                "uvicorn[standard]>=0.24.0",
                "pydantic>=2.5.0",
                "pydantic-settings>=2.0.0",
                "python-dotenv>=1.0.0",
                "PyYAML>=6.0.0",
                "aiofiles>=23.0.0",
                "requests>=2.31.0",
            ]
            try:
                subprocess.run(
                    [str(pip_path), "install"] + core_deps, check=True, timeout=300
                )
                print("✅ 核心依赖安装完成")
            except Exception as e:
                print(f"⚠️ 核心依赖安装失败: {e}, 使用系统Python")
                python_path = sys.executable
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 依赖安装失败: {e}, 尝试使用系统Python")
            python_path = sys.executable
    else:
        print("⚠️ requirements.txt不存在，跳过依赖安装")
        python_path = sys.executable

    # 创建必要的目录
    directories = [
        "data/vectordb",
        "data/documents",
        "data/cache",
        "logs",
        "config",
        "backups",
    ]
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
        ("config/mcp_servers.example.json", "config/mcp_servers.json"),
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
        try:
            # 构建 npm install 命令
            if os.name == "nt" and FOUND_NPM_PATH == "npm":
                # Windows 上使用 PowerShell 执行 npm
                cmd = ["powershell", "-Command", "npm install"]
            else:
                cmd = [FOUND_NPM_PATH, "install"]

            subprocess.run(cmd, cwd=frontend_path, check=True, timeout=300)
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

    # 直接使用uvicorn启动服务器，避免复杂的导入问题
    print("使用uvicorn直接启动API服务器...")

    # 启动后端服务
    cmd = [
        str(python_path),
        "-m",
        "uvicorn",
        "src.server.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]

    # 设置环境变量
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    backend_process = subprocess.Popen(cmd, cwd=PROJECT_ROOT, env=env)

    # 等待后端服务启动
    print("等待后端服务启动...")
    for i in range(60):  # 等待60秒
        try:
            import requests

            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                print("✅ 后端服务启动成功")
                return backend_process
        except:
            pass
        time.sleep(1)
        if i % 10 == 9:  # 每10秒显示一次进度
            print(f"等待中... ({i+1}/60)")

    print("❌ 后端服务启动超时，但进程可能仍在运行")
    return backend_process


def start_frontend():
    """启动前端服务"""
    print("\n🌐 启动前端服务...")

    frontend_path = PROJECT_ROOT / "frontend"

    try:
        # 构建 npm run dev 命令
        if os.name == "nt" and FOUND_NPM_PATH == "npm":
            # Windows 上使用 PowerShell 执行 npm
            cmd = ["powershell", "-Command", "npm run dev"]
        else:
            cmd = [FOUND_NPM_PATH, "run", "dev"]

        frontend_process = subprocess.Popen(cmd, cwd=frontend_path)
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
        # 检查Python依赖
        if sys.version_info < (3, 9):
            print("❌ Python版本过低，需要Python 3.9+")
            sys.exit(1)
        print("✅ Python版本:", sys.version.split()[0])

        # 设置后端环境
        python_path = setup_backend()

        # 检查Node.js依赖
        node_dependencies_ok = check_dependencies()

        if node_dependencies_ok:
            # 完整启动（后端 + 前端）
            if not setup_frontend():
                print("\n⚠️ 前端环境设置失败，仅启动后端服务")
                node_dependencies_ok = False

        # 启动后端服务
        backend_process = start_backend(python_path)
        if not backend_process:
            print("\n❌ 后端服务启动失败")
            sys.exit(1)

        frontend_process = None
        if node_dependencies_ok:
            # 尝试启动前端服务
            frontend_process = start_frontend()
            if not frontend_process:
                print("\n⚠️ 前端服务启动失败，仅运行后端服务")

        # 等待服务运行
        if frontend_process:
            wait_for_services(backend_process, frontend_process)
        else:
            wait_for_backend_only(backend_process)

    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)


def wait_for_backend_only(backend_process):
    """仅等待后端服务运行"""
    print("\n🎉 后端服务启动完成！")
    print("📖 访问地址:")
    print("   - 后端API: http://localhost:8000")
    print("   - API文档: http://localhost:8000/docs")
    print("   - 健康检查: http://localhost:8000/health")
    print("\n💡 提示: 安装Node.js后可启动完整的前后端服务")
    print("\n按 Ctrl+C 停止服务")

    try:
        # 等待进程结束
        while True:
            if backend_process.poll() is not None:
                print("❌ 后端服务已停止")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
        try:
            backend_process.terminate()
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_process.kill()
        print("✅ 后端服务已停止")


if __name__ == "__main__":
    main()
