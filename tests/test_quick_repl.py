#!/usr/bin/env python3
"""快速测试优化版本的Python REPL工具"""

import os
import sys

# 导入优化版本
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "tools"))

from python_repl_optimized import python_repl_tool


def quick_test():
    """快速功能测试"""
    print("🚀 快速测试优化版本的Python REPL工具")
    print("=" * 50)

    # 测试用例
    test_cases = [
        ("基本计算", "print(2 + 3)"),
        ("数学函数", "math.sqrt(25)"),
        ("列表操作", "len([1, 2, 3, 4, 5])"),
        ("字符串操作", "print('Hello, World!'.upper())"),
        ("循环计算", "sum(range(1, 11))"),
        ("条件表达式", "max([1, 5, 3, 9, 2])"),
        ("安全测试-exec", "exec('print(1)')"),
        ("安全测试-import", "import os"),
        ("错误测试", "1 / 0"),
    ]

    for name, code in test_cases:
        print(f"\n📝 {name}:")
        print(f"代码: {code}")
        result = python_repl_tool(code)

        # 简化输出显示
        if "Successfully executed:" in result:
            # 提取输出部分
            lines = result.split("\n")
            stdout_line = [line for line in lines if line.startswith("Stdout:")]
            if stdout_line:
                print(f"✅ 结果: {stdout_line[0].replace('Stdout: ', '')}")
            else:
                print("✅ 执行成功")
        else:
            # 错误情况
            if "Error:" in result:
                error_part = result.split("Error:")[-1].strip()
                print(f"❌ 错误: {error_part}")
            else:
                print(f"❌ {result}")

    print("\n" + "=" * 50)
    print("🎉 快速测试完成！")


if __name__ == "__main__":
    quick_test()
