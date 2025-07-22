#!/usr/bin/env python3
"""直接测试简化的Python REPL工具"""

import sys
import os
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)

# 直接导入简化版本
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'tools'))
from python_repl_simple import python_repl_tool, repl

def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试基本功能 ===")
    
    # 测试简单计算
    result = python_repl_tool("print(1 + 1)")
    print(f"1 + 1 结果:\n{result}\n")
    
    # 测试表达式
    result = python_repl_tool("2 * 3")
    print(f"2 * 3 结果:\n{result}\n")
    
    # 测试数学函数
    result = python_repl_tool("print(math.sqrt(16))")
    print(f"数学函数结果:\n{result}\n")

def test_error_handling():
    """测试错误处理"""
    print("=== 测试错误处理 ===")
    
    # 测试语法错误
    result = python_repl_tool("print(1 + )")
    print(f"语法错误结果:\n{result}\n")
    
    # 测试运行时错误
    result = python_repl_tool("print(1 / 0)")
    print(f"运行时错误结果:\n{result}\n")

def test_security():
    """测试安全性"""
    print("=== 测试安全性 ===")
    
    # 测试危险函数调用
    result = python_repl_tool("exec('print(\"hello\")')")
    print(f"exec调用结果:\n{result}\n")
    
    # 测试导入限制
    result = python_repl_tool("import os")
    print(f"导入限制结果:\n{result}\n")

def test_comparison_with_deer_flow():
    """与deer-flow风格对比测试"""
    print("=== 与deer-flow风格对比 ===")
    
    # 测试简单成功案例
    result = python_repl_tool("print(1 + 1)")
    print(f"成功案例:\n{result}\n")
    
    # 测试错误案例
    result = python_repl_tool("print(1 / 0)")
    print(f"错误案例:\n{result}\n")

if __name__ == "__main__":
    print("开始测试简化的Python REPL工具...")
    
    test_basic_functionality()
    test_error_handling()
    test_security()
    test_comparison_with_deer_flow()
    
    print("测试完成！")