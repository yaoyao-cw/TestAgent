#!/usr/bin/env python3
"""
研究员节点测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.state import TestAgentState, TaskType
from src.models.execution import ExecutionPlan, ExecutionStep, StepType
from src.graph.nodes import ResearcherNode
from src.exceptions import TestAgentException


class TestResearcherNode:
    """研究员节点测试类"""

    @pytest.fixture
    def researcher(self):
        """创建研究员实例"""
        with (
            patch("src.graph.nodes.LLMService") as mock_llm_service,
            patch("src.rag.rag_service.RAGService") as mock_rag_service,
        ):
            mock_llm_service.return_value = Mock()
            mock_rag_service.return_value = Mock()
            researcher = ResearcherNode()
            researcher.llm_service = mock_llm_service.return_value
            researcher.rag_service = mock_rag_service.return_value
            return researcher

    @pytest.fixture
    def mock_execution_plan(self):
        """创建模拟执行计划"""
        steps = [
            ExecutionStep(
                title="需求分析",
                description="分析用户需求文档，提取测试要点",
                step_type=StepType.RESEARCH,
            ),
            ExecutionStep(
                title="测试思维导图",
                description="生成测试思维导图",
                step_type=StepType.RESEARCH,
            ),
            ExecutionStep(
                title="测试用例设计",
                description="基于思维导图设计详细测试用例",
                step_type=StepType.RESEARCH,
            ),
            ExecutionStep(
                title="脚本实现",
                description="实现具体测试脚本",
                step_type=StepType.CODING,
            ),
        ]

        return ExecutionPlan(
            title="测试用例生成计划",
            thought="基于需求分析生成测试用例",
            locale="zh-CN",
            task_type=TaskType.TEST_CASE_GENERATION.value,
            steps=steps,
            has_enough_context=True,
        )

    @pytest.fixture
    def mock_state(self, mock_execution_plan):
        """创建模拟状态"""
        return {
            "messages": [HumanMessage(content="请为用户登录功能生成测试用例")],
            "locale": "zh-CN",
            "task_topic": "用户登录功能",
            "task_type": TaskType.TEST_CASE_GENERATION,
            "current_plan": mock_execution_plan,
            "current_step": 0,
            "observations": [],
            "resources": [],
            "rag_results": [],
            "final_report": "",
            "review_score": None,
        }

    @pytest.mark.asyncio
    async def test_process_research_step(self, researcher, mock_state):
        """测试处理研究步骤"""
        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(
            return_value="需求分析结果"
        )

        # 模拟RAG检索结果
        researcher.rag_service.search_documents = AsyncMock(
            return_value=[{"id": "doc1", "content": "用户登录相关文档内容"}]
        )

        result = await researcher.process(mock_state)

        assert "current_step" in result
        assert "observations" in result
        assert "next_node" in result
        assert result["current_step"] == 1
        assert len(result["observations"]) == 1
        assert result["observations"][0]["step_title"] == "需求分析"
        assert result["observations"][0]["result"]["type"] == "requirement_analysis"

    @pytest.mark.asyncio
    async def test_process_analysis_step(self, researcher, mock_state):
        """测试处理分析步骤"""
        # 设置为分析步骤
        mock_state["current_step"] = 0
        mock_state["current_plan"].steps[0] = ExecutionStep(
            title="边界条件分析",
            description="分析边界条件和异常情况",
            step_type=StepType.ANALYSIS,
        )

        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(
            return_value="边界条件分析结果"
        )

        result = await researcher.process(mock_state)

        assert result["current_step"] == 1
        assert len(result["observations"]) == 1
        assert result["observations"][0]["result"]["type"] == "boundary_analysis"

    @pytest.mark.asyncio
    async def test_process_coding_step(self, researcher, mock_state):
        """测试处理编码步骤（应该移交给编码员）"""
        # 设置为编码步骤
        mock_state["current_step"] = 3  # 脚本实现步骤

        result = await researcher.process(mock_state)

        assert result["current_step"] == 3
        assert result["next_node"] == "coder"

    @pytest.mark.asyncio
    async def test_process_all_steps_completed(self, researcher, mock_state):
        """测试所有步骤完成的情况"""
        # 设置步骤索引超出范围
        mock_state["current_step"] = 10

        result = await researcher.process(mock_state)

        assert result["current_step"] == 10
        assert result["next_node"] == "reporter"

    @pytest.mark.asyncio
    async def test_requirement_analysis(self, researcher, mock_state):
        """测试需求分析功能"""
        step = ExecutionStep(
            title="需求分析",
            description="分析用户需求文档，提取测试要点",
            step_type=StepType.RESEARCH,
        )

        # 模拟RAG检索结果
        researcher.rag_service.search_documents = AsyncMock(
            return_value=[
                {
                    "id": "doc1",
                    "content": "用户登录需求：用户可以通过用户名和密码登录系统",
                }
            ]
        )

        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(
            return_value="""
        需求分析结果：
        1. 功能需求：用户登录验证
        2. 非功能需求：安全性、性能
        3. 用户场景：正常登录、异常登录
        """
        )

        result = await researcher._perform_requirement_analysis(step, mock_state)

        assert result["type"] == "requirement_analysis"
        assert result["task_topic"] == "用户登录功能"
        assert "需求分析结果" in result["analysis_result"]
        assert len(result["rag_results"]) == 1

    @pytest.mark.asyncio
    async def test_generate_test_mind_map(self, researcher, mock_state):
        """测试生成测试思维导图"""
        step = ExecutionStep(
            title="测试思维导图",
            description="生成测试思维导图",
            step_type=StepType.RESEARCH,
        )

        # 添加需求分析的观察结果
        mock_state["observations"] = [
            {
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "用户登录功能需求分析",
                }
            }
        ]

        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(
            return_value="""
        # 测试思维导图：用户登录功能
        ## 1. 功能测试
        ### 1.1 正常流程测试
        - 有效用户名和密码登录
        ### 1.2 异常流程测试
        - 无效用户名或密码
        """
        )

        result = await researcher._generate_test_mind_map(step, mock_state)

        assert result["type"] == "test_mind_map"
        assert result["task_topic"] == "用户登录功能"
        assert "测试思维导图" in result["mind_map"]

    @pytest.mark.asyncio
    async def test_generate_test_cases(self, researcher, mock_state):
        """测试生成测试用例"""
        step = ExecutionStep(
            title="测试用例设计",
            description="基于思维导图设计详细测试用例",
            step_type=StepType.RESEARCH,
        )

        # 添加需求分析和思维导图的观察结果
        mock_state["observations"] = [
            {
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "用户登录功能需求分析",
                }
            },
            {"result": {"type": "test_mind_map", "mind_map": "用户登录测试思维导图"}},
        ]

        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(
            return_value="""
        # 测试用例：用户登录功能
        ## 测试用例1：正常登录
        - **测试目标**：验证用户能够正常登录
        - **前置条件**：用户账号存在且有效
        - **测试步骤**：
          1. 输入有效用户名
          2. 输入正确密码
          3. 点击登录按钮
        - **预期结果**：成功登录系统
        """
        )

        result = await researcher._generate_test_cases(step, mock_state)

        assert result["type"] == "test_cases"
        assert result["task_topic"] == "用户登录功能"
        assert "测试用例" in result["test_cases"]

    @pytest.mark.asyncio
    async def test_document_research(self, researcher, mock_state):
        """测试文档研究功能"""
        step = ExecutionStep(
            title="文档检索",
            description="检索相关需求文档",
            step_type=StepType.RESEARCH,
        )

        # 模拟RAG检索结果
        researcher.rag_service.search_documents = AsyncMock(
            return_value=[
                {"id": "doc1", "content": "用户登录API文档：POST /api/login"},
                {"id": "doc2", "content": "用户认证规范：支持用户名密码认证"},
            ]
        )

        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(
            return_value="""
        文档分析结果：
        1. 关键功能点：用户登录API
        2. 技术规范：POST请求，JSON格式
        3. 业务流程：用户名密码验证
        """
        )

        result = await researcher._perform_document_research(step, mock_state)

        assert result["type"] == "document_research"
        assert result["documents_found"] == 2
        assert "文档分析结果" in result["analysis_result"]

    @pytest.mark.asyncio
    async def test_boundary_analysis(self, researcher, mock_state):
        """测试边界条件分析"""
        step = ExecutionStep(
            title="边界条件分析",
            description="分析边界条件和异常情况",
            step_type=StepType.ANALYSIS,
        )

        # 添加之前的观察结果
        mock_state["observations"] = [
            {
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "用户登录功能需求分析",
                }
            }
        ]

        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(
            return_value="""
        边界条件分析：
        ## 1. 输入边界条件
        - 用户名长度：最小1字符，最大50字符
        - 密码长度：最小6字符，最大20字符
        ## 2. 系统边界条件
        - 登录尝试次数：最多5次
        """
        )

        result = await researcher._analyze_boundary_conditions(step, mock_state)

        assert result["type"] == "boundary_analysis"
        assert "边界条件分析" in result["boundary_analysis"]

    @pytest.mark.asyncio
    async def test_validation_analysis(self, researcher, mock_state):
        """测试验证分析"""
        step = ExecutionStep(
            title="结果验证",
            description="验证生成结果的完整性和准确性",
            step_type=StepType.ANALYSIS,
        )

        # 添加多个之前的观察结果
        mock_state["observations"] = [
            {
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "需求分析结果",
                }
            },
            {"result": {"type": "test_cases", "test_cases": "测试用例结果"}},
        ]

        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(
            return_value="""
        验证分析结果：
        ## 1. 完整性验证
        - 需求覆盖度：90%
        - 测试覆盖度：85%
        ## 2. 一致性验证
        - 需求一致性：良好
        ## 3. 改进建议
        - 增加异常场景测试
        """
        )

        result = await researcher._perform_validation_analysis(step, mock_state)

        assert result["type"] == "validation_analysis"
        assert result["analyzed_results_count"] == 2
        assert "验证分析结果" in result["validation_result"]

    @pytest.mark.asyncio
    async def test_process_without_plan(self, researcher):
        """测试没有执行计划的情况"""
        state = {"current_plan": None, "current_step": 0}

        with pytest.raises(TestAgentException):
            await researcher.process(state)

    @pytest.mark.asyncio
    async def test_process_without_llm_service(self, mock_state):
        """测试没有LLM服务的情况"""
        researcher = ResearcherNode()
        researcher.llm_service = None
        researcher.rag_service = None

        result = await researcher.process(mock_state)

        # 应该能正常处理，但结果可能包含错误信息
        assert "current_step" in result
        assert "observations" in result

    @pytest.mark.asyncio
    async def test_rag_service_failure(self, researcher, mock_state):
        """测试RAG服务失败的情况"""
        step = ExecutionStep(
            title="需求分析",
            description="分析用户需求文档，提取测试要点",
            step_type=StepType.RESEARCH,
        )

        # 模拟RAG服务失败
        researcher.rag_service.search_documents = AsyncMock(
            side_effect=Exception("RAG服务不可用")
        )

        # 模拟LLM正常工作
        researcher.llm_service.generate_response = AsyncMock(
            return_value="需求分析结果"
        )

        result = await researcher._perform_requirement_analysis(step, mock_state)

        assert result["type"] == "requirement_analysis"
        assert result["rag_results"] == []  # RAG失败时应该返回空列表
        assert "需求分析结果" in result["analysis_result"]

    @pytest.mark.asyncio
    async def test_llm_service_failure(self, researcher, mock_state):
        """测试LLM服务失败的情况"""
        step = ExecutionStep(
            title="需求分析",
            description="分析用户需求文档，提取测试要点",
            step_type=StepType.RESEARCH,
        )

        # 模拟LLM服务失败
        researcher.llm_service.generate_response = AsyncMock(
            side_effect=Exception("LLM服务不可用")
        )

        # 模拟RAG正常工作
        researcher.rag_service.search_documents = AsyncMock(return_value=[])

        result = await researcher._perform_requirement_analysis(step, mock_state)

        assert result["type"] == "requirement_analysis"
        assert "需求分析失败" in result["analysis_result"]

    @pytest.mark.asyncio
    async def test_multiple_research_steps(self, researcher, mock_state):
        """测试多个连续的研究步骤"""
        # 模拟LLM响应
        researcher.llm_service.generate_response = AsyncMock(return_value="研究结果")
        researcher.rag_service.search_documents = AsyncMock(return_value=[])

        # 第一个研究步骤
        result1 = await researcher.process(mock_state)
        assert result1["current_step"] == 1
        assert result1["next_node"] == "researcher"

        # 更新状态并执行第二个研究步骤
        mock_state["current_step"] = 1
        mock_state["observations"] = result1["observations"]

        result2 = await researcher.process(mock_state)
        assert result2["current_step"] == 2
        assert result2["next_node"] == "researcher"

        # 更新状态并执行第三个研究步骤
        mock_state["current_step"] = 2
        mock_state["observations"] = result2["observations"]

        result3 = await researcher.process(mock_state)
        assert result3["current_step"] == 3
        assert result3["next_node"] == "coder"  # 下一步是编码步骤，移交给编码员


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
