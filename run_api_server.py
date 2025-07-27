#!/usr/bin/env python3
"""
TestAgent API服务器启动脚本
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.server.main import start_server
from src.config.logging_config import setup_logging


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="TestAgent API服务器")
    parser.add_argument("--host", default="0.0.0.0", help="服务器主机地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="启用自动重载")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数")
    parser.add_argument("--log-level", default="info", help="日志级别")

    args = parser.parse_args()

    # 设置日志
    setup_logging(level=args.log_level.upper())

    # 创建必要的目录
    directories = ["data/vectordb", "data/documents", "data/cache", "logs", "config"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    print(f"🚀 启动TestAgent API服务器")
    print(f"📍 地址: http://{args.host}:{args.port}")
    print(f"📚 API文档: http://{args.host}:{args.port}/docs")
    print(f"🔧 工作进程: {args.workers}")
    print(f"🔄 自动重载: {'启用' if args.reload else '禁用'}")

    # 启动服务器
    start_server(
        host=args.host, port=args.port, reload=args.reload, workers=args.workers
    )


if __name__ == "__main__":
    main()
