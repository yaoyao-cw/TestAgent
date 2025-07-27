"""数据模型测试"""

import pytest
from pydantic import ValidationError

from src.models.execution import ExecutionPlan, ExecutionStep
from src.models.review import (
    RequirementReview,
    ReviewScore,
    TestCaseReview,
    TestScriptReview,
)
from src.models.state import (
    TestAgentState,
    add_observation,
    add_resource,
    create_initial_state,
    get_completion_percentage,
    get_task_context,
    is_task_completed,
)
from src.models.types import StepType, TaskType


class TestExecutionStep:
    """执行步骤测试"""

    def test_create_execution_step(self):
        """测试创建执行步骤"""
        step = ExecutionStep(
            title="测试步骤",
            description="这是一个测试步骤",
            step_type=StepType.RESEARCH,
        )

        assert step.title == "测试步骤"
        assert step.description == "这是一个测试步骤"
        assert step.step_type == StepType.RESEARCH.value
        assert step.execution_res is None

    def test_execution_step_with_result(self):
        """测试带结果的执行步骤"""
        step = ExecutionStep(
            title="测试步骤",
            description="这是一个测试步骤",
            step_type=StepType.RESEARCH,
            execution_res="执行完成",
        )

        assert step.execution_res == "执行完成"


class TestExecutionPlan:
    """执行计划测试"""

    def test_create_execution_plan(self):
        """测试创建执行计划"""
        plan = ExecutionPlan(
            title="测试计划",
            thought="这是测试计划的思路",
            task_type=TaskType.TEST_CASE_GENERATION,
        )

        assert plan.title == "测试计划"
        assert plan.thought == "这是测试计划的思路"
        assert plan.task_type == TaskType.TEST_CASE_GENERATION.value
        assert plan.locale == "zh-CN"
        assert plan.has_enough_context is False
        assert len(plan.steps) == 0

    def test_plan_with_steps(self):
        """测试带步骤的执行计划"""
        steps = [
            ExecutionStep(
                title="步骤1", description="第一个步骤", step_type=StepType.RESEARCH
            ),
            ExecutionStep(
                title="步骤2",
                description="第二个步骤",
                step_type=StepType.CODING,
                execution_res="已完成",
            ),
        ]

        plan = ExecutionPlan(
            title="测试计划",
            thought="测试思路",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=steps,
        )

        assert len(plan.steps) == 2
        assert len(plan.get_incomplete_steps()) == 1
        assert len(plan.get_completed_steps()) == 1
        assert plan.is_completed() is False

    def test_plan_completion(self):
        """测试计划完成状态"""
        steps = [
            ExecutionStep(
                title="步骤1",
                description="第一个步骤",
                step_type=StepType.RESEARCH,
                execution_res="完成1",
            ),
            ExecutionStep(
                title="步骤2",
                description="第二个步骤",
                step_type=StepType.CODING,
                execution_res="完成2",
            ),
        ]

        plan = ExecutionPlan(
            title="测试计划",
            thought="测试思路",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=steps,
        )

        assert plan.is_completed() is True
        assert plan.get_next_step() is None

    def test_complete_step(self):
        """测试完成步骤"""
        step = ExecutionStep(
            title="测试步骤", description="测试描述", step_type=StepType.RESEARCH
        )

        plan = ExecutionPlan(
            title="测试计划",
            thought="测试思路",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=[step],
        )

        assert plan.complete_step("测试步骤", "执行结果") is True
        assert step.execution_res == "执行结果"
        assert plan.complete_step("不存在的步骤", "结果") is False


