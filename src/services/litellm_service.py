"""
LiteLLM统一接口服务

实现LiteLLM统一接口，支持多LLM提供商，提供统一的LLM调用接口。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

try:
    import litellm
    from litellm import acompletion, completion

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    litellm = None

from ..config.logging_config import get_logger
from .health_monitor import (
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    register_health_check,
)
from .service_registry import (
    ServiceInfo,
    ServicePriority,
    ServiceType,
    register_service,
)

logger = get_logger("litellm_service")


@dataclass
class LiteLLMConfig:
    """LiteLLM配置"""

    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60
    retry_attempts: int = 3
    custom_llm_provider: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def model_name(self) -> str:
        """获取完整的模型名称"""
        if self.custom_llm_provider:
            return f"{self.custom_llm_provider}/{self.model}"
        return self.model


@dataclass
class LLMCallMetrics:
    """LLM调用指标"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time: float = 0.0
    last_call_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100

    def update_call_metrics(
        self, success: bool, response_time: float, tokens: int = 0, cost: float = 0.0
    ):
        """更新调用指标"""
        self.total_calls += 1
        self.last_call_time = datetime.now()

        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1

        self.total_tokens += tokens
        self.total_cost += cost

        # 更新平均响应时间
        if self.total_calls == 1:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (
                self.avg_response_time * (self.total_calls - 1) + response_time
            ) / self.total_calls


class LiteLLMHealthChecker(HealthChecker):
    """LiteLLM健康检查器"""

    def __init__(self, config: LiteLLMConfig):
        self.config = config

    async def check_health(self) -> HealthCheckResult:
        """执行健康检查"""
        start_time = time.time()
        service_name = f"litellm_{self.config.provider}"

        try:
            if not LITELLM_AVAILABLE:
                return HealthCheckResult(
                    service_name=service_name,
                    status=HealthStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    timestamp=datetime.now(),
                    message="LiteLLM未安装",
                )

            # 发送简单的测试请求
            test_messages = [{"role": "user", "content": "Hello"}]

            response = await acompletion(
                model=self.config.model_name,
                messages=test_messages,
                max_tokens=10,
                timeout=10,
                api_key=self.config.api_key,
                api_base=self.config.api_base,
            )

            response_time = time.time() - start_time

            if response and response.choices:
                return HealthCheckResult(
                    service_name=service_name,
                    status=HealthStatus.HEALTHY,
                    response_time=response_time,
                    timestamp=datetime.now(),
                    message="LiteLLM服务正常",
                    details={
                        "model": self.config.model_name,
                        "provider": self.config.provider,
                        "response_length": len(
                            response.choices[0].message.content or ""
                        ),
                    },
                )
            else:
                return HealthCheckResult(
                    service_name=service_name,
                    status=HealthStatus.DEGRADED,
                    response_time=response_time,
                    timestamp=datetime.now(),
                    message="LiteLLM响应异常",
                )

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=datetime.now(),
                message=f"LiteLLM健康检查失败: {str(e)}",
            )


