#!/usr/bin/env python3
"""比较不同Python REPL实现的效果"""

import sys
import os
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)

# 直接导入简化版本
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "tools"))
from python_repl_simple import python_repl_tool, repl


def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试基本功能 ===")

    # 测试基本计算
    result = python_repl_tool("print(1 + 1)")
    print(f"基本计算: {result}")

    # 测试表达式返回值
    result = python_repl_tool("2 * 3 + 4")
    print(f"表达式计算: {result}")


def test_security():
    """测试安全性"""
    print("\n=== 测试安全性 ===")

    # 测试危险操作
    result = python_repl_tool("exec('print(\"hello\")')")
    print(f"exec阻止: {result}")

    result = python_repl_tool("import os")
    print(f"import阻止: {result}")


if __name__ == "__main__":
    print("开始测试...")
    test_basic_functionality()
    test_security()
    print("测试完成！")
