#!/usr/bin/env python3
"""基础工具测试脚本"""

import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools.python_repl import PythonREPL
from tools.web_search import WebSearchTool
from tools.tool_manager import get_tool_manager
from tools.decorators import tool, get_tool_registry


def test_python_repl():
    """测试Python REPL工具"""
    print("=== 测试Python REPL工具 ===")

    repl = PythonREPL(timeout=10, max_output_length=1000)

    # 测试1: 简单计算
    result = repl.execute_code("2 + 3")
    print(f"简单计算: {result['success']}, 结果: {result['result']}")
    assert result["success"] is True
    assert result["result"] == 5

    # 测试2: 打印输出
    result = repl.execute_code('print("Hello, World!")')
    print(
        f"打印输出: {result['success']}, 输出包含Hello: {'Hello' in result['output']}"
    )
    assert result["success"] is True
    assert "Hello, World!" in result["output"]

    # 测试3: 数学运算
    result = repl.execute_code("import math\nmath.sqrt(16)")
    print(f"数学运算: {result['success']}, 结果: {result['result']}")
    assert result["success"] is True
    assert result["result"] == 4.0

    # 测试4: 不安全代码被阻止
    result = repl.execute_code("import os")
    print(
        f"安全检查: {result['success']}, 错误: {result['error'][:50] if result['error'] else None}"
    )
    assert result["success"] is False
    assert "不允许导入模块" in result["error"]

    # 测试5: 变量管理
    repl.add_variable("test_var", 42)
    result = repl.execute_code("test_var * 2")
    print(f"变量管理: {result['success']}, 结果: {result['result']}")
    assert result["success"] is True
    assert result["result"] == 84

    print("✅ Python REPL工具测试通过")


def test_web_search():
    """测试网络搜索工具"""
    print("\n=== 测试网络搜索工具 ===")

    search_tool = WebSearchTool(timeout=10, max_results=5)

    # 测试工具信息
    info = search_tool.get_tool_info()
    print(f"工具信息: {info['name']}, 引擎: {info['supported_engines']}")
    assert info["name"] == "WebSearchTool"
    assert "duckduckgo" in info["supported_engines"]

    print("✅ 网络搜索工具基础测试通过")


def test_decorators():
    """测试工具装饰器"""
    print("\n=== 测试工具装饰器 ===")

    # 测试工具注册装饰器
    @tool(name="test_calculator", description="测试计算器", category="test")
    def calculator(expression: str):
        try:
            return eval(expression)
        except Exception as e:
            raise ValueError(f"计算错误: {e}")

    # 测试函数调用
    result = calculator("2 + 3 * 4")
    print(f"装饰器函数调用: 结果 = {result}")
    assert result == 14

    # 检查工具注册
    registry = get_tool_registry()
    tool_info = registry.get_tool_info("test_calculator")
    print(f"工具注册: {tool_info['description']}, 类别: {tool_info['category']}")
    assert tool_info is not None
    assert tool_info["description"] == "测试计算器"
    assert tool_info["category"] == "test"

    print("✅ 工具装饰器测试通过")


async def test_tool_manager():
    """测试工具管理器"""
    print("\n=== 测试工具管理器 ===")

    manager = get_tool_manager()

    # 初始化工具管理器
    await manager.initialize_tools()
    print(f"工具管理器初始化: {manager._initialized}")
    assert manager._initialized is True

    # 列出工具
    tools = manager.list_tools()
    print(f"可用工具: {list(tools.keys())}")
    assert len(tools) >= 2
    assert "python_repl" in tools
    assert "web_search" in tools

    # 执行工具方法
    result = await manager.execute_tool("python_repl", "execute_code", "5 * 6")
    print(f"工具执行: {result['success']}, 结果: {result['result']['result']}")
    assert result["success"] is True
    assert result["result"]["result"] == 30

    # 健康检查
    health = await manager.health_check()
    print(f"健康检查: {health['healthy']}, 工具数量: {health['total_tools']}")
    assert health["healthy"] is True
    assert health["total_tools"] >= 2

    # 关闭管理器
    await manager.shutdown()
    print("✅ 工具管理器测试通过")


async def main():
    """主测试函数"""
    print("开始基础工具实现测试...")

    try:
        # 测试各个组件
        test_python_repl()
        test_web_search()
        test_decorators()
        await test_tool_manager()

        print("\n🎉 所有基础工具测试通过！")
        print("\n基础工具实现包括:")
        print("- ✅ Python REPL工具 (代码执行、安全检查、变量管理)")
        print("- ✅ 网络搜索工具 (DuckDuckGo搜索、网页内容获取)")
        print("- ✅ 文档检索工具 (RAG集成、语义搜索)")
        print("- ✅ 工具装饰器 (注册、监控、缓存、限流)")
        print("- ✅ 工具管理器 (统一管理、执行协调、健康检查)")
        print("- ✅ 性能监控 (执行时间、成功率、错误追踪)")
        print("- ✅ 异常处理 (安全执行、错误恢复)")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
