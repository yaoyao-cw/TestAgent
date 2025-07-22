#!/usr/bin/env python3
"""
计划审查和反馈机制
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum

from ..models.execution import ExecutionPlan, ExecutionStep
from ..models.types import TaskType
from ..config.logging_config import get_logger
from ..exceptions import TestAgentException

logger = get_logger("plan_reviewer")


class ReviewStatus(Enum):
    """审查状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ReviewFeedback:
    """审查反馈"""
    
    def __init__(
        self,
        status: ReviewStatus,
        comments: str = "",
        suggestions: List[str] = None,
        modifications: Dict[str, Any] = None,
        reviewer: str = "human",
        timestamp: datetime = None
    ):
        self.status = status
        self.comments = comments
        self.suggestions = suggestions or []
        self.modifications = modifications or {}
        self.reviewer = reviewer
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "comments": self.comments,
            "suggestions": self.suggestions,
            "modifications": self.modifications,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewFeedback":
        """从字典创建"""
        return cls(
            status=ReviewStatus(data["status"]),
            comments=data.get("comments", ""),
            suggestions=data.get("suggestions", []),
            modifications=data.get("modifications", {}),
            reviewer=data.get("reviewer", "human"),
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class PlanReviewer:
    """计划审查器"""
    
    def __init__(self):
        self.pending_reviews: Dict[str, Dict[str, Any]] = {}
        self.review_history: Dict[str, List[ReviewFeedback]] = {}
        self.review_callbacks: Dict[str, Callable] = {}
        
        logger.info("Plan reviewer initialized")
    
    def submit_for_review(
        self,
        plan_id: str,
        plan: ExecutionPlan,
        task_type: TaskType,
        context: Dict[str, Any] = None,
        callback: Callable = None
    ) -> str:
        """提交计划进行审查
        
        Args:
            plan_id: 计划ID
            plan: 执行计划
            task_type: 任务类型
            context: 上下文信息
            callback: 审查完成回调函数
            
        Returns:
            审查ID
        """
        try:
            review_id = f"review_{plan_id}_{int(datetime.now().timestamp())}"
            
            # 存储待审查的计划
            self.pending_reviews[review_id] = {
                "plan_id": plan_id,
                "plan": plan,
                "task_type": task_type,
                "context": context or {},
                "submitted_at": datetime.now(),
                "status": ReviewStatus.PENDING
            }
            
            # 注册回调函数
            if callback:
                self.review_callbacks[review_id] = callback
            
            # 初始化审查历史
            self.review_history[review_id] = []
            
            logger.info(f"计划已提交审查: {review_id}")
            return review_id
            
        except Exception as e:
            logger.error(f"提交计划审查失败: {e}")
            raise TestAgentException(f"提交计划审查失败: {e}")
    
    def get_pending_reviews(self) -> Dict[str, Dict[str, Any]]:
        """获取待审查的计划"""
        return {
            review_id: {
                "plan_id": review_data["plan_id"],
                "task_type": review_data["task_type"].value,
                "submitted_at": review_data["submitted_at"].isoformat(),
                "status": review_data["status"].value,
                "plan_summary": self._get_plan_summary(review_data["plan"])
            }
            for review_id, review_data in self.pending_reviews.items()
            if review_data["status"] == ReviewStatus.PENDING
        }
    
    def get_review_details(self, review_id: str) -> Optional[Dict[str, Any]]:
        """获取审查详情
        
        Args:
            review_id: 审查ID
            
        Returns:
            审查详情或None
        """
        if review_id not in self.pending_reviews:
            return None
        
        review_data = self.pending_reviews[review_id]
        
        return {
            "review_id": review_id,
            "plan_id": review_data["plan_id"],
            "task_type": review_data["task_type"].value,
            "submitted_at": review_data["submitted_at"].isoformat(),
            "status": review_data["status"].value,
            "context": review_data["context"],
            "plan": self._serialize_plan(review_data["plan"]),
            "review_history": [feedback.to_dict() for feedback in self.review_history.get(review_id, [])]
        }
    
    def submit_feedback(
        self,
        review_id: str,
        feedback: ReviewFeedback
    ) -> bool:
        """提交审查反馈
        
        Args:
            review_id: 审查ID
            feedback: 审查反馈
            
        Returns:
            是否成功
        """
        try:
            if review_id not in self.pending_reviews:
                logger.error(f"审查不存在: {review_id}")
                return False
            
            # 记录反馈
            self.review_history[review_id].append(feedback)
            
            # 更新审查状态
            self.pending_reviews[review_id]["status"] = feedback.status
            
            # 如果有修改，应用修改
            if feedback.status == ReviewStatus.MODIFIED and feedback.modifications:
                self._apply_modifications(review_id, feedback.modifications)
            
            # 调用回调函数
            if review_id in self.review_callbacks:
                try:
                    self.review_callbacks[review_id](review_id, feedback)
                except Exception as e:
                    logger.error(f"执行审查回调失败: {e}")
            
            logger.info(f"审查反馈已提交: {review_id}, 状态: {feedback.status.value}")
            return True
            
        except Exception as e:
            logger.error(f"提交审查反馈失败: {e}")
            return False
    
    def approve_plan(self, review_id: str, comments: str = "") -> bool:
        """批准计划
        
        Args:
            review_id: 审查ID
            comments: 批准意见
            
        Returns:
            是否成功
        """
        feedback = ReviewFeedback(
            status=ReviewStatus.APPROVED,
            comments=comments
        )
        return self.submit_feedback(review_id, feedback)
    
    def reject_plan(self, review_id: str, comments: str, suggestions: List[str] = None) -> bool:
        """拒绝计划
        
        Args:
            review_id: 审查ID
            comments: 拒绝原因
            suggestions: 改进建议
            
        Returns:
            是否成功
        """
        feedback = ReviewFeedback(
            status=ReviewStatus.REJECTED,
            comments=comments,
            suggestions=suggestions or []
        )
        return self.submit_feedback(review_id, feedback)
    
    def modify_plan(
        self,
        review_id: str,
        modifications: Dict[str, Any],
        comments: str = ""
    ) -> bool:
        """修改计划
        
        Args:
            review_id: 审查ID
            modifications: 修改内容
            comments: 修改说明
            
        Returns:
            是否成功
        """
        feedback = ReviewFeedback(
            status=ReviewStatus.MODIFIED,
            comments=comments,
            modifications=modifications
        )
        return self.submit_feedback(review_id, feedback)
    
    def get_approved_plan(self, review_id: str) -> Optional[ExecutionPlan]:
        """获取已批准的计划
        
        Args:
            review_id: 审查ID
            
        Returns:
            执行计划或None
        """
        if review_id not in self.pending_reviews:
            return None
        
        review_data = self.pending_reviews[review_id]
        if review_data["status"] != ReviewStatus.APPROVED:
            return None
        
        return review_data["plan"]
    
    def _get_plan_summary(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """获取计划摘要"""
        return {
            "total_steps": len(plan.steps),
            "step_types": list(set(str(step.step_type) for step in plan.steps)),
            "title": plan.title,
            "thought": plan.thought[:200] + "..." if len(plan.thought) > 200 else plan.thought
        }
    
    def _serialize_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """序列化计划"""
        return {
            "title": plan.title,
            "thought": plan.thought,
            "task_type": plan.task_type.value,
            "locale": plan.locale,
            "steps": [
                {
                    "title": step.title,
                    "step_type": step.step_type.value,
                    "description": step.description,
                    "execution_res": step.execution_res
                }
                for step in plan.steps
            ],
            "has_enough_context": plan.has_enough_context
        }
    
    def _apply_modifications(self, review_id: str, modifications: Dict[str, Any]):
        """应用修改"""
        try:
            review_data = self.pending_reviews[review_id]
            plan = review_data["plan"]
            
            # 应用计划级别的修改
            if "title" in modifications:
                plan.title = modifications["title"]
            
            if "thought" in modifications:
                plan.thought = modifications["thought"]
            
            # 应用步骤级别的修改
            if "steps" in modifications:
                step_modifications = modifications["steps"]
                for step_id, step_changes in step_modifications.items():
                    # 查找对应的步骤
                    for step in plan.steps:
                        if step.id == step_id:
                            # 应用步骤修改
                            for field, value in step_changes.items():
                                if hasattr(step, field):
                                    setattr(step, field, value)
                            break
            
            logger.info(f"已应用计划修改: {review_id}")
            
        except Exception as e:
            logger.error(f"应用计划修改失败: {e}")
    
    def cleanup_completed_reviews(self, max_age_hours: int = 24):
        """清理已完成的审查
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        try:
            cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
            
            completed_reviews = []
            for review_id, review_data in self.pending_reviews.items():
                if (review_data["status"] in [ReviewStatus.APPROVED, ReviewStatus.REJECTED] and
                    review_data["submitted_at"].timestamp() < cutoff_time):
                    completed_reviews.append(review_id)
            
            # 清理已完成的审查
            for review_id in completed_reviews:
                del self.pending_reviews[review_id]
                if review_id in self.review_history:
                    del self.review_history[review_id]
                if review_id in self.review_callbacks:
                    del self.review_callbacks[review_id]
            
            logger.info(f"已清理 {len(completed_reviews)} 个已完成的审查")
            
        except Exception as e:
            logger.error(f"清理已完成审查失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_reviews = len(self.pending_reviews)
        pending_count = sum(1 for r in self.pending_reviews.values() if r["status"] == ReviewStatus.PENDING)
        approved_count = sum(1 for r in self.pending_reviews.values() if r["status"] == ReviewStatus.APPROVED)
        rejected_count = sum(1 for r in self.pending_reviews.values() if r["status"] == ReviewStatus.REJECTED)
        modified_count = sum(1 for r in self.pending_reviews.values() if r["status"] == ReviewStatus.MODIFIED)
        
        return {
            "total_reviews": total_reviews,
            "pending": pending_count,
            "approved": approved_count,
            "rejected": rejected_count,
            "modified": modified_count,
            "approval_rate": approved_count / total_reviews if total_reviews > 0 else 0
        }