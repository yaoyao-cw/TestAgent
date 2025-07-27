#!/usr/bin/env python3
"""
智能体行为优化系统

实现注意力引导、上下文多样性注入和错误驱动的适应性学习机制
"""

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config.logging_config import get_logger
from ..models.workspace import GlobalState
from .error_recovery_manager import (ErrorContext, ErrorRecoveryManager,
                                     ErrorType)

logger = get_logger("agent_behavior_optimizer")


@dataclass
class AttentionGuide:
    """注意力引导信息"""

    task_goal: str
    current_focus: str
    priority_items: List[str]
    context_reminders: List[str]
    progress_indicators: Dict[str, Any]

    def to_prompt_section(self) -> str:
        """转换为提示词片段"""
        sections = [
            f"## 任务目标\n{self.task_goal}",
            f"## 当前焦点\n{self.current_focus}",
        ]

        if self.priority_items:
            sections.append(
                f"## 优先处理项目\n"
                + "\n".join(f"- {item}" for item in self.priority_items)
            )

        if self.context_reminders:
            sections.append(
                f"## 重要提醒\n"
                + "\n".join(f"- {reminder}" for reminder in self.context_reminders)
            )

        if self.progress_indicators:
            progress_text = "\n".join(
                f"- {key}: {value}" for key, value in self.progress_indicators.items()
            )
            sections.append(f"## 进度状态\n{progress_text}")

        return "\n\n".join(sections)


@dataclass
class ContextDiversityInjection:
    """上下文多样性注入"""

    variation_type: str
    content: str
    injection_probability: float
    effectiveness_score: float

    def should_inject(self) -> bool:
        """判断是否应该注入"""
        return random.random() < self.injection_probability


@dataclass
class BehaviorPattern:
    """行为模式"""

    pattern_id: str
    agent_id: str
    pattern_type: str  # "success", "failure", "drift"
    context_hash: str
    actions_sequence: List[str]
    outcome: str
    frequency: int
    last_seen: datetime

    def is_drift_pattern(self) -> bool:
        """判断是否为漂移模式"""
        return self.pattern_type == "drift"

    def is_repetitive(self, threshold: int = 3) -> bool:
        """判断是否为重复模式"""
        return self.frequency >= threshold


