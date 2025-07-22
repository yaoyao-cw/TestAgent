#!/usr/bin/env python3
"""
自动接受模式管理器
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from enum import Enum

from ..config.logging_config import get_logger
from ..exceptions import TestAgentException

logger = get_logger("auto_accept_manager")


class AutoAcceptMode(Enum):
    """自动接受模式"""
    DISABLED = "disabled"  # 禁用自动接受
    ALWAYS = "always"      # 总是自动接受
    CONDITIONAL = "conditional"  # 条件自动接受
    TIME_BASED = "time_based"    # 基于时间的自动接受


class AutoAcceptCondition:
    """自动接受条件"""
    
    def __init__(
        self,
        name: str,
        condition_type: str,
        parameters: Dict[str, Any],
        enabled: bool = True
    ):
        self.name = name
        self.condition_type = condition_type
        self.parameters = parameters
        self.enabled = enabled
        self.created_at = datetime.now()
        self.last_used = None
        self.usage_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "condition_type": self.condition_type,
            "parameters": self.parameters,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "usage_count": self.usage_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutoAcceptCondition":
        """从字典创建"""
        condition = cls(
            name=data["name"],
            condition_type=data["condition_type"],
            parameters=data["parameters"],
            enabled=data.get("enabled", True)
        )
        condition.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("last_used"):
            condition.last_used = datetime.fromisoformat(data["last_used"])
        condition.usage_count = data.get("usage_count", 0)
        return condition


class AutoAcceptManager:
    """自动接受管理器"""
    
    def __init__(self):
        self.mode = AutoAcceptMode.DISABLED
        self.conditions: List[AutoAcceptCondition] = []
        self.time_settings = {
            "auto_accept_after_minutes": 30,  # 30分钟后自动接受
            "working_hours_only": True,       # 仅在工作时间
            "working_hours": {
                "start": "09:00",
                "end": "18:00"
            },
            "working_days": [0, 1, 2, 3, 4]  # 周一到周五
        }
        self.global_settings = {
            "max_auto_accepts_per_day": 10,
            "require_confidence_threshold": 0.8,
            "blacklist_task_types": [],
            "whitelist_users": []
        }
        self.statistics = {
            "total_auto_accepts": 0,
            "auto_accepts_today": 0,
            "last_reset_date": datetime.now().date(),
            "success_rate": 0.0
        }
        
        logger.info("Auto accept manager initialized")
    
    def set_mode(self, mode: AutoAcceptMode, settings: Dict[str, Any] = None):
        """设置自动接受模式
        
        Args:
            mode: 自动接受模式
            settings: 模式相关设置
        """
        try:
            self.mode = mode
            
            if settings:
                if mode == AutoAcceptMode.TIME_BASED:
                    self.time_settings.update(settings)
                elif mode == AutoAcceptMode.CONDITIONAL:
                    # 更新条件设置
                    pass
            
            logger.info(f"自动接受模式已设置为: {mode.value}")
            
        except Exception as e:
            logger.error(f"设置自动接受模式失败: {e}")
            raise TestAgentException(f"设置自动接受模式失败: {e}")
    
    def add_condition(self, condition: AutoAcceptCondition):
        """添加自动接受条件
        
        Args:
            condition: 自动接受条件
        """
        try:
            # 检查是否已存在同名条件
            existing_names = [c.name for c in self.conditions]
            if condition.name in existing_names:
                raise ValueError(f"条件名称已存在: {condition.name}")
            
            self.conditions.append(condition)
            logger.info(f"已添加自动接受条件: {condition.name}")
            
        except Exception as e:
            logger.error(f"添加自动接受条件失败: {e}")
            raise TestAgentException(f"添加自动接受条件失败: {e}")
    
    def remove_condition(self, condition_name: str) -> bool:
        """移除自动接受条件
        
        Args:
            condition_name: 条件名称
            
        Returns:
            是否成功移除
        """
        try:
            for i, condition in enumerate(self.conditions):
                if condition.name == condition_name:
                    del self.conditions[i]
                    logger.info(f"已移除自动接受条件: {condition_name}")
                    return True
            
            logger.warning(f"未找到自动接受条件: {condition_name}")
            return False
            
        except Exception as e:
            logger.error(f"移除自动接受条件失败: {e}")
            return False
    
    def should_auto_accept(
        self,
        review_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Tuple[bool, str]:
        """判断是否应该自动接受
        
        Args:
            review_data: 审查数据
            context: 上下文信息
            
        Returns:
            (是否自动接受, 原因)
        """
        try:
            # 检查全局限制
            if not self._check_global_limits(review_data):
                return False, "超出全局限制"
            
            # 根据模式判断
            if self.mode == AutoAcceptMode.DISABLED:
                return False, "自动接受已禁用"
            
            elif self.mode == AutoAcceptMode.ALWAYS:
                return True, "总是自动接受模式"
            
            elif self.mode == AutoAcceptMode.TIME_BASED:
                return self._check_time_based_acceptance(review_data)
            
            elif self.mode == AutoAcceptMode.CONDITIONAL:
                return self._check_conditional_acceptance(review_data, context)
            
            return False, "未知模式"
            
        except Exception as e:
            logger.error(f"判断自动接受失败: {e}")
            return False, f"判断失败: {e}"
    
    def _check_global_limits(self, review_data: Dict[str, Any]) -> bool:
        """检查全局限制"""
        # 重置每日计数
        self._reset_daily_stats_if_needed()
        
        # 检查每日限制
        if self.statistics["auto_accepts_today"] >= self.global_settings["max_auto_accepts_per_day"]:
            return False
        
        # 检查任务类型黑名单
        task_type = review_data.get("task_type", "")
        if task_type in self.global_settings["blacklist_task_types"]:
            return False
        
        # 检查置信度阈值
        confidence = review_data.get("confidence", 0.0)
        if confidence < self.global_settings["require_confidence_threshold"]:
            return False
        
        return True
    
    def _check_time_based_acceptance(
        self,
        review_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """检查基于时间的自动接受"""
        now = datetime.now()
        submitted_at = datetime.fromisoformat(review_data.get("submitted_at", now.isoformat()))
        
        # 检查是否超过等待时间
        wait_minutes = self.time_settings["auto_accept_after_minutes"]
        if (now - submitted_at).total_seconds() < wait_minutes * 60:
            return False, f"等待时间不足 {wait_minutes} 分钟"
        
        # 检查工作时间
        if self.time_settings["working_hours_only"]:
            if not self._is_working_time(now):
                return False, "非工作时间"
        
        return True, f"等待 {wait_minutes} 分钟后自动接受"
    
    def _check_conditional_acceptance(
        self,
        review_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Tuple[bool, str]:
        """检查条件自动接受"""
        if not self.conditions:
            return False, "未设置自动接受条件"
        
        # 检查所有启用的条件
        matched_conditions = []
        for condition in self.conditions:
            if not condition.enabled:
                continue
            
            if self._evaluate_condition(condition, review_data, context):
                matched_conditions.append(condition.name)
                condition.last_used = datetime.now()
                condition.usage_count += 1
        
        if matched_conditions:
            return True, f"满足条件: {', '.join(matched_conditions)}"
        
        return False, "不满足任何自动接受条件"
    
    def _evaluate_condition(
        self,
        condition: AutoAcceptCondition,
        review_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> bool:
        """评估单个条件"""
        try:
            condition_type = condition.condition_type
            parameters = condition.parameters
            
            if condition_type == "task_type":
                # 任务类型条件
                allowed_types = parameters.get("allowed_types", [])
                task_type = review_data.get("task_type", "")
                return task_type in allowed_types
            
            elif condition_type == "confidence_threshold":
                # 置信度阈值条件
                threshold = parameters.get("threshold", 0.8)
                confidence = review_data.get("confidence", 0.0)
                return confidence >= threshold
            
            elif condition_type == "plan_complexity":
                # 计划复杂度条件
                max_steps = parameters.get("max_steps", 10)
                step_count = len(review_data.get("plan", {}).get("steps", []))
                return step_count <= max_steps
            
            elif condition_type == "user_whitelist":
                # 用户白名单条件
                allowed_users = parameters.get("allowed_users", [])
                user = context.get("user", "") if context else ""
                return user in allowed_users
            
            elif condition_type == "time_window":
                # 时间窗口条件
                start_time = parameters.get("start_time", "00:00")
                end_time = parameters.get("end_time", "23:59")
                current_time = datetime.now().strftime("%H:%M")
                return start_time <= current_time <= end_time
            
            elif condition_type == "custom":
                # 自定义条件（可以扩展）
                return self._evaluate_custom_condition(parameters, review_data, context)
            
            return False
            
        except Exception as e:
            logger.error(f"评估条件失败 {condition.name}: {e}")
            return False
    
    def _evaluate_custom_condition(
        self,
        parameters: Dict[str, Any],
        review_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> bool:
        """评估自定义条件"""
        # 这里可以实现更复杂的自定义条件逻辑
        # 例如：基于历史数据、机器学习模型等
        return False
    
    def _is_working_time(self, dt: datetime) -> bool:
        """检查是否为工作时间"""
        # 检查工作日
        if dt.weekday() not in self.time_settings["working_days"]:
            return False
        
        # 检查工作时间
        current_time = dt.strftime("%H:%M")
        start_time = self.time_settings["working_hours"]["start"]
        end_time = self.time_settings["working_hours"]["end"]
        
        return start_time <= current_time <= end_time
    
    def _reset_daily_stats_if_needed(self):
        """如果需要，重置每日统计"""
        today = datetime.now().date()
        if self.statistics["last_reset_date"] != today:
            self.statistics["auto_accepts_today"] = 0
            self.statistics["last_reset_date"] = today
    
    def record_auto_accept(self, success: bool = True):
        """记录自动接受"""
        self._reset_daily_stats_if_needed()
        
        self.statistics["total_auto_accepts"] += 1
        self.statistics["auto_accepts_today"] += 1
        
        # 更新成功率（简化计算）
        if success:
            self.statistics["success_rate"] = min(1.0, self.statistics["success_rate"] + 0.01)
        else:
            self.statistics["success_rate"] = max(0.0, self.statistics["success_rate"] - 0.05)
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置"""
        return {
            "mode": self.mode.value,
            "time_settings": self.time_settings,
            "global_settings": self.global_settings,
            "conditions": [condition.to_dict() for condition in self.conditions],
            "statistics": self.statistics
        }
    
    def update_settings(self, settings: Dict[str, Any]):
        """更新设置"""
        try:
            if "mode" in settings:
                self.mode = AutoAcceptMode(settings["mode"])
            
            if "time_settings" in settings:
                self.time_settings.update(settings["time_settings"])
            
            if "global_settings" in settings:
                self.global_settings.update(settings["global_settings"])
            
            logger.info("自动接受设置已更新")
            
        except Exception as e:
            logger.error(f"更新自动接受设置失败: {e}")
            raise TestAgentException(f"更新自动接受设置失败: {e}")
    
    def create_preset_conditions(self) -> List[AutoAcceptCondition]:
        """创建预设条件"""
        presets = [
            AutoAcceptCondition(
                name="高置信度自动接受",
                condition_type="confidence_threshold",
                parameters={"threshold": 0.9},
                enabled=False
            ),
            AutoAcceptCondition(
                name="简单任务自动接受",
                condition_type="plan_complexity",
                parameters={"max_steps": 5},
                enabled=False
            ),
            AutoAcceptCondition(
                name="测试用例生成自动接受",
                condition_type="task_type",
                parameters={"allowed_types": ["test_case_generation"]},
                enabled=False
            ),
            AutoAcceptCondition(
                name="工作时间自动接受",
                condition_type="time_window",
                parameters={"start_time": "09:00", "end_time": "17:00"},
                enabled=False
            )
        ]
        
        return presets
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        self._reset_daily_stats_if_needed()
        
        return {
            "mode": self.mode.value,
            "total_conditions": len(self.conditions),
            "enabled_conditions": len([c for c in self.conditions if c.enabled]),
            "statistics": self.statistics,
            "recent_usage": [
                {
                    "name": c.name,
                    "usage_count": c.usage_count,
                    "last_used": c.last_used.isoformat() if c.last_used else None
                }
                for c in sorted(self.conditions, key=lambda x: x.usage_count, reverse=True)[:5]
            ]
        }