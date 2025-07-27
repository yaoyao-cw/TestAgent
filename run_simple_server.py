#!/usr/bin/env python3
"""
TestAgent简化API服务器启动脚本
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """主函数"""
    print("🚀 启动TestAgent简化API服务器")
    print("=" * 50)

    # 创建必要的目录
    directories = ["data", "logs"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    # 启动服务器
    from src.server.main_simple import start_server

    start_server(host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
