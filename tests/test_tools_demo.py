"""工具演示脚本"""

import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.tools import PythonREPL, get_tool_registry, list_available_tools
from src.tools.tool_examples import (
    calculator_tool,
    code_executor_tool,
    data_analyzer_tool,
)


async def demo_python_repl():
    """演示Python REPL工具"""
    print("=== Python REPL 工具演示 ===")

    repl = PythonREPL(timeout=10)

    # 测试简单计算
    print("\n1. 简单计算:")
    result = await repl.execute_code("2 + 3 * 4")
    print(f"   代码: 2 + 3 * 4")
    print(f"   结果: {result['result']}")
    print(f"   成功: {result['success']}")

    # 测试变量操作
    print("\n2. 变量操作:")
    result = await repl.execute_code("x = 10\ny = 20\nprint(f'x + y = {x + y}')")
    print(f"   代码: x = 10; y = 20; print(f'x + y = {{x + y}}')")
    print(f"   输出: {result['output'].strip()}")

    # 测试数学函数
    print("\n3. 数学函数:")
    result = await repl.execute_code("import math\nmath.sqrt(16)")
    print(f"   代码: import math; math.sqrt(16)")
    print(f"   结果: {result['result']}")

    # 测试列表操作
    print("\n4. 列表操作:")
    code = """
numbers = [1, 2, 3, 4, 5]
squares = [n**2 for n in numbers]
print(f"原数字: {numbers}")
print(f"平方: {squares}")
sum(squares)
"""
    result = await repl.execute_code(code)
    print(f"   输出: {result['output'].strip()}")
    print(f"   返回值: {result['result']}")

    # 测试错误处理
    print("\n5. 错误处理:")
    result = await repl.execute_code("1 / 0")
    print(f"   代码: 1 / 0")
    print(f"   成功: {result['success']}")
    print(f"   错误: {result['error']}")


async def demo_tool_decorators():
    """演示工具装饰器"""
    print("\n=== 工具装饰器演示 ===")

    # 测试计算器工具
    print("\n1. 计算器工具:")
    result = await calculator_tool("(10 + 5) * 2")
    print(f"   表达式: (10 + 5) * 2")
    print(f"   结果: {result['result']}")
    print(f"   成功: {result['success']}")

    # 测试代码执行工具
    print("\n2. 代码执行工具:")
    code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = [fibonacci(i) for i in range(8)]
print(f"斐波那契数列前8项: {result}")
"""
    result = await code_executor_tool(code)
    print(f"   执行成功: {result['success']}")
    print(f"   输出: {result['output'].strip()}")
    print(f"   执行时间: {result['execution_time']:.3f}秒")

    # 测试数据分析工具
    print("\n3. 数据分析工具:")
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25]
    result = await data_analyzer_tool(data, "advanced")
    print(f"   数据: {data}")
    print(f"   分析成功: {result['success']}")
    if result["success"]:
        analysis = result["analysis"]
        print(f"   统计信息:")
        print(f"     数量: {analysis['count']}")
        print(f"     平均值: {analysis['mean']:.2f}")
        print(f"     中位数: {analysis['median']:.2f}")
        print(f"     标准差: {analysis['std_dev']:.2f}")
        print(f"     最小值: {analysis['min']}")
        print(f"     最大值: {analysis['max']}")


def demo_tool_registry():
    """演示工具注册表"""
    print("\n=== 工具注册表演示 ===")

    registry = get_tool_registry()

    # 列出所有工具
    tools = list_available_tools()
    print(f"\n注册的工具数量: {len(tools)}")

    for name, info in tools.items():
        print(f"\n工具: {name}")
        print(f"  描述: {info.get('description', 'N/A')}")
        print(f"  类别: {info.get('category', 'N/A')}")
        print(f"  标签: {info.get('tags', [])}")
        print(f"  异步: {info.get('is_async', False)}")

        # 显示指标
        if hasattr(info.get("metrics"), "call_count"):
            metrics = info["metrics"]
            print(f"  调用次数: {metrics.call_count}")
            print(f"  成功次数: {metrics.success_count}")
            print(f"  错误次数: {metrics.error_count}")
            if metrics.call_count > 0:
                print(f"  平均执行时间: {metrics.avg_time:.3f}秒")


async def demo_error_handling():
    """演示错误处理"""
    print("\n=== 错误处理演示 ===")

    repl = PythonREPL(timeout=5)

    # 测试语法错误
    print("\n1. 语法错误:")
    result = await repl.execute_code("print(")
    print(f"   代码: print(")
    print(f"   成功: {result['success']}")
    print(f"   错误类型: 语法错误")

    # 测试运行时错误
    print("\n2. 运行时错误:")
    result = await repl.execute_code("undefined_variable")
    print(f"   代码: undefined_variable")
    print(f"   成功: {result['success']}")
    print(f"   错误: {result['error']}")

    # 测试安全限制
    print("\n3. 安全限制:")
    result = await repl.execute_code("import os")
    print(f"   代码: import os")
    print(f"   成功: {result['success']}")
    print(f"   错误: {result['error']}")

    # 测试超时
    print("\n4. 超时测试:")
    repl_short = PythonREPL(timeout=1)
    result = await repl_short.execute_code("import time; time.sleep(2)")
    print(f"   代码: import time; time.sleep(2)")
    print(f"   成功: {result['success']}")
    print(f"   错误: {result['error']}")


async def main():
    """主演示函数"""
    print("TestAgent 工具系统演示")
    print("=" * 50)

    try:
        # 演示Python REPL
        await demo_python_repl()

        # 演示工具装饰器
        await demo_tool_decorators()

        # 演示工具注册表
        demo_tool_registry()

        # 演示错误处理
        await demo_error_handling()

        print("\n" + "=" * 50)
        print("演示完成！")

    except Exception as e:
        print(f"\n演示过程中发生错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
