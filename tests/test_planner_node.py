#!/usr/bin/env python3
"""
规划器节点测试
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
from src.graph.nodes import PlannerNode
from src.exceptions import PlanningException


class TestPlannerNode:
    """规划器节点测试类"""

    @pytest.fixture
    def planner(self):
        """创建规划器实例"""
        with patch("src.graph.nodes.LLMService") as mock_llm_service:
            mock_llm_service.return_value = Mock()
            planner = PlannerNode()
            planner.llm_service = mock_llm_service.return_value
            return planner

    @pytest.fixture
    def mock_state(self):
        """创建模拟状态"""
        from src.models.state import TestAgentState

        state = TestAgentState(
            messages=[HumanMessage(content="请为用户登录功能生成测试用例")],
            locale="zh-CN",
            task_topic="用户登录功能测试用例生成",
            task_type=TaskType.TEST_CASE_GENERATION,
            plan_iterations=0,
            current_plan=None,
            observations=[],
            resources=[],
            rag_results=[],
            final_report="",
            review_score=None,
            auto_accepted_plan=False,
            enable_rag_search=True,
            enable_human_feedback=True,
        )
        return state

    @pytest.mark.asyncio
    async def test_get_plan_templates_chinese(self, planner):
        """测试中文计划模板"""
        templates = planner._get_plan_templates("zh-CN")

        assert "test_case_generation" in templates
        assert "test_script_generation" in templates
        assert "requirement_extraction" in templates
        assert "test_script_execution" in templates
        assert "default" in templates

        # 检查测试用例生成模板
        test_case_template = templates["test_case_generation"]
        assert test_case_template["title"] == "测试用例生成计划"
        assert len(test_case_template["steps"]) >= 3
        assert test_case_template["steps"][0]["title"] == "需求分析"

    @pytest.mark.asyncio
    async def test_get_plan_templates_english(self, planner):
        """测试英文计划模板"""
        templates = planner._get_plan_templates("en-US")

        assert "test_case_generation" in templates

        # 检查测试用例生成模板
        test_case_template = templates["test_case_generation"]
        assert test_case_template["title"] == "Test Case Generation Plan"
        assert len(test_case_template["steps"]) >= 3
        assert test_case_template["steps"][0]["title"] == "Requirement Analysis"

    @pytest.mark.asyncio
    async def test_build_planning_prompt_chinese(self, planner):
        """测试中文规划提示词构建"""
        task_type = TaskType.TEST_CASE_GENERATION
        task_topic = "用户登录功能"
        template = {
            "title": "测试用例生成计划",
            "steps": [{"title": "需求分析", "type": "research", "desc": "分析需求"}],
        }

        prompt = planner._build_planning_prompt(
            task_type, task_topic, template, "zh-CN"
        )

        assert "用户登录功能" in prompt
        assert "test_case_generation" in prompt
        assert "JSON格式" in prompt
        assert "zh-CN" in prompt

    @pytest.mark.asyncio
    async def test_build_planning_prompt_english(self, planner):
        """测试英文规划提示词构建"""
        task_type = TaskType.TEST_CASE_GENERATION
        task_topic = "User login functionality"
        template = {
            "title": "Test Case Generation Plan",
            "steps": [
                {
                    "title": "Requirement Analysis",
                    "type": "research",
                    "desc": "Analyze requirements",
                }
            ],
        }

        prompt = planner._build_planning_prompt(
            task_type, task_topic, template, "en-US"
        )

        assert "User login functionality" in prompt
        assert "test_case_generation" in prompt
        assert "JSON format" in prompt
        assert "en-US" in prompt

    @pytest.mark.asyncio
    async def test_parse_execution_plan_valid_json(self, planner):
        """测试解析有效的JSON执行计划"""
        response = """
        {
            "title": "测试用例生成计划",
            "thought": "基于需求分析生成测试用例",
            "locale": "zh-CN",
            "task_type": "test_case_generation",
            "steps": [
                {
                    "title": "需求分析",
                    "description": "分析用户需求",
                    "step_type": "research"
                },
                {
                    "title": "测试设计",
                    "description": "设计测试用例",
                    "step_type": "analysis"
                }
            ],
            "has_enough_context": true
        }
        """

        plan = planner._parse_execution_plan(
            response, TaskType.TEST_CASE_GENERATION, "zh-CN"
        )

        assert plan.title == "测试用例生成计划"
        assert plan.thought == "基于需求分析生成测试用例"
        assert plan.locale == "zh-CN"
        assert plan.task_type == TaskType.TEST_CASE_GENERATION.value
        assert len(plan.steps) == 2
        assert plan.steps[0].title == "需求分析"
        assert plan.steps[0].step_type == StepType.RESEARCH.value
        assert plan.has_enough_context is True

    @pytest.mark.asyncio
    async def test_parse_execution_plan_invalid_json(self, planner):
        """测试解析无效JSON时的降级处理"""
        response = "这不是有效的JSON响应"

        plan = planner._parse_execution_plan(
            response, TaskType.TEST_CASE_GENERATION, "zh-CN"
        )

        # 应该返回默认计划
        assert plan.title == "测试用例生成计划"
        assert plan.task_type == TaskType.TEST_CASE_GENERATION.value
        assert len(plan.steps) >= 3

    @pytest.mark.asyncio
    async def test_create_default_plan(self, planner):
        """测试创建默认计划"""
        plan = planner._create_default_plan(TaskType.TEST_SCRIPT_GENERATION, "zh-CN")

        assert plan.title == "测试脚本生成计划"
        assert plan.task_type == TaskType.TEST_SCRIPT_GENERATION.value
        assert plan.locale == "zh-CN"
        assert len(plan.steps) >= 3
        assert plan.has_enough_context is False

    @pytest.mark.asyncio
    async def test_generate_cache_key(self, planner):
        """测试缓存键生成"""
        key1 = planner._generate_cache_key(
            TaskType.TEST_CASE_GENERATION, "登录功能", "zh-CN"
        )
        key2 = planner._generate_cache_key(
            TaskType.TEST_CASE_GENERATION, "登录功能", "zh-CN"
        )
        key3 = planner._generate_cache_key(
            TaskType.TEST_SCRIPT_GENERATION, "登录功能", "zh-CN"
        )

        # 相同参数应该生成相同的键
        assert key1 == key2
        # 不同参数应该生成不同的键
        assert key1 != key3
        # 键应该是32位的MD5哈希
        assert len(key1) == 32

    @pytest.mark.asyncio
    async def test_validate_execution_plan_valid(self, planner):
        """测试有效执行计划的验证"""
        steps = [
            ExecutionStep(
                title="需求分析",
                description="分析用户需求",
                step_type=StepType.RESEARCH,
            ),
            ExecutionStep(
                title="测试设计",
                description="设计测试用例",
                step_type=StepType.ANALYSIS,
            ),
        ]

        plan = ExecutionPlan(
            title="测试计划",
            thought="测试思路",
            locale="zh-CN",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=steps,
            has_enough_context=True,
        )

        assert planner._validate_execution_plan(plan) is True

    @pytest.mark.asyncio
    async def test_validate_execution_plan_invalid(self, planner):
        """测试无效执行计划的验证"""
        # 测试空计划
        assert planner._validate_execution_plan(None) is False

        # 测试没有标题的计划 - 由于Pydantic验证，无法创建空标题的计划
        # 所以我们测试验证函数对None的处理
        pass

        # 测试没有步骤的计划
        plan_no_steps = ExecutionPlan(
            title="测试计划",
            thought="测试思路",
            locale="zh-CN",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=[],
            has_enough_context=True,
        )
        assert planner._validate_execution_plan(plan_no_steps) is False

    @pytest.mark.asyncio
    async def test_validate_step_sequence(self, planner):
        """测试步骤序列验证"""
        # 有效序列：research -> coding
        valid_steps = [
            ExecutionStep(
                title="分析", description="分析需求", step_type=StepType.RESEARCH
            ),
            ExecutionStep(
                title="编码", description="编写代码", step_type=StepType.CODING
            ),
        ]
        assert planner._validate_step_sequence(valid_steps) is True

        # 有效序列：analysis -> coding
        valid_steps2 = [
            ExecutionStep(
                title="分析", description="分析需求", step_type=StepType.ANALYSIS
            ),
            ExecutionStep(
                title="编码", description="编写代码", step_type=StepType.CODING
            ),
        ]
        assert planner._validate_step_sequence(valid_steps2) is True

        # 有效序列：只有research
        research_only = [
            ExecutionStep(
                title="研究", description="研究需求", step_type=StepType.RESEARCH
            )
        ]
        assert planner._validate_step_sequence(research_only) is True

    @pytest.mark.asyncio
    async def test_get_additional_steps(self, planner):
        """测试获取额外步骤"""
        # 测试用例生成任务
        steps = planner._get_additional_steps(TaskType.TEST_CASE_GENERATION, "zh-CN")
        assert len(steps) >= 1
        assert any("边界条件" in step.title for step in steps)

        # 测试脚本生成任务
        steps = planner._get_additional_steps(TaskType.TEST_SCRIPT_GENERATION, "zh-CN")
        assert len(steps) >= 1
        assert any("测试数据" in step.title for step in steps)

    @pytest.mark.asyncio
    async def test_get_validation_step(self, planner):
        """测试获取验证步骤"""
        step = planner._get_validation_step(TaskType.TEST_CASE_GENERATION, "zh-CN")

        assert step is not None
        assert "验证" in step.title
        assert step.step_type == StepType.ANALYSIS.value

    @pytest.mark.asyncio
    async def test_enhance_execution_plan(self, planner, mock_state):
        """测试增强执行计划"""
        # 创建一个步骤很少的计划
        minimal_plan = ExecutionPlan(
            title="最小计划",
            thought="测试思路",
            locale="zh-CN",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=[
                ExecutionStep(
                    title="单一步骤", description="描述", step_type=StepType.RESEARCH
                )
            ],
            has_enough_context=True,
        )

        enhanced_plan = planner._enhance_execution_plan(minimal_plan, mock_state)

        # 应该添加了额外步骤和验证步骤
        assert len(enhanced_plan.steps) > 1
        assert any("验证" in step.title for step in enhanced_plan.steps)

    @pytest.mark.asyncio
    async def test_process_with_cache(self, planner, mock_state):
        """测试带缓存的处理流程"""
        # 第一次处理
        with patch.object(
            planner, "_create_execution_plan_enhanced", new_callable=AsyncMock
        ) as mock_create:
            mock_plan = planner._create_default_plan(
                TaskType.TEST_CASE_GENERATION, "zh-CN"
            )
            mock_create.return_value = mock_plan

            result1 = await planner.process(mock_state)

            # 应该调用了创建方法
            mock_create.assert_called_once()
            assert result1["current_plan"] == mock_plan

        # 重置状态的迭代次数
        mock_state["plan_iterations"] = 0

        # 第二次处理相同任务（应该使用缓存）
        with patch.object(
            planner, "_create_execution_plan_enhanced", new_callable=AsyncMock
        ) as mock_create2:
            result2 = await planner.process(mock_state)

            # 不应该调用创建方法（使用缓存）
            mock_create2.assert_not_called()
            assert result2["current_plan"] == mock_plan

    @pytest.mark.asyncio
    async def test_process_max_iterations(self, planner, mock_state):
        """测试最大迭代次数限制"""
        # 设置超过最大迭代次数
        mock_state["plan_iterations"] = 5  # 超过默认的3次

        result = await planner.process(mock_state)

        # 应该使用默认计划
        assert result["current_plan"] is not None
        assert result["plan_iterations"] == 6  # 5 + 1

    @pytest.mark.asyncio
    async def test_process_missing_task_info(self, planner):
        """测试缺少任务信息的处理"""
        incomplete_state = TestAgentState(
            messages=[],
            locale="zh-CN",
            task_topic="",  # 缺少任务主题
            task_type=None,  # 缺少任务类型
            plan_iterations=0,
            current_plan=None,
            observations=[],
            resources=[],
            rag_results=[],
            final_report="",
            review_score=None,
            auto_accepted_plan=False,
            enable_rag_search=True,
            enable_human_feedback=True,
        )

        with pytest.raises(PlanningException):
            await planner.process(incomplete_state)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
