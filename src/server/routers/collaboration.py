#!/usr/bin/env python3
"""
人机协作API路由
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field

from ...collaboration.plan_reviewer import get_plan_reviewer, ReviewStatus
from ...collaboration.auto_accept_manager import get_auto_accept_manager, AutoAcceptMode
from ...collaboration.feedback_processor import get_feedback_processor
from ...config.logging_config import get_logger

logger = get_logger("collaboration_api")

router = APIRouter()


# 请求和响应模型
class PlanReviewRequest(BaseModel):
    """计划审查请求"""
    plan_id: str = Field(..., description="计划ID")
    plan_data: Dict[str, Any] = Field(..., description="计划数据")
    task_type: str = Field(..., description="任务类型")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class ReviewApprovalRequest(BaseModel):
    """审查批准请求"""
    comment: Optional[str] = Field(None, description="批准意见")
    modifications: Optional[Dict[str, Any]] = Field(None, description="修改建议")


class ReviewRejectionRequest(BaseModel):
    """审查拒绝请求"""
    comment: str = Field(..., description="拒绝原因")
    feedback: Optional[str] = Field(None, description="改进建议")
    required_changes: Optional[List[str]] = Field(None, description="必需的更改")


class FeedbackRequest(BaseModel):
    """反馈请求"""
    target_id: str = Field(..., description="目标ID")
    target_type: str = Field(..., description="目标类型: plan, report, task")
    feedback: str = Field(..., description="反馈内容")
    feedback_type: str = Field("improvement", description="反馈类型: improvement, correction, addition")
    priority: str = Field("medium", description="优先级: low, medium, high")


class AutoAcceptConfigRequest(BaseModel):
    """自动接受配置请求"""
    mode: str = Field(..., description="模式: always, never, conditional")
    conditions: Optional[Dict[str, Any]] = Field(None, description="条件配置")


# 响应模型
class ReviewInfo(BaseModel):
    """审查信息"""
    review_id: str = Field(..., description="审查ID")
    plan_id: str = Field(..., description="计划ID")
    status: str = Field(..., description="审查状态")
    submitted_at: str = Field(..., description="提交时间")
    reviewed_at: Optional[str] = Field(None, description="审查时间")
    reviewer_comment: Optional[str] = Field(None, description="审查意见")
    plan_data: Dict[str, Any] = Field(..., description="计划数据")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class ReviewListResponse(BaseModel):
    """审查列表响应"""
    reviews: List[ReviewInfo] = Field(..., description="审查列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")


class FeedbackInfo(BaseModel):
    """反馈信息"""
    feedback_id: str = Field(..., description="反馈ID")
    target_id: str = Field(..., description="目标ID")
    target_type: str = Field(..., description="目标类型")
    feedback: str = Field(..., description="反馈内容")
    feedback_type: str = Field(..., description="反馈类型")
    priority: str = Field(..., description="优先级")
    status: str = Field(..., description="处理状态")
    created_at: str = Field(..., description="创建时间")
    processed_at: Optional[str] = Field(None, description="处理时间")
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")


class AutoAcceptStatus(BaseModel):
    """自动接受状态"""
    mode: str = Field(..., description="当前模式")
    conditions: Dict[str, Any] = Field(..., description="条件配置")
    statistics: Dict[str, Any] = Field(..., description="统计信息")


# 依赖注入
async def get_plan_reviewer_dep():
    """获取计划审查器依赖"""
    return get_plan_reviewer()


async def get_auto_accept_manager_dep():
    """获取自动接受管理器依赖"""
    return get_auto_accept_manager()


async def get_feedback_processor_dep():
    """获取反馈处理器依赖"""
    return get_feedback_processor()


@router.post("/reviews/submit")
async def submit_plan_for_review(
    request: PlanReviewRequest,
    plan_reviewer = Depends(get_plan_reviewer_dep)
):
    """提交计划审查"""
    try:
        # 提交审查
        review_id = plan_reviewer.submit_for_review(
            plan_id=request.plan_id,
            plan_data=request.plan_data,
            task_type=request.task_type,
            metadata=request.metadata or {}
        )
        
        logger.info(f"计划已提交审查: {request.plan_id} -> {review_id}")
        
        return {
            "message": "计划已提交审查",
            "review_id": review_id,
            "plan_id": request.plan_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"提交计划审查失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"提交计划审查失败: {str(e)}"
        )


@router.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    status: Optional[str] = Query(None, description="状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    plan_reviewer = Depends(get_plan_reviewer_dep)
):
    """列出审查"""
    try:
        # 获取审查列表
        reviews_data = plan_reviewer.list_reviews(
            status_filter=status,
            page=page,
            page_size=page_size
        )
        
        # 构建响应
        reviews = []
        for review in reviews_data["reviews"]:
            review_info = ReviewInfo(
                review_id=review["review_id"],
                plan_id=review["plan_id"],
                status=review["status"],
                submitted_at=review["submitted_at"],
                reviewed_at=review.get("reviewed_at"),
                reviewer_comment=review.get("reviewer_comment"),
                plan_data=review["plan_data"],
                metadata=review.get("metadata", {})
            )
            reviews.append(review_info)
        
        return ReviewListResponse(
            reviews=reviews,
            total=reviews_data["total"],
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"列出审查失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"列出审查失败: {str(e)}"
        )


@router.get("/reviews/{review_id}", response_model=ReviewInfo)
async def get_review(
    review_id: str,
    plan_reviewer = Depends(get_plan_reviewer_dep)
):
    """获取审查详情"""
    try:
        # 获取审查信息
        review = plan_reviewer.get_review(review_id)
        
        if not review:
            raise HTTPException(
                status_code=404,
                detail=f"未找到审查: {review_id}"
            )
        
        return ReviewInfo(
            review_id=review["review_id"],
            plan_id=review["plan_id"],
            status=review["status"],
            submitted_at=review["submitted_at"],
            reviewed_at=review.get("reviewed_at"),
            reviewer_comment=review.get("reviewer_comment"),
            plan_data=review["plan_data"],
            metadata=review.get("metadata", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取审查详情失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取审查详情失败: {str(e)}"
        )


@router.post("/reviews/{review_id}/approve")
async def approve_review(
    review_id: str,
    request: ReviewApprovalRequest,
    plan_reviewer = Depends(get_plan_reviewer_dep)
):
    """批准审查"""
    try:
        # 批准审查
        result = plan_reviewer.approve_plan(
            review_id=review_id,
            comment=request.comment,
            modifications=request.modifications
        )
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"未找到审查或审查无法批准: {review_id}"
            )
        
        logger.info(f"审查已批准: {review_id}")
        
        return {
            "message": "审查已批准",
            "review_id": review_id,
            "status": "approved"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批准审查失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"批准审查失败: {str(e)}"
        )


@router.post("/reviews/{review_id}/reject")
async def reject_review(
    review_id: str,
    request: ReviewRejectionRequest,
    plan_reviewer = Depends(get_plan_reviewer_dep)
):
    """拒绝审查"""
    try:
        # 拒绝审查
        result = plan_reviewer.reject_plan(
            review_id=review_id,
            comment=request.comment,
            feedback=request.feedback,
            required_changes=request.required_changes
        )
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"未找到审查或审查无法拒绝: {review_id}"
            )
        
        logger.info(f"审查已拒绝: {review_id}")
        
        return {
            "message": "审查已拒绝",
            "review_id": review_id,
            "status": "rejected",
            "feedback": request.feedback
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"拒绝审查失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"拒绝审查失败: {str(e)}"
        )


@router.post("/feedback/submit")
async def submit_feedback(
    request: FeedbackRequest,
    feedback_processor = Depends(get_feedback_processor_dep)
):
    """提交反馈"""
    try:
        # 提交反馈
        feedback_id = await feedback_processor.submit_feedback(
            target_id=request.target_id,
            target_type=request.target_type,
            feedback=request.feedback,
            feedback_type=request.feedback_type,
            priority=request.priority
        )
        
        logger.info(f"反馈已提交: {feedback_id}")
        
        return {
            "message": "反馈已提交",
            "feedback_id": feedback_id,
            "status": "submitted"
        }
        
    except Exception as e:
        logger.error(f"提交反馈失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"提交反馈失败: {str(e)}"
        )


@router.get("/feedback")
async def list_feedback(
    target_id: Optional[str] = Query(None, description="目标ID过滤"),
    target_type: Optional[str] = Query(None, description="目标类型过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    feedback_processor = Depends(get_feedback_processor_dep)
):
    """列出反馈"""
    try:
        # 获取反馈列表
        feedback_data = await feedback_processor.list_feedback(
            target_id=target_id,
            target_type=target_type,
            status_filter=status,
            page=page,
            page_size=page_size
        )
        
        # 构建响应
        feedback_list = []
        for feedback in feedback_data["feedback"]:
            feedback_info = FeedbackInfo(
                feedback_id=feedback["feedback_id"],
                target_id=feedback["target_id"],
                target_type=feedback["target_type"],
                feedback=feedback["feedback"],
                feedback_type=feedback["feedback_type"],
                priority=feedback["priority"],
                status=feedback["status"],
                created_at=feedback["created_at"],
                processed_at=feedback.get("processed_at"),
                result=feedback.get("result")
            )
            feedback_list.append(feedback_info)
        
        return {
            "feedback": feedback_list,
            "total": feedback_data["total"],
            "page": page,
            "page_size": page_size
        }
        
    except Exception as e:
        logger.error(f"列出反馈失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"列出反馈失败: {str(e)}"
        )


@router.get("/feedback/{feedback_id}", response_model=FeedbackInfo)
async def get_feedback(
    feedback_id: str,
    feedback_processor = Depends(get_feedback_processor_dep)
):
    """获取反馈详情"""
    try:
        # 获取反馈信息
        feedback = await feedback_processor.get_feedback(feedback_id)
        
        if not feedback:
            raise HTTPException(
                status_code=404,
                detail=f"未找到反馈: {feedback_id}"
            )
        
        return FeedbackInfo(
            feedback_id=feedback["feedback_id"],
            target_id=feedback["target_id"],
            target_type=feedback["target_type"],
            feedback=feedback["feedback"],
            feedback_type=feedback["feedback_type"],
            priority=feedback["priority"],
            status=feedback["status"],
            created_at=feedback["created_at"],
            processed_at=feedback.get("processed_at"),
            result=feedback.get("result")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取反馈详情失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取反馈详情失败: {str(e)}"
        )


@router.post("/feedback/{feedback_id}/process")
async def process_feedback(
    feedback_id: str,
    feedback_processor = Depends(get_feedback_processor_dep)
):
    """处理反馈"""
    try:
        # 处理反馈
        result = await feedback_processor.process_feedback(feedback_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"未找到反馈或反馈无法处理: {feedback_id}"
            )
        
        logger.info(f"反馈已处理: {feedback_id}")
        
        return {
            "message": "反馈已处理",
            "feedback_id": feedback_id,
            "status": "processed",
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理反馈失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"处理反馈失败: {str(e)}"
        )


@router.get("/auto-accept/status", response_model=AutoAcceptStatus)
async def get_auto_accept_status(
    auto_accept_manager = Depends(get_auto_accept_manager_dep)
):
    """获取自动接受状态"""
    try:
        # 获取状态
        status = auto_accept_manager.get_status()
        
        return AutoAcceptStatus(
            mode=status["mode"],
            conditions=status["conditions"],
            statistics=status["statistics"]
        )
        
    except Exception as e:
        logger.error(f"获取自动接受状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取自动接受状态失败: {str(e)}"
        )


@router.post("/auto-accept/configure")
async def configure_auto_accept(
    request: AutoAcceptConfigRequest,
    auto_accept_manager = Depends(get_auto_accept_manager_dep)
):
    """配置自动接受"""
    try:
        # 验证模式
        valid_modes = ["always", "never", "conditional"]
        if request.mode not in valid_modes:
            raise HTTPException(
                status_code=400,
                detail=f"无效的模式: {request.mode}。有效模式: {valid_modes}"
            )
        
        # 设置模式
        mode_enum = AutoAcceptMode(request.mode)
        auto_accept_manager.set_mode(mode_enum)
        
        # 设置条件（如果是条件模式）
        if request.mode == "conditional" and request.conditions:
            auto_accept_manager.set_conditions(request.conditions)
        
        logger.info(f"自动接受配置已更新: {request.mode}")
        
        return {
            "message": "自动接受配置已更新",
            "mode": request.mode,
            "conditions": request.conditions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置自动接受失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"配置自动接受失败: {str(e)}"
        )


@router.get("/statistics")
async def get_collaboration_statistics(
    plan_reviewer = Depends(get_plan_reviewer_dep),
    feedback_processor = Depends(get_feedback_processor_dep)
):
    """获取协作统计信息"""
    try:
        # 获取审查统计
        review_stats = plan_reviewer.get_statistics()
        
        # 获取反馈统计
        feedback_stats = await feedback_processor.get_statistics()
        
        return {
            "reviews": review_stats,
            "feedback": feedback_stats,
            "summary": {
                "total_reviews": review_stats["total"],
                "total_feedback": feedback_stats["total"],
                "approval_rate": review_stats.get("approval_rate", 0),
                "feedback_processing_rate": feedback_stats.get("processing_rate", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"获取协作统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取协作统计失败: {str(e)}"
        )