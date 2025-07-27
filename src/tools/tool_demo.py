"""工具演示模块 - 展示如何使用各种工具"""

import asyncio
from typing import Any, Dict

from ..config.logging_config import get_logger
from .decorators import rate_limit, tool, validate_input
from .python_repl import PythonREPL
from .tool_manager import ToolConfig, get_tool_manager
from .web_search import WebSearchTool

logger = get_logger("tool_demo")


@tool(name="demo_calculator", description="演示计算器工具", category="demo")
@validate_input(expression=str)
def demo_calculator(expression: str) -> Dict[str, Any]:
    """演示计算器工具"""
    try:
        # 简单的数学表达式计算
        allowed_chars = set("0123456789+-*/().")
        if not all(c in allowed_chars or c.isspace() for c in expression):
            return {"success": False, "error": "表达式包含不允许的字符", "result": None}

        result = eval(expression)
        return {
            "success": True,
            "expression": expression,
            "result": result,
            "error": None,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "result": None}


@tool(name="demo_text_processor", description="演示文本处理工具", category="demo")
@rate_limit(calls_per_minute=30)
@validate_input(
    text=str, operation={"type": str, "pattern": r"^(upper|lower|reverse|count)$"}
)
def demo_text_processor(text: str, operation: str) -> Dict[str, Any]:
    """演示文本处理工具"""
    try:
        if operation == "upper":
            result = text.upper()
        elif operation == "lower":
            result = text.lower()
        elif operation == "reverse":
            result = text[::-1]
        elif operation == "count":
            result = len(text)
        else:
            return {
                "success": False,
                "error": f"不支持的操作: {operation}",
                "result": None,
            }

        return {
            "success": True,
            "text": text,
            "operation": operation,
            "result": result,
            "error": None,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "result": None}


