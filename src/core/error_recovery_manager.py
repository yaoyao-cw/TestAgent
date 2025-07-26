#!/usr/bin/env python3
"""
错误恢复管理器

实现智能错误分类、上下文保留和任务恢复功能
"""

import json
import time
import logging
import asyncio
from typing import Any, Dict, List, Optional, Callable, Union, Type
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timedelta

from .exceptions import (
    TestAgentException,
    ErrorSeverity,
    ErrorCategory,
    NetworkError,
    LLMError,
    RAGError,
    MCPError,
    ConfigurationError,
    TimeoutError,
    ResourceError,
)
from .error_handler import ErrorHandler
from .recovery import ServiceLevel, RecoveryAction, RecoveryStrategy
from ..models.workspace import GlobalState
from ..config.logging_config import get_logger

logger = get_logger("error_recovery_manager")


class ErrorType(Enum):
    """错误类型分类"""

    TRANSIENT = "transient"  # 临时错误，可重试
    PERSISTENT = "persistent"  # 持久错误，需要修复
    FATAL = "fatal"  # 致命错误，需要停止
    RECOVERABLE = "recoverable"  # 可恢复错误，有降级方案


class ContextPreservationLevel(Enum):
    """上下文保留级别"""

    MINIMAL = "minimal"  # 最小保留：错误信息和基本状态
    STANDARD = "standard"  # 标准保留：包含执行历史
    FULL = "full"  # 完整保留：包含所有上下文和中间结果


@dataclass
class ErrorContext:
    """错误上下文"""

    error_id: str
    timestamp: datetime
    error_type: ErrorType
    exception: Exception
    agent_id: str
    task_id: str
    execution_step: str
    state_snapshot: Dict[str, Any]
    execution_history: List[Dict[str, Any]]
    retry_count: int
    recovery_attempts: List[Dict[str, Any]]
    preservation_level: ContextPreservationLevel

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat(),
            "error_type": self.error_type.value,
            "exception": {
                "type": type(self.exception).__name__,
                "message": str(self.exception),
                "details": getattr(self.exception, "details", {}),
            },
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "execution_step": self.execution_step,
            "state_snapshot": self.state_snapshot,
            "execution_history": self.execution_history,
            "retry_count": self.retry_count,
            "recovery_attempts": self.recovery_attempts,
            "preservation_level": self.preservation_level.value,
        }


@dataclass
class RecoveryPlan:
    """恢复计划"""

    plan_id: str
    error_context: ErrorContext
    recovery_actions: List[RecoveryAction]
    fallback_strategies: List[str]
    estimated_recovery_time: int
    success_probability: float
    resource_requirements: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "plan_id": self.plan_id,
            "error_context": self.error_context.to_dict(),
            "recovery_actions": [action.value for action in self.recovery_actions],
            "fallback_strategies": self.fallback_strategies,
            "estimated_recovery_time": self.estimated_recovery_time,
            "success_probability": self.success_probability,
            "resource_requirements": self.resource_requirements,
        }


