"""测试Reviewer和Reporter智能体"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.agents.human import (
    HumanAgent,
    InterventionPriority,
    InterventionType,
    create_human_agent,
)
from src.agents.quality_assurance import (
    QualityAssuranceWorkflow,
    TestCaseQualityChecker,
    TestScriptQualityChecker,
    get_quality_assurance_workflow,
)
from src.agents.reporter import ReporterAgent, create_reporter_agent
from src.agents.reviewer import ReviewerAgent, create_reviewer_agent
from src.core.base_agent import AgentInput
from src.models.types import AgentType, TaskType
from src.models.workspace import GlobalState, TaskMetadata, TaskStatus


class TestReviewerAgent:
    """测试Reviewer智能体"""

    def setup_method(self):
        """设置测试环境"""
        self.global_state = GlobalState()
        self.task_metadata = TaskMetadata(
            task_id="test_task_001",
            title="测试任务",
            description="测试描述",
            task_type=TaskType.TEST_CASE_GENERATION,
            status=TaskStatus.IN_PROGRESS,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            workspace_path="/test/workspace",
        )
        self.global_state.initialize_task(self.task_metadata)

    def test_reviewer_agent_creation(self):
        """测试Reviewer智能体创建"""
        reviewer = create_reviewer_agent(self.global_state)

        assert isinstance(reviewer, ReviewerAgent)
        assert reviewer.agent_type == AgentType.REVIEWER
        assert reviewer.global_state == self.global_state
        assert "file_read" in reviewer.available_tools
        assert "quality_check" in reviewer.available_tools

    def test_reviewer_load_phase(self):
        """测试Reviewer加载阶段"""
        reviewer = create_reviewer_agent(self.global_state)

        input_data = AgentInput(
            data={
                "review_type": "test_case",
                "content_path": "/test/content.md",
                "review_criteria": {"threshold": 80},
            }
        )

        state = reviewer.load(input_data)

        assert state["review_type"] == "test_case"
        assert state["content_path"] == "/test/content.md"
        assert "quality_standards" in state
        assert not state["review_completed"]

    @patch("src.agents.reviewer.get_llm_service")
    def test_reviewer_llm_phase(self, mock_llm_service):
        """测试Reviewer LLM阶段"""
        # 模拟LLM服务响应
        mock_response = Mock()
        mock_response.content = "评审结果：总分85分，建议改进测试覆盖率"
        mock_llm_service.return_value.invoke_sync.return_value = mock_response

        reviewer = create_reviewer_agent(self.global_state)

        state = {
            "review_type": "test_case",
            "content_to_review": "测试用例内容",
            "error_logs": [],
            "quality_standards": {"completeness_threshold": 80},
            "prompt_template": reviewer.get_prompt_template(),
            "available_tools": reviewer.available_tools,
        }

        result_state = reviewer.llm(state)

        assert "llm_output" in result_state
        assert result_state["llm_output"]["review_completed"]
        assert "review_result" in result_state["llm_output"]

    def test_reviewer_router_phase(self):
        """测试Reviewer路由阶段"""
        reviewer = create_reviewer_agent(self.global_state)

        state = {
            "llm_output": {
                "review_completed": True,
                "review_result": {"overall_score": 85},
                "error_analysis": {},
                "improvement_suggestions": ["改进建议"],
                "review_report": "评审报告内容",
            },
            "review_type": "test_case",
        }

        output = reviewer.router(state)

        assert output.data["review_completed"]
        assert output.data["review_result"]["overall_score"] == 85
        assert output.next_agent == "reporter"  # 高分数应该进入报告阶段


class TestReporterAgent:
    """测试Reporter智能体"""

    def setup_method(self):
        """设置测试环境"""
        self.global_state = GlobalState()
        self.task_metadata = TaskMetadata(
            task_id="test_task_002",
            title="报告测试任务",
            description="测试报告生成",
            task_type=TaskType.TEST_CASE_GENERATION,
            status=TaskStatus.IN_PROGRESS,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            workspace_path="/test/workspace",
        )
        self.global_state.initialize_task(self.task_metadata)

    def test_reporter_agent_creation(self):
        """测试Reporter智能体创建"""
        reporter = create_reporter_agent(self.global_state)

        assert isinstance(reporter, ReporterAgent)
        assert reporter.agent_type == AgentType.REPORTER
        assert reporter.global_state == self.global_state
        assert "file_read" in reporter.available_tools
        assert "report_generation" in reporter.available_tools

    def test_reporter_load_phase(self):
        """测试Reporter加载阶段"""
        reporter = create_reporter_agent(self.global_state)

        input_data = AgentInput(
            data={"report_type": "comprehensive", "task_id": "test_task_002"}
        )

        state = reporter.load(input_data)

        assert state["report_type"] == "comprehensive"
        assert state["task_id"] == "test_task_002"
        assert "task_data" in state
        assert not state["report_generated"]

    @patch("src.agents.reporter.get_llm_service")
    def test_reporter_llm_phase(self, mock_llm_service):
        """测试Reporter LLM阶段"""
        # 模拟LLM服务响应
        mock_response = Mock()
        mock_response.content = "# 综合测试报告\n\n测试执行完成，总体质量良好。"
        mock_llm_service.return_value.invoke_sync.return_value = mock_response

        reporter = create_reporter_agent(self.global_state)

        state = {
            "report_type": "comprehensive",
            "task_data": {"task_id": "test_task_002"},
            "execution_history": [],
            "review_results": {"overall_score": 85},
            "prompt_template": reporter.get_prompt_template(),
        }

        result_state = reporter.llm(state)

        assert "llm_output" in result_state
        assert result_state["llm_output"]["report_generated"]
        assert "final_report" in result_state["llm_output"]

    def test_reporter_router_phase(self):
        """测试Reporter路由阶段"""
        reporter = create_reporter_agent(self.global_state)

        state = {
            "llm_output": {
                "report_generated": True,
                "final_report": "# 测试报告\n报告内容",
                "execution_summary": {"total_steps": 5},
                "recommendations": ["建议1", "建议2"],
            },
            "task_id": "test_task_002",
        }

        output = reporter.router(state)

        assert output.data["report_generated"]
        assert output.data["task_completed"]
        assert "# 测试报告" in output.data["report_content"]


class TestHumanAgent:
    """测试Human智能体"""

    def setup_method(self):
        """设置测试环境"""
        self.global_state = GlobalState()
        self.task_metadata = TaskMetadata(
            task_id="test_task_003",
            title="人工干预测试",
            description="测试人工干预功能",
            task_type=TaskType.TEST_CASE_GENERATION,
            status=TaskStatus.IN_PROGRESS,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            workspace_path="/test/workspace",
        )
        self.global_state.initialize_task(self.task_metadata)

    def test_human_agent_creation(self):
        """测试Human智能体创建"""
        human = create_human_agent(self.global_state)

        assert isinstance(human, HumanAgent)
        assert human.name == "human"
        assert human.global_state == self.global_state
        assert "user_input" in human.available_tools

    def test_human_load_phase(self):
        """测试Human加载阶段"""
        human = create_human_agent(self.global_state)

        input_data = AgentInput(
            data={
                "intervention_type": "approval",
                "priority": "high",
                "question": "是否批准当前测试结果？",
                "options": ["approve", "reject"],
            }
        )

        state = human.load(input_data)

        assert state["intervention_type"] == InterventionType.APPROVAL
        assert state["priority"] == InterventionPriority.HIGH
        assert state["question"] == "是否批准当前测试结果？"
        assert state["options"] == ["approve", "reject"]
        assert not state["intervention_completed"]

    def test_human_llm_phase(self):
        """测试Human LLM阶段"""
        human = create_human_agent(self.global_state)

        # 创建干预请求
        from src.agents.human import HumanInterventionRequest

        intervention_request = HumanInterventionRequest(
            intervention_type=InterventionType.APPROVAL,
            priority=InterventionPriority.MEDIUM,
            context={"task_id": "test_task_003"},
            question="测试问题",
            options=["yes", "no"],
        )

        state = {
            "intervention_request": intervention_request,
            "intervention_type": InterventionType.APPROVAL,
            "question": "测试问题",
        }

        result_state = human.llm(state)

        assert "llm_output" in result_state
        assert result_state["llm_output"]["intervention_completed"]
        assert "human_response" in result_state["llm_output"]

    def test_human_router_phase(self):
        """测试Human路由阶段"""
        human = create_human_agent(self.global_state)

        state = {
            "llm_output": {
                "intervention_completed": True,
                "processed_response": {
                    "decision": "批准",
                    "next_agent": "reporter",
                    "next_action": "continue",
                },
            },
            "intervention_type": InterventionType.APPROVAL,
        }

        output = human.router(state)

        assert output.data["intervention_completed"]
        assert output.data["decision"] == "批准"
        assert output.next_agent == "reporter"


class TestQualityAssurance:
    """测试质量保证工作流"""

    def test_test_case_quality_checker(self):
        """测试测试用例质量检查器"""
        checker = TestCaseQualityChecker()

        test_case_content = """
