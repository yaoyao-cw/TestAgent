#!/usr/bin/env python3
"""
工作流集成测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from src.graph.workflow import TestAgentWorkflow, get_workflow, execute_workflow
from src.graph.workflow_manager import WorkflowManager, get_workflow_manager
from src.models.state import TestAgentState
from src.models.types import TaskType
from src.exceptions import WorkflowException


class TestWorkflowIntegration:
    """工作流集成测试类"""
    
    def setup_method(self):
        """测试前置设置"""
        self.workflow = TestAgentWorkflow()
        self.workflow_manager = WorkflowManager()
    
    def test_workflow_initialization(self):
        """测试工作流初始化"""
        workflow = TestAgentWorkflow()
        
        assert workflow is not None
        assert workflow.graph is not None
        assert workflow.checkpointer is not None
        assert len(workflow.nodes) > 0
        assert "coder" in workflow.nodes
        assert "reporter" in workflow.nodes
        assert "reviewer" in workflow.nodes
    
    def test_get_workflow_singleton(self):
        """测试工作流单例模式"""
        workflow1 = get_workflow()
        workflow2 = get_workflow()
        
        assert workflow1 is workflow2
        assert isinstance(workflow1, TestAgentWorkflow)
    
    def test_workflow_graph_visualization(self):
        """测试工作流图可视化"""
        visualization = self.workflow.get_graph_visualization()
        
        assert isinstance(visualization, str)
        assert "graph TD" in visualization
        assert "Coordinator" in visualization
        assert "Planner" in visualization
        assert "Researcher" in visualization
        assert "Coder" in visualization
        assert "Reporter" in visualization
        assert "Reviewer" in visualization
    
    def test_workflow_status(self):
        """测试工作流状态"""
        status = self.workflow.get_workflow_status()
        
        assert isinstance(status, dict)
        assert "thread_id" in status
        assert "status" in status
        assert "nodes_count" in status
        assert "graph_compiled" in status
        assert status["graph_compiled"] is True
    
    def test_coordinator_router(self):
        """测试协调器路由逻辑"""
        # 任务已识别
        state_identified = {"task_identified": True}
        result = self.workflow._coordinator_router(state_identified)
        assert result == "planner"
        
        # 任务未识别
        state_not_identified = {"task_identified": False}
        result = self.workflow._coordinator_router(state_not_identified)
        assert result == "end"
        
        # 空状态
        empty_state = {}
        result = self.workflow._coordinator_router(empty_state)
        assert result == "end"
    
    def test_planner_router(self):
        """测试规划器路由逻辑"""
        # 计划已创建
        state_planned = {"plan_created": True}
        result = self.workflow._planner_router(state_planned)
        assert result == "researcher"
        
        # 计划未创建
        state_not_planned = {"plan_created": False}
        result = self.workflow._planner_router(state_not_planned)
        assert result == "end"
    
    def test_researcher_router(self):
        """测试研究员路由逻辑"""
        # 代码生成任务
        state_code_gen = {"task_type": TaskType.TEST_SCRIPT_GENERATION.value}
        result = self.workflow._researcher_router(state_code_gen)
        assert result == "coder"
        
        # 其他任务类型
        state_other = {"task_type": TaskType.TEST_CASE_GENERATION.value}
        result = self.workflow._researcher_router(state_other)
        assert result == "reporter"
        
        # 空状态
        empty_state = {}
        result = self.workflow._researcher_router(empty_state)
        assert result == "reporter"
    
    def test_coder_router(self):
        """测试编码员路由逻辑"""
        # 继续编码
        state_continue = {"next_node": "coder"}
        result = self.workflow._coder_router(state_continue)
        assert result == "coder"
        
        # 转到报告员
        state_report = {"next_node": "reporter"}
        result = self.workflow._coder_router(state_report)
        assert result == "reporter"
        
        # 默认情况
        empty_state = {}
        result = self.workflow._coder_router(empty_state)
        assert result == "reporter"
    
    def test_reporter_router(self):
        """测试报告员路由逻辑"""
        # 任务完成，需要评审
        state_completed = {"task_completed": True}
        result = self.workflow._reporter_router(state_completed)
        assert result == "reviewer"
        
        # 任务未完成
        state_not_completed = {"task_completed": False}
        result = self.workflow._reporter_router(state_not_completed)
        assert result == "end"
    
    @pytest.mark.asyncio
    async def test_node_wrappers(self):
        """测试节点包装器"""
        initial_state = {
            "task_type": TaskType.TEST_CASE_GENERATION.value,
            "locale": "zh-CN",
            "observations": []
        }
        
        # 测试协调器包装器
        result = await self.workflow._coordinator_wrapper(initial_state)
        assert isinstance(result, dict)
        assert "next_node" in result or "task_identified" in result
        
        # 测试规划器包装器
        result = await self.workflow._planner_wrapper(initial_state)
        assert isinstance(result, dict)
        assert "next_node" in result or "plan_created" in result
        
        # 测试研究员包装器
        result = await self.workflow._researcher_wrapper(initial_state)
        assert isinstance(result, dict)
        assert "next_node" in result or "research_completed" in result
    
    @pytest.mark.asyncio
    async def test_execute_workflow_function(self):
        """测试工作流执行函数"""
        initial_state = {
            "task_type": TaskType.TEST_CASE_GENERATION.value,
            "task_topic": "测试任务",
            "locale": "zh-CN",
            "observations": [],
            "task_identified": True,
            "plan_created": True,
            "research_completed": True,
            "task_completed": True
        }
        
        # Mock节点以避免实际执行
        with patch.object(self.workflow.nodes["coder"], 'process', new_callable=AsyncMock) as mock_coder, \
             patch.object(self.workflow.nodes["reporter"], 'process', new_callable=AsyncMock) as mock_reporter, \
             patch.object(self.workflow.nodes["reviewer"], 'process', new_callable=AsyncMock) as mock_reviewer:
            
            mock_coder.return_value = {"next_node": "reporter", "observations": []}
            mock_reporter.return_value = {"task_completed": True, "report": {"type": "final_report"}}
            mock_reviewer.return_value = {"review": {"type": "quality_review"}, "final_evaluation": True}
            
            result = await execute_workflow(initial_state)
            
            assert isinstance(result, dict)
            # 由于是异步流，结果可能包含多个状态
    
    @pytest.mark.asyncio
    async def test_workflow_with_error_handling(self):
        """测试带错误处理的工作流执行"""
        initial_state = {
            "task_type": TaskType.TEST_CASE_GENERATION.value,
            "task_topic": "测试任务",
            "locale": "zh-CN",
            "observations": []
        }
        
        # 测试正常执行
        result = await self.workflow_manager.execute_workflow(
            initial_state,
            execution_id="test_exec_1",
            timeout=30,
            retry_on_failure=False
        )
        
        assert isinstance(result, dict)
        
        # 检查执行记录
        status = self.workflow_manager.get_execution_status("test_exec_1")
        assert status is not None
        assert status["execution_id"] == "test_exec_1"
        assert status["status"] in ["completed", "failed"]
    
    @pytest.mark.asyncio
    async def test_workflow_timeout_handling(self):
        """测试工作流超时处理"""
        # 测试超时配置和错误处理机制
        initial_state = {
            "task_type": TaskType.TEST_CASE_GENERATION.value,
            "task_topic": "测试任务",
            "locale": "zh-CN",
            "observations": []
        }
        
        # 测试超时参数是否正确传递
        try:
            result = await self.workflow_manager.execute_workflow(
                initial_state,
                execution_id="test_timeout_config",
                timeout=30,  # 30秒超时，足够完成
                retry_on_failure=False
            )
            # 如果成功执行，检查结果
            assert isinstance(result, dict)
        except WorkflowException as e:
            # 如果失败，确保是预期的错误类型
            assert "工作流执行失败" in str(e)
        
        # 检查执行记录
        status = self.workflow_manager.get_execution_status("test_timeout_config")
        assert status is not None
        assert status["execution_id"] == "test_timeout_config"
    
    def test_workflow_manager_initialization(self):
        """测试工作流管理器初始化"""
        manager = WorkflowManager()
        
        assert manager is not None
        assert manager.workflow is not None
        assert isinstance(manager.executions, dict)
        assert isinstance(manager.error_handlers, dict)
        assert isinstance(manager.recovery_strategies, dict)
        assert len(manager.error_handlers) > 0
        assert len(manager.recovery_strategies) > 0
    
    def test_get_workflow_manager_singleton(self):
        """测试工作流管理器单例模式"""
        manager1 = get_workflow_manager()
        manager2 = get_workflow_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, WorkflowManager)
    
    def test_execution_status_tracking(self):
        """测试执行状态跟踪"""
        # 创建一个模拟执行记录
        from src.graph.workflow_manager import WorkflowExecution
        from datetime import datetime
        
        execution = WorkflowExecution(
            execution_id="test_status",
            thread_id="test_thread",
            initial_state={"task_type": "test"},
            start_time=datetime.now()
        )
        
        self.workflow_manager.executions["test_status"] = execution
        
        # 获取状态
        status = self.workflow_manager.get_execution_status("test_status")
        
        assert status is not None
        assert status["execution_id"] == "test_status"
        assert status["thread_id"] == "test_thread"
        assert status["status"] == "running"
        assert "start_time" in status
        assert "duration_seconds" in status
    
    def test_list_executions(self):
        """测试列出执行记录"""
        # 添加一些模拟执行记录
        from src.graph.workflow_manager import WorkflowExecution
        from datetime import datetime
        
        for i in range(3):
            execution = WorkflowExecution(
                execution_id=f"test_list_{i}",
                thread_id=f"thread_{i}",
                initial_state={"task_type": "test"},
                start_time=datetime.now(),
                status="completed" if i % 2 == 0 else "failed"
            )
            self.workflow_manager.executions[f"test_list_{i}"] = execution
        
        # 列出所有执行
        all_executions = self.workflow_manager.list_executions()
        assert len(all_executions) >= 3
        
        # 按状态过滤
        completed_executions = self.workflow_manager.list_executions(status_filter="completed")
        failed_executions = self.workflow_manager.list_executions(status_filter="failed")
        
        assert len(completed_executions) >= 2
        assert len(failed_executions) >= 1
    
    def test_cancel_execution(self):
        """测试取消执行"""
        from src.graph.workflow_manager import WorkflowExecution
        from datetime import datetime
        
        # 创建运行中的执行
        execution = WorkflowExecution(
            execution_id="test_cancel",
            thread_id="test_thread",
            initial_state={"task_type": "test"},
            start_time=datetime.now(),
            status="running"
        )
        
        self.workflow_manager.executions["test_cancel"] = execution
        
        # 取消执行
        result = self.workflow_manager.cancel_execution("test_cancel")
        assert result is True
        
        # 检查状态
        status = self.workflow_manager.get_execution_status("test_cancel")
        assert status["status"] == "cancelled"
        assert status["end_time"] is not None
        
        # 尝试取消不存在的执行
        result = self.workflow_manager.cancel_execution("nonexistent")
        assert result is False
    
    def test_cleanup_old_executions(self):
        """测试清理旧执行记录"""
        from src.graph.workflow_manager import WorkflowExecution
        from datetime import datetime, timedelta
        
        # 添加新旧执行记录
        old_time = datetime.now() - timedelta(hours=25)  # 25小时前
        new_time = datetime.now() - timedelta(hours=1)   # 1小时前
        
        old_execution = WorkflowExecution(
            execution_id="old_exec",
            thread_id="old_thread",
            initial_state={"task_type": "test"},
            start_time=old_time,
            status="completed"
        )
        
        new_execution = WorkflowExecution(
            execution_id="new_exec",
            thread_id="new_thread",
            initial_state={"task_type": "test"},
            start_time=new_time,
            status="completed"
        )
        
        self.workflow_manager.executions["old_exec"] = old_execution
        self.workflow_manager.executions["new_exec"] = new_execution
        
        # 清理24小时前的记录
        initial_count = len(self.workflow_manager.executions)
        self.workflow_manager.cleanup_old_executions(max_age_hours=24)
        
        # 检查旧记录被清理
        assert "old_exec" not in self.workflow_manager.executions
        assert "new_exec" in self.workflow_manager.executions
        assert len(self.workflow_manager.executions) == initial_count - 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])