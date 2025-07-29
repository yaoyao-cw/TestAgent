#!/usr/bin/env python3
"""测试优化版本的Python REPL工具"""

import sys
import os
import time

# 导入优化版本
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "tools"))

from python_repl_optimized import (
    python_repl_tool,
    repl,
    get_repl_info,
    execute_with_details,
)


def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试基本功能 ===")

    # 测试简单计算
    print("\n1. 简单计算:")
    result = python_repl_tool("print(1 + 1)")
    print(result)

    # 测试表达式
    print("\n2. 表达式计算:")
    result = python_repl_tool("2 * 3 + 4")
    print(result)

    # 测试数学函数
    print("\n3. 数学函数:")
    result = python_repl_tool("math.sqrt(16)")
    print(result)

    # 测试复杂计算
    print("\n4. 复杂计算:")
    result = python_repl_tool("sum(i*i for i in range(10))")
    print(result)


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")

    # 语法错误
    print("\n1. 语法错误:")
    result = python_repl_tool("print(1 + )")
    print(result)

    # 运行时错误
    print("\n2. 运行时错误:")
    result = python_repl_tool("print(1 / 0)")
    print(result)

    # 未定义变量
    print("\n3. 未定义变量:")
    result = python_repl_tool("print(undefined_var)")
    print(result)


def test_security():
    """测试安全性"""
    print("\n=== 测试安全性 ===")

    # 危险函数调用
    print("\n1. 危险函数调用:")
    result = python_repl_tool("exec('print(\"hello\")')")
    print(result)

    # 文件操作
    print("\n2. 文件操作:")
    result = python_repl_tool("open('test.txt', 'w')")
    print(result)

    # 导入限制
    print("\n3. 导入限制:")
    result = python_repl_tool("import os")
    print(result)


def test_direct_repl():
    """测试直接REPL接口"""
    print("\n=== 测试直接REPL接口 ===")

    # 测试run方法
    print("\n1. run方法:")
    result = repl.run("print('Hello from REPL')")
    print(f"结果: {result}")

    # 测试详细信息
    print("\n2. 详细执行信息:")
    details = execute_with_details("x = 5; print(x * 2)")
    print(f"详细信息: {details}")


def test_performance():
    """测试性能"""
    print("\n=== 测试性能 ===")

    # 简单计算性能
    start_time = time.time()
    result = python_repl_tool("sum(range(1000))")
    end_time = time.time()
    print(f"简单计算: {result}")
    print(f"执行时间: {end_time - start_time:.4f}秒")

    # 复杂计算性能
    start_time = time.time()
    result = python_repl_tool("sum(i*i*i for i in range(1000))")
    end_time = time.time()
    print(f"复杂计算: {result}")
    print(f"执行时间: {end_time - start_time:.4f}秒")


def test_deer_flow_compatibility():
    """测试与deer-flow的兼容性"""
    print("\n=== 测试deer-flow兼容性 ===")

    # 类似deer-flow的使用方式
    test_cases = [
        "print(1 + 1)",
        "2 + 3",
        "print('Hello, World!')",
        "math.pi",
        "len([1, 2, 3, 4, 5])",
    ]

    for code in test_cases:
        print(f"\n代码: {code}")
        result = python_repl_tool(code)
        print(f"结果: {result}")


def show_repl_info():
    """显示REPL信息"""
    print("\n=== REPL信息 ===")
    info = get_repl_info()
    for key, value in info.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    print("开始测试优化版本的Python REPL工具...")

    show_repl_info()
    test_basic_functionality()
    test_error_handling()
    test_security()
    test_direct_repl()
    test_performance()
    test_deer_flow_compatibility()

    print("\n测试完成！")
