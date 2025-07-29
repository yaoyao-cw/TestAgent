#!/usr/bin/env python3
"""
编码员节点单元测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from src.graph.coder_node import CoderNode
from src.models.state import TestAgentState
from src.models.execution import ExecutionStep, StepType
from src.exceptions import TestAgentException


class TestCoderNode:
    """编码员节点测试类"""

    def setup_method(self):
        """测试前置设置"""
        self.coder_node = CoderNode()
        self.mock_llm_service = Mock()
        self.coder_node.llm_service = self.mock_llm_service

    def test_init(self):
        """测试初始化"""
        node = CoderNode()
        assert node is not None
        assert hasattr(node, "code_cache")
        assert hasattr(node, "supported_frameworks")
        assert hasattr(node, "code_templates")
        assert "pytest" in node.supported_frameworks
        assert "unittest" in node.supported_frameworks

    def test_determine_coding_type(self):
        """测试编码类型判断"""
        # API测试
        assert self.coder_node._determine_coding_type("生成API接口测试") == "api_test"
        assert (
            self.coder_node._determine_coding_type("Create REST API test") == "api_test"
        )

        # UI测试
        assert self.coder_node._determine_coding_type("生成UI界面测试") == "ui_test"
        assert (
            self.coder_node._determine_coding_type("Create Selenium web test")
            == "ui_test"
        )

        # 性能测试
        assert (
            self.coder_node._determine_coding_type("生成性能测试脚本")
            == "performance_test"
        )
        assert (
            self.coder_node._determine_coding_type("Create load test")
            == "performance_test"
        )

        # 自动化脚本
        assert (
            self.coder_node._determine_coding_type("生成自动化脚本")
            == "automation_script"
        )
        assert (
            self.coder_node._determine_coding_type("Create automation script")
            == "automation_script"
        )

        # 默认测试脚本
        assert self.coder_node._determine_coding_type("生成测试用例") == "test_script"

    def test_clean_generated_code(self):
        """测试代码清理"""
        # 测试移除markdown标记
        code_with_markdown = """```python
import pytest

def test_example():
    assert True
```"""

        cleaned = self.coder_node._clean_generated_code(code_with_markdown)
        assert "```python" not in cleaned
        assert "```" not in cleaned
        assert "import pytest" in cleaned
        assert "def test_example():" in cleaned

    def test_validate_python_code(self):
        """测试Python代码验证"""
        # 有效代码
        valid_code = """
import pytest

def test_example():
    assert True
"""
        result = self.coder_node._validate_python_code(valid_code)
        assert result["is_valid"] is True

        # 无效代码
        invalid_code = """
import pytest

