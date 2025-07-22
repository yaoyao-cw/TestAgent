#!/usr/bin/env python3
"""比较不同Python REPL实现的效果"""

import sys
import os
import time

# 直接导入简化版本
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'tools'))

from python_repl_simple import SimplePythonREPL, python_repl_tool

def test_simple_repl():
    """测试简化版本的REPL"""
    print("=== 测试简化版本的Python REPL ===")
    
    repl = SimplePythonREPL()
    
    # 测试基本计算
    print("\n1. 基本计算测试:")
    result = repl.run("print(1 + 1)")
    print(f"1 + 1 = {result}")
    
    # 测试表达式返回值
    print("\n2. 表达式测试:")
    result = repl.run("2 * 3 + 4")
    print(f"2 * 3 + 4 = {result}")
    
    # 测试数学函数
    print("\n3. 数学函数测试:")
    result = repl.run("math.sqrt(16)")
    print(f"math.sqrt(16) = {result}")
    
    # 测试复杂计算
    print("\n4. 复杂计算测试:")
    result = repl.run("sum(range(1, 11))")
    print(f"sum(range(1, 11)) = {result}")
    
    # 测试错误处理
    print("\n5. 错误处理测试:")
    result = repl.run("1 / 0")
    print(f"1 / 0 错误: {result}")
    
    # 测试安全性
    print("\n6. 安全性测试:")
    result = repl.run("exec('print(\"hello\")')")
    print(f"exec调用: {result}")
    
    # 测试性能
    print("\n7. 性能测试:")
    start_time = time.time()
    result = repl.run("sum(i*i for i in range(1000))")
    end_time = time.time()
    print(f"大计算结果: {result}")
    print(f"执行时间: {end_time - start_time:.4f}秒")

def test_tool_interface():
    """测试工具接口"""
    print("\n=== 测试工具接口 ===")
    
    # 测试成功执行
    print("\n1. 成功执行:")
    result = python_repl_tool("print('Hello, World!')")
    print(result)
    
    # 测试计算
    print("\n2. 计算测试:")
    result = python_repl_tool("result = 10 * 5; print(f'10 * 5 = {result}')")
    print(result)
    
    # 测试错误
    print("\n3. 错误测试:")
    result = python_repl_tool("print(undefined_var)")
    print(result)

def compare_with_langchain_style():
    """比较与LangChain风格的差异"""
    print("\n=== 与LangChain风格比较 ===")
    
    # 我们的实现
    print("\n我们的实现:")
    repl = SimplePythonREPL()
    
    test_cases = [
        "print(1 + 1)",
        "2 * 3",
        "print(1 / 0)",
        "undefined_variable"
    ]
    
    for code in test_cases:
        print(f"\n代码: {code}")
        result = repl.run(code)
        print(f"结果: {result}")
        
        # 获取详细信息
        detailed = repl.execute_code(code)
        print(f"详细信息: success={detailed['success']}, time={detailed['execution_time']:.4f}s")

if __name__ == "__main__":
    print("开始比较Python REPL实现...")
    
    test_simple_repl()
    test_tool_interface()
    compare_with_langchain_style()
    
    print("\n比较测试完成！")