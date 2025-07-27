"""
外部服务集成测试

测试外部服务的集成和功能。
"""

import asyncio
import logging
from typing import Any, Dict

from ..config.logging_config import get_logger
from .config_loader import get_service_config_loader
from .external_service_manager import (ServiceStatus,
                                       get_external_service_manager)

logger = get_logger("service_integration_test")


async def test_service_initialization():
    """测试服务初始化"""
    logger.info("开始测试服务初始化")

    try:
        # 获取服务管理器
        service_manager = get_external_service_manager()

        # 初始化服务
        await service_manager.initialize()

        # 检查服务状态
        stats = service_manager.get_service_statistics()
        logger.info(f"服务统计: {stats}")

        # 测试各个服务
        await test_litellm_service(service_manager)
        await test_redis_service(service_manager)

        logger.info("服务初始化测试完成")
        return True

    except Exception as e:
        logger.error(f"服务初始化测试失败: {e}")
        return False


async def test_litellm_service(service_manager):
    """测试LiteLLM服务"""
    logger.info("测试LiteLLM服务")

    try:
        litellm_service = service_manager.get_service("litellm")
        if litellm_service:
            # 测试简单的LLM调用
            messages = [{"role": "user", "content": "Hello, this is a test."}]

            # 获取支持的提供商
            providers = litellm_service.get_supported_providers()
            logger.info(f"支持的LLM提供商: {providers}")

            if providers:
                # 测试第一个提供商
                provider = providers[0]
                logger.info(f"测试提供商: {provider}")

                try:
                    # 注意：这里可能会因为API密钥问题失败，这是正常的
                    response = await litellm_service.complete(
                        messages=messages, provider=provider, max_tokens=10
                    )
                    logger.info(f"LLM调用成功: {response.get('content', '')[:50]}...")
                except Exception as e:
                    logger.warning(f"LLM调用失败（可能是API密钥问题）: {e}")

            # 获取服务统计
            stats = litellm_service.get_statistics()
            logger.info(f"LiteLLM统计: {stats}")

        else:
            logger.warning("LiteLLM服务未初始化")

    except Exception as e:
        logger.error(f"测试LiteLLM服务失败: {e}")


async def test_redis_service(service_manager):
    """测试Redis服务"""
    logger.info("测试Redis服务")

    try:
        redis_service = service_manager.get_service("redis")
        if redis_service:
            # 测试基本的Redis操作
            test_key = "test:integration"
            test_value = {"message": "Hello Redis", "timestamp": "2024-01-01"}

            # 设置值
            success = await redis_service.set(test_key, test_value, ex=60)
            logger.info(f"Redis SET操作: {success}")

            # 获取值
            retrieved_value = await redis_service.get(test_key)
            logger.info(f"Redis GET操作: {retrieved_value}")

            # 检查键是否存在
            exists = await redis_service.exists(test_key)
            logger.info(f"Redis EXISTS操作: {exists}")

            # 删除键
            deleted = await redis_service.delete(test_key)
            logger.info(f"Redis DELETE操作: {deleted}")

            # 测试会话存储
            session_id = "test_session_123"
            session_data = {"user_id": "user123", "login_time": "2024-01-01"}

            success = await redis_service.set_session(session_id, session_data, ttl=300)
            logger.info(f"Redis会话设置: {success}")

            session = await redis_service.get_session(session_id)
            logger.info(f"Redis会话获取: {session}")

            # 获取服务统计
            stats = await redis_service.get_statistics()
            logger.info(f"Redis统计: {stats}")

        else:
            logger.warning("Redis服务未初始化")

    except Exception as e:
        logger.error(f"测试Redis服务失败: {e}")


async def test_health_monitoring():
    """测试健康监控"""
    logger.info("测试健康监控")

    try:
        service_manager = get_external_service_manager()

        # 等待一些时间让健康检查运行
        await asyncio.sleep(5)

        # 获取健康监控摘要
        health_summary = service_manager.health_monitor.get_summary()
        logger.info(f"健康监控摘要: {health_summary}")

        # 获取所有服务状态
        all_statuses = service_manager.health_monitor.get_all_statuses()
        for service_name, status in all_statuses.items():
            logger.info(
                f"服务 {service_name} 状态: {status.status.value} - {status.message}"
            )

        # 获取所有服务指标
        all_metrics = service_manager.health_monitor.get_all_metrics()
        for service_name, metrics in all_metrics.items():
            logger.info(
                f"服务 {service_name} 指标: 成功率={metrics.success_rate:.1f}%, 平均响应时间={metrics.avg_response_time:.3f}s"
            )

    except Exception as e:
        logger.error(f"测试健康监控失败: {e}")


async def test_service_registry():
    """测试服务注册中心"""
    logger.info("测试服务注册中心")

    try:
        service_manager = get_external_service_manager()
        registry = service_manager.service_registry

        # 获取所有服务
        all_services = registry.list_services()
        logger.info(f"注册的服务数量: {len(all_services)}")

        for service in all_services:
            logger.info(
                f"服务: {service.name} - 类型: {service.service_type.value} - 优先级: {service.priority.value}"
            )

        # 获取统计信息
        stats = registry.get_service_statistics()
        logger.info(f"服务注册中心统计: {stats}")

    except Exception as e:
        logger.error(f"测试服务注册中心失败: {e}")


async def test_config_loader():
    """测试配置加载器"""
    logger.info("测试配置加载器")

    try:
        config_loader = get_service_config_loader()

        # 获取所有配置
        all_configs = config_loader.get_all_service_configs()

        logger.info("配置验证结果:")
        for service, is_valid in all_configs["validation"].items():
            logger.info(f"  {service}: {'✓' if is_valid else '✗'}")

        # 显示LiteLLM配置
        litellm_configs = all_configs["litellm"]
        if litellm_configs:
            logger.info(f"LiteLLM提供商: {list(litellm_configs.keys())}")

        # 显示Redis配置
        redis_config = all_configs["redis"]
        if redis_config:
            logger.info(
                f"Redis配置: {redis_config.url or f'{redis_config.host}:{redis_config.port}'}"
            )

    except Exception as e:
        logger.error(f"测试配置加载器失败: {e}")


async def run_integration_tests():
    """运行集成测试"""
    logger.info("开始运行外部服务集成测试")

    try:
        # 测试配置加载器
        await test_config_loader()

        # 测试服务初始化
        success = await test_service_initialization()
        if not success:
            logger.error("服务初始化失败，跳过其他测试")
            return False

        # 测试健康监控
        await test_health_monitoring()

        # 测试服务注册中心
        await test_service_registry()

        logger.info("外部服务集成测试完成")
        return True

    except Exception as e:
        logger.error(f"集成测试失败: {e}")
        return False
    finally:
        # 清理资源
        try:
            service_manager = get_external_service_manager()
            await service_manager.shutdown()
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


if __name__ == "__main__":
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    # 运行测试
    asyncio.run(run_integration_tests())
