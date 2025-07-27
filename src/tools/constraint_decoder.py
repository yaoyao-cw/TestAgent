#!/usr/bin/env python3
"""
约束解码器模块
通过token logits遮蔽控制工具可用性，实现约束解码机制
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from .state_machine import AgentState, ToolCallMode, ToolStateMachine

logger = logging.getLogger(__name__)


@dataclass
class TokenConstraint:
    """Token约束定义"""

    allowed_tokens: Set[str]
    blocked_tokens: Set[str]
    boost_tokens: Dict[str, float]  # token -> boost_score
    penalty_tokens: Dict[str, float]  # token -> penalty_score


class ConstraintDecoder:
    """约束解码器

    实现通过token logits遮蔽控制工具可用性的约束解码机制
    支持三种调用模式的约束解码
    """

    def __init__(self, state_machine: ToolStateMachine):
        """初始化约束解码器

        Args:
            state_machine: 工具状态机实例
        """
        self.state_machine = state_machine

        # Token映射缓存
        self._token_cache: Dict[str, Set[str]] = {}

        # 工具名称到token的映射
        self._tool_tokens: Dict[str, Set[str]] = {}

        # 约束配置缓存
        self._constraint_cache: Dict[str, TokenConstraint] = {}

        # 初始化工具token映射
        self._initialize_tool_tokens()

        logger.info("约束解码器初始化完成")

    def _initialize_tool_tokens(self):
        """初始化工具名称到token的映射"""
        # 获取所有工具定义
        for tool_name in self.state_machine.all_tools:
            # 将工具名称分解为tokens
            tokens = self._tokenize_tool_name(tool_name)
            self._tool_tokens[tool_name] = tokens

        logger.info(f"初始化了 {len(self._tool_tokens)} 个工具的token映射")

    def _tokenize_tool_name(self, tool_name: str) -> Set[str]:
        """将工具名称分解为tokens

        Args:
            tool_name: 工具名称

        Returns:
            token集合
        """
        # 简单的token化：按下划线分割，并包含完整名称
        tokens = set()

        # 添加完整工具名称
        tokens.add(tool_name)

        # 添加分割后的部分
        parts = tool_name.split("_")
        tokens.update(parts)

        # 添加前缀
        if "_" in tool_name:
            prefix = tool_name.split("_")[0] + "_"
            tokens.add(prefix)

        return tokens

    def get_token_constraints(
        self, agent_state: AgentState, call_mode: ToolCallMode
    ) -> TokenConstraint:
        """获取token约束

        Args:
            agent_state: 智能体状态
            call_mode: 调用模式

        Returns:
            Token约束
        """
        cache_key = f"{agent_state.value}_{call_mode.value}"

        # 检查缓存
        if cache_key in self._constraint_cache:
            return self._constraint_cache[cache_key]

        # 计算约束
        constraint = self._calculate_token_constraints(agent_state, call_mode)

        # 缓存结果
        self._constraint_cache[cache_key] = constraint

        return constraint

    def _calculate_token_constraints(
        self, agent_state: AgentState, call_mode: ToolCallMode
    ) -> TokenConstraint:
        """计算token约束

        Args:
            agent_state: 智能体状态
            call_mode: 调用模式

        Returns:
            Token约束
        """
        # 获取可用工具
        available_tools = self.state_machine.get_available_tools(agent_state, call_mode)

        # 计算允许和阻止的tokens
        allowed_tokens = set()
        blocked_tokens = set()
        boost_tokens = {}
        penalty_tokens = {}

        # 收集所有工具的tokens
        all_tool_tokens = set()
        for tool_name in self.state_machine.all_tools:
            all_tool_tokens.update(self._tool_tokens.get(tool_name, set()))

        # 收集可用工具的tokens
        available_tool_tokens = set()
        for tool_name in available_tools:
            tool_tokens = self._tool_tokens.get(tool_name, set())
            available_tool_tokens.update(tool_tokens)
            allowed_tokens.update(tool_tokens)

        # 阻止不可用工具的tokens
        for tool_name in self.state_machine.all_tools:
            if tool_name not in available_tools:
                tool_tokens = self._tool_tokens.get(tool_name, set())
                # 只阻止那些不在可用工具中的tokens
                unique_tokens = tool_tokens - available_tool_tokens
                blocked_tokens.update(unique_tokens)

        # 根据调用模式设置boost和penalty
        if call_mode == ToolCallMode.REQUIRED:
            # 必需模式：强烈boost工具调用相关的tokens
            for token in available_tool_tokens:
                boost_tokens[token] = 2.0

            # 强烈penalty非工具调用的tokens
            penalty_tokens.update(
                {"I": -5.0, "Let": -5.0, "Based": -5.0, "The": -3.0, "Here": -3.0}
            )

        elif call_mode == ToolCallMode.SPECIFIED:
            # 指定模式：适度boost可用工具tokens
            for token in available_tool_tokens:
                boost_tokens[token] = 1.0

            # 适度penalty不可用工具tokens
            for token in blocked_tokens:
                penalty_tokens[token] = -2.0

        elif call_mode == ToolCallMode.AUTO:
            # 自动模式：轻微boost工具tokens，但不强制
            for token in available_tool_tokens:
                boost_tokens[token] = 0.5

        return TokenConstraint(
            allowed_tokens=allowed_tokens,
            blocked_tokens=blocked_tokens,
            boost_tokens=boost_tokens,
            penalty_tokens=penalty_tokens,
        )

    def apply_logits_mask(
        self,
        logits: np.ndarray,
        token_to_id: Dict[str, int],
        constraint: TokenConstraint,
    ) -> np.ndarray:
        """应用logits遮蔽

        Args:
            logits: 原始logits数组
            token_to_id: token到ID的映射
            constraint: token约束

        Returns:
            遮蔽后的logits数组
        """
        masked_logits = logits.copy()

        # 应用阻止tokens的遮蔽（设置为负无穷）
        for token in constraint.blocked_tokens:
            if token in token_to_id:
                token_id = token_to_id[token]
                if token_id < len(masked_logits):
                    masked_logits[token_id] = float("-inf")

        # 应用boost tokens
        for token, boost_score in constraint.boost_tokens.items():
            if token in token_to_id:
                token_id = token_to_id[token]
                if token_id < len(masked_logits):
                    masked_logits[token_id] += boost_score

        # 应用penalty tokens
        for token, penalty_score in constraint.penalty_tokens.items():
            if token in token_to_id:
                token_id = token_to_id[token]
                if token_id < len(masked_logits):
                    masked_logits[token_id] += penalty_score

        return masked_logits

    def get_response_prefill(
        self, agent_state: AgentState, call_mode: ToolCallMode
    ) -> Optional[str]:
        """获取响应预填充内容

        Args:
            agent_state: 智能体状态
            call_mode: 调用模式

        Returns:
            预填充内容
        """
        available_tools = self.state_machine.get_available_tools(agent_state, call_mode)

        if call_mode == ToolCallMode.REQUIRED:
            if available_tools:
                # 必需模式：预填充工具调用开始
                return self._generate_tool_call_prefill(available_tools[0])
            else:
                return None

        elif call_mode == ToolCallMode.SPECIFIED:
            if len(available_tools) == 1:
                # 指定模式且只有一个工具：预填充该工具调用
                return self._generate_tool_call_prefill(available_tools[0])
            elif len(available_tools) > 1:
                # 多个工具可用：预填充工具调用结构
                return '{"tool_calls": [{"type": "function", "function": {"name": "'
            else:
                return None

        elif call_mode == ToolCallMode.AUTO:
            # 自动模式：不预填充，让模型自由选择
            return None

        return None

    def _generate_tool_call_prefill(self, tool_name: str) -> str:
        """生成工具调用预填充

        Args:
            tool_name: 工具名称

        Returns:
            预填充字符串
        """
        return json.dumps(
            {
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": tool_name, "arguments": ""},
                    }
                ]
            },
            separators=(",", ":"),
        )[
            :-3
        ]  # 移除最后的 "}]}

    def validate_tool_call(
        self,
        tool_call: Dict[str, Any],
        agent_state: AgentState,
        call_mode: ToolCallMode,
    ) -> Tuple[bool, Optional[str]]:
        """验证工具调用是否符合约束

        Args:
            tool_call: 工具调用
            agent_state: 智能体状态
            call_mode: 调用模式

        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 提取工具名称
            if "function" in tool_call and "name" in tool_call["function"]:
                tool_name = tool_call["function"]["name"]
            else:
                return False, "工具调用格式错误：缺少function.name"

            # 获取可用工具
            available_tools = self.state_machine.get_available_tools(
                agent_state, call_mode
            )

            # 检查工具是否可用
            if tool_name not in available_tools:
                return (
                    False,
                    f"工具 {tool_name} 在当前状态 {agent_state.value} 和模式 {call_mode.value} 下不可用",
                )

            # 检查调用模式特定的约束
            if call_mode == ToolCallMode.REQUIRED:
                # 必需模式：必须调用工具
                if not tool_name:
                    return False, "必需模式下必须调用工具"

            elif call_mode == ToolCallMode.SPECIFIED:
                # 指定模式：只能调用指定的工具
                if tool_name not in available_tools:
                    return (
                        False,
                        f"指定模式下只能调用以下工具之一: {', '.join(available_tools)}",
                    )

            return True, None

        except Exception as e:
            logger.error(f"验证工具调用时出错: {e}")
            return False, f"验证工具调用时出错: {str(e)}"

    def get_tool_call_suggestions(
        self,
        agent_state: AgentState,
        call_mode: ToolCallMode,
        context: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取工具调用建议

        Args:
            agent_state: 智能体状态
            call_mode: 调用模式
            context: 上下文信息

        Returns:
            工具调用建议列表
        """
        available_tools = self.state_machine.get_available_tools(agent_state, call_mode)
        suggestions = []

        for tool_name in available_tools:
            tool_def = self.state_machine.get_tool_definition(tool_name)
            if tool_def:
                suggestion = {
                    "tool_name": tool_name,
                    "description": tool_def.description,
                    "category": tool_def.category,
                    "parameters": tool_def.parameters,
                    "priority": tool_def.priority,
                    "example_call": self._generate_example_call(tool_name, tool_def),
                }
                suggestions.append(suggestion)

        # 按优先级排序
        suggestions.sort(key=lambda x: x["priority"], reverse=True)

        return suggestions

    def _generate_example_call(self, tool_name: str, tool_def) -> Dict[str, Any]:
        """生成示例工具调用

        Args:
            tool_name: 工具名称
            tool_def: 工具定义

        Returns:
            示例工具调用
        """
        # 生成示例参数
        example_args = {}
        if "properties" in tool_def.parameters:
            for param_name, param_def in tool_def.parameters["properties"].items():
                param_type = param_def.get("type", "string")
                if param_type == "string":
                    example_args[param_name] = f"示例{param_name}"
                elif param_type == "integer":
                    example_args[param_name] = 1
                elif param_type == "boolean":
                    example_args[param_name] = True
                elif param_type == "array":
                    example_args[param_name] = []
                elif param_type == "object":
                    example_args[param_name] = {}

        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(example_args, ensure_ascii=False),
            },
        }

    def clear_cache(self):
        """清除缓存"""
        self._constraint_cache.clear()
        self._token_cache.clear()
        logger.info("约束解码器缓存已清除")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息
        """
        return {
            "total_tools": len(self._tool_tokens),
            "total_tokens": sum(len(tokens) for tokens in self._tool_tokens.values()),
            "constraint_cache_size": len(self._constraint_cache),
            "token_cache_size": len(self._token_cache),
            "unique_tokens": len(set().union(*self._tool_tokens.values())),
        }


# 全局约束解码器实例
_constraint_decoder: Optional[ConstraintDecoder] = None


def get_constraint_decoder() -> ConstraintDecoder:
    """获取全局约束解码器实例

    Returns:
        约束解码器实例
    """
    global _constraint_decoder
    if _constraint_decoder is None:
        from .state_machine import get_tool_state_machine

        state_machine = get_tool_state_machine()
        _constraint_decoder = ConstraintDecoder(state_machine)
    return _constraint_decoder


def apply_tool_constraints(
    logits: np.ndarray,
    token_to_id: Dict[str, int],
    agent_state: AgentState,
    call_mode: ToolCallMode,
) -> np.ndarray:
    """应用工具约束的便捷函数

    Args:
        logits: 原始logits数组
        token_to_id: token到ID的映射
        agent_state: 智能体状态
        call_mode: 调用模式

    Returns:
        约束后的logits数组
    """
    decoder = get_constraint_decoder()
    constraint = decoder.get_token_constraints(agent_state, call_mode)
    return decoder.apply_logits_mask(logits, token_to_id, constraint)


def get_tool_call_prefill(
    agent_state: AgentState, call_mode: ToolCallMode
) -> Optional[str]:
    """获取工具调用预填充的便捷函数

    Args:
        agent_state: 智能体状态
        call_mode: 调用模式

    Returns:
        预填充内容
    """
    decoder = get_constraint_decoder()
    return decoder.get_response_prefill(agent_state, call_mode)