class TestReviewScore:
    """评审分数测试"""

    def test_create_review_score(self):
        """测试创建评审分数"""
        review = ReviewScore(
            overall_score=85.0,
            completeness=90.0,
            accuracy=80.0,
            maintainability=85.0,
            suggestions=["建议1", "建议2"],
        )

        assert review.overall_score == 85.0
        assert review.completeness == 90.0
        assert review.accuracy == 80.0
        assert review.maintainability == 85.0
        assert len(review.suggestions) == 2

    def test_score_validation(self):
        """测试分数验证"""
        with pytest.raises(ValidationError):
            ReviewScore(
                overall_score=150.0,  # 超出范围
                completeness=90.0,
                accuracy=80.0,
                maintainability=85.0,
            )

        with pytest.raises(ValidationError):
            ReviewScore(
                overall_score=-10.0,  # 低于范围
                completeness=90.0,
                accuracy=80.0,
                maintainability=85.0,
            )

    def test_get_grade(self):
        """测试获取等级"""
        review = ReviewScore(
            overall_score=95.0, completeness=90.0, accuracy=80.0, maintainability=85.0
        )
        assert review.get_grade() == "优秀"

        review.overall_score = 75.0
        assert review.get_grade() == "中等"

        review.overall_score = 50.0
        assert review.get_grade() == "不及格"

    def test_is_passing(self):
        """测试是否通过"""
        review = ReviewScore(
            overall_score=75.0, completeness=90.0, accuracy=80.0, maintainability=85.0
        )

        assert review.is_passing() is True
        assert review.is_passing(80.0) is False

    def test_add_suggestion(self):
        """测试添加建议"""
        review = ReviewScore(
            overall_score=75.0, completeness=90.0, accuracy=80.0, maintainability=85.0
        )

        review.add_suggestion("新建议")
        assert "新建议" in review.suggestions

        # 测试重复建议不会添加
        review.add_suggestion("新建议")
        assert review.suggestions.count("新建议") == 1


class TestTestAgentState:
    """TestAgent状态测试"""

    def test_create_state(self):
        """测试创建状态"""
        state = create_initial_state()

        assert state["locale"] == "zh-CN"
        assert state["task_topic"] == ""
        assert state["task_type"] is None
        assert state["plan_iterations"] == 0
        assert state["current_plan"] is None
        assert len(state["observations"]) == 0
        assert len(state["resources"]) == 0
        assert state["final_report"] == ""
        assert state["review_score"] is None
        assert state["auto_accepted_plan"] is True
        assert state["enable_rag_search"] is True

    def test_add_observation(self):
        """测试添加观察结果"""
        state = create_initial_state()

        add_observation(state, "观察1")
        add_observation(state, "观察2")
        assert len(state["observations"]) == 2

        # 测试重复观察不会添加
        add_observation(state, "观察1")
        assert len(state["observations"]) == 2

    def test_add_resource(self):
        """测试添加资源"""
        state = create_initial_state()

        resource1 = {"id": "1", "name": "资源1"}
        resource2 = {"id": "2", "name": "资源2"}

        add_resource(state, resource1)
        add_resource(state, resource2)
        assert len(state["resources"]) == 2

        # 测试重复资源不会添加
        add_resource(state, resource1)
        assert len(state["resources"]) == 2

    def test_get_task_context(self):
        """测试获取任务上下文"""
        state = create_initial_state()
        state["task_topic"] = "测试任务"
        state["task_type"] = TaskType.TEST_CASE_GENERATION

        context = get_task_context(state)
        assert "测试任务" in context
        assert "test_case_generation" in context

    def test_is_task_completed(self):
        """测试任务完成状态"""
        state = create_initial_state()
        assert is_task_completed(state) is False

        # 设置完成的计划和报告
        plan = ExecutionPlan(
            title="测试计划",
            thought="测试思路",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=[
                ExecutionStep(
                    title="步骤1",
                    description="描述1",
                    step_type=StepType.RESEARCH,
                    execution_res="完成",
                )
            ],
        )

        state["current_plan"] = plan
        state["final_report"] = "最终报告"

        assert is_task_completed(state) is True

    def test_get_completion_percentage(self):
        """测试获取完成百分比"""
        state = create_initial_state()
        assert get_completion_percentage(state) == 0.0

        steps = [
            ExecutionStep(
                title="步骤1",
                description="描述1",
                step_type=StepType.RESEARCH,
                execution_res="完成",
            ),
            ExecutionStep(
                title="步骤2", description="描述2", step_type=StepType.CODING
            ),
        ]

        plan = ExecutionPlan(
            title="测试计划",
            thought="测试思路",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=steps,
        )

        state["current_plan"] = plan
        assert get_completion_percentage(state) == 50.0


if __name__ == "__main__":
    pytest.main([__file__])
