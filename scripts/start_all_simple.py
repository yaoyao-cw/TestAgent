#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestAgent简化启动脚本
同时启动后端API服务器和前端开发服务器
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

def print_banner():
    """打印启动横幅"""
    print("=" * 60)
    print("🚀 TestAgent 简化启动脚本")
    print("=" * 60)
    print("📍 项目目录:", PROJECT_ROOT)
    print("🔧 后端服务: http://localhost:8000")
    print("🌐 前端服务: http://localhost:3000")
    print("=" * 60)

def start_backend():
    """启动后端服务"""
    print("\n🔧 启动后端服务...")
    
    # 使用虚拟环境中的Python
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if not venv_python.exists():
        print("❌ 虚拟环境不存在，请先创建虚拟环境")
        return None
    
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
    try:
        backend_process = subprocess.Popen([
            str(venv_python), str(script_to_use)
        ], cwd=PROJECT_ROOT)
        print("✅ 后端服务启动中...")
        return backend_process
    except Exception as e:
        print(f"❌ 后端服务启动失败: {e}")
        return None

def start_frontend():
    """启动前端服务"""
    print("\n🌐 启动前端服务...")
    
    frontend_path = PROJECT_ROOT / "frontend"
    if not frontend_path.exists():
        print("❌ 前端目录不存在")
        return None
    
    # 检查node_modules
    node_modules = frontend_path / "node_modules"
    if not node_modules.exists():
        print("❌ 前端依赖未安装，请先运行: cd frontend && npm install")
        return None
    
    # 启动前端服务
    try:
        # 设置环境变量以确保能找到node和npm
        env = os.environ.copy()
        nvm_path = os.path.expanduser("~/.nvm/versions/node/v18.20.7/bin")
        if os.path.exists(nvm_path):
            env['PATH'] = f"{nvm_path}:{env.get('PATH', '')}"
        
        frontend_process = subprocess.Popen([
            "npm", "run", "dev"
        ], cwd=frontend_path, env=env)
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
    
    def signal_handler(sig, frame):
        print("\n🛑 正在停止服务...")
        try:
            if backend_process:
                backend_process.terminate()
            if frontend_process:
                frontend_process.terminate()
            
            # 等待进程结束
            time.sleep(2)
            
            if backend_process and backend_process.poll() is None:
                backend_process.kill()
            if frontend_process and frontend_process.poll() is None:
                frontend_process.kill()
                
        except Exception as e:
            print(f"停止服务时出错: {e}")
        
        print("✅ 所有服务已停止")
        sys.exit(0)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 等待进程结束
        while True:
            if backend_process and backend_process.poll() is not None:
                print("❌ 后端服务已停止")
                break
            if frontend_process and frontend_process.poll() is not None:
                print("❌ 前端服务已停止")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

def main():
    """主函数"""
    print_banner()
    
    try:
        # 启动服务
        backend_process = start_backend()
        if not backend_process:
            print("\n❌ 后端服务启动失败")
            sys.exit(1)
        
        # 等待一下让后端启动
        time.sleep(2)
        
        frontend_process = start_frontend()
        if not frontend_process:
            print("\n❌ 前端服务启动失败")
            if backend_process:
                backend_process.terminate()
            sys.exit(1)
        
        # 等待服务运行
        wait_for_services(backend_process, frontend_process)
        
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)





if __name__ == "__main__":
    main()