def test_example(
    assert True
"""
        result = self.coder_node._validate_python_code(invalid_code)
        assert result["is_valid"] is False
        assert "error" in result

    def test_extract_test_methods(self):
        """测试提取测试方法"""
        code = """
import pytest

class TestExample:
    def test_method_1(self):
        pass
    
    def test_method_2(self):
        pass
    
    def helper_method(self):
        pass
"""
        methods = self.coder_node._extract_test_methods(code)
        assert "test_method_1" in methods
        assert "test_method_2" in methods
        assert "helper_method" not in methods

    def test_extract_api_methods(self):
        """测试提取API方法"""
        code = """
import requests

def test_api():
    requests.get('http://example.com')
    requests.post('http://example.com')
    session.put('http://example.com')
"""
        methods = self.coder_node._extract_api_methods(code)
        assert "GET" in methods
        assert "POST" in methods
        assert "PUT" in methods

    def test_generate_default_generic_test(self):
        """测试生成默认通用测试"""
        step = ExecutionStep(
            title="通用测试生成",
            description="生成通用测试脚本",
            step_type=StepType.CODING.value,
            expected_output="通用测试脚本",
        )

        result = self.coder_node._generate_default_generic_test(step, "通用测试任务")

        assert result["type"] == "generic_test_generation"
        assert result["framework"] == "pytest"
        assert result["is_valid"] is True
        assert result["is_default"] is True
        assert "import pytest" in result["generated_code"]
        assert "class Test" in result["generated_code"]

    def test_sanitize_class_name(self):
        """测试类名清理"""
        assert self.coder_node._sanitize_class_name("测试用例") == "测试用例"
        assert self.coder_node._sanitize_class_name("Test-Case!") == "TestCase"
        assert self.coder_node._sanitize_class_name("123Test") == "Test123Test"
        assert self.coder_node._sanitize_class_name("") == "TestClass"

    def test_sanitize_method_name(self):
        """测试方法名清理"""
        assert self.coder_node._sanitize_method_name("Test Method") == "test_method"
        assert self.coder_node._sanitize_method_name("测试-方法!") == "测试_方法"
        assert self.coder_node._sanitize_method_name("") == "test_method"

    def test_extract_context_from_observations(self):
        """测试从观察结果提取上下文"""
        observations = [
            {
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "需求分析结果",
                }
            },
            {"result": {"type": "test_case_generation", "test_cases": "测试用例内容"}},
            {"result": {"type": "other_type", "data": "其他数据"}},
        ]

        context = self.coder_node._extract_context_from_observations(observations)
        assert "需求分析: 需求分析结果" in context
        assert "测试用例: 测试用例内容" in context
        assert "其他数据" not in context

    @pytest.mark.asyncio
    async def test_process_with_coding_step(self):
        """测试处理编码步骤"""
        # 准备测试数据
        step = ExecutionStep(
            title="生成测试脚本",
            description="生成测试用例代码",  # 修改描述以匹配test_script类型
            step_type=StepType.CODING.value,
            expected_output="测试脚本代码",
        )

        state = {
            "current_plan": Mock(steps=[step]),
            "current_step": 0,
            "observations": [],
            "task_topic": "测试任务",
            "task_type": "test_case_generation",
            "locale": "zh-CN",
        }

        # Mock LLM服务
        self.mock_llm_service.generate_response = AsyncMock(
            return_value="""
import pytest

class TestExample:
    def test_method(self):
        assert True
"""
        )

        # 执行测试
        result = await self.coder_node.process(state)

        # 验证结果
        assert "observations" in result
        assert len(result["observations"]) == 1
        assert result["observations"][0]["result"]["type"] == "test_script_generation"
        assert "generated_code" in result["observations"][0]["result"]

    @pytest.mark.asyncio
    async def test_process_with_non_coding_step(self):
        """测试处理非编码步骤"""
        step = ExecutionStep(
            title="分析需求",
            description="分析用户需求",
            step_type=StepType.RESEARCH.value,
            expected_output="需求分析结果",
        )

        state = {
            "current_plan": Mock(steps=[step]),
            "current_step": 0,
            "observations": [],
        }

        result = await self.coder_node.process(state)

        # 应该移交给其他节点
        assert result["next_node"] == "reporter"

    @pytest.mark.asyncio
    async def test_process_with_error(self):
        """测试处理错误情况"""
        state = {"current_plan": None, "current_step": 0, "observations": []}

        result = await self.coder_node.process(state)

        # 应该记录错误并继续流程
        assert "observations" in result
        assert result["next_node"] == "reporter"
        if result["observations"]:
            assert result["observations"][0].get("error") is True

    def test_generate_default_test_script(self):
        """测试生成默认测试脚本"""
        step = ExecutionStep(
            title="测试脚本生成",
            description="生成基础测试脚本",
            step_type=StepType.CODING.value,
            expected_output="测试脚本",
        )

        result = self.coder_node._generate_default_test_script(step, "测试任务")

        assert result["type"] == "test_script_generation"
        assert result["framework"] == "pytest"
        assert result["is_valid"] is True
        assert result["is_default"] is True
        assert "import pytest" in result["generated_code"]
        assert "class Test" in result["generated_code"]

    def test_generate_default_api_test(self):
        """测试生成默认API测试"""
        step = ExecutionStep(
            title="API测试生成",
            description="生成API测试脚本",
            step_type=StepType.CODING.value,
            expected_output="API测试脚本",
        )

        result = self.coder_node._generate_default_api_test(step, "API测试任务")

        assert result["type"] == "api_test_generation"
        assert result["framework"] == "pytest + requests"
        assert result["is_valid"] is True
        assert result["is_default"] is True
        assert "import requests" in result["generated_code"]
        assert "test_get_request" in result["generated_code"]
        assert "test_post_request" in result["generated_code"]

    @pytest.mark.asyncio
    async def test_generate_api_test_code(self):
        """测试生成API测试代码"""
        step = ExecutionStep(
            title="API测试生成",
            description="生成API测试脚本",
            step_type=StepType.CODING.value,
            expected_output="API测试脚本",
        )

        # Mock LLM响应
        mock_code = """
import pytest
import requests

class TestAPI:
    def test_get_request(self):
        response = requests.get('http://example.com')
        assert response.status_code == 200
"""
        self.mock_llm_service.generate_response = AsyncMock(return_value=mock_code)

        result = await self.coder_node._generate_api_test_code(
            step, "API测试任务", "上下文信息", "zh-CN"
        )

        assert result["type"] == "api_test_generation"
        assert result["framework"] == "pytest + requests"
        assert result["is_valid"] is True
        assert "import requests" in result["generated_code"]

        # 验证LLM被调用
        self.mock_llm_service.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_generic_test_code(self):
        """测试生成通用测试代码"""
        step = ExecutionStep(
            title="通用测试生成",
            description="生成通用测试脚本",
            step_type=StepType.CODING.value,
            expected_output="通用测试脚本",
        )

        # Mock LLM响应
        mock_code = """
import pytest

class TestGeneric:
    def test_generic_method(self):
        assert True
"""
        self.mock_llm_service.generate_response = AsyncMock(return_value=mock_code)

        result = await self.coder_node._generate_generic_test_code(
            step, "通用测试任务", "上下文信息", "zh-CN"
        )

        assert result["type"] == "generic_test_generation"
        assert result["framework"] == "pytest/unittest"
        assert result["is_valid"] is True
        assert "import pytest" in result["generated_code"]

        # 验证LLM被调用
        self.mock_llm_service.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_test_script_with_llm(self):
        """测试使用LLM生成测试脚本"""
        step = ExecutionStep(
            title="生成测试脚本",
            description="生成Python测试脚本",
            step_type=StepType.CODING.value,
            expected_output="测试脚本",
        )

        # Mock LLM响应
        mock_code = """
import pytest

class TestExample:
    def test_method(self):
        assert True
"""
        self.mock_llm_service.generate_response = AsyncMock(return_value=mock_code)

        result = await self.coder_node._generate_test_script(
            step, "测试任务", "上下文信息", "zh-CN"
        )

        assert result["type"] == "test_script_generation"
        assert result["framework"] == "pytest"
        assert result["is_valid"] is True
        assert "import pytest" in result["generated_code"]

        # 验证LLM被调用
        self.mock_llm_service.generate_response.assert_called_once()

    def test_load_code_templates(self):
        """测试加载代码模板"""
        templates = self.coder_node._load_code_templates()

        assert isinstance(templates, dict)
        assert "pytest_basic" in templates
        assert "unittest_basic" in templates
        assert "import pytest" in templates["pytest_basic"]
        assert "import unittest" in templates["unittest_basic"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
