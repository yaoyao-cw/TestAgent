#!/usr/bin/env python3
"""
日志配置模块

提供统一的日志配置和管理
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    from .settings import get_settings
except ImportError:
    # 如果无法导入设置，使用默认配置
    def get_settings():
        class MockSettings:
            class LoggingSettings:
                level = "INFO"
                file = "./logs/testagent.log"
                format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                rotation = "1 day"
                retention = "30 days"
                compression = "zip"

            logging = LoggingSettings()

        return MockSettings()


# 默认日志格式
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def parse_log_level(level: str) -> int:
    """解析日志级别"""
    level_upper = level.upper()
    return LOG_LEVELS.get(level_upper, logging.INFO)


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    rotation: Optional[str] = None,
) -> None:
    """设置全局日志配置"""
    # 获取配置
    try:
        settings = get_settings()
        logging_config = settings.logging
    except:
        # 使用默认配置
        class DefaultConfig:
            level = "INFO"
            file = "./logs/testagent.log"
            format = DEFAULT_LOG_FORMAT
            rotation = "1 day"

        logging_config = DefaultConfig()

    # 使用传入参数或配置文件中的值
    log_level = level or logging_config.level
    log_file_path = log_file or logging_config.file
    format_str = log_format or logging_config.format
    rotation_str = rotation or getattr(logging_config, "rotation", "1 day")

    # 解析日志级别
    numeric_level = parse_log_level(log_level)

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建格式化器
    formatter = logging.Formatter(format_str)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（如果指定了文件路径）
    if log_file_path:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # 根据轮转配置选择处理器
        if "day" in rotation_str.lower():
            # 按天轮转
            days = 1
            if rotation_str.lower().startswith(("1", "2", "3", "4", "5", "6", "7")):
                try:
                    days = int(rotation_str.split()[0])
                except:
                    days = 1

            file_handler = TimedRotatingFileHandler(
                log_file_path,
                when="D",
                interval=days,
                backupCount=30,  # 保留30个备份文件
                encoding="utf-8",
            )
        elif "mb" in rotation_str.lower() or "size" in rotation_str.lower():
            # 按大小轮转
            max_bytes = 10 * 1024 * 1024  # 默认10MB
            if rotation_str.lower().startswith(
                ("1", "2", "5", "10", "20", "50", "100")
            ):
                try:
                    size_mb = int(rotation_str.split()[0])
                    max_bytes = size_mb * 1024 * 1024
                except:
                    max_bytes = 10 * 1024 * 1024

            file_handler = RotatingFileHandler(
                log_file_path, maxBytes=max_bytes, backupCount=10, encoding="utf-8"
            )
        else:
            # 简单文件处理器
            file_handler = logging.FileHandler(log_file_path, encoding="utf-8")

        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器"""
    return logging.getLogger(name)


def configure_module_logger(
    module_name: str, level: Optional[str] = None, handlers: Optional[list] = None
) -> logging.Logger:
    """配置模块特定的日志记录器"""
    logger = logging.getLogger(module_name)

    if level:
        logger.setLevel(parse_log_level(level))

    if handlers:
        # 清除现有处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # 添加新处理器
        for handler in handlers:
            logger.addHandler(handler)

    return logger


def create_file_handler(
    file_path: str,
    level: str = "INFO",
    format_str: Optional[str] = None,
    rotation: Optional[str] = None,
) -> Union[logging.FileHandler, RotatingFileHandler, TimedRotatingFileHandler]:
    """创建文件处理器"""
    # 确保目录存在
    log_dir = os.path.dirname(file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # 创建格式化器
    formatter = logging.Formatter(format_str or DEFAULT_LOG_FORMAT)

    # 根据轮转配置选择处理器类型
    if rotation:
        if "day" in rotation.lower():
            days = 1
            if rotation.lower().startswith(("1", "2", "3", "4", "5", "6", "7")):
                try:
                    days = int(rotation.split()[0])
                except:
                    days = 1

            handler = TimedRotatingFileHandler(
                file_path, when="D", interval=days, backupCount=30, encoding="utf-8"
            )
        elif "mb" in rotation.lower() or "size" in rotation.lower():
            max_bytes = 10 * 1024 * 1024  # 默认10MB
            if rotation.lower().startswith(("1", "2", "5", "10", "20", "50", "100")):
                try:
                    size_mb = int(rotation.split()[0])
                    max_bytes = size_mb * 1024 * 1024
                except:
                    max_bytes = 10 * 1024 * 1024

            handler = RotatingFileHandler(
                file_path, maxBytes=max_bytes, backupCount=10, encoding="utf-8"
            )
        else:
            handler = logging.FileHandler(file_path, encoding="utf-8")
    else:
        handler = logging.FileHandler(file_path, encoding="utf-8")

    handler.setLevel(parse_log_level(level))
    handler.setFormatter(formatter)

    return handler


class LoggingManager:
    """日志管理器"""

    def __init__(self):
        self.configured = False
        self.handlers: Dict[str, logging.Handler] = {}

    def initialize(self) -> None:
        """初始化日志系统"""
        if not self.configured:
            setup_logging()
            self.configured = True

    def add_handler(self, name: str, handler: logging.Handler) -> None:
        """添加处理器"""
        self.handlers[name] = handler
        logging.getLogger().addHandler(handler)

    def remove_handler(self, name: str) -> bool:
        """移除处理器"""
        if name in self.handlers:
            handler = self.handlers.pop(name)
            logging.getLogger().removeHandler(handler)
            return True
        return False

    def get_handler(self, name: str) -> Optional[logging.Handler]:
        """获取处理器"""
        return self.handlers.get(name)

    def reconfigure(self) -> None:
        """重新配置日志系统"""
        self.configured = False
        self.initialize()

    def set_level(self, level: str, logger_name: Optional[str] = None) -> None:
        """设置日志级别"""
        numeric_level = parse_log_level(level)
        if logger_name:
            logging.getLogger(logger_name).setLevel(numeric_level)
        else:
            logging.getLogger().setLevel(numeric_level)


# 全局日志管理器实例
_logging_manager: Optional[LoggingManager] = None


def get_logging_manager() -> LoggingManager:
    """获取日志管理器单例"""
    global _logging_manager
    if _logging_manager is None:
        _logging_manager = LoggingManager()
    return _logging_manager


# 初始化日志配置
def init_logging():
    """初始化日志配置"""
    # 从环境变量获取配置
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "./logs/testagent.log")

    setup_logging(level=log_level, log_file=log_file)


# 自动初始化
if not logging.getLogger().handlers:
    init_logging()
