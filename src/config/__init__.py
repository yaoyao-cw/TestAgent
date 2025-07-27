#!/usr/bin/env python3
"""
配置管理模块

提供统一的配置管理功能，包括：
- 配置设置和管理
- 环境变量管理
- 配置验证和自动修复
- 日志配置
"""

from .logging_config import (
    LoggingManager,
    configure_module_logger,
    create_file_handler,
    get_logger,
    get_logging_manager,
    init_logging,
    setup_logging,
)
from .settings import TestAgentSettings, get_settings

# from .manager import (
#     ConfigManager,
#     ConfigChangeEvent,
#     get_config_manager,
#     config_dependent
# )

# from .env_manager import (
#     EnvManager,
#     EnvVarError,
#     ConfigFromEnv,
#     get_env_manager,
#     reload_env_manager,
#     get_env,
#     set_env,
#     delete_env
# )

# from .validator import (
#     ValidationResult,
#     ConfigValidator,
#     validate_config,
#     auto_fix_config
# )


__all__ = [
    # Settings
    "TestAgentSettings",
    "get_settings",
    # Logging
    "setup_logging",
    "get_logger",
    "configure_module_logger",
    "create_file_handler",
    "LoggingManager",
    "get_logging_manager",
    "init_logging",
]


def initialize_config_system():
    """初始化配置系统"""
    try:
        # 初始化日志系统
        from .logging_config import get_logging_manager

        logging_manager = get_logging_manager()
        logging_manager.initialize()

        # 基本配置系统已初始化
        logger = get_logger("config_init")
        logger.info("配置系统初始化完成")

        return True

    except Exception as e:
        print(f"配置系统初始化失败: {e}")
        return False


# 自动初始化配置系统
_initialized = False


def ensure_initialized():
    """确保配置系统已初始化"""
    global _initialized
    if not _initialized:
        _initialized = initialize_config_system()
    return _initialized


# 在模块导入时自动初始化
ensure_initialized()
