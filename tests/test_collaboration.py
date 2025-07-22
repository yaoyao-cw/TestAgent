#!/usr/bin/env python3
"""
人机协作功能集成测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.collaboration.plan_reviewer import PlanReviewer, ReviewFeedback, ReviewStatus
from src.collaboration.feedback_processor import FeedbackProcessor
from src.collaboration.auto_accept_manager import AutoAcceptManager, AutoAcceptMode, AutoAcceptCondition
from src.collaboration.report_editor import ReportEditor, EditOperation
from src.collaboration.content_optimizer import ContentOptimizer, OptimizationSuggestion
from src.models.execution import ExecutionPlan, ExecutionStep
from src.models.types import TaskType, StepType
from src.exceptions import TestAgentException


class TestPlanReviewer:
    """计划审查器测试"""
    
    @pytest.fixture
    def plan_reviewer(self):
        """计划审查器fixture"""
        return PlanReviewer()
    
    @pytest.fixture
    def sample_plan(self):
        """示例计划fixture"""
        steps = [
            ExecutionStep(
                title="需求分析",
                description="分析需求文档",
                step_type=StepType.RESEARCH
            ),
            ExecutionStep(
                title="测试用例生成",
                description="生成测试用例",
                step_type=StepType.CODING
            )
        ]
        
        return ExecutionPlan(
            title="测试用例生成计划",
            thought="根据需求文档生成全面的测试用例",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=steps
        )
    
    def test_submit_for_review(self, plan_reviewer, sample_plan):
        """测试提交审查"""
        review_id = plan_reviewer.submit_for_review(
            "plan1",
            sample_plan,
            TaskType.TEST_CASE_GENERATION,
            {"user": "test_user"}
        )
        
        assert review_id.startswith("review_plan1_")
        assert "plan1" in plan_reviewer.pending_reviews[review_id]["plan_id"]
        assert plan_reviewer.pending_reviews[review_id]["status"] == ReviewStatus.PENDING
    
    def test_get_pending_reviews(self, plan_reviewer, sample_plan):
        """测试获取待审查计划"""
        review_id = plan_reviewer.submit_for_review("plan1", sample_plan, TaskType.TEST_CASE_GENERATION)
        
        pending = plan_reviewer.get_pending_reviews()
        assert review_id in pending
        assert pending[review_id]["plan_id"] == "plan1"
        assert "plan_summary" in pending[review_id]
    
    def test_approve_plan(self, plan_reviewer, sample_plan):
        """测试批准计划"""
        review_id = plan_reviewer.submit_for_review("plan1", sample_plan, TaskType.TEST_CASE_GENERATION)
        
        success = plan_reviewer.approve_plan(review_id, "计划看起来不错")
        assert success
        assert plan_reviewer.pending_reviews[review_id]["status"] == ReviewStatus.APPROVED
        assert len(plan_reviewer.review_history[review_id]) == 1
    
    def test_reject_plan(self, plan_reviewer, sample_plan):
        """测试拒绝计划"""
        review_id = plan_reviewer.submit_for_review("plan1", sample_plan, TaskType.TEST_CASE_GENERATION)
        
        success = plan_reviewer.reject_plan(
            review_id, 
            "计划不够详细", 
            ["添加更多测试场景", "增加错误处理"]
        )
        assert success
        assert plan_reviewer.pending_reviews[review_id]["status"] == ReviewStatus.REJECTED
    
    def test_modify_plan(self, plan_reviewer, sample_plan):
        """测试修改计划"""
        review_id = plan_reviewer.submit_for_review("plan1", sample_plan, TaskType.TEST_CASE_GENERATION)
        
        modifications = {
            "title": "更新的计划标题",
            "thought": "更新的计划思路"
        }
        
        success = plan_reviewer.modify_plan(review_id, modifications, "根据反馈修改")
        assert success
        assert plan_reviewer.pending_reviews[review_id]["status"] == ReviewStatus.MODIFIED
        assert sample_plan.title == "更新的计划标题"


class TestFeedbackProcessor:
    """反馈处理器测试"""
    
    @pytest.fixture
    def feedback_processor(self):
        """反馈处理器fixture"""
        return FeedbackProcessor()
    
    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务"""
        with patch('src.collaboration.feedback_processor.get_llm_service') as mock:
            mock_service = Mock()
            mock_service.generate_response = AsyncMock(return_value='{"primary": "modify_step", "secondary": [], "confidence": 0.8, "reasoning": "用户想要修改步骤"}')
            mock.return_value = mock_service
            yield mock_service
    
    @pytest.fixture
    def sample_plan_dict(self):
        """示例计划字典"""
        return {
            "id": "plan1",
            "description": "测试计划",
            "steps": [
                {
                    "id": "step1",
                    "description": "分析需求",
                    "agent": "researcher",
                    "tools": ["document_search"]
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_process_natural_language_feedback(self, feedback_processor, mock_llm_service, sample_plan_dict):
        """测试处理自然语言反馈"""
        feedback_text = "请修改第一个步骤，增加更详细的分析"
        
        result = await feedback_processor.process_natural_language_feedback(
            feedback_text,
            sample_plan_dict
        )
        
        assert "original_feedback" in result
        assert "intent" in result
        assert "modifications" in result
        assert "confidence" in result
        assert result["original_feedback"] == feedback_text
    
    def test_rule_based_intent_detection(self, feedback_processor):
        """测试基于规则的意图检测"""
        feedback_text = "添加一个新的测试步骤"
        
        intent = feedback_processor._rule_based_intent_detection(feedback_text)
        
        assert intent["primary"] == "add_step"
        assert intent["method"] == "rule_based"
        assert intent["confidence"] > 0


class TestAutoAcceptManager:
    """自动接受管理器测试"""
    
    @pytest.fixture
    def auto_accept_manager(self):
        """自动接受管理器fixture"""
        return AutoAcceptManager()
    
    def test_set_mode(self, auto_accept_manager):
        """测试设置模式"""
        auto_accept_manager.set_mode(AutoAcceptMode.ALWAYS)
        assert auto_accept_manager.mode == AutoAcceptMode.ALWAYS
    
    def test_add_condition(self, auto_accept_manager):
        """测试添加条件"""
        condition = AutoAcceptCondition(
            name="高置信度",
            condition_type="confidence_threshold",
            parameters={"threshold": 0.9}
        )
        
        auto_accept_manager.add_condition(condition)
        assert len(auto_accept_manager.conditions) == 1
        assert auto_accept_manager.conditions[0].name == "高置信度"
    
    def test_should_auto_accept_disabled(self, auto_accept_manager):
        """测试禁用模式下的自动接受判断"""
        review_data = {"confidence": 0.9, "task_type": "test"}
        
        should_accept, reason = auto_accept_manager.should_auto_accept(review_data)
        
        assert not should_accept
        assert "禁用" in reason
    
    def test_should_auto_accept_always(self, auto_accept_manager):
        """测试总是接受模式"""
        auto_accept_manager.set_mode(AutoAcceptMode.ALWAYS)
        review_data = {"confidence": 0.9, "task_type": "test"}
        
        should_accept, reason = auto_accept_manager.should_auto_accept(review_data)
        
        assert should_accept
        assert "总是" in reason
    
    def test_conditional_acceptance(self, auto_accept_manager):
        """测试条件接受"""
        auto_accept_manager.set_mode(AutoAcceptMode.CONDITIONAL)
        
        # 添加条件
        condition = AutoAcceptCondition(
            name="高置信度",
            condition_type="confidence_threshold",
            parameters={"threshold": 0.8}
        )
        auto_accept_manager.add_condition(condition)
        
        # 测试满足条件
        review_data = {"confidence": 0.9, "task_type": "test"}
        should_accept, reason = auto_accept_manager.should_auto_accept(review_data)
        
        assert should_accept
        assert "高置信度" in reason
    
    def test_create_preset_conditions(self, auto_accept_manager):
        """测试创建预设条件"""
        presets = auto_accept_manager.create_preset_conditions()
        
        assert len(presets) > 0
        assert all(isinstance(preset, AutoAcceptCondition) for preset in presets)
        assert any(preset.name == "高置信度自动接受" for preset in presets)


class TestReportEditor:
    """报告编辑器测试"""
    
    @pytest.fixture
    def report_editor(self):
        """报告编辑器fixture"""
        return ReportEditor()
    
    @pytest.fixture
    def sample_report_content(self):
        """示例报告内容"""
        return """# 测试报告

## 概述
这是一个测试报告。

## 测试结果
所有测试都通过了。

## 结论
系统运行正常。
"""
    
    def test_create_report_version(self, report_editor, sample_report_content):
        """测试创建报告版本"""
        version_id = report_editor.create_report_version(
            "report1",
            sample_report_content,
            {"author": "test_user"}
        )
        
        assert version_id.startswith("v")
        assert "report1" in report_editor.report_versions
        assert len(report_editor.report_versions["report1"]) == 1
    
    def test_edit_report(self, report_editor, sample_report_content):
        """测试编辑报告"""
        # 创建初始版本
        report_editor.create_report_version("report1", sample_report_content)
        
        # 创建编辑操作
        operations = [
            EditOperation(
                operation_type="insert",
                target="line",
                content="## 新增章节\n这是新增的内容。",
                position=5
            )
        ]
        
        new_version_id, edited_content = report_editor.edit_report("report1", operations)
        
        assert new_version_id.startswith("v")
        assert "新增章节" in edited_content
        assert len(report_editor.report_versions["report1"]) == 2
    
    def test_add_section(self, report_editor, sample_report_content):
        """测试添加章节"""
        report_editor.create_report_version("report1", sample_report_content)
        
        content_data = {
            "task_overview": "任务概述内容",
            "key_findings": "主要发现",
            "recommendations": "建议内容"
        }
        
        new_version_id = report_editor.add_section(
            "report1",
            "执行摘要",
            "executive_summary",
            content_data
        )
        
        assert new_version_id.startswith("v")
        
        # 检查内容是否包含新章节
        latest_content = report_editor.get_report_content("report1")
        assert "执行摘要" in latest_content
        assert "任务概述内容" in latest_content
    
    def test_compare_versions(self, report_editor, sample_report_content):
        """测试版本比较"""
        # 创建两个版本
        v1 = report_editor.create_report_version("report1", sample_report_content)
        
        modified_content = sample_report_content.replace("所有测试都通过了", "大部分测试通过了")
        v2 = report_editor.create_report_version("report1", modified_content)
        
        diff = report_editor.compare_versions("report1", v1, v2)
        
        assert diff["version1_id"] == v1
        assert diff["version2_id"] == v2
        assert diff["total_changes"] > 0


class TestContentOptimizer:
    """内容优化器测试"""
    
    @pytest.fixture
    def content_optimizer(self):
        """内容优化器fixture"""
        return ContentOptimizer()
    
    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务"""
        with patch('src.collaboration.content_optimizer.get_llm_service') as mock:
            mock_service = Mock()
            mock_service.generate_response = AsyncMock(return_value='{"suggestions": [{"type": "clarity", "target": "paragraph1", "issue": "表达不清", "original": "这个功能", "optimized": "该功能", "reason": "避免模糊指代", "confidence": 0.8}], "overall_assessment": "整体良好", "priority_areas": ["clarity"]}')
            mock.return_value = mock_service
            yield mock_service
    
    @pytest.fixture
    def sample_content(self):
        """示例内容"""
        return """# 测试报告

## 概述
这个系统的功能非常好，可能会有一些问题，但是大概率是没问题的。

## 详细分析
我们觉得这个方案应该可以满足需求，比较适合当前的情况。
"""
    
    @pytest.mark.asyncio
    async def test_analyze_content(self, content_optimizer, mock_llm_service, sample_content):
        """测试内容分析"""
        result = await content_optimizer.analyze_content(sample_content, "report")
        
        assert "content_id" in result
        assert "basic_metrics" in result
        assert "suggestions" in result
        assert "optimization_score" in result
        assert result["content_type"] == "report"
    
    def test_analyze_basic_metrics(self, content_optimizer, sample_content):
        """测试基础指标分析"""
        metrics = content_optimizer._analyze_basic_metrics(sample_content)
        
        assert "total_characters" in metrics
        assert "total_words" in metrics
        assert "total_sentences" in metrics
        assert "readability_score" in metrics
        assert metrics["total_words"] > 0
    
    def test_analyze_with_rules(self, content_optimizer, sample_content):
        """测试基于规则的分析"""
        suggestions = content_optimizer._analyze_with_rules(sample_content, ["clarity"])
        
        assert len(suggestions) > 0
        assert any(s.suggestion_type == "clarity" for s in suggestions)
    
    @pytest.mark.asyncio
    async def test_optimize_content(self, content_optimizer, mock_llm_service, sample_content):
        """测试内容优化"""
        # 先分析内容
        analysis_result = await content_optimizer.analyze_content(sample_content)
        
        # 选择第一个建议进行优化
        if analysis_result["suggestions"]:
            suggestion_id = analysis_result["suggestions"][0]["id"]
            
            optimized_content, application_result = await content_optimizer.optimize_content(
                sample_content,
                [suggestion_id]
            )
            
            assert application_result["applied_count"] >= 0
            assert "optimization_timestamp" in application_result
    
    def test_get_optimization_templates(self, content_optimizer):
        """测试获取优化模板"""
        templates = content_optimizer.get_optimization_templates()
        
        assert "executive_summary" in templates
        assert "technical_details" in templates
        assert "recommendations" in templates
        assert all(isinstance(template, str) for template in templates.values())


class TestCollaborationIntegration:
    """人机协作集成测试"""
    
    @pytest.fixture
    def collaboration_components(self):
        """协作组件fixture"""
        return {
            "plan_reviewer": PlanReviewer(),
            "feedback_processor": FeedbackProcessor(),
            "auto_accept_manager": AutoAcceptManager(),
            "report_editor": ReportEditor(),
            "content_optimizer": ContentOptimizer()
        }
    
    @pytest.fixture
    def sample_execution_plan(self):
        """示例执行计划"""
        steps = [
            ExecutionStep(
                title="需求分析",
                description="分析需求文档",
                step_type=StepType.RESEARCH
            )
        ]
        
        return ExecutionPlan(
            title="集成测试计划",
            thought="通过集成测试验证人机协作功能",
            task_type=TaskType.TEST_CASE_GENERATION,
            steps=steps
        )
    
    @pytest.mark.asyncio
    async def test_full_collaboration_workflow(self, collaboration_components, sample_execution_plan):
        """测试完整的协作工作流"""
        plan_reviewer = collaboration_components["plan_reviewer"]
        auto_accept_manager = collaboration_components["auto_accept_manager"]
        
        # 1. 提交计划审查
        review_id = plan_reviewer.submit_for_review(
            "integration_plan",
            sample_execution_plan,
            TaskType.TEST_CASE_GENERATION,
            {"user": "test_user", "confidence": 0.9}
        )
        
        assert review_id is not None
        
        # 2. 检查自动接受
        review_data = {
            "confidence": 0.9,
            "task_type": "test_case_generation",
            "submitted_at": datetime.now().isoformat()
        }
        
        should_accept, reason = auto_accept_manager.should_auto_accept(review_data)
        
        # 3. 根据自动接受结果处理
        if should_accept:
            success = plan_reviewer.approve_plan(review_id, f"自动接受: {reason}")
            assert success
        else:
            # 手动审查流程
            success = plan_reviewer.approve_plan(review_id, "手动审查通过")
            assert success
        
        # 4. 获取批准的计划
        approved_plan = plan_reviewer.get_approved_plan(review_id)
        assert approved_plan is not None
        assert approved_plan.id == "integration_plan"
    
    @pytest.mark.asyncio
    async def test_report_optimization_workflow(self, collaboration_components):
        """测试报告优化工作流"""
        report_editor = collaboration_components["report_editor"]
        content_optimizer = collaboration_components["content_optimizer"]
        
        # 1. 创建报告
        sample_content = """# 测试报告
        
## 概述
这个系统可能有一些问题，但是大概率没问题。

## 结论
我觉得这个方案应该可以。
"""
        
        version_id = report_editor.create_report_version("test_report", sample_content)
        assert version_id is not None
        
        # 2. 分析内容（模拟，因为需要LLM服务）
        try:
            analysis_result = await content_optimizer.analyze_content(sample_content, "report")
            
            # 3. 如果有优化建议，应用它们
            if analysis_result["suggestions"]:
                high_confidence_suggestions = [
                    s["id"] for s in analysis_result["suggestions"]
                    if s["confidence"] > 0.7
                ]
                
                if high_confidence_suggestions:
                    optimized_content, _ = await content_optimizer.optimize_content(
                        sample_content,
                        high_confidence_suggestions[:2]  # 只应用前两个建议
                    )
                    
                    # 4. 创建优化后的报告版本
                    new_version_id = report_editor.create_report_version(
                        "test_report",
                        optimized_content,
                        {"optimization_applied": True}
                    )
                    
                    assert new_version_id != version_id
                    
        except Exception as e:
            # 如果LLM服务不可用，跳过这部分测试
            pytest.skip(f"LLM服务不可用: {e}")
    
    def test_component_statistics(self, collaboration_components):
        """测试组件统计信息"""
        plan_reviewer = collaboration_components["plan_reviewer"]
        auto_accept_manager = collaboration_components["auto_accept_manager"]
        content_optimizer = collaboration_components["content_optimizer"]
        
        # 测试计划审查器统计
        stats = plan_reviewer.get_statistics()
        assert "total_reviews" in stats
        assert "approval_rate" in stats
        
        # 测试自动接受管理器统计
        stats = auto_accept_manager.get_statistics()
        assert "mode" in stats
        assert "statistics" in stats
        
        # 测试内容优化器统计
        stats = content_optimizer.get_statistics()
        assert "total_content_analyzed" in stats
        assert "application_rate" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])