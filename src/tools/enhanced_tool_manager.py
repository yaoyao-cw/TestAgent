#!/usr/bin/env python3
"""
增强工具管理器
集成工具状态机和约束解码器，提供上下文感知的工具管理
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass

from .tool_manager import ToolManager, ToolConfig
from .state_machine import (
    ToolStateMachine, AgentState, ToolCallMode, 
    get_tool_state_machine, ToolDefinition
)
from .constraint_decoder import ConstraintDecoder, get_constraint_decoder
from ..config.logging_config import get_logger
from ..exceptions import ToolException

logger = get_logger("enhanced_tool_manager")


@dataclass
class ToolExecutionContext:
    """工具执行上下文"""
    agent_name: str
    agent_state: AgentState
    call_mode: ToolCallMode
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    context_data: Dict[str, Any] = None


class EnhancedToolManager(ToolManager):
    """增强工具管理器
    
    在原有工具管理器基础上集成：
    1. 工具状态机管理
    2. 约束解码机制
    3. 上下文感知的工具可用性控制
    4. 响应预填充支持
    """
    
    def __init__(self):
        """初始化增强工具管理器"""
        super().__init__()
        
        # 集成工具状态机和约束解码器
        self.state_machine: ToolStateMachine = get_tool_state_machine()
        self.constraint_decoder: ConstraintDecoder = get_constraint_decoder()
        
        # 执行上下文
        self.current_context: Optional[ToolExecutionContext] = None
        
        # 工具执行历史
        self.execution_history: List[Dict[str, Any]] = []
        
        # 性能指标
        self.performance_metrics: Dict[str, Any] = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "constraint_violations": 0,
            "cache_hits": 0,
            "average_execution_time": 0.0
        }
        
        logger.info("增强工具管理器初始化完成")
    
    async def initialize_tools(self):
        """初始化工具（重写父类方法）"""
        await super().initialize_tools()
        
        # 同步工具定义到状态机
        await self._sync_tools_to_state_machine()
        
        logger.info("增强工具管理器工具初始化完成")
    
    async def _sync_tools_to_state_machine(self):
        """同步工具定义到状态机"""
        try:
            # 获取所有已注册的工具
            tool_list = self.list_tools(enabled_only=False)
            
            # 更新状态机中的工具定义
            for tool_name, tool_info in tool_list.items():
                # 确定工具类别
                category = self._determine_tool_category(tool_name)
                
                # 创建工具定义
                tool_def = ToolDefinition(
                    name=tool_name,
                    category=category,
                    description=tool_info.get("description", ""),
                    parameters=self._get_tool_parameters(tool_name),
                    enabled=tool_info.get("enabled", True),
                    priority=self._get_tool_priority(tool_name, category)
                )
                
                # 更新状态机
                self.state_machine.tool_definitions[tool_name] = tool_def
                self.state_machine.all_tools.add(tool_name)
            
            logger.info(f"同步了 {len(tool_list)} 个工具到状态机")
            
        except Exception as e:
            logger.error(f"同步工具到状态机失败: {e}")
            raise ToolException(f"工具同步失败: {e}")
    
    def _determine_tool_category(self, tool_name: str) -> str:
        """确定工具类别
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具类别
        """
        # 根据工具名称前缀确定类别
        for category_prefix in self.state_machine.TOOL_CATEGORIES.keys():
            if tool_name.startswith(category_prefix):
                return category_prefix.rstrip('_')
        
        # 根据工具名称模式匹配
        if 'file' in tool_name.lower():
            return 'file'
        elif 'knowledge' in tool_name.lower() or 'search' in tool_name.lower():
            return 'knowledge'
        elif 'sandbox' in tool_name.lower() or 'execute' in tool_name.lower():
            return 'sandbox'
        elif 'browser' in tool_name.lower() or 'web' in tool_name.lower():
            return 'browser'
        elif 'shell' in tool_name.lower():
            return 'shell'
        elif 'mcp' in tool_name.lower():
            return 'mcp'
        elif 'workflow' in tool_name.lower():
            return 'workflow'
        else:
            return 'general'
    
    def _get_tool_parameters(self, tool_name: str) -> Dict[str, Any]:
        """获取工具参数定义
        
        Args:
            tool_name: 工具名称
            
        Returns:
            参数定义
        """
        # 尝试从实际工具获取参数定义
        tool = self.get_tool(tool_name)
        if tool and hasattr(tool, 'get_parameters'):
            try:
                return tool.get_parameters()
            except Exception as e:
                logger.warning(f"获取工具 {tool_name} 参数失败: {e}")
        
        # 返回默认参数定义
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": f"{tool_name}的输入参数"
                }
            },
            "required": ["input"]
        }
    
    def _get_tool_priority(self, tool_name: str, category: str) -> int:
        """获取工具优先级
        
        Args:
            tool_name: 工具名称
            category: 工具类别
            
        Returns:
            优先级（数字越大优先级越高）
        """
        # 基于类别的基础优先级
        category_priority = {
            'file': 10,
            'knowledge': 8,
            'sandbox': 9,
            'browser': 6,
            'shell': 7,
            'mcp': 5,
            'workflow': 8,
            'general': 3
        }
        
        base_priority = category_priority.get(category, 3)
        
        # 基于工具名称的调整
        if 'execute' in tool_name:
            base_priority += 2
        elif 'search' in tool_name:
            base_priority += 1
        elif 'list' in tool_name:
            base_priority -= 1
        
        return base_priority
    
    def set_execution_context(self, context: ToolExecutionContext):
        """设置工具执行上下文
        
        Args:
            context: 执行上下文
        """
        self.current_context = context
        
        # 更新状态机状态
        self.state_machine.set_agent_state(context.agent_name, context.agent_state)
        self.state_machine.set_call_mode(context.call_mode)
        
        logger.info(f"设置执行上下文: {context.agent_name} - {context.agent_state.value} - {context.call_mode.value}")
    
    def get_available_tools_for_context(self, 
                                      context: Optional[ToolExecutionContext] = None) -> List[str]:
        """获取当前上下文可用的工具
        
        Args:
            context: 执行上下文（可选，默认使用当前上下文）
            
        Returns:
            可用工具列表
        """
        ctx = context or self.current_context
        if not ctx:
            # 没有上下文时返回所有启用的工具
            return [name for name, tool_def in self.state_machine.tool_definitions.items() 
                   if tool_def.enabled]
        
        # 使用状态机获取可用工具
        return self.state_machine.get_available_tools(ctx.agent_state, ctx.call_mode)
    
    def get_constraint_config_for_llm(self, 
                                    context: Optional[ToolExecutionContext] = None) -> Dict[str, Any]:
        """获取LLM约束解码配置
        
        Args:
            context: 执行上下文
            
        Returns:
            约束解码配置
        """
        ctx = context or self.current_context
        if not ctx:
            return {"mode": "auto", "available_tools": [], "tool_schemas": []}
        
        return self.state_machine.get_constraint_config(ctx.agent_state, ctx.call_mode)
    
    def get_response_prefill(self, 
                           context: Optional[ToolExecutionContext] = None) -> Optional[str]:
        """获取响应预填充内容
        
        Args:
            context: 执行上下文
            
        Returns:
            预填充内容
        """
        ctx = context or self.current_context
        if not ctx:
            return None
        
        return self.constraint_decoder.get_response_prefill(ctx.agent_state, ctx.call_mode)
    
    async def execute_tool_with_constraints(self,
                                          tool_name: str,
                                          method_name: str,
                                          *args,
                                          context: Optional[ToolExecutionContext] = None,
                                          **kwargs) -> Dict[str, Any]:
        """在约束条件下执行工具
        
        Args:
            tool_name: 工具名称
            method_name: 方法名称
            *args: 位置参数
            context: 执行上下文
            **kwargs: 关键字参数
            
        Returns:
            执行结果
        """
        start_time = datetime.now()
        ctx = context or self.current_context
        
        try:
            # 更新性能指标
            self.performance_metrics["total_calls"] += 1
            
            # 检查工具可用性
            if ctx:
                available_tools = self.get_available_tools_for_context(ctx)
                if tool_name not in available_tools:
                    self.performance_metrics["constraint_violations"] += 1
                    return {
                        "success": False,
                        "error": f"工具 {tool_name} 在当前上下文下不可用",
                        "constraint_violation": True,
                        "available_tools": available_tools,
                        "context": {
                            "agent": ctx.agent_name,
                            "state": ctx.agent_state.value,
                            "mode": ctx.call_mode.value
                        }
                    }
            
            # 执行工具
            result = await super().execute_tool(tool_name, method_name, *args, **kwargs)
            
            # 记录执行历史
            execution_record = {
                "timestamp": start_time.isoformat(),
                "tool_name": tool_name,
                "method_name": method_name,
                "success": result.get("success", False),
                "execution_time": result.get("execution_time", 0),
                "context": ctx.__dict__ if ctx else None
            }
            self.execution_history.append(execution_record)
            
            # 更新性能指标
            if result.get("success", False):
                self.performance_metrics["successful_calls"] += 1
            else:
                self.performance_metrics["failed_calls"] += 1
            
            # 更新平均执行时间
            total_time = (self.performance_metrics["average_execution_time"] * 
                         (self.performance_metrics["total_calls"] - 1) + 
                         result.get("execution_time", 0))
            self.performance_metrics["average_execution_time"] = total_time / self.performance_metrics["total_calls"]
            
            return result
            
        except Exception as e:
            self.performance_metrics["failed_calls"] += 1
            logger.error(f"约束工具执行失败: {tool_name}.{method_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "method_name": method_name,
                "execution_time": (datetime.now() - start_time).total_seconds()
            }
    
    def validate_tool_call(self, tool_call: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证工具调用是否符合约束
        
        Args:
            tool_call: 工具调用
            
        Returns:
            (是否有效, 错误信息)
        """
        if not self.current_context:
            return True, None  # 没有上下文时不进行约束验证
        
        return self.constraint_decoder.validate_tool_call(
            tool_call,
            self.current_context.agent_state,
            self.current_context.call_mode
        )
    
    def get_tool_suggestions(self, 
                           context: Optional[ToolExecutionContext] = None) -> List[Dict[str, Any]]:
        """获取工具调用建议
        
        Args:
            context: 执行上下文
            
        Returns:
            工具建议列表
        """
        ctx = context or self.current_context
        if not ctx:
            return []
        
        return self.constraint_decoder.get_tool_call_suggestions(
            ctx.agent_state,
            ctx.call_mode,
            ctx.context_data.get("context") if ctx.context_data else None
        )
    
    def get_tools_by_category(self, 
                            category: str,
                            context: Optional[ToolExecutionContext] = None) -> List[str]:
        """根据类别获取工具（考虑上下文约束）
        
        Args:
            category: 工具类别
            context: 执行上下文
            
        Returns:
            该类别的可用工具列表
        """
        # 获取类别中的所有工具
        category_tools = self.state_machine.get_tools_by_category(category)
        
        # 如果有上下文，进一步过滤
        if context or self.current_context:
            ctx = context or self.current_context
            available_tools = self.get_available_tools_for_context(ctx)
            category_tools = [tool for tool in category_tools if tool in available_tools]
        
        return category_tools
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查（重写父类方法）"""
        base_health = await super().health_check()
        
        # 添加状态机和约束解码器的健康信息
        enhanced_health = base_health.copy()
        enhanced_health.update({
            "state_machine": self.state_machine.get_state_info(),
            "constraint_decoder": self.constraint_decoder.get_statistics(),
            "performance_metrics": self.performance_metrics.copy(),
            "execution_history_size": len(self.execution_history),
            "current_context": self.current_context.__dict__ if self.current_context else None
        })
        
        return enhanced_health
    
    def clear_execution_history(self, keep_last: int = 100):
        """清除执行历史
        
        Args:
            keep_last: 保留最近的记录数量
        """
        if len(self.execution_history) > keep_last:
            self.execution_history = self.execution_history[-keep_last:]
            logger.info(f"清除执行历史，保留最近 {keep_last} 条记录")
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """获取执行统计信息
        
        Returns:
            统计信息
        """
        if not self.execution_history:
            return {"message": "暂无执行历史"}
        
        # 计算统计信息
        total_executions = len(self.execution_history)
        successful_executions = sum(1 for record in self.execution_history if record["success"])
        
        # 按工具统计
        tool_stats = {}
        for record in self.execution_history:
            tool_name = record["tool_name"]
            if tool_name not in tool_stats:
                tool_stats[tool_name] = {"total": 0, "successful": 0, "total_time": 0}
            
            tool_stats[tool_name]["total"] += 1
            if record["success"]:
                tool_stats[tool_name]["successful"] += 1
            tool_stats[tool_name]["total_time"] += record["execution_time"]
        
        # 计算平均执行时间
        for tool_name, stats in tool_stats.items():
            stats["average_time"] = stats["total_time"] / stats["total"] if stats["total"] > 0 else 0
            stats["success_rate"] = stats["successful"] / stats["total"] if stats["total"] > 0 else 0
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
            "tool_statistics": tool_stats,
            "performance_metrics": self.performance_metrics.copy()
        }
    
    def export_configuration(self) -> Dict[str, Any]:
        """导出配置
        
        Returns:
            配置字典
        """
        return {
            "state_machine_config": self.state_machine.export_config(),
            "performance_metrics": self.performance_metrics.copy(),
            "tool_list": self.list_tools(),
            "current_context": self.current_context.__dict__ if self.current_context else None
        }


# 全局增强工具管理器实例
_enhanced_tool_manager: Optional[EnhancedToolManager] = None


def get_enhanced_tool_manager() -> EnhancedToolManager:
    """获取全局增强工具管理器实例
    
    Returns:
        增强工具管理器实例
    """
    global _enhanced_tool_manager
    if _enhanced_tool_manager is None:
        _enhanced_tool_manager = EnhancedToolManager()
    return _enhanced_tool_manager


async def initialize_enhanced_tools():
    """初始化增强工具管理器"""
    manager = get_enhanced_tool_manager()
    await manager.initialize_tools()
    return manager


# 便捷函数
def set_tool_context(agent_name: str, 
                    agent_state: AgentState, 
                    call_mode: ToolCallMode = ToolCallMode.AUTO,
                    task_id: Optional[str] = None,
                    step_id: Optional[str] = None,
                    context_data: Optional[Dict[str, Any]] = None):
    """设置工具执行上下文的便捷函数
    
    Args:
        agent_name: 智能体名称
        agent_state: 智能体状态
        call_mode: 调用模式
        task_id: 任务ID
        step_id: 步骤ID
        context_data: 上下文数据
    """
    manager = get_enhanced_tool_manager()
    context = ToolExecutionContext(
        agent_name=agent_name,
        agent_state=agent_state,
        call_mode=call_mode,
        task_id=task_id,
        step_id=step_id,
        context_data=context_data or {}
    )
    manager.set_execution_context(context)


async def execute_tool_with_context(tool_name: str, 
                                  method_name: str,
                                  *args,
                                  **kwargs) -> Dict[str, Any]:
    """在当前上下文下执行工具的便捷函数
    
    Args:
        tool_name: 工具名称
        method_name: 方法名称
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        执行结果
    """
    manager = get_enhanced_tool_manager()
    return await manager.execute_tool_with_constraints(tool_name, method_name, *args, **kwargs)


def get_available_tools_for_current_context() -> List[str]:
    """获取当前上下文可用工具的便捷函数
    
    Returns:
        可用工具列表
    """
    manager = get_enhanced_tool_manager()
    return manager.get_available_tools_for_context()


def get_llm_constraint_config() -> Dict[str, Any]:
    """获取LLM约束配置的便捷函数
    
    Returns:
        约束配置
    """
    manager = get_enhanced_tool_manager()
    return manager.get_constraint_config_for_llm()