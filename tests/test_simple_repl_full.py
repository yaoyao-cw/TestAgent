#!/usr/bin/env python3
"""测试简化的Python REPL工具"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools.python_repl_simple import python_repl_tool, repl


def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试基本功能 ===")

    # 测试简单计算
    result = python_repl_tool("print(1 + 1)")
    print(f"1 + 1 结果: {result}")

    # 测试表达式
    result = python_repl_tool("2 * 3")
    print(f"2 * 3 结果: {result}")

    # 测试数学函数
    result = python_repl_tool("import math; print(math.sqrt(16))")
    print(f"数学函数结果: {result}")


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")

    # 测试语法错误
    result = python_repl_tool("print(1 + )")
    print(f"语法错误结果: {result}")

    # 测试运行时错误
    result = python_repl_tool("print(1 / 0)")
    print(f"运行时错误结果: {result}")

    # 测试未定义变量
    result = python_repl_tool("print(undefined_variable)")
    print(f"未定义变量结果: {result}")


def test_security():
    """测试安全性"""
    print("\n=== 测试安全性 ===")

    # 测试危险函数调用
    result = python_repl_tool("exec('print(\"hello\")')")
    print(f"exec调用结果: {result}")

    # 测试文件操作
    result = python_repl_tool("open('test.txt', 'w')")
    print(f"文件操作结果: {result}")

    # 测试导入限制
    result = python_repl_tool("import os")
    print(f"导入限制结果: {result}")


def test_direct_repl():
    """测试直接REPL接口"""
    print("\n=== 测试直接REPL接口 ===")

    # 测试run方法
    result = repl.run("print('Hello from direct REPL')")
    print(f"直接调用结果: {result}")

    # 测试execute_code方法
    result = repl.execute_code("x = 5; print(x * 2)")
    print(f"execute_code结果: {result}")


def test_math_operations():
    """测试数学运算"""
    print("\n=== 测试数学运算 ===")

    # 测试基本运算
    result = python_repl_tool("print(10 + 5, 10 - 5, 10 * 5, 10 / 5)")
    print(f"基本运算: {result}")

    # 测试数学模块
    result = python_repl_tool("print(math.pi, math.e)")
    print(f"数学常数: {result}")

    # 测试复杂计算
    result = python_repl_tool(
        "result = sum(range(1, 11)); print(f'1到10的和: {result}')"
    )
    print(f"复杂计算: {result}")


if __name__ == "__main__":
    print("开始测试简化的Python REPL工具...")

    test_basic_functionality()
    test_error_handling()
    test_security()
    test_direct_repl()
    test_math_operations()

    print("\n测试完成！")
