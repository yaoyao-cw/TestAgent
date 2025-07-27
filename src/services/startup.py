"""
外部服务启动脚本

用于在应用启动时初始化外部服务。
"""

import asyncio
import logging
from typing import Optional

from ..config.logging_config import get_logger
from .config_loader import get_service_config_loader
from .external_service_manager import get_external_service_manager

logger = get_logger("service_startup")


async def initialize_external_services() -> bool:
    """初始化外部服务"""
    logger.info("开始初始化外部服务")

    try:
        # 获取配置加载器
        config_loader = get_service_config_loader()

        # 验证配置
        validation_results = config_loader.validate_configs()
        logger.info(f"配置验证结果: {validation_results}")

        # 获取服务管理器
        service_manager = get_external_service_manager()

        # 初始化服务
        await service_manager.initialize()

        # 获取初始化结果
        stats = service_manager.get_service_statistics()
        logger.info(
            f"服务初始化完成: {stats['active_services']}/{stats['total_services']} 个服务正常运行"
        )

        return True

    except Exception as e:
        logger.error(f"初始化外部服务失败: {e}")
        return False


async def shutdown_external_services():
    """关闭外部服务"""
    logger.info("开始关闭外部服务")

    try:
        service_manager = get_external_service_manager()
        await service_manager.shutdown()
        logger.info("外部服务关闭完成")

    except Exception as e:
        logger.error(f"关闭外部服务失败: {e}")


def setup_service_startup_hooks():
    """设置服务启动钩子"""
    import atexit

    # 注册退出时的清理函数
    def cleanup():
        try:
            asyncio.run(shutdown_external_services())
        except Exception as e:
            logger.error(f"清理外部服务失败: {e}")

    atexit.register(cleanup)
    logger.info("已注册服务清理钩子")


# 便捷函数
async def startup():
    """启动外部服务"""
    setup_service_startup_hooks()
    return await initialize_external_services()


async def shutdown():
    """关闭外部服务"""
    await shutdown_external_services()


if __name__ == "__main__":
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    # 运行启动脚本
    async def main():
        success = await startup()
        if success:
            logger.info("外部服务启动成功")

            # 等待一段时间以观察服务状态
            await asyncio.sleep(10)

            # 显示服务状态
            service_manager = get_external_service_manager()
            stats = service_manager.get_service_statistics()
            logger.info(f"当前服务状态: {stats}")

        else:
            logger.error("外部服务启动失败")

        await shutdown()

    asyncio.run(main())
