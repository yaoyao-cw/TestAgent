#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestAgent简化启动脚本
快速启动前后端服务，避免阻塞问题
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

def print_banner():
    """打印启动横幅"""
    print("=" * 50)
    print("🚀 TestAgent 简化启动脚本")
    print("=" * 50)
    print("📍 项目目录:", PROJECT_ROOT)
    print("🔧 后端服务: http://localhost:8000")
    print("🌐 前端服务: http://localhost:3000")
    print("=" * 50)

def start_backend():
    """启动后端服务"""
    print("\n🔧 启动后端服务...")
    
    # 检查后端脚本
    simple_script = PROJECT_ROOT / "run_simple_server.py"
    api_script = PROJECT_ROOT / "run_api_server.py"
    
    if simple_script.exists():
        script_to_use = simple_script
        print("使用简化版API服务器...")
    elif api_script.exists():
        script_to_use = api_script
        print("使用完整版API服务器...")
    else:
        print("❌ 找不到API服务器脚本")
        return None
    
    # 使用虚拟环境的Python
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = sys.executable
    
    # 启动后端（非阻塞）
    try:
        backend_process = subprocess.Popen([
            str(venv_python), str(script_to_use)
        ], cwd=PROJECT_ROOT)
        print("✅ 后端服务启动中...")
        return backend_process
    except Exception as e:
        print(f"❌ 后端启动失败: {e}")
        return None

def start_frontend():
    """启动前端服务"""
    print("\n🌐 启动前端服务...")
    
    frontend_path = PROJECT_ROOT / "frontend"
    if not frontend_path.exists():
        print("❌ 前端目录不存在")
        return None
    
    # 启动前端（非阻塞）
    try:
        frontend_process = subprocess.Popen([
            "npm", "run", "dev"
        ], cwd=frontend_path, shell=True)
        print("✅ 前端服务启动中...")
        return frontend_process
    except Exception as e:
        print(f"❌ 前端启动失败: {e}")
        return None

def main():
    """主函数"""
    print_banner()
    
    # 启动后端
    backend_process = start_backend()
    if not backend_process:
        print("❌ 后端启动失败")
        return
    
    # 等待一秒
    time.sleep(1)
    
    # 启动前端
    frontend_process = start_frontend()
    if not frontend_process:
        print("❌ 前端启动失败")
        if backend_process:
            backend_process.terminate()
        return
    
    print("\n🎉 服务启动完成！")
    print("📖 访问地址:")
    print("   - 后端API: http://localhost:8000")
    print("   - API文档: http://localhost:8000/docs")
    print("   - 前端界面: http://localhost:3000")
    print("\n提示: 服务在后台运行，可以关闭此终端")
    print("要停止服务，请使用: pkill -f 'run_simple_server\\|vite'")

if __name__ == "__main__":
    main()