class ToolDemo:
    """工具演示类"""

    def __init__(self):
        self.manager = get_tool_manager()

    async def demo_python_repl(self) -> Dict[str, Any]:
        """演示Python REPL工具"""
        logger.info("演示Python REPL工具")

        results = {}

        try:
            # 初始化工具管理器
            await self.manager.initialize_tools()

            # 获取Python REPL工具
            repl = self.manager.get_tool("python_repl")
            if not repl:
                return {"error": "Python REPL工具未找到"}

            # 演示1: 简单计算
            result1 = repl.execute_code("2 + 3 * 4")
            results["simple_calculation"] = result1

            # 演示2: 变量操作
            result2 = repl.execute_code("x = 10\ny = 20\nprint(f'x + y = {x + y}')")
            results["variable_operations"] = result2

            # 演示3: 数学运算
            result3 = repl.execute_code("import math\nmath.sqrt(16) + math.pi")
            results["math_operations"] = result3

            # 演示4: 列表操作
            result4 = repl.execute_code("numbers = [1, 2, 3, 4, 5]\nsum(numbers)")
            results["list_operations"] = result4

            # 演示5: 字符串处理
            result5 = repl.execute_code("text = 'Hello, World!'\ntext.upper()")
            results["string_operations"] = result5

            return {"success": True, "demo": "python_repl", "results": results}

        except Exception as e:
            logger.error(f"Python REPL演示失败: {e}")
            return {"success": False, "error": str(e), "demo": "python_repl"}

    async def demo_web_search(self) -> Dict[str, Any]:
        """演示网络搜索工具"""
        logger.info("演示网络搜索工具")

        results = {}

        try:
            # 初始化工具管理器
            await self.manager.initialize_tools()

            # 获取网络搜索工具
            web_search = self.manager.get_tool("web_search")
            if not web_search:
                return {"error": "网络搜索工具未找到"}

            # 演示1: 基本搜索
            result1 = await web_search.search("Python programming", max_results=3)
            results["basic_search"] = {
                "query": "Python programming",
                "success": result1["success"],
                "results_count": result1.get("results_count", 0),
            }

            # 演示2: 中文搜索
            result2 = await web_search.search("人工智能", max_results=3)
            results["chinese_search"] = {
                "query": "人工智能",
                "success": result2["success"],
                "results_count": result2.get("results_count", 0),
            }

            # 演示3: 技术搜索
            result3 = await web_search.search(
                "machine learning algorithms", max_results=2
            )
            results["tech_search"] = {
                "query": "machine learning algorithms",
                "success": result3["success"],
                "results_count": result3.get("results_count", 0),
            }

            return {"success": True, "demo": "web_search", "results": results}

        except Exception as e:
            logger.error(f"网络搜索演示失败: {e}")
            return {"success": False, "error": str(e), "demo": "web_search"}

    async def demo_tool_decorators(self) -> Dict[str, Any]:
        """演示工具装饰器"""
        logger.info("演示工具装饰器")

        results = {}

        try:
            # 演示1: 计算器工具
            calc_result1 = demo_calculator("2 + 3 * 4")
            results["calculator_valid"] = calc_result1

            calc_result2 = demo_calculator("import os")  # 应该失败
            results["calculator_invalid"] = calc_result2

            # 演示2: 文本处理工具
            text_result1 = demo_text_processor("Hello World", "upper")
            results["text_upper"] = text_result1

            text_result2 = demo_text_processor("Hello World", "reverse")
            results["text_reverse"] = text_result2

            text_result3 = demo_text_processor("Hello World", "count")
            results["text_count"] = text_result3

            # 演示3: 无效操作
            text_result4 = demo_text_processor("Hello World", "invalid")
            results["text_invalid"] = text_result4

            return {"success": True, "demo": "tool_decorators", "results": results}

        except Exception as e:
            logger.error(f"工具装饰器演示失败: {e}")
            return {"success": False, "error": str(e), "demo": "tool_decorators"}

    async def demo_tool_manager(self) -> Dict[str, Any]:
        """演示工具管理器"""
        logger.info("演示工具管理器")

        results = {}

        try:
            # 初始化工具管理器
            await self.manager.initialize_tools()

            # 演示1: 列出所有工具
            tools_list = self.manager.list_tools()
            results["tools_list"] = {
                "count": len(tools_list),
                "tools": list(tools_list.keys()),
            }

            # 演示2: 获取工具指标
            metrics = self.manager.get_tool_metrics()
            results["metrics"] = {
                "total_tools": metrics.get("total_tools", 0),
                "total_calls": metrics.get("total_calls", 0),
            }

            # 演示3: 健康检查
            health = await self.manager.health_check()
            results["health_check"] = {
                "healthy": health["healthy"],
                "initialized": health["initialized"],
                "total_tools": health["total_tools"],
            }

            # 演示4: 执行工具方法
            exec_result = await self.manager.execute_tool(
                "python_repl", "execute_code", "print('Hello from tool manager!')"
            )
            results["tool_execution"] = {
                "success": exec_result["success"],
                "has_output": "output" in exec_result.get("result", {}),
            }

            return {"success": True, "demo": "tool_manager", "results": results}

        except Exception as e:
            logger.error(f"工具管理器演示失败: {e}")
            return {"success": False, "error": str(e), "demo": "tool_manager"}

    async def run_all_demos(self) -> Dict[str, Any]:
        """运行所有演示"""
        logger.info("开始运行所有工具演示")

        all_results = {}

        # 运行各个演示
        demos = [
            ("python_repl", self.demo_python_repl),
            ("web_search", self.demo_web_search),
            ("tool_decorators", self.demo_tool_decorators),
            ("tool_manager", self.demo_tool_manager),
        ]

        for demo_name, demo_func in demos:
            try:
                logger.info(f"运行演示: {demo_name}")
                result = await demo_func()
                all_results[demo_name] = result

                if result.get("success"):
                    logger.info(f"演示 {demo_name} 成功完成")
                else:
                    logger.warning(f"演示 {demo_name} 失败: {result.get('error')}")

            except Exception as e:
                logger.error(f"演示 {demo_name} 异常: {e}")
                all_results[demo_name] = {
                    "success": False,
                    "error": str(e),
                    "demo": demo_name,
                }

        # 统计结果
        successful_demos = sum(
            1 for result in all_results.values() if result.get("success")
        )
        total_demos = len(all_results)

        return {
            "success": successful_demos > 0,
            "summary": {
                "total_demos": total_demos,
                "successful_demos": successful_demos,
                "failed_demos": total_demos - successful_demos,
                "success_rate": (
                    successful_demos / total_demos if total_demos > 0 else 0
                ),
            },
            "results": all_results,
        }


async def main():
    """主函数 - 运行工具演示"""
    print("=== 工具演示开始 ===")

    demo = ToolDemo()
    results = await demo.run_all_demos()

    print(f"\n=== 演示结果摘要 ===")
    summary = results["summary"]
    print(f"总演示数: {summary['total_demos']}")
    print(f"成功演示: {summary['successful_demos']}")
    print(f"失败演示: {summary['failed_demos']}")
    print(f"成功率: {summary['success_rate']:.2%}")

    print(f"\n=== 详细结果 ===")
    for demo_name, result in results["results"].items():
        status = "✓" if result.get("success") else "✗"
        print(f"{status} {demo_name}: {result.get('error', '成功')}")

    print("\n=== 工具演示结束 ===")

    return results


if __name__ == "__main__":
    asyncio.run(main())