class AgentBehaviorOptimizer:
    """智能体行为优化器"""

    def __init__(
        self, global_state: GlobalState, error_recovery_manager: ErrorRecoveryManager
    ):
        self.global_state = global_state
        self.error_recovery_manager = error_recovery_manager

        # 行为模式存储
        self.behavior_patterns: Dict[str, BehaviorPattern] = {}
        self.attention_guides: Dict[str, AttentionGuide] = {}

        # 多样性注入库
        self.diversity_injections: List[ContextDiversityInjection] = []
        self._initialize_diversity_injections()

        # 配置参数
        self.drift_detection_window = 10  # 检测窗口大小
        self.repetition_threshold = 3  # 重复行为阈值
        self.attention_update_frequency = 5  # 注意力更新频率
        self.diversity_injection_rate = 0.3  # 多样性注入概率

        # 统计信息
        self.optimization_stats = {
            "attention_guides_generated": 0,
            "diversity_injections_applied": 0,
            "drift_patterns_detected": 0,
            "behavior_adaptations": 0,
        }

        logger.info("智能体行为优化器初始化完成")

    def generate_attention_guide(
        self,
        agent_id: str,
        task_id: str,
        todo_content: str,
        execution_history: List[Dict[str, Any]],
    ) -> AttentionGuide:
        """生成注意力引导"""

        # 解析todo.md内容提取任务目标
        task_goal = self._extract_task_goal(todo_content)

        # 分析当前执行状态
        current_focus = self._determine_current_focus(execution_history, todo_content)

        # 识别优先处理项目
        priority_items = self._identify_priority_items(todo_content, execution_history)

        # 生成上下文提醒
        context_reminders = self._generate_context_reminders(
            agent_id, task_id, execution_history
        )

        # 计算进度指标
        progress_indicators = self._calculate_progress_indicators(
            todo_content, execution_history
        )

        attention_guide = AttentionGuide(
            task_goal=task_goal,
            current_focus=current_focus,
            priority_items=priority_items,
            context_reminders=context_reminders,
            progress_indicators=progress_indicators,
        )

        # 存储注意力引导
        guide_key = f"{agent_id}_{task_id}"
        self.attention_guides[guide_key] = attention_guide

        self.optimization_stats["attention_guides_generated"] += 1
        logger.info(f"为智能体 {agent_id} 生成注意力引导")

        return attention_guide

    def inject_context_diversity(
        self,
        agent_id: str,
        current_context: str,
        execution_history: List[Dict[str, Any]],
    ) -> str:
        """注入上下文多样性"""

        # 检测是否需要多样性注入
        if not self._should_inject_diversity(agent_id, execution_history):
            return current_context

        # 选择合适的多样性注入
        suitable_injections = self._select_suitable_injections(
            agent_id, current_context, execution_history
        )

        if not suitable_injections:
            return current_context

        # 随机选择一个注入
        injection = random.choice(suitable_injections)

        if injection.should_inject():
            # 应用多样性注入
            enhanced_context = self._apply_diversity_injection(
                current_context, injection
            )

            self.optimization_stats["diversity_injections_applied"] += 1
            logger.info(
                f"为智能体 {agent_id} 应用多样性注入: {injection.variation_type}"
            )

            return enhanced_context

        return current_context

    def detect_behavior_drift(
        self, agent_id: str, recent_actions: List[str], context_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检测行为漂移"""

        # 生成上下文哈希
        context_hash = self._generate_context_hash(context_info)

        # 记录行为模式
        pattern_id = f"{agent_id}_{context_hash}_{hash(tuple(recent_actions))}"

        if pattern_id in self.behavior_patterns:
            # 更新现有模式
            pattern = self.behavior_patterns[pattern_id]
            pattern.frequency += 1
            pattern.last_seen = datetime.now()
        else:
            # 创建新模式
            pattern = BehaviorPattern(
                pattern_id=pattern_id,
                agent_id=agent_id,
                pattern_type="unknown",
                context_hash=context_hash,
                actions_sequence=recent_actions,
                outcome="pending",
                frequency=1,
                last_seen=datetime.now(),
            )
            self.behavior_patterns[pattern_id] = pattern

        # 分析行为模式
        drift_analysis = self._analyze_behavior_patterns(agent_id)

        if drift_analysis["drift_detected"]:
            self.optimization_stats["drift_patterns_detected"] += 1
            logger.warning(
                f"检测到智能体 {agent_id} 行为漂移: {drift_analysis['drift_type']}"
            )

        return drift_analysis

    def adapt_from_errors(
        self, agent_id: str, error_contexts: List[ErrorContext]
    ) -> Dict[str, Any]:
        """基于错误进行适应性学习"""

        if not error_contexts:
            return {"adaptations": [], "success": False}

        adaptations = []

        # 分析错误模式
        error_patterns = self._analyze_error_patterns(error_contexts)

        # 为每种错误模式生成适应策略
        for pattern in error_patterns:
            adaptation = self._generate_adaptation_strategy(agent_id, pattern)
            if adaptation:
                adaptations.append(adaptation)

        # 应用适应策略
        applied_adaptations = []
        for adaptation in adaptations:
            if self._apply_adaptation(agent_id, adaptation):
                applied_adaptations.append(adaptation)

        self.optimization_stats["behavior_adaptations"] += len(applied_adaptations)

        logger.info(f"为智能体 {agent_id} 应用了 {len(applied_adaptations)} 个适应策略")

        return {
            "adaptations": applied_adaptations,
            "success": len(applied_adaptations) > 0,
            "error_patterns_analyzed": len(error_patterns),
        }

    def optimize_agent_behavior(
        self,
        agent_id: str,
        task_id: str,
        current_context: str,
        execution_history: List[Dict[str, Any]],
        todo_content: str = "",
    ) -> Dict[str, Any]:
        """综合优化智能体行为"""

        optimization_result = {
            "attention_guide": None,
            "enhanced_context": current_context,
            "drift_analysis": None,
            "adaptations": [],
            "optimizations_applied": [],
        }

        try:
            # 1. 生成注意力引导
            if todo_content:
                attention_guide = self.generate_attention_guide(
                    agent_id, task_id, todo_content, execution_history
                )
                optimization_result["attention_guide"] = attention_guide
                optimization_result["optimizations_applied"].append("attention_guide")

            # 2. 注入上下文多样性
            enhanced_context = self.inject_context_diversity(
                agent_id, current_context, execution_history
            )
            if enhanced_context != current_context:
                optimization_result["enhanced_context"] = enhanced_context
                optimization_result["optimizations_applied"].append("context_diversity")

            # 3. 检测行为漂移
            recent_actions = self._extract_recent_actions(execution_history)
            context_info = {
                "task_id": task_id,
                "history_length": len(execution_history),
            }

            drift_analysis = self.detect_behavior_drift(
                agent_id, recent_actions, context_info
            )
            optimization_result["drift_analysis"] = drift_analysis

            # 4. 错误驱动适应
            agent_error_contexts = [
                ctx
                for ctx in self.error_recovery_manager.error_contexts.values()
                if ctx.agent_id == agent_id
            ]

            if agent_error_contexts:
                adaptation_result = self.adapt_from_errors(
                    agent_id, agent_error_contexts
                )
                optimization_result["adaptations"] = adaptation_result["adaptations"]
                if adaptation_result["success"]:
                    optimization_result["optimizations_applied"].append(
                        "error_adaptation"
                    )

            logger.info(
                f"智能体 {agent_id} 行为优化完成，应用了: {optimization_result['optimizations_applied']}"
            )

        except Exception as e:
            logger.error(f"智能体行为优化失败: {e}")
            optimization_result["error"] = str(e)

        return optimization_result

    def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        return {
            **self.optimization_stats,
            "total_behavior_patterns": len(self.behavior_patterns),
            "active_attention_guides": len(self.attention_guides),
            "diversity_injection_types": len(self.diversity_injections),
            "drift_patterns": len(
                [p for p in self.behavior_patterns.values() if p.is_drift_pattern()]
            ),
            "repetitive_patterns": len(
                [p for p in self.behavior_patterns.values() if p.is_repetitive()]
            ),
        }

    # 私有方法
    def _initialize_diversity_injections(self):
        """初始化多样性注入库"""
        self.diversity_injections = [
            ContextDiversityInjection(
                variation_type="perspective_shift",
                content="从不同角度思考这个问题：",
                injection_probability=0.3,
                effectiveness_score=0.8,
            ),
            ContextDiversityInjection(
                variation_type="alternative_approach",
                content="考虑使用替代方法：",
                injection_probability=0.25,
                effectiveness_score=0.7,
            ),
            ContextDiversityInjection(
                variation_type="edge_case_reminder",
                content="注意边界情况和异常处理：",
                injection_probability=0.2,
                effectiveness_score=0.9,
            ),
            ContextDiversityInjection(
                variation_type="quality_focus",
                content="重点关注代码质量和最佳实践：",
                injection_probability=0.15,
                effectiveness_score=0.85,
            ),
            ContextDiversityInjection(
                variation_type="user_experience",
                content="从用户体验角度考虑：",
                injection_probability=0.2,
                effectiveness_score=0.75,
            ),
        ]

    def _extract_task_goal(self, todo_content: str) -> str:
        """从todo内容提取任务目标"""
        lines = todo_content.split("\n")
        for line in lines:
            if line.strip().startswith("# ") or line.strip().startswith("## "):
                return line.strip().lstrip("#").strip()
        return "完成当前任务"

    def _determine_current_focus(
        self, execution_history: List[Dict[str, Any]], todo_content: str
    ) -> str:
        """确定当前焦点"""
        if not execution_history:
            return "开始任务执行"

        last_action = execution_history[-1]
        action_type = last_action.get("action", "unknown")

        focus_map = {
            "test_generation": "生成测试用例",
            "code_generation": "编写代码",
            "code_execution": "执行代码",
            "error_handling": "处理错误",
            "review": "代码审查",
        }

        return focus_map.get(action_type, "继续当前任务")

    def _identify_priority_items(
        self, todo_content: str, execution_history: List[Dict[str, Any]]
    ) -> List[str]:
        """识别优先处理项目"""
        priority_items = []

        # 从todo内容中提取优先项
        lines = todo_content.split("\n")
        for line in lines:
            if "[ ]" in line or "- [ ]" in line:
                item = line.strip().lstrip("- ").lstrip("[ ]").strip()
                if item:
                    priority_items.append(item)

        # 基于执行历史调整优先级
        if execution_history:
            last_errors = [
                h for h in execution_history[-5:] if h.get("status") == "error"
            ]
            if last_errors:
                priority_items.insert(0, "处理最近的错误")

        return priority_items[:5]  # 最多返回5个优先项

    def _generate_context_reminders(
        self, agent_id: str, task_id: str, execution_history: List[Dict[str, Any]]
    ) -> List[str]:
        """生成上下文提醒"""
        reminders = []

        # 基于智能体类型的提醒
        agent_reminders = {
            "tester": [
                "确保测试用例覆盖边界条件",
                "考虑正面和负面测试场景",
                "验证错误处理逻辑",
            ],
            "coder": [
                "遵循代码规范和最佳实践",
                "添加适当的注释和文档",
                "考虑代码的可维护性",
            ],
            "executor": ["注意资源使用限制", "处理执行超时情况", "记录详细的执行日志"],
        }

        if agent_id in agent_reminders:
            reminders.extend(agent_reminders[agent_id])

        # 基于执行历史的提醒
        if execution_history:
            recent_failures = [
                h for h in execution_history[-3:] if h.get("status") == "failed"
            ]
            if recent_failures:
                reminders.append("注意避免重复之前的错误")

        return reminders

    def _calculate_progress_indicators(
        self, todo_content: str, execution_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """计算进度指标"""
        indicators = {}

        # 计算任务完成度
        total_items = todo_content.count("[ ]") + todo_content.count("[x]")
        completed_items = todo_content.count("[x]")

        if total_items > 0:
            indicators["任务完成度"] = (
                f"{completed_items}/{total_items} ({completed_items/total_items*100:.1f}%)"
            )

        # 计算执行步骤
        indicators["执行步骤"] = len(execution_history)

        # 计算成功率
        if execution_history:
            successful_steps = len(
                [h for h in execution_history if h.get("status") == "success"]
            )
            success_rate = successful_steps / len(execution_history) * 100
            indicators["成功率"] = f"{success_rate:.1f}%"

        return indicators

    def _should_inject_diversity(
        self, agent_id: str, execution_history: List[Dict[str, Any]]
    ) -> bool:
        """判断是否需要多样性注入"""
        if len(execution_history) < 3:
            return False

        # 检查最近的行为是否重复
        recent_actions = [h.get("action") for h in execution_history[-3:]]
        if len(set(recent_actions)) == 1:  # 所有动作都相同
            return True

        # 检查是否有连续失败
        recent_statuses = [h.get("status") for h in execution_history[-3:]]
        if recent_statuses.count("failed") >= 2:
            return True

        # 随机注入
        return random.random() < self.diversity_injection_rate

    def _select_suitable_injections(
        self,
        agent_id: str,
        current_context: str,
        execution_history: List[Dict[str, Any]],
    ) -> List[ContextDiversityInjection]:
        """选择合适的多样性注入"""
        suitable = []

        for injection in self.diversity_injections:
            # 基于智能体类型过滤
            if agent_id == "tester" and injection.variation_type in [
                "edge_case_reminder"
            ]:
                suitable.append(injection)
            elif agent_id == "coder" and injection.variation_type in [
                "quality_focus",
                "alternative_approach",
            ]:
                suitable.append(injection)
            elif injection.variation_type in ["perspective_shift", "user_experience"]:
                suitable.append(injection)

        # 按效果评分排序
        suitable.sort(key=lambda x: x.effectiveness_score, reverse=True)
        return suitable[:3]  # 最多返回3个

    def _apply_diversity_injection(
        self, current_context: str, injection: ContextDiversityInjection
    ) -> str:
        """应用多样性注入"""
        injection_text = f"\n\n💡 {injection.content}\n"

        # 在上下文的适当位置插入
        if "## 任务目标" in current_context:
            # 在任务目标后插入
            parts = current_context.split("## 任务目标", 1)
            if len(parts) == 2:
                return parts[0] + "## 任务目标" + parts[1] + injection_text

        # 默认追加到末尾
        return current_context + injection_text

    def _generate_context_hash(self, context_info: Dict[str, Any]) -> str:
        """生成上下文哈希"""
        context_str = json.dumps(context_info, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()[:8]

    def _analyze_behavior_patterns(self, agent_id: str) -> Dict[str, Any]:
        """分析行为模式"""
        agent_patterns = [
            p for p in self.behavior_patterns.values() if p.agent_id == agent_id
        ]

        if not agent_patterns:
            return {"drift_detected": False}

        # 检查重复模式
        repetitive_patterns = [p for p in agent_patterns if p.is_repetitive()]

        # 检查时间窗口内的模式变化
        recent_time = datetime.now() - timedelta(hours=1)
        recent_patterns = [p for p in agent_patterns if p.last_seen > recent_time]

        drift_detected = len(repetitive_patterns) > 0 or len(recent_patterns) > 5

        return {
            "drift_detected": drift_detected,
            "drift_type": (
                "repetitive" if repetitive_patterns else "excessive_variation"
            ),
            "pattern_count": len(agent_patterns),
            "repetitive_count": len(repetitive_patterns),
            "recent_count": len(recent_patterns),
        }

    def _analyze_error_patterns(
        self, error_contexts: List[ErrorContext]
    ) -> List[Dict[str, Any]]:
        """分析错误模式"""
        patterns = []

        # 按错误类型分组
        error_groups = {}
        for context in error_contexts:
            error_type = context.error_type.value
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(context)

        # 为每个错误组生成模式
        for error_type, contexts in error_groups.items():
            if len(contexts) >= 2:  # 至少2个相同类型的错误才算模式
                pattern = {
                    "error_type": error_type,
                    "frequency": len(contexts),
                    "common_steps": self._find_common_execution_steps(contexts),
                    "recovery_success_rate": self._calculate_recovery_success_rate(
                        contexts
                    ),
                }
                patterns.append(pattern)

        return patterns

    def _find_common_execution_steps(self, contexts: List[ErrorContext]) -> List[str]:
        """找到共同的执行步骤"""
        if not contexts:
            return []

        # 简化实现：返回最常见的执行步骤
        steps = [ctx.execution_step for ctx in contexts]
        step_counts = {}
        for step in steps:
            step_counts[step] = step_counts.get(step, 0) + 1

        # 返回出现频率最高的步骤
        common_steps = [step for step, count in step_counts.items() if count > 1]
        return common_steps

    def _calculate_recovery_success_rate(self, contexts: List[ErrorContext]) -> float:
        """计算恢复成功率"""
        if not contexts:
            return 0.0

        successful_recoveries = 0
        total_attempts = 0

        for context in contexts:
            for attempt in context.recovery_attempts:
                total_attempts += 1
                if attempt.get("success", False):
                    successful_recoveries += 1

        return successful_recoveries / total_attempts if total_attempts > 0 else 0.0

    def _generate_adaptation_strategy(
        self, agent_id: str, error_pattern: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """生成适应策略"""
        error_type = error_pattern["error_type"]
        frequency = error_pattern["frequency"]

        # 基于错误类型和频率生成策略
        if error_type == "transient" and frequency > 3:
            return {
                "type": "increase_retry_delay",
                "description": "增加重试延迟时间",
                "parameters": {"delay_multiplier": 1.5},
            }
        elif (
            error_type == "recoverable" and error_pattern["recovery_success_rate"] < 0.5
        ):
            return {
                "type": "improve_fallback_strategy",
                "description": "改进降级策略",
                "parameters": {"fallback_priority": "high"},
            }
        elif frequency > 5:
            return {
                "type": "add_prevention_check",
                "description": "添加预防性检查",
                "parameters": {"check_frequency": "before_action"},
            }

        return None

    def _apply_adaptation(self, agent_id: str, adaptation: Dict[str, Any]) -> bool:
        """应用适应策略"""
        try:
            adaptation_type = adaptation["type"]

            # 这里应该实际应用适应策略
            # 暂时返回模拟结果
            logger.info(
                f"为智能体 {agent_id} 应用适应策略: {adaptation['description']}"
            )
            return True

        except Exception as e:
            logger.error(f"应用适应策略失败: {e}")
            return False

    def _extract_recent_actions(
        self, execution_history: List[Dict[str, Any]]
    ) -> List[str]:
        """提取最近的动作"""
        recent_count = min(self.drift_detection_window, len(execution_history))
        recent_history = execution_history[-recent_count:] if recent_count > 0 else []
        return [h.get("action", "unknown") for h in recent_history]


# 全局智能体行为优化器实例
_behavior_optimizer: Optional[AgentBehaviorOptimizer] = None


def get_behavior_optimizer(
    global_state: GlobalState = None,
    error_recovery_manager: ErrorRecoveryManager = None,
) -> AgentBehaviorOptimizer:
    """获取智能体行为优化器实例"""
    global _behavior_optimizer

    if _behavior_optimizer is None:
        if global_state is None or error_recovery_manager is None:
            raise ValueError(
                "首次调用时必须提供 global_state 和 error_recovery_manager"
            )
        _behavior_optimizer = AgentBehaviorOptimizer(
            global_state, error_recovery_manager
        )

    return _behavior_optimizer


def reset_behavior_optimizer():
    """重置智能体行为优化器（主要用于测试）"""
    global _behavior_optimizer
    _behavior_optimizer = None