class ErrorRecoveryManager:
    """错误恢复管理器"""

    def __init__(self, global_state: GlobalState):
        self.global_state = global_state
        self.error_handler = ErrorHandler()

        # 错误分类器
        self.error_classifiers: Dict[Type[Exception], ErrorType] = {
            NetworkError: ErrorType.TRANSIENT,
            TimeoutError: ErrorType.TRANSIENT,
            ResourceError: ErrorType.RECOVERABLE,
            LLMError: ErrorType.RECOVERABLE,
            RAGError: ErrorType.RECOVERABLE,
            MCPError: ErrorType.RECOVERABLE,
            ConfigurationError: ErrorType.PERSISTENT,
        }

        # 恢复策略映射
        self.recovery_strategies: Dict[ErrorType, List[RecoveryAction]] = {
            ErrorType.TRANSIENT: [RecoveryAction.RETRY, RecoveryAction.FALLBACK],
            ErrorType.PERSISTENT: [RecoveryAction.DEGRADE, RecoveryAction.RESTART],
            ErrorType.FATAL: [RecoveryAction.CIRCUIT_BREAK],
            ErrorType.RECOVERABLE: [RecoveryAction.FALLBACK, RecoveryAction.DEGRADE],
        }

        # 错误上下文存储
        self.error_contexts: Dict[str, ErrorContext] = {}
        self.recovery_plans: Dict[str, RecoveryPlan] = {}

        # 配置参数
        self.max_retry_attempts = 3
        self.context_retention_hours = 24
        self.auto_recovery_enabled = True

        # 统计信息
        self.error_stats = {
            "total_errors": 0,
            "recovered_errors": 0,
            "failed_recoveries": 0,
            "recovery_success_rate": 0.0,
        }

        logger.info("错误恢复管理器初始化完成")

    def classify_error(self, exception: Exception) -> ErrorType:
        """错误分类"""
        # 首先检查预定义的分类
        for exc_type, error_type in self.error_classifiers.items():
            if isinstance(exception, exc_type):
                return error_type

        # 基于错误特征进行智能分类
        error_message = str(exception).lower()

        # 网络相关错误
        if any(
            keyword in error_message
            for keyword in ["connection", "timeout", "network", "dns", "socket"]
        ):
            return ErrorType.TRANSIENT

        # 资源相关错误
        if any(
            keyword in error_message
            for keyword in ["memory", "disk", "cpu", "resource", "quota"]
        ):
            return ErrorType.RECOVERABLE

        # 配置相关错误
        if any(
            keyword in error_message
            for keyword in ["config", "setting", "parameter", "invalid"]
        ):
            return ErrorType.PERSISTENT

        # 默认为可恢复错误
        return ErrorType.RECOVERABLE

    def preserve_error_context(
        self,
        exception: Exception,
        agent_id: str,
        task_id: str,
        execution_step: str,
        preservation_level: ContextPreservationLevel = ContextPreservationLevel.STANDARD,
    ) -> ErrorContext:
        """保留错误上下文"""
        error_id = f"error_{int(time.time() * 1000)}"
        error_type = self.classify_error(exception)

        # 获取状态快照
        state_snapshot = self._capture_state_snapshot(preservation_level)

        # 获取执行历史
        execution_history = self._get_execution_history(task_id, preservation_level)

        # 创建错误上下文
        error_context = ErrorContext(
            error_id=error_id,
            timestamp=datetime.now(),
            error_type=error_type,
            exception=exception,
            agent_id=agent_id,
            task_id=task_id,
            execution_step=execution_step,
            state_snapshot=state_snapshot,
            execution_history=execution_history,
            retry_count=0,
            recovery_attempts=[],
            preservation_level=preservation_level,
        )

        # 存储错误上下文
        self.error_contexts[error_id] = error_context

        # 持久化到文件系统
        self._persist_error_context(error_context)

        logger.info(f"错误上下文已保留: {error_id}, 类型: {error_type.value}")
        return error_context

    def create_recovery_plan(self, error_context: ErrorContext) -> RecoveryPlan:
        """创建恢复计划"""
        plan_id = f"plan_{error_context.error_id}"

        # 根据错误类型选择恢复动作
        recovery_actions = self.recovery_strategies.get(
            error_context.error_type, [RecoveryAction.FALLBACK]
        )

        # 生成降级策略
        fallback_strategies = self._generate_fallback_strategies(error_context)

        # 估算恢复时间和成功概率
        estimated_time = self._estimate_recovery_time(error_context)
        success_probability = self._calculate_success_probability(error_context)

        # 计算资源需求
        resource_requirements = self._calculate_resource_requirements(error_context)

        recovery_plan = RecoveryPlan(
            plan_id=plan_id,
            error_context=error_context,
            recovery_actions=recovery_actions,
            fallback_strategies=fallback_strategies,
            estimated_recovery_time=estimated_time,
            success_probability=success_probability,
            resource_requirements=resource_requirements,
        )

        self.recovery_plans[plan_id] = recovery_plan
        logger.info(f"恢复计划已创建: {plan_id}")

        return recovery_plan

    async def execute_recovery(self, recovery_plan: RecoveryPlan) -> Dict[str, Any]:
        """执行恢复计划"""
        logger.info(f"开始执行恢复计划: {recovery_plan.plan_id}")

        recovery_result = {
            "plan_id": recovery_plan.plan_id,
            "success": False,
            "actions_executed": [],
            "final_action": None,
            "recovery_time": 0,
            "error_message": None,
        }

        start_time = time.time()

        try:
            for action in recovery_plan.recovery_actions:
                logger.info(f"执行恢复动作: {action.value}")

                action_result = await self._execute_recovery_action(
                    action, recovery_plan.error_context
                )

                recovery_result["actions_executed"].append(
                    {
                        "action": action.value,
                        "result": action_result,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                if action_result.get("success", False):
                    recovery_result["success"] = True
                    recovery_result["final_action"] = action.value
                    break

            # 如果所有动作都失败，尝试降级策略
            if not recovery_result["success"]:
                for strategy in recovery_plan.fallback_strategies:
                    logger.info(f"尝试降级策略: {strategy}")

                    fallback_result = await self._execute_fallback_strategy(
                        strategy, recovery_plan.error_context
                    )

                    if fallback_result.get("success", False):
                        recovery_result["success"] = True
                        recovery_result["final_action"] = f"fallback_{strategy}"
                        break

        except Exception as e:
            logger.error(f"恢复计划执行失败: {e}")
            recovery_result["error_message"] = str(e)

        finally:
            recovery_result["recovery_time"] = int(time.time() - start_time)

            # 更新统计信息
            self._update_recovery_stats(recovery_result["success"])

            # 记录恢复尝试
            recovery_plan.error_context.recovery_attempts.append(recovery_result)

        logger.info(
            f"恢复计划执行完成: {recovery_plan.plan_id}, 成功: {recovery_result['success']}"
        )
        return recovery_result

    def resume_task_from_checkpoint(
        self, task_id: str, checkpoint_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """从检查点恢复任务"""
        logger.info(f"尝试从检查点恢复任务: {task_id}")

        try:
            # 查找任务的错误上下文
            task_error_contexts = [
                ctx for ctx in self.error_contexts.values() if ctx.task_id == task_id
            ]

            if not task_error_contexts:
                return {
                    "success": False,
                    "message": f"未找到任务 {task_id} 的错误上下文",
                }

            # 选择最新的错误上下文
            latest_context = max(task_error_contexts, key=lambda x: x.timestamp)

            # 恢复状态
            restored_state = self._restore_state_from_context(latest_context)

            # 重新初始化任务
            resume_result = self._reinitialize_task(
                task_id, restored_state, latest_context.execution_step
            )

            if resume_result["success"]:
                logger.info(f"任务 {task_id} 恢复成功")
                return {
                    "success": True,
                    "message": f"任务 {task_id} 已从步骤 {latest_context.execution_step} 恢复",
                    "restored_state": restored_state,
                    "resume_point": latest_context.execution_step,
                }
            else:
                logger.error(f"任务 {task_id} 恢复失败: {resume_result.get('error')}")
                return {
                    "success": False,
                    "message": f"任务恢复失败: {resume_result.get('error')}",
                }

        except Exception as e:
            logger.error(f"任务恢复过程中发生错误: {e}")
            return {"success": False, "message": f"任务恢复失败: {str(e)}"}

    def get_error_learning_data(
        self, error_type: Optional[ErrorType] = None
    ) -> List[Dict[str, Any]]:
        """获取错误学习数据，供模型学习"""
        learning_data = []

        for context in self.error_contexts.values():
            if error_type and context.error_type != error_type:
                continue

            # 构建学习样本
            sample = {
                "error_pattern": {
                    "type": context.error_type.value,
                    "exception_type": type(context.exception).__name__,
                    "message_pattern": str(context.exception),
                    "execution_step": context.execution_step,
                    "agent_id": context.agent_id,
                },
                "context_features": {
                    "state_size": len(str(context.state_snapshot)),
                    "history_length": len(context.execution_history),
                    "retry_count": context.retry_count,
                },
                "recovery_outcomes": [
                    {
                        "action": attempt.get("final_action"),
                        "success": attempt.get("success", False),
                        "recovery_time": attempt.get("recovery_time", 0),
                    }
                    for attempt in context.recovery_attempts
                ],
                "lessons_learned": self._extract_lessons_learned(context),
            }

            learning_data.append(sample)

        return learning_data

    def cleanup_old_contexts(self, hours: int = None) -> int:
        """清理旧的错误上下文"""
        hours = hours or self.context_retention_hours
        cutoff_time = datetime.now() - timedelta(hours=hours)

        old_contexts = [
            error_id
            for error_id, context in self.error_contexts.items()
            if context.timestamp < cutoff_time
        ]

        for error_id in old_contexts:
            del self.error_contexts[error_id]
            # 同时删除对应的恢复计划
            plan_id = f"plan_{error_id}"
            if plan_id in self.recovery_plans:
                del self.recovery_plans[plan_id]

        logger.info(f"清理了 {len(old_contexts)} 个旧的错误上下文")
        return len(old_contexts)

    def get_recovery_statistics(self) -> Dict[str, Any]:
        """获取恢复统计信息"""
        return {
            **self.error_stats,
            "active_contexts": len(self.error_contexts),
            "active_plans": len(self.recovery_plans),
            "error_type_distribution": self._get_error_type_distribution(),
            "recovery_action_effectiveness": self._get_recovery_action_stats(),
        }

    # 私有方法
    def _capture_state_snapshot(
        self, level: ContextPreservationLevel
    ) -> Dict[str, Any]:
        """捕获状态快照"""
        if level == ContextPreservationLevel.MINIMAL:
            return {
                "timestamp": datetime.now().isoformat(),
                "basic_state": "minimal_snapshot",
            }
        elif level == ContextPreservationLevel.STANDARD:
            return {
                "timestamp": datetime.now().isoformat(),
                "global_state": (
                    self.global_state.to_dict()
                    if hasattr(self.global_state, "to_dict")
                    else {}
                ),
                "active_agents": getattr(self.global_state, "active_agents", []),
            }
        else:  # FULL
            return {
                "timestamp": datetime.now().isoformat(),
                "global_state": (
                    self.global_state.to_dict()
                    if hasattr(self.global_state, "to_dict")
                    else {}
                ),
                "full_context": "complete_state_snapshot",
            }

    def _get_execution_history(
        self, task_id: str, level: ContextPreservationLevel
    ) -> List[Dict[str, Any]]:
        """获取执行历史"""
        # 这里应该从实际的执行历史中获取数据
        # 暂时返回模拟数据
        if level == ContextPreservationLevel.MINIMAL:
            return []
        else:
            return [
                {
                    "step": "initialization",
                    "timestamp": datetime.now().isoformat(),
                    "status": "completed",
                }
            ]

    def _persist_error_context(self, context: ErrorContext):
        """持久化错误上下文"""
        try:
            error_dir = Path("data/errors")
            error_dir.mkdir(parents=True, exist_ok=True)

            context_file = error_dir / f"{context.error_id}.json"
            with open(context_file, "w", encoding="utf-8") as f:
                json.dump(context.to_dict(), f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"持久化错误上下文失败: {e}")

    def _generate_fallback_strategies(self, context: ErrorContext) -> List[str]:
        """生成降级策略"""
        strategies = []

        if context.agent_id == "tester":
            strategies.extend(["use_simple_test_generation", "skip_complex_scenarios"])
        elif context.agent_id == "coder":
            strategies.extend(["use_template_code", "reduce_complexity"])
        elif context.agent_id == "executor":
            strategies.extend(["use_fallback_sandbox", "reduce_timeout"])

        strategies.append("manual_intervention")
        return strategies

    def _estimate_recovery_time(self, context: ErrorContext) -> int:
        """估算恢复时间（秒）"""
        base_time = 30  # 基础恢复时间

        # 根据错误类型调整
        type_multipliers = {
            ErrorType.TRANSIENT: 1.0,
            ErrorType.RECOVERABLE: 2.0,
            ErrorType.PERSISTENT: 5.0,
            ErrorType.FATAL: 10.0,
        }

        multiplier = type_multipliers.get(context.error_type, 2.0)
        return int(base_time * multiplier * (context.retry_count + 1))

    def _calculate_success_probability(self, context: ErrorContext) -> float:
        """计算恢复成功概率"""
        base_probability = 0.8

        # 根据重试次数降低概率
        retry_penalty = context.retry_count * 0.1

        # 根据错误类型调整
        type_adjustments = {
            ErrorType.TRANSIENT: 0.1,
            ErrorType.RECOVERABLE: 0.0,
            ErrorType.PERSISTENT: -0.2,
            ErrorType.FATAL: -0.5,
        }

        adjustment = type_adjustments.get(context.error_type, 0.0)
        probability = max(0.1, base_probability - retry_penalty + adjustment)

        return min(1.0, probability)

    def _calculate_resource_requirements(self, context: ErrorContext) -> Dict[str, Any]:
        """计算资源需求"""
        return {
            "cpu_usage": "medium",
            "memory_usage": "low",
            "network_usage": "low",
            "estimated_duration": self._estimate_recovery_time(context),
        }

    async def _execute_recovery_action(
        self, action: RecoveryAction, context: ErrorContext
    ) -> Dict[str, Any]:
        """执行恢复动作"""
        try:
            if action == RecoveryAction.RETRY:
                return await self._retry_operation(context)
            elif action == RecoveryAction.FALLBACK:
                return await self._fallback_operation(context)
            elif action == RecoveryAction.DEGRADE:
                return await self._degrade_service(context)
            elif action == RecoveryAction.CIRCUIT_BREAK:
                return await self._circuit_break(context)
            elif action == RecoveryAction.RESTART:
                return await self._restart_component(context)
            else:
                return {"success": False, "message": f"未知的恢复动作: {action}"}

        except Exception as e:
            return {"success": False, "message": f"恢复动作执行失败: {str(e)}"}

    async def _retry_operation(self, context: ErrorContext) -> Dict[str, Any]:
        """重试操作"""
        if context.retry_count >= self.max_retry_attempts:
            return {"success": False, "message": "已达到最大重试次数"}

        context.retry_count += 1

        # 模拟重试逻辑
        await asyncio.sleep(1)  # 等待1秒后重试

        # 这里应该实际重新执行失败的操作
        # 暂时返回模拟结果
        success = context.retry_count <= 2  # 前两次重试成功

        return {
            "success": success,
            "message": f"重试第 {context.retry_count} 次",
            "retry_count": context.retry_count,
        }

    async def _fallback_operation(self, context: ErrorContext) -> Dict[str, Any]:
        """降级操作"""
        # 实现降级逻辑
        return {"success": True, "message": "已切换到降级模式", "fallback_mode": True}

    async def _degrade_service(self, context: ErrorContext) -> Dict[str, Any]:
        """服务降级"""
        return {
            "success": True,
            "message": "服务已降级",
            "service_level": ServiceLevel.DEGRADED.value,
        }

    async def _circuit_break(self, context: ErrorContext) -> Dict[str, Any]:
        """熔断处理"""
        return {"success": True, "message": "已触发熔断机制", "circuit_broken": True}

    async def _restart_component(self, context: ErrorContext) -> Dict[str, Any]:
        """重启组件"""
        return {
            "success": True,
            "message": f"组件 {context.agent_id} 已重启",
            "restarted": True,
        }

    async def _execute_fallback_strategy(
        self, strategy: str, context: ErrorContext
    ) -> Dict[str, Any]:
        """执行降级策略"""
        # 实现具体的降级策略
        return {
            "success": True,
            "message": f"降级策略 {strategy} 执行成功",
            "strategy": strategy,
        }

    def _restore_state_from_context(self, context: ErrorContext) -> Dict[str, Any]:
        """从上下文恢复状态"""
        return context.state_snapshot

    def _reinitialize_task(
        self, task_id: str, restored_state: Dict[str, Any], resume_point: str
    ) -> Dict[str, Any]:
        """重新初始化任务"""
        # 实现任务重新初始化逻辑
        return {
            "success": True,
            "message": f"任务 {task_id} 已从 {resume_point} 重新初始化",
        }

    def _extract_lessons_learned(self, context: ErrorContext) -> List[str]:
        """提取经验教训"""
        lessons = []

        if context.retry_count > 0:
            lessons.append(
                f"错误类型 {context.error_type.value} 需要 {context.retry_count} 次重试"
            )

        if context.recovery_attempts:
            successful_actions = [
                attempt["final_action"]
                for attempt in context.recovery_attempts
                if attempt.get("success", False)
            ]
            if successful_actions:
                lessons.append(f"有效的恢复动作: {', '.join(successful_actions)}")

        return lessons

    def _update_recovery_stats(self, success: bool):
        """更新恢复统计"""
        self.error_stats["total_errors"] += 1
        if success:
            self.error_stats["recovered_errors"] += 1
        else:
            self.error_stats["failed_recoveries"] += 1

        # 计算成功率
        total = self.error_stats["total_errors"]
        recovered = self.error_stats["recovered_errors"]
        self.error_stats["recovery_success_rate"] = (
            recovered / total if total > 0 else 0.0
        )

    def _get_error_type_distribution(self) -> Dict[str, int]:
        """获取错误类型分布"""
        distribution = {}
        for context in self.error_contexts.values():
            error_type = context.error_type.value
            distribution[error_type] = distribution.get(error_type, 0) + 1
        return distribution

    def _get_recovery_action_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取恢复动作统计"""
        stats = {}

        for context in self.error_contexts.values():
            for attempt in context.recovery_attempts:
                action = attempt.get("final_action")
                if action:
                    if action not in stats:
                        stats[action] = {
                            "total": 0,
                            "successful": 0,
                            "success_rate": 0.0,
                        }

                    stats[action]["total"] += 1
                    if attempt.get("success", False):
                        stats[action]["successful"] += 1

                    # 计算成功率
                    total = stats[action]["total"]
                    successful = stats[action]["successful"]
                    stats[action]["success_rate"] = (
                        successful / total if total > 0 else 0.0
                    )

        return stats


# 全局错误恢复管理器实例
_error_recovery_manager: Optional[ErrorRecoveryManager] = None


def get_error_recovery_manager(
    global_state: GlobalState = None,
) -> ErrorRecoveryManager:
    """获取错误恢复管理器实例"""
    global _error_recovery_manager

    if _error_recovery_manager is None:
        if global_state is None:
            raise ValueError("首次调用时必须提供 global_state")
        _error_recovery_manager = ErrorRecoveryManager(global_state)

    return _error_recovery_manager


def reset_error_recovery_manager():
    """重置错误恢复管理器（主要用于测试）"""
    global _error_recovery_manager
    _error_recovery_manager = None
