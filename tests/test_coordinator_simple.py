#!/usr/bin/env python3
"""
协调器节点简化演示脚本
"""

import os
import sys

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.graph.nodes import CoordinatorNode


def test_coordinator_methods():
    """测试协调器的基础方法"""
    print("=== 协调器基础功能演示 ===")

    coordinator = CoordinatorNode()

    # 测试语言检测
    print("\n1. 语言检测测试：")
    test_texts = [
        "请帮我生成测试用例",
        "Generate test cases for login",
        "Hello, 你好世界",
        "This is English text",
        "这是中文文本",
    ]

    for text in test_texts:
        locale = coordinator._detect_language(text)
        print(f"'{text}' -> {locale}")

    # 测试简单回复生成
    print("\n2. 简单回复生成测试：")
    test_cases = [
        ("你好", "zh-CN"),
        ("Hello", "en-US"),
        ("今天天气怎么样？", "zh-CN"),
        ("What's the weather like?", "en-US"),
    ]

    for user_input, locale in test_cases:
        response = coordinator._generate_simple_response(user_input, locale)
        print(f"输入: '{user_input}' ({locale})")
        print(f"回复: {response[:100]}...")
        print()

    # 测试错误响应生成
    print("\n3. 错误响应生成测试：")
    error_cases = [("连接超时", "zh-CN"), ("Connection timeout", "en-US")]

    for error, locale in error_cases:
        response = coordinator._generate_error_response(error, locale)
        print(f"错误: '{error}' ({locale})")
        print(f"响应: {response[:100]}...")
        print()

    print("✅ 协调器基础功能演示完成")


if __name__ == "__main__":
    test_coordinator_methods()
