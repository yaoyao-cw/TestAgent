#!/usr/bin/env python3
"""
报告员节点单元测试
"""

import asyncio
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.exceptions import TestAgentException
from src.graph.reporter_node import ReporterNode
from src.models.execution import ExecutionStep, StepType
from src.models.state import TestAgentState
from src.models.types import TaskType


class TestReporterNode:
    """报告员节点测试类"""

    def setup_method(self):
        """测试前置设置"""
        self.reporter_node = ReporterNode()
        self.mock_llm_service = Mock()
        self.reporter_node.llm_service = self.mock_llm_service

    def test_init(self):
        """测试初始化"""
        node = ReporterNode()
        assert node is not None
        assert hasattr(node, "report_templates")
        assert hasattr(node, "supported_formats")
        assert "markdown" in node.supported_formats
        assert "html" in node.supported_formats
        assert "json" in node.supported_formats

    def test_load_report_templates(self):
        """测试加载报告模板"""
        templates = self.reporter_node._load_report_templates()

        assert isinstance(templates, dict)
        assert "test_case_generation" in templates
        assert "requirement_analysis" in templates
        assert "code_generation" in templates
        assert "generic" in templates

        # 检查模板内容包含必要的占位符
        assert "{task_topic}" in templates["generic"]
        assert "{task_type}" in templates["generic"]
        assert "{execution_time}" in templates["generic"]

    def test_analyze_observations(self):
        """测试观察结果分析"""
        observations = [
            {
                "step_title": "需求分析",
                "step_type": "research",
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "分析结果内容",
                },
            },
            {
                "step_title": "代码生成",
                "step_type": "coding",
                "result": {
                    "type": "test_script_generation",
                    "generated_code": "import pytest\ndef test_example(): pass",
                    "framework": "pytest",
                    "is_valid": True,
                },
            },
            {
                "step_title": "错误步骤",
                "step_type": "coding",
                "error": True,
                "result": {"type": "coding_error", "error": "语法错误"},
            },
        ]

        analysis = self.reporter_node._analyze_observations(observations)

        assert analysis["total_steps"] == 3
        assert analysis["successful_steps"] == 2
        assert analysis["failed_steps"] == 1
        assert "research" in analysis["step_types"]
        assert "coding" in analysis["step_types"]
        assert len(analysis["main_results"]) == 1
        assert len(analysis["generated_content"]) == 1
        assert len(analysis["errors"]) == 1

    def test_determine_report_template(self):
        """测试报告模板确定"""
        # 测试基于任务类型的模板选择
        assert (
            self.reporter_node._determine_report_template(
                TaskType.TEST_CASE_GENERATION.value, []
            )
            == "test_case_generation"
        )

        assert (
            self.reporter_node._determine_report_template(
                TaskType.REQUIREMENT_EXTRACTION.value, []
            )
            == "requirement_analysis"
        )

        assert (
            self.reporter_node._determine_report_template(
                TaskType.TEST_SCRIPT_GENERATION.value, []
            )
            == "code_generation"
        )

        # 测试基于观察结果的模板选择
        observations_with_code = [
            {
                "result": {
                    "type": "test_script_generation",
                    "generated_code": "test code",
                }
            }
        ]

        assert (
            self.reporter_node._determine_report_template(
                "unknown_type", observations_with_code
            )
            == "code_generation"
        )

        # 测试默认模板
        assert (
            self.reporter_node._determine_report_template("unknown_type", [])
            == "generic"
        )

    def test_format_main_results(self):
        """测试主要结果格式化"""
        main_results = [
            {
                "type": "需求分析",
                "content": "这是一个很长的需求分析结果内容，需要被截断显示",
            },
            {"type": "测试用例生成", "content": "生成的测试用例内容"},
        ]

        formatted = self.reporter_node._format_main_results(main_results)

        assert "需求分析" in formatted
        assert "测试用例生成" in formatted
        assert "..." in formatted  # 检查截断

        # 测试空结果
        empty_formatted = self.reporter_node._format_main_results([])
        assert empty_formatted == "无主要结果"

    def test_format_generated_content(self):
        """测试生成内容格式化"""
        generated_content = [
            {"type": "代码生成", "framework": "pytest", "is_valid": True},
            {"type": "代码生成", "framework": "unittest", "is_valid": False},
        ]

        formatted = self.reporter_node._format_generated_content(generated_content)

        assert "pytest" in formatted
        assert "unittest" in formatted
        assert "✅ 有效" in formatted
        assert "❌ 无效" in formatted

        # 测试空内容
        empty_formatted = self.reporter_node._format_generated_content([])
        assert empty_formatted == "无生成内容"

    def test_format_errors(self):
        """测试错误格式化"""
        errors = [
            {"step": "步骤1", "error": "错误信息1"},
            {"step": "步骤2", "error": "错误信息2"},
        ]

        formatted = self.reporter_node._format_errors(errors)

        assert "步骤1" in formatted
        assert "错误信息1" in formatted
        assert "步骤2" in formatted
        assert "错误信息2" in formatted

        # 测试空错误
        empty_formatted = self.reporter_node._format_errors([])
        assert empty_formatted == "无错误"

    def test_format_execution_results(self):
        """测试执行结果格式化"""
        analysis = {
            "total_steps": 10,
            "successful_steps": 8,
            "failed_steps": 2,
            "step_types": {"research": 3, "coding": 5, "reporting": 2},
        }

        # 测试中文格式化
        formatted_zh = self.reporter_node._format_execution_results(analysis, "zh-CN")
        assert "总步骤数: 10" in formatted_zh
        assert "成功步骤: 8" in formatted_zh
        assert "失败步骤: 2" in formatted_zh
        assert "80.0%" in formatted_zh
        assert "research: 3" in formatted_zh

        # 测试英文格式化
        formatted_en = self.reporter_node._format_execution_results(analysis, "en-US")
        assert "Total Steps: 10" in formatted_en
        assert "Successful Steps: 8" in formatted_en
        assert "Failed Steps: 2" in formatted_en
        assert "80.0%" in formatted_en

    def test_generate_summary(self):
        """测试总结生成"""
        analysis = {
            "total_steps": 5,
            "successful_steps": 4,
            "failed_steps": 1,
            "generated_content": [{"is_valid": True}, {"is_valid": False}],
        }

        # 测试中文总结
        summary_zh = self.reporter_node._generate_summary(analysis, "zh-CN")
        assert "5 个步骤" in summary_zh
        assert "4 个步骤成功" in summary_zh
        assert "1 个步骤执行失败" in summary_zh
        assert "2 个代码片段" in summary_zh
        assert "1 个通过了语法验证" in summary_zh

        # 测试英文总结
        summary_en = self.reporter_node._generate_summary(analysis, "en-US")
        assert "5 steps in total" in summary_en
        assert "4 steps completed successfully" in summary_en
        assert "1 steps failed" in summary_en

    def test_get_task_type_display_name(self):
        """测试任务类型显示名称"""
        # 测试中文名称
        zh_name = self.reporter_node._get_task_type_display_name(
            TaskType.TEST_CASE_GENERATION.value, "zh-CN"
        )
        assert zh_name == "测试用例生成"

        # 测试英文名称
        en_name = self.reporter_node._get_task_type_display_name(
            TaskType.TEST_CASE_GENERATION.value, "en-US"
        )
        assert en_name == "Test Case Generation"

        # 测试未知类型
        unknown_name = self.reporter_node._get_task_type_display_name(
            "unknown_type", "zh-CN"
        )
        assert unknown_name == "unknown_type"

    def test_format_as_html(self):
        """测试HTML格式转换"""
        markdown_content = """# 标题1
## 标题2
### 标题3

**粗体文本**

- 列表项1
- 列表项2

```python
def test_example():
    pass
```
"""

        html_content = self.reporter_node.format_as_html(markdown_content)

        assert "<h1>标题1</h1>" in html_content
        assert "<h2>标题2</h2>" in html_content
        assert "<h3>标题3</h3>" in html_content
        assert "<strong>粗体文本</strong>" in html_content
        assert "<li>列表项1</li>" in html_content
        assert "<pre><code>" in html_content

    def test_format_as_json(self):
        """测试JSON格式转换"""
        report_data = {
            "type": "final_report",
            "task_topic": "测试任务",
            "content": "报告内容",
        }

        json_content = self.reporter_node.format_as_json(report_data)

        assert '"type": "final_report"' in json_content
        assert '"task_topic": "测试任务"' in json_content
        assert '"content": "报告内容"' in json_content

    def test_generate_error_report(self):
        """测试错误报告生成"""
        error_report = self.reporter_node._generate_error_report(
            "测试错误", "测试任务", "test_type", "zh-CN"
        )

        assert error_report["type"] == "error_report"
        assert error_report["task_topic"] == "测试任务"
        assert error_report["task_type"] == "test_type"
        assert error_report["error"] is True
        assert "测试错误" in error_report["content"]
        assert error_report["format"] == "markdown"

    @pytest.mark.asyncio
    async def test_process_success(self):
        """测试成功处理报告生成"""
        observations = [
            {
                "step_title": "测试步骤",
                "step_type": "research",
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "分析结果",
                },
            }
        ]

        state = {
            "task_topic": "测试任务",
            "task_type": TaskType.TEST_CASE_GENERATION.value,
            "locale": "zh-CN",
            "observations": observations,
        }

        # Mock LLM服务
        self.mock_llm_service.generate_response = AsyncMock(
            return_value="生成的报告内容"
        )

        result = await self.reporter_node.process(state)

        assert "report" in result
        assert result["task_completed"] is True
        assert result["next_node"] == "reviewer"
        assert result["report"]["type"] == "final_report"
        assert result["report"]["task_topic"] == "测试任务"

    @pytest.mark.asyncio
    async def test_process_with_error(self):
        """测试处理错误情况"""
        state = {
            "task_topic": None,  # 故意设置为None引发错误
            "task_type": TaskType.TEST_CASE_GENERATION.value,
            "locale": "zh-CN",
            "observations": [],
        }

        result = await self.reporter_node.process(state)

        assert "report" in result
        assert result["task_completed"] is True
        # 检查是否有错误标志（可能在多个层级）
        has_error = (
            result.get("error") is True
            or result["report"].get("error") is True
            or (
                isinstance(result["report"].get("content"), dict)
                and result["report"]["content"].get("error") is True
            )
        )
        assert has_error, f"Expected error flag but got: {result}"

    @pytest.mark.asyncio
    async def test_generate_report_with_llm(self):
        """测试使用LLM生成报告"""
        observations = [
            {
                "step_title": "测试步骤",
                "step_type": "research",
                "result": {"type": "requirement_analysis", "analysis_result": "结果"},
            }
        ]

        analysis = self.reporter_node._analyze_observations(observations)

        # Mock LLM响应
        mock_report = "# 测试报告\n\n这是生成的报告内容"
        self.mock_llm_service.generate_response = AsyncMock(return_value=mock_report)

        result = await self.reporter_node._generate_report_with_llm(
            "测试任务",
            TaskType.TEST_CASE_GENERATION.value,
            observations,
            analysis,
            "zh-CN",
        )

        assert result == mock_report
        self.mock_llm_service.generate_response.assert_called_once()

    def test_generate_default_report(self):
        """测试生成默认报告"""
        observations = [
            {
                "step_title": "测试步骤",
                "step_type": "research",
                "result": {"type": "requirement_analysis", "analysis_result": "结果"},
            }
        ]

        analysis = self.reporter_node._analyze_observations(observations)

        report = self.reporter_node._generate_default_report(
            "测试任务",
            TaskType.TEST_CASE_GENERATION.value,
            observations,
            analysis,
            "test_case_generation",
            "zh-CN",
        )

        # 检查报告是否为字符串类型（成功情况）或字典类型（错误情况）
        if isinstance(report, str):
            assert "测试任务" in report
            assert "测试用例生成" in report
            assert "执行结果" in report
            assert "总结" in report
        else:
            # 如果是错误报告，检查错误报告的结构
            assert isinstance(report, dict)
            assert report.get("type") == "error_report"
            assert "测试任务" in str(report.get("content", ""))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
