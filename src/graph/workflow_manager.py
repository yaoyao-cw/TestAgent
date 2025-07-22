#!/usr/bin/env python3
"""
工作流管理器
提供工作流的高级管理功能，包括错误处理、恢复和监控
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..models.state import TestAgentState
from ..models.types import TaskType
from ..exceptions import WorkflowException
from .workflow import TestAgentWorkflow, get_workflow

logger = logging.getLogger(__name__)


@dataclass
class WorkflowExecution:
    """工作流执行记录"""
    execution_id: str
    thread_id: str
    initial_state: TestAgentState
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # running, completed, failed, cancelled
    final_state: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3


class WorkflowManager:
    """工作流管理器"""
    
    def __init__(self):
        """初始化工作流管理器"""
        self.workflow = get_workflow()
        self.executions: Dict[str, WorkflowExecution] = {}
        self.error_handlers: Dict[str, Callable] = {}
        self.recovery_strategies: Dict[str, Callable] = {}
        self._setup_default_handlers()
        logger.info("工作流管理器初始化完成")
    
    def _setup_default_handlers(self):
        """设置默认的错误处理器和恢复策略"""
        # 默认错误处理器
        self.error_handlers.update({
            "timeout": self._handle_timeout_error,
            "node_failure": self._handle_node_failure,
            "state_corruption": self._handle_state_corruption,
            "resource_exhaustion": self._handle_resource_exhaustion
        })
        
        # 默认恢复策略
        self.recovery_strategies.update({
            "retry": self._retry_strategy,
            "skip_node": self._skip_node_strategy,
            "reset_state": self._reset_state_strategy,
            "fallback": self._fallback_strategy
        })
    
    async def execute_workflow(
        self,
        initial_state: TestAgentState,
        execution_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = 300,  # 5分钟超时
        retry_on_failure: bool = True
    ) -> Dict[str, Any]:
        """
        执行工作流（带错误处理和恢复）
        
        Args:
            initial_state: 初始状态
            execution_id: 执行ID
            config: 配置参数
            timeout: 超时时间（秒）
            retry_on_failure: 失败时是否重试
            
        Returns:
            Dict: 执行结果
        """
        if execution_id is None:
            execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        thread_id = config.get("configurable", {}).get("thread_id", "default") if config else "default"
        
        # 创建执行记录
        execution = WorkflowExecution(
            execution_id=execution_id,
            thread_id=thread_id,
            initial_state=initial_state,
            start_time=datetime.now(),
            max_retries=3 if retry_on_failure else 0
        )
        
        self.executions[execution_id] = execution
        
        try:
            logger.info(f"开始执行工作流 {execution_id}")
            
            # 执行工作流（带超时）
            if timeout:
                final_state = await asyncio.wait_for(
                    self._execute_with_monitoring(execution, config),
                    timeout=timeout
                )
            else:
                final_state = await self._execute_with_monitoring(execution, config)
            
            # 更新执行记录
            execution.status = "completed"
            execution.end_time = datetime.now()
            execution.final_state = final_state
            
            logger.info(f"工作流 {execution_id} 执行成功")
            return final_state
            
        except asyncio.TimeoutError:
            logger.error(f"工作流 {execution_id} 执行超时")
            execution.status = "failed"
            execution.error = "执行超时"
            execution.end_time = datetime.now()
            
            # 尝试恢复
            if retry_on_failure and execution.retry_count < execution.max_retries:
                return await self._retry_execution(execution)
            
            raise WorkflowException(f"工作流执行超时: {execution_id}")
            
        except Exception as e:
            logger.error(f"工作流 {execution_id} 执行失败: {e}")
            execution.status = "failed"
            execution.error = str(e)
            execution.end_time = datetime.now()
            
            # 尝试恢复
            if retry_on_failure and execution.retry_count < execution.max_retries:
                return await self._retry_execution(execution)
            
            raise WorkflowException(f"工作流执行失败: {e}")
    
    async def _execute_with_monitoring(self, execution: WorkflowExecution, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        带监控的工作流执行
        
        Args:
            execution: 执行记录
            config: 配置参数
            
        Returns:
            Dict: 执行结果
        """
        try:
            step_count = 0
            final_state = None
            
            # 确保配置包含必要的参数
            if config is None:
                config = {"configurable": {"thread_id": execution.thread_id}}
            elif "configurable" not in config:
                config["configurable"] = {"thread_id": execution.thread_id}
            elif "thread_id" not in config["configurable"]:
                config["configurable"]["thread_id"] = execution.thread_id
            
            # 执行工作流并监控每个步骤
            async for state in self.workflow.graph.astream(execution.initial_state, config):
                step_count += 1
                step_info = {
                    "step": step_count,
                    "timestamp": datetime.now().isoformat(),
                    "state_keys": list(state.keys()) if isinstance(state, dict) else [],
                    "current_node": state.get("current_node") if isinstance(state, dict) else None
                }
                
                execution.steps.append(step_info)
                final_state = state
                
                # 检查是否需要干预
                await self._check_intervention_needed(execution, state, step_count)
                
                # 防止无限循环
                if step_count > 50:
                    logger.warning(f"工作流 {execution.execution_id} 步数过多，可能存在循环")
                    break
            
            if final_state is None:
                raise WorkflowException("工作流执行失败，未获得最终状态")
            
            return final_state
            
        except Exception as e:
            logger.error(f"监控执行失败: {e}")
            raise
    
    async def _check_intervention_needed(self, execution: WorkflowExecution, state: Dict[str, Any], step_count: int):
        """
        检查是否需要干预
        
        Args:
            execution: 执行记录
            state: 当前状态
            step_count: 步骤计数
        """
        try:
            # 检查状态异常
            if isinstance(state, dict):
                # 检查错误状态
                if state.get("error"):
                    logger.warning(f"检测到错误状态: {state.get('error')}")
                
                # 检查资源使用
                if step_count > 30:
                    logger.warning(f"工作流 {execution.execution_id} 执行步数较多: {step_count}")
                
                # 检查状态完整性
                required_keys = ["task_type", "locale"]
                missing_keys = [key for key in required_keys if key not in state]
                if missing_keys:
                    logger.warning(f"状态缺少必要字段: {missing_keys}")
        
        except Exception as e:
            logger.error(f"干预检查失败: {e}")
    
    async def _retry_execution(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """
        重试执行
        
        Args:
            execution: 执行记录
            
        Returns:
            Dict: 执行结果
        """
        execution.retry_count += 1
        execution.status = "retrying"
        
        logger.info(f"重试工作流 {execution.execution_id} (第 {execution.retry_count} 次)")
        
        # 等待一段时间后重试
        await asyncio.sleep(min(execution.retry_count * 2, 10))
        
        try:
            # 重新执行
            config = {"configurable": {"thread_id": execution.thread_id}}
            final_state = await self._execute_with_monitoring(execution, config)
            
            execution.status = "completed"
            execution.end_time = datetime.now()
            execution.final_state = final_state
            
            logger.info(f"工作流 {execution.execution_id} 重试成功")
            return final_state
            
        except Exception as e:
            logger.error(f"工作流 {execution.execution_id} 重试失败: {e}")
            
            if execution.retry_count < execution.max_retries:
                return await self._retry_execution(execution)
            else:
                execution.status = "failed"
                execution.error = f"重试失败: {e}"
                execution.end_time = datetime.now()
                raise WorkflowException(f"工作流重试失败: {e}")
    
    def cancel_execution(self, execution_id: str) -> bool:
        """
        取消工作流执行
        
        Args:
            execution_id: 执行ID
            
        Returns:
            bool: 是否成功取消
        """
        try:
            if execution_id in self.executions:
                execution = self.executions[execution_id]
                if execution.status == "running":
                    execution.status = "cancelled"
                    execution.end_time = datetime.now()
                    logger.info(f"工作流 {execution_id} 已取消")
                    return True
            return False
        except Exception as e:
            logger.error(f"取消工作流失败: {e}")
            return False
    
    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取执行状态
        
        Args:
            execution_id: 执行ID
            
        Returns:
            Dict: 执行状态信息
        """
        try:
            if execution_id not in self.executions:
                return None
            
            execution = self.executions[execution_id]
            
            duration = None
            if execution.end_time:
                duration = (execution.end_time - execution.start_time).total_seconds()
            else:
                duration = (datetime.now() - execution.start_time).total_seconds()
            
            return {
                "execution_id": execution.execution_id,
                "thread_id": execution.thread_id,
                "status": execution.status,
                "start_time": execution.start_time.isoformat(),
                "end_time": execution.end_time.isoformat() if execution.end_time else None,
                "duration_seconds": duration,
                "steps_count": len(execution.steps),
                "retry_count": execution.retry_count,
                "error": execution.error,
                "initial_state": execution.initial_state,
                "final_state": execution.final_state,
                "logs": [step.get("current_node", "") for step in execution.steps],
                "progress": min(len(execution.steps) * 10, 100) if execution.status == "running" else (100 if execution.status == "completed" else 0),
                "current_step": execution.steps[-1].get("current_node") if execution.steps else None
            }
        except Exception as e:
            logger.error(f"获取执行状态失败: {e}")
            return {"error": str(e)}
    
    def list_executions(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出所有执行记录
        
        Args:
            status_filter: 状态过滤器
            
        Returns:
            List[Dict]: 执行记录列表
        """
        try:
            executions = []
            for execution in self.executions.values():
                if status_filter is None or execution.status == status_filter:
                    executions.append(self.get_execution_status(execution.execution_id))
            
            return sorted(executions, key=lambda x: x.get("start_time", ""), reverse=True)
        except Exception as e:
            logger.error(f"列出执行记录失败: {e}")
            return []
    
    def cleanup_old_executions(self, max_age_hours: int = 24):
        """
        清理旧的执行记录
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            to_remove = []
            
            for execution_id, execution in self.executions.items():
                if execution.start_time < cutoff_time and execution.status in ["completed", "failed", "cancelled"]:
                    to_remove.append(execution_id)
            
            for execution_id in to_remove:
                del self.executions[execution_id]
                logger.info(f"清理旧执行记录: {execution_id}")
            
            logger.info(f"清理了 {len(to_remove)} 个旧执行记录")
        except Exception as e:
            logger.error(f"清理执行记录失败: {e}")
    
    # 错误处理器
    async def _handle_timeout_error(self, execution: WorkflowExecution, error: Exception):
        """处理超时错误"""
        logger.warning(f"处理超时错误: {execution.execution_id}")
        # 可以实现特定的超时处理逻辑
    
    async def _handle_node_failure(self, execution: WorkflowExecution, error: Exception):
        """处理节点失败"""
        logger.warning(f"处理节点失败: {execution.execution_id}")
        # 可以实现节点失败的处理逻辑
    
    async def _handle_state_corruption(self, execution: WorkflowExecution, error: Exception):
        """处理状态损坏"""
        logger.warning(f"处理状态损坏: {execution.execution_id}")
        # 可以实现状态修复逻辑
    
    async def _handle_resource_exhaustion(self, execution: WorkflowExecution, error: Exception):
        """处理资源耗尽"""
        logger.warning(f"处理资源耗尽: {execution.execution_id}")
        # 可以实现资源管理逻辑
    
    # 恢复策略
    async def _retry_strategy(self, execution: WorkflowExecution) -> bool:
        """重试策略"""
        return execution.retry_count < execution.max_retries
    
    async def _skip_node_strategy(self, execution: WorkflowExecution) -> bool:
        """跳过节点策略"""
        # 实现跳过失败节点的逻辑
        return False
    
    async def _reset_state_strategy(self, execution: WorkflowExecution) -> bool:
        """重置状态策略"""
        # 实现状态重置逻辑
        return False
    
    async def _fallback_strategy(self, execution: WorkflowExecution) -> bool:
        """降级策略"""
        # 实现降级处理逻辑
        return False


# 全局工作流管理器实例
_workflow_manager_instance = None


def get_workflow_manager() -> WorkflowManager:
    """获取工作流管理器实例（单例模式）"""
    global _workflow_manager_instance
    if _workflow_manager_instance is None:
        _workflow_manager_instance = WorkflowManager()
    return _workflow_manager_instance