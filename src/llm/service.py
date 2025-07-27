"""LLM服务类"""

import asyncio
from typing import Any, Dict, List, Optional, Union

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ..config.logging_config import get_logger
from ..exceptions import LLMServiceException
from ..models.types import AgentType, LLMType
from ..utils.performance import async_monitor_performance, timer
from .factory import get_llm_by_type, get_llm_factory, get_llm_for_agent

logger = get_logger("llm_service")


class LLMService:
    """LLM服务类，提供统一的LLM调用接口"""

    def __init__(self):
        self.factory = get_llm_factory()
        self._call_count = 0
        self._error_count = 0

    @async_monitor_performance
    async def invoke_async(
        self,
        messages: List[Union[BaseMessage, Dict[str, Any]]],
        llm_type: LLMType = LLMType.BASIC,
        **kwargs,
    ) -> AIMessage:
        """异步调用LLM

        Args:
            messages: 消息列表
            llm_type: LLM类型
            **kwargs: 额外参数

        Returns:
            AI消息响应

        Raises:
            LLMServiceException: LLM调用失败时抛出
        """
        try:
            with timer(f"llm_invoke_{llm_type.value}"):
                llm = self.factory.create_llm(llm_type)
                formatted_messages = self._format_messages(messages)

                logger.debug(
                    f"Invoking LLM {llm_type.value} with {len(formatted_messages)} messages"
                )

                response = await llm.ainvoke(formatted_messages, **kwargs)
                self._call_count += 1

                logger.debug(f"LLM response received, length: {len(response.content)}")
                return response

        except Exception as e:
            self._error_count += 1
            logger.error(f"LLM invocation failed: {e}")
            raise LLMServiceException(f"LLM invocation failed: {e}")

    def invoke_sync(
        self,
        messages: List[Union[BaseMessage, Dict[str, Any]]],
        llm_type: LLMType = LLMType.BASIC,
        **kwargs,
    ) -> AIMessage:
        """同步调用LLM

        Args:
            messages: 消息列表
            llm_type: LLM类型
            **kwargs: 额外参数

        Returns:
            AI消息响应
        """
        try:
            with timer(f"llm_invoke_sync_{llm_type.value}"):
                llm = self.factory.create_llm(llm_type)
                formatted_messages = self._format_messages(messages)

                logger.debug(
                    f"Invoking LLM {llm_type.value} with {len(formatted_messages)} messages"
                )

                response = llm.invoke(formatted_messages, **kwargs)
                self._call_count += 1

                logger.debug(f"LLM response received, length: {len(response.content)}")
                return response

        except Exception as e:
            self._error_count += 1
            logger.error(f"LLM invocation failed: {e}")
            raise LLMServiceException(f"LLM invocation failed: {e}")

    async def invoke_for_agent(
        self,
        messages: List[Union[BaseMessage, Dict[str, Any]]],
        agent_type: AgentType,
        **kwargs,
    ) -> AIMessage:
        """为指定智能体调用LLM

        Args:
            messages: 消息列表
            agent_type: 智能体类型
            **kwargs: 额外参数

        Returns:
            AI消息响应
        """
        llm_type = self.factory.agent_mapping.get_llm_type_for_agent(agent_type)
        return await self.invoke_async(messages, llm_type, **kwargs)

    async def stream_async(
        self,
        messages: List[Union[BaseMessage, Dict[str, Any]]],
        llm_type: LLMType = LLMType.BASIC,
        **kwargs,
    ):
        """异步流式调用LLM

        Args:
            messages: 消息列表
            llm_type: LLM类型
            **kwargs: 额外参数

        Yields:
            流式响应块
        """
        try:
            llm = self.factory.create_llm(llm_type)
            formatted_messages = self._format_messages(messages)

            logger.debug(f"Starting stream for LLM {llm_type.value}")

            async for chunk in llm.astream(formatted_messages, **kwargs):
                yield chunk

            self._call_count += 1

        except Exception as e:
            self._error_count += 1
            logger.error(f"LLM streaming failed: {e}")
            raise LLMServiceException(f"LLM streaming failed: {e}")

    def _format_messages(
        self, messages: List[Union[BaseMessage, Dict[str, Any]]]
    ) -> List[BaseMessage]:
        """格式化消息列表

        Args:
            messages: 原始消息列表

        Returns:
            格式化后的消息列表
        """
        formatted = []

        for msg in messages:
            if isinstance(msg, BaseMessage):
                formatted.append(msg)
            elif isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    formatted.append(SystemMessage(content=content))
                elif role == "assistant":
                    formatted.append(AIMessage(content=content))
                else:  # user or other
                    formatted.append(HumanMessage(content=content))
            else:
                # 尝试转换为字符串
                formatted.append(HumanMessage(content=str(msg)))

        return formatted

    def get_statistics(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        return {
            "total_calls": self._call_count,
            "error_count": self._error_count,
            "success_rate": (self._call_count - self._error_count)
            / max(self._call_count, 1),
            "cache_info": self.factory.get_cache_info(),
        }

    def reset_statistics(self):
        """重置统计信息"""
        self._call_count = 0
        self._error_count = 0
        logger.info("LLM service statistics reset")


# 全局LLM服务实例
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """获取LLM服务单例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


# 便捷函数
async def invoke_llm(
    messages: List[Union[BaseMessage, Dict[str, Any]]],
    llm_type: LLMType = LLMType.BASIC,
    **kwargs,
) -> AIMessage:
    """便捷的LLM调用函数"""
    service = get_llm_service()
    return await service.invoke_async(messages, llm_type, **kwargs)


async def invoke_llm_for_agent(
    messages: List[Union[BaseMessage, Dict[str, Any]]], agent_type: AgentType, **kwargs
) -> AIMessage:
    """为智能体调用LLM的便捷函数"""
    service = get_llm_service()
    return await service.invoke_for_agent(messages, agent_type, **kwargs)
