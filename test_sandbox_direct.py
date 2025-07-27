#!/usr/bin/env python3
"""直接测试沙盒组件"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_fallback_sandbox_direct():
    """直接测试回退沙盒"""
    print("直接测试回退沙盒...")

    from src.tools.fallback_sandbox import FallbackSandboxExecutor

    executor = FallbackSandboxExecutor(timeout=30)

    try:
        await executor.start_sandbox()
        print(f"沙盒启动成功，工作目录: {executor.temp_dir}")

        # 测试Python代码执行
        result = await executor.execute_python_code('print("Hello World!")')
        print(f"代码执行成功: {result['success']}")
        print(f"输出: {result['stdout'].strip()}")

        # 测试脚本执行
        script = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

for i in range(10):
    print(f"fib({i}) = {fibonacci(i)}")
"""
        result = await executor.execute_python_script(script, "fib.py")
        print(f"\n脚本执行成功: {result['success']}")
        print(f"执行时间: {result['execution_time']:.2f}秒")
        print("输出:")
        print(result["stdout"])

        # 测试pytest执行
        test_script = """
def test_addition():
    assert 1 + 1 == 2

def test_multiplication():
    assert 2 * 3 == 6

def test_division():
    assert 10 / 2 == 5
"""
        result = await executor.execute_pytest_script(test_script, "test_math.py")
        print(f"\npytest执行成功: {result['success']}")
        if result["success"]:
            test_results = result.get("test_results", {})
            print(f"测试结果: {test_results}")
        else:
            print(f"pytest错误: {result['error']}")

    finally:
        await executor.stop_sandbox()
        print("沙盒已停止")


async def test_unified_sandbox_direct():
    """直接测试统一沙盒"""
    print("\n直接测试统一沙盒...")

    from src.tools.unified_sandbox import UnifiedSandboxExecutor

    executor = UnifiedSandboxExecutor(prefer_e2b=False, timeout=30)

    try:
        await executor.start_sandbox()
        print(f"统一沙盒启动成功，类型: {executor.get_sandbox_type()}")

        # 测试代码执行
        result = await executor.execute_python_code(
            """
import json
data = {"message": "Hello from unified sandbox!", "numbers": [1, 2, 3, 4, 5]}
print(json.dumps(data, indent=2))
"""
        )
        print(f"代码执行成功: {result['success']}")
        print("输出:")
        print(result["stdout"])

        # 测试系统信息
        info = await executor.get_system_info()
        print(f"\n系统信息:")
        for key, value in info.items():
            print(f"  {key}: {value}")

    finally:
        await executor.stop_sandbox()
        print("统一沙盒已停止")


async def test_convenience_function():
    """测试便捷函数"""
    print("\n测试便捷函数...")

    from src.tools.unified_sandbox import execute_code_safely

    # 测试Python代码执行
    result = await execute_code_safely(
        'print("Hello from convenience function!")', execution_type="python", timeout=30
    )

    print(f"便捷函数执行成功: {result.is_successful()}")
    print(f"有输出: {result.has_output()}")
    print(f"沙盒类型: {result.sandbox_type}")
    print(f"输出: {result.stdout.strip()}")


async def main():
    """主测试函数"""
    try:
        await test_fallback_sandbox_direct()
        await test_unified_sandbox_direct()
        await test_convenience_function()
        print("\n所有直接测试完成!")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
