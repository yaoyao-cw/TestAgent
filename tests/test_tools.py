"""工具模块单元测试"""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.exceptions import ToolException
from src.tools.decorators import (
    cache_result,
    get_tool_registry,
    rate_limit,
    tool,
    validate_input,
)
from src.tools.python_repl import PythonREPL
from src.tools.web_search import WebSearchTool


class TestPythonREPL:
    """Python REPL工具测试"""

    @pytest.fixture
    def repl(self):
        """创建Python REPL实例"""
        return PythonREPL(timeout=10, max_output_length=1000)

    def test_simple_calculation(self, repl):
        """测试简单计算"""
        result = repl.execute_code("2 + 3")

        assert result["success"] is True
        assert result["result"] == 5
        assert result["error"] is None
        assert result["execution_time"] >= 0

    def test_print_output(self, repl):
        """测试打印输出"""
        result = repl.execute_code('print("Hello, World!")')

        assert result["success"] is True
        assert "Hello, World!" in result["output"]
        assert result["result"] is None

    def test_variable_assignment(self, repl):
        """测试变量赋值"""
        result = repl.execute_code("x = 10\ny = 20\nprint(x + y)")

        assert result["success"] is True
        assert "30" in result["output"]

    def test_math_operations(self, repl):
        """测试数学运算"""
        result = repl.execute_code("import math\nmath.sqrt(16)")

        assert result["success"] is True
        assert result["result"] == 4.0

    def test_unsafe_code_blocked(self, repl):
        """测试不安全代码被阻止"""
        # 测试导入被阻止
        result = repl.execute_code("import os")
        assert result["success"] is False
        assert "不允许导入模块" in result["error"]

        # 测试函数定义被阻止
        result = repl.execute_code("def test_func(): pass")
        assert result["success"] is False
        assert "不允许定义函数" in result["error"]

        # 测试危险函数调用被阻止
        result = repl.execute_code("exec('print(1)')")
        assert result["success"] is False
        assert "不允许调用函数: exec" in result["error"]

    def test_syntax_error(self, repl):
        """测试语法错误处理"""
        result = repl.execute_code("print(")

        assert result["success"] is False
        assert "语法错误" in result["error"]

    def test_runtime_error(self, repl):
        """测试运行时错误处理"""
        result = repl.execute_code("1 / 0")

        assert result["success"] is False
        assert "division by zero" in result["error"]

    def test_variable_management(self, repl):
        """测试变量管理"""
        # 添加变量
        repl.add_variable("test_var", 42)

        result = repl.execute_code("test_var * 2")
        assert result["success"] is True
        assert result["result"] == 84

        # 列出变量
        variables = repl.list_variables()
        assert "test_var" in variables

        # 移除变量
        repl.remove_variable("test_var")
        variables = repl.list_variables()
        assert "test_var" not in variables

    def test_tool_info(self, repl):
        """测试工具信息获取"""
        info = repl.get_tool_info()

        assert info["name"] == "PythonREPL"
        assert "description" in info
        assert "timeout" in info
        assert "capabilities" in info


class TestWebSearchTool:
    """网络搜索工具测试"""

    @pytest.fixture
    async def search_tool(self):
        """创建网络搜索工具实例"""
        tool = WebSearchTool(timeout=10, max_results=5)
        yield tool
        await tool.close()

    @pytest.mark.asyncio
    async def test_search_with_auto_engine(self, search_tool):
        """测试自动引擎选择"""
        with patch.object(search_tool, "search_duckduckgo") as mock_ddg:
            mock_ddg.return_value = {
                "success": True,
                "results": [{"title": "Test", "content": "Content"}],
            }

            result = await search_tool.search("test query", engine="auto")

            assert result["success"] is True
            mock_ddg.assert_called_once_with("test query", 10)

    @pytest.mark.asyncio
    async def test_empty_query(self, search_tool):
        """测试空查询处理"""
        result = await search_tool.search("")

        assert result["success"] is False
        assert "搜索查询不能为空" in result["error"]

    def test_tool_info(self, search_tool):
        """测试工具信息获取"""
        info = search_tool.get_tool_info()

        assert info["name"] == "WebSearchTool"
        assert "description" in info
        assert "supported_engines" in info
        assert "capabilities" in info


class TestToolDecorators:
    """工具装饰器测试"""

    def test_tool_decorator_registration(self):
        """测试工具装饰器注册"""

        @tool(name="test_tool", description="Test tool", category="test")
        def test_function():
            return "test result"

        registry = get_tool_registry()
        tool_info = registry.get_tool_info("test_tool")

        assert tool_info is not None
        assert tool_info["description"] == "Test tool"
        assert tool_info["category"] == "test"

    def test_rate_limit_decorator(self):
        """测试速率限制装饰器"""
        call_count = 0

        @rate_limit(calls_per_minute=2)
        def limited_function():
            nonlocal call_count
            call_count += 1
            return call_count

        # 前两次调用应该成功
        assert limited_function() == 1
        assert limited_function() == 2

        # 第三次调用应该失败
        with pytest.raises(ToolException) as exc_info:
            limited_function()
        assert "Rate limit exceeded" in str(exc_info.value)

    def test_cache_result_decorator(self):
        """测试结果缓存装饰器"""
        call_count = 0

        @cache_result(ttl=1)
        def cached_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用
        result1 = cached_function(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用应该使用缓存
        result2 = cached_function(5)
        assert result2 == 10
        assert call_count == 1  # 没有增加

        # 不同参数应该重新计算
        result3 = cached_function(6)
        assert result3 == 12
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