# 用户登录功能测试

## 前置条件
- 系统已部署
- 测试用户已创建

## 测试步骤
1. 打开登录页面
2. 输入用户名和密码
3. 点击登录按钮

## 预期结果
- 成功跳转到主页面
- 显示用户信息
"""

        review = checker.check_quality(test_case_content)

        assert isinstance(review.overall_score, float)
        assert 0 <= review.overall_score <= 100
        assert isinstance(review.suggestions, list)

    def test_test_script_quality_checker(self):
        """测试测试脚本质量检查器"""
        checker = TestScriptQualityChecker()

        script_content = """
def test_user_login():
    \"\"\"测试用户登录功能\"\"\"
    try:
        # 准备测试数据
        username = "test_user"
        password = "test_password"
        
        # 执行登录
        result = login(username, password)
        
        # 验证结果
        assert result.success == True
        assert result.user_id is not None
        
    except Exception as e:
        print(f"测试失败: {e}")
        raise
"""

        review = checker.check_quality(script_content)

        assert isinstance(review.overall_score, float)
        assert 0 <= review.overall_score <= 100
        assert isinstance(review.suggestions, list)

    def test_quality_assurance_workflow(self):
        """测试质量保证工作流"""
        workflow = get_quality_assurance_workflow()

        # 测试用例评估
        test_case_content = "# 简单测试用例\n测试步骤：1. 执行操作\n预期结果：成功"
        test_case_review = workflow.evaluate_test_cases(test_case_content)

        assert isinstance(test_case_review.overall_score, float)

        # 测试脚本评估
        script_content = "def test_function():\n    assert True"
        script_review = workflow.evaluate_test_scripts(script_content)

        assert isinstance(script_review.overall_score, float)

        # 创建反馈循环
        feedback = workflow.create_feedback_loop(test_case_review, ["改进建议"])

        assert "feedback_id" in feedback
        assert "trend_analysis" in feedback

    def test_quality_metrics(self):
        """测试质量指标"""
        workflow = get_quality_assurance_workflow()

        # 执行一些评估以生成数据
        workflow.evaluate_test_cases("# 测试用例")
        workflow.evaluate_test_scripts("def test(): pass")

        metrics = workflow.get_quality_metrics()

        assert "total_evaluations" in metrics
        assert "average_score" in metrics
        assert "improvement_trend" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
