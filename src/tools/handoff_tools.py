#!/usr/bin/env python3
"""
移交工具 - 用于节点间的任务移交
"""

import logging
from typing import Dict, Any
from ..models.state import TestAgentState

logger = logging.getLogger(__name__)


def handoff_to_planner(state: TestAgentState, reason: str = "") -> Dict[str, Any]:
    """
    移交给规划器的工具函数
    
    Args:
        state: 当前系统状态
        reason: 移交原因
        
    Returns:
        Dict: 移交信息
    """
    logger.info(f"准备移交给规划器: {reason}")
    
    return {
        "next_node": "planner",
        "reason": reason,
        "task_type": state.task_type,
        "task_topic": state.task_topic,
        "locale": state.locale
    }


def handoff_to_research_team(state: TestAgentState, reason: str = "") -> Dict[str, Any]:
    """
    移交给研究团队的工具函数
    
    Args:
        state: 当前系统状态
        reason: 移交原因
        
    Returns:
        Dict: 移交信息
    """
    logger.info(f"准备移交给研究团队: {reason}")
    
    return {
        "next_node": "research_team",
        "reason": reason,
        "current_plan": state.current_plan,
        "locale": state.locale
    }


def handoff_to_reporter(state: TestAgentState, reason: str = "") -> Dict[str, Any]:
    """
    移交给报告员的工具函数
    
    Args:
        state: 当前系统状态
        reason: 移交原因
        
    Returns:
        Dict: 移交信息
    """
    logger.info(f"准备移交给报告员: {reason}")
    
    return {
        "next_node": "reporter",
        "reason": reason,
        "observations": state.observations,
        "task_type": state.task_type,
        "locale": state.locale
    }


def handoff_to_reviewer(state: TestAgentState, reason: str = "") -> Dict[str, Any]:
    """
    移交给评审员的工具函数
    
    Args:
        state: 当前系统状态
        reason: 移交原因
        
    Returns:
        Dict: 移交信息
    """
    logger.info(f"准备移交给评审员: {reason}")
    
    return {
        "next_node": "reviewer",
        "reason": reason,
        "final_report": state.final_report,
        "task_type": state.task_type,
        "locale": state.locale
    }