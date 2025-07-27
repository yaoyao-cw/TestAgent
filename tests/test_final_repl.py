#!/usr/bin/env python3
"""测试最终版本的Python REPL工具 - 包含所有扩展功能"""

import os
import sys

# 导入最终优化版本
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "tools"))

from python_repl_optimized import (batch_execute, execute_with_details,
                                   execute_with_metrics, get_performance_info,
                                   get_repl_info, get_security_info,
                                   python_repl_tool, validate_code_safety)


def test_info_functions():
    """测试信息查询函数"""
    print("🔍 测试信息查询功能")
    print("=" * 50)

    # 测试基本信息
    print("\n📋 REPL基本信息:")
    info = get_repl_info()
    print(f"名称: {info['name']}")
    print(f"版本: {info['version']}")
    print(f"描述: {info['description']}")
    print(f"可用模块: {', '.join(info['available_modules'])}")
    print(f"安全特性数量: {len(info['security_features'])}")

    # 测试安全信息
    print("\n🔒 安全配置信息:")
    security = get_security_info()
    print(f"安全级别: {security['security_level']}")
    print(f"沙箱启用: {security['sandbox_enabled']}")
    print(f"被阻止的函数数量: {len(security['blocked_functions'])}")
    print(f"允许的内置函数数量: {len(security['allowed_builtins'])}")

    # 测试性能信息
    print("\n⚡ 性能信息:")
    performance = get_performance_info()
    print(
        f"简单计算时间: {performance['performance_metrics']['simple_calculation_time']}"
    )
    print(f"超时限制: {performance['performance_metrics']['timeout_limit']}")
    print(f"优化特性数量: {len(performance['optimization_features'])}")


def test_detailed_execution():
    """测试详细执行功能"""
    print("\n📊 测试详细执行功能")
    print("=" * 50)

    # 测试基本详细执行
    print("\n1. 基本详细执行:")
    result = execute_with_details("x = 5; print(x * 2)")
    print(f"成功: {result['success']}")
    print(f"输出: {result['output']}")
    print(f"执行时间: {result['execution_time']:.4f}秒")

    # 测试性能指标执行
    print("\n2. 性能指标执行:")
    metrics = execute_with_metrics("sum(i*i for i in range(100))")
    print(f"成功: {metrics['success']}")
    print(f"输出: {metrics['output']}")
    print(f"代码长度: {metrics['performance_metrics']['code_length']}")
    print(f"代码行数: {metrics['performance_metrics']['code_lines']}")
    print(f"复杂度: {metrics['code_analysis']['estimated_complexity']}")
    print(f"安全评分: {metrics['code_analysis']['security_score']['safety_score']}")


def test_batch_execution():
    """测试批量执行功能"""
    print("\n📦 测试批量执行功能")
    print("=" * 50)

    codes = [
        "print(1 + 1)",
        "math.sqrt(16)",
        "len([1, 2, 3, 4, 5])",
        "sum(range(10))",
        "max([3, 1, 4, 1, 5])",
    ]

    results = batch_execute(codes)

    for i, result in enumerate(results):
        print(f"\n批次 {i+1}/{len(results)}:")
        print(f"  代码: {codes[i]}")
        print(f"  成功: {result['success']}")
        if result["success"]:
            print(f"  输出: {result['output']}")
        else:
            print(f"  错误: {result['error']}")


def test_safety_validation():
    """测试安全验证功能"""
    print("\n🛡️ 测试安全验证功能")
    print("=" * 50)

    test_codes = [
        ("安全代码", "print(math.sqrt(25))"),
        ("危险exec", "exec('print(1)')"),
        ("文件操作", "open('test.txt', 'w')"),
        ("模块导入", "import os"),
        ("私有属性", "[].__class__"),
    ]

    for name, code in test_codes:
        print(f"\n{name}:")
        validation = validate_code_safety(code)
        print(f"  代码: {code}")
        print(f"  安全: {'✅' if validation['is_safe'] else '❌'}")
        if not validation["is_safe"]:
            print(f"  错误: {validation['error_message']}")
        print(f"  建议: {validation['recommendations'][0]}")


def test_error_cases():
    """测试错误情况"""
    print("\n❌ 测试错误处理")
    print("=" * 50)

    error_codes = [
        ("语法错误", "print(1 + )"),
        ("运行时错误", "1 / 0"),
        ("名称错误", "undefined_variable"),
        ("类型错误", "'string' + 5"),
    ]

    for name, code in error_codes:
        print(f"\n{name}:")
        result = execute_with_details(code)
        print(f"  代码: {code}")
        print(f"  成功: {result['success']}")
        print(f"  错误: {result['error']}")


def test_performance_comparison():
    """测试性能对比"""
    print("\n🏃 测试性能对比")
    print("=" * 50)

    import time

    # 测试不同复杂度的代码
    test_cases = [
        ("简单计算", "1 + 1"),
        ("中等复杂", "sum(range(100))"),
        ("复杂计算", "sum(i*i*i for i in range(1000))"),
        ("字符串操作", "'hello world'.upper().replace('WORLD', 'PYTHON')"),
    ]

    for name, code in test_cases:
        start_time = time.time()
        result = python_repl_tool(code)
        end_time = time.time()

        print(f"\n{name}:")
        print(f"  执行时间: {end_time - start_time:.4f}秒")
        print(f"  成功: {'✅' if 'Successfully executed' in result else '❌'}")


def show_summary():
    """显示测试总结"""
    print("\n🎉 测试总结")
    print("=" * 50)

    info = get_repl_info()

    print(f"✅ {info['name']} v{info['version']} 测试完成")
    print(f"✅ 安全特性: {len(info['security_features'])} 项")
    print(f"✅ 功能特性: {len(info['features'])} 项")
    print(f"✅ 支持模块: {len(info['available_modules'])} 个")
    print(f"✅ 兼容性: {info['compatibility']}")

    print("\n🔥 主要优势:")
    print("  • 结合deer-flow简洁性和强安全性")
    print("  • 完整的错误处理和用户友好的错误信息")
    print("  • 丰富的工具函数和扩展接口")
    print("  • 详细的执行信息和性能监控")
    print("  • 批量执行和安全验证功能")


if __name__ == "__main__":
    print("🚀 开始测试最终版本的Python REPL工具")
    print("包含所有扩展功能的完整测试")

    test_info_functions()
    test_detailed_execution()
    test_batch_execution()
    test_safety_validation()
    test_error_cases()
    test_performance_comparison()
    show_summary()

    print("\n🎊 所有测试完成！")