class LiteLLMService:
    """LiteLLM服务"""

    def __init__(self, configs: Dict[str, LiteLLMConfig]):
        if not LITELLM_AVAILABLE:
            raise ImportError("LiteLLM未安装，请运行: pip install litellm")

        self.configs = configs
        self.metrics: Dict[str, LLMCallMetrics] = {}
        self._initialized = False

        # 初始化指标
        for provider in configs.keys():
            self.metrics[provider] = LLMCallMetrics()

        self._initialize_litellm()

    def _initialize_litellm(self):
        """初始化LiteLLM"""
        try:
            # 设置全局配置
            litellm.set_verbose = False
            litellm.drop_params = True  # 自动删除不支持的参数

            # 注册健康检查和服务
            for provider, config in self.configs.items():
                service_name = f"litellm_{provider}"

                # 注册健康检查
                health_checker = LiteLLMHealthChecker(config)
                register_health_check(service_name, health_checker)

                # 注册服务
                service_info = ServiceInfo(
                    name=service_name,
                    service_type=ServiceType.LLM,
                    priority=(
                        ServicePriority.PRIMARY
                        if provider == "openai"
                        else ServicePriority.SECONDARY
                    ),
                    endpoint=config.api_base or f"{provider}_api",
                    config=config.__dict__,
                    tags=["llm", provider, "litellm"],
                )
                register_service(service_info)

            self._initialized = True
            logger.info(f"LiteLLM服务已初始化，支持提供商: {list(self.configs.keys())}")

        except Exception as e:
            logger.error(f"初始化LiteLLM服务失败: {e}")
            raise

    async def complete(
        self, messages: List[Dict[str, str]], provider: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """异步完成调用"""
        if not self._initialized:
            raise RuntimeError("LiteLLM服务未初始化")

        # 选择提供商
        if provider is None:
            provider = next(iter(self.configs.keys()))

        if provider not in self.configs:
            raise ValueError(f"不支持的提供商: {provider}")

        config = self.configs[provider]
        start_time = time.time()

        try:
            # 合并配置参数
            call_params = {
                "model": config.model_name,
                "messages": messages,
                "temperature": kwargs.get("temperature", config.temperature),
                "max_tokens": kwargs.get("max_tokens", config.max_tokens),
                "timeout": kwargs.get("timeout", config.timeout),
            }

            # 添加API配置
            if config.api_key:
                call_params["api_key"] = config.api_key
            if config.api_base:
                call_params["api_base"] = config.api_base

            # 添加其他参数
            for key, value in kwargs.items():
                if key not in call_params:
                    call_params[key] = value

            # 执行调用
            response = await acompletion(**call_params)

            # 更新指标
            response_time = time.time() - start_time
            tokens = (
                getattr(response.usage, "total_tokens", 0)
                if hasattr(response, "usage")
                else 0
            )
            cost = self._calculate_cost(provider, tokens)

            self.metrics[provider].update_call_metrics(
                success=True, response_time=response_time, tokens=tokens, cost=cost
            )

            # 转换响应格式
            result = {
                "content": (
                    response.choices[0].message.content if response.choices else ""
                ),
                "model": response.model,
                "usage": response.usage.__dict__ if hasattr(response, "usage") else {},
                "provider": provider,
                "response_time": response_time,
                "cost": cost,
            }

            logger.debug(f"LiteLLM调用成功: {provider} - {response_time:.2f}s")
            return result

        except Exception as e:
            # 更新失败指标
            response_time = time.time() - start_time
            self.metrics[provider].update_call_metrics(
                success=False, response_time=response_time
            )

            logger.error(f"LiteLLM调用失败 ({provider}): {e}")
            raise

    def complete_sync(
        self, messages: List[Dict[str, str]], provider: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """同步完成调用"""
        if not self._initialized:
            raise RuntimeError("LiteLLM服务未初始化")

        # 选择提供商
        if provider is None:
            provider = next(iter(self.configs.keys()))

        if provider not in self.configs:
            raise ValueError(f"不支持的提供商: {provider}")

        config = self.configs[provider]
        start_time = time.time()

        try:
            # 合并配置参数
            call_params = {
                "model": config.model_name,
                "messages": messages,
                "temperature": kwargs.get("temperature", config.temperature),
                "max_tokens": kwargs.get("max_tokens", config.max_tokens),
                "timeout": kwargs.get("timeout", config.timeout),
            }

            # 添加API配置
            if config.api_key:
                call_params["api_key"] = config.api_key
            if config.api_base:
                call_params["api_base"] = config.api_base

            # 添加其他参数
            for key, value in kwargs.items():
                if key not in call_params:
                    call_params[key] = value

            # 执行调用
            response = completion(**call_params)

            # 更新指标
            response_time = time.time() - start_time
            tokens = (
                getattr(response.usage, "total_tokens", 0)
                if hasattr(response, "usage")
                else 0
            )
            cost = self._calculate_cost(provider, tokens)

            self.metrics[provider].update_call_metrics(
                success=True, response_time=response_time, tokens=tokens, cost=cost
            )

            # 转换响应格式
            result = {
                "content": (
                    response.choices[0].message.content if response.choices else ""
                ),
                "model": response.model,
                "usage": response.usage.__dict__ if hasattr(response, "usage") else {},
                "provider": provider,
                "response_time": response_time,
                "cost": cost,
            }

            logger.debug(f"LiteLLM同步调用成功: {provider} - {response_time:.2f}s")
            return result

        except Exception as e:
            # 更新失败指标
            response_time = time.time() - start_time
            self.metrics[provider].update_call_metrics(
                success=False, response_time=response_time
            )

            logger.error(f"LiteLLM同步调用失败 ({provider}): {e}")
            raise

    async def stream_complete(
        self, messages: List[Dict[str, str]], provider: Optional[str] = None, **kwargs
    ):
        """流式完成调用"""
        if not self._initialized:
            raise RuntimeError("LiteLLM服务未初始化")

        # 选择提供商
        if provider is None:
            provider = next(iter(self.configs.keys()))

        if provider not in self.configs:
            raise ValueError(f"不支持的提供商: {provider}")

        config = self.configs[provider]
        start_time = time.time()

        try:
            # 合并配置参数
            call_params = {
                "model": config.model_name,
                "messages": messages,
                "temperature": kwargs.get("temperature", config.temperature),
                "max_tokens": kwargs.get("max_tokens", config.max_tokens),
                "timeout": kwargs.get("timeout", config.timeout),
                "stream": True,
            }

            # 添加API配置
            if config.api_key:
                call_params["api_key"] = config.api_key
            if config.api_base:
                call_params["api_base"] = config.api_base

            # 添加其他参数
            for key, value in kwargs.items():
                if key not in call_params:
                    call_params[key] = value

            # 执行流式调用
            stream = await acompletion(**call_params)

            total_tokens = 0
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    yield {
                        "content": chunk.choices[0].delta.content or "",
                        "model": chunk.model,
                        "provider": provider,
                        "chunk": chunk,
                    }
                    total_tokens += 1  # 简单估算

            # 更新指标
            response_time = time.time() - start_time
            cost = self._calculate_cost(provider, total_tokens)

            self.metrics[provider].update_call_metrics(
                success=True,
                response_time=response_time,
                tokens=total_tokens,
                cost=cost,
            )

            logger.debug(f"LiteLLM流式调用完成: {provider} - {response_time:.2f}s")

        except Exception as e:
            # 更新失败指标
            response_time = time.time() - start_time
            self.metrics[provider].update_call_metrics(
                success=False, response_time=response_time
            )

            logger.error(f"LiteLLM流式调用失败 ({provider}): {e}")
            raise

    def get_supported_providers(self) -> List[str]:
        """获取支持的提供商列表"""
        return list(self.configs.keys())

    def get_provider_config(self, provider: str) -> Optional[LiteLLMConfig]:
        """获取提供商配置"""
        return self.configs.get(provider)

    def get_metrics(
        self, provider: Optional[str] = None
    ) -> Union[Dict[str, LLMCallMetrics], LLMCallMetrics]:
        """获取指标"""
        if provider:
            return self.metrics.get(provider, LLMCallMetrics())
        return self.metrics

    def reset_metrics(self, provider: Optional[str] = None):
        """重置指标"""
        if provider:
            if provider in self.metrics:
                self.metrics[provider] = LLMCallMetrics()
        else:
            for provider in self.metrics.keys():
                self.metrics[provider] = LLMCallMetrics()

        logger.info(f"LiteLLM指标已重置: {provider or '所有提供商'}")

    def _calculate_cost(self, provider: str, tokens: int) -> float:
        """计算调用成本（简单估算）"""
        # 这里可以根据不同提供商的定价来计算成本
        # 目前使用简单的估算
        cost_per_1k_tokens = {
            "openai": 0.002,
            "anthropic": 0.008,
            "google": 0.001,
            "azure": 0.002,
        }

        rate = cost_per_1k_tokens.get(provider, 0.002)
        return (tokens / 1000) * rate

    def get_statistics(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        total_calls = sum(m.total_calls for m in self.metrics.values())
        total_successful = sum(m.successful_calls for m in self.metrics.values())
        total_failed = sum(m.failed_calls for m in self.metrics.values())
        total_tokens = sum(m.total_tokens for m in self.metrics.values())
        total_cost = sum(m.total_cost for m in self.metrics.values())

        provider_stats = {}
        for provider, metrics in self.metrics.items():
            provider_stats[provider] = {
                "calls": metrics.total_calls,
                "success_rate": metrics.success_rate,
                "avg_response_time": metrics.avg_response_time,
                "tokens": metrics.total_tokens,
                "cost": metrics.total_cost,
            }

        return {
            "initialized": self._initialized,
            "supported_providers": list(self.configs.keys()),
            "total_calls": total_calls,
            "success_rate": (
                (total_successful / total_calls * 100) if total_calls > 0 else 0
            ),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "provider_statistics": provider_stats,
        }


# 全局LiteLLM服务实例
_litellm_service: Optional[LiteLLMService] = None


def get_litellm_service() -> Optional[LiteLLMService]:
    """获取全局LiteLLM服务实例"""
    return _litellm_service


def initialize_litellm_service(configs: Dict[str, LiteLLMConfig]) -> LiteLLMService:
    """初始化LiteLLM服务"""
    global _litellm_service
    if _litellm_service is None:
        _litellm_service = LiteLLMService(configs)
    return _litellm_service
