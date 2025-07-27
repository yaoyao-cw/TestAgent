#!/usr/bin/env python3
"""基本沙盒测试"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_fallback_sandbox():
    """测试回退沙盒"""
    print("测试回退沙盒...")

    from src.tools.fallback_sandbox import FallbackSandboxExecutor

    async with FallbackSandboxExecutor() as executor:
        # 测试简单代码执行
        result = await executor.execute_python_code(
            'print("Hello from fallback sandbox!")'
        )
        print(f"成功: {result['success']}")
        print(f"输出: {result['stdout'].strip()}")
        print(f"沙盒ID: {result.get('sandbox_id', 'unknown')}")

        # 测试脚本执行
        script_content = """
import math
print(f"圆周率: {math.pi}")
print(f"平方根: {math.sqrt(16)}")
"""
        result = await executor.execute_python_script(script_content, "math_test.py")
        print(f"\n脚本执行成功: {result['success']}")
        print(f"脚本输出: {result['stdout'].strip()}")


async def test_unified_sandbox():
    """测试统一沙盒"""
    print("\n测试统一沙盒...")

    from src.tools.unified_sandbox import UnifiedSandboxExecutor

    async with UnifiedSandboxExecutor(prefer_e2b=False) as executor:
        print(f"沙盒类型: {executor.get_sandbox_type()}")

        # 测试代码执行
        result = await executor.execute_python_code(
            'print("Hello from unified sandbox!")'
        )
        print(f"成功: {result['success']}")
        print(f"输出: {result['stdout'].strip()}")
        print(f"沙盒类型: {result.get('sandbox_type', 'unknown')}")


async def test_enhanced_executor():
    """测试增强执行器"""
    print("\n测试增强执行器...")

    from src.agents.executor import EnhancedSandboxExecutor

    async with EnhancedSandboxExecutor(prefer_e2b=False) as executor:
        print(f"沙盒类型: {executor.get_sandbox_type()}")

        # 测试代码执行
        result = await executor.execute_python_code(
            'print("Hello from enhanced executor!")'
        )
        print(f"成功: {result['success']}")
        print(f"输出: {result['stdout'].strip()}")


async def main():
    """主测试函数"""
    try:
        await test_fallback_sandbox()
        await test_unified_sandbox()
        await test_enhanced_executor()
        print("\n所有测试完成!")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
