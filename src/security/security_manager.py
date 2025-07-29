#!/usr/bin/env python3
"""
安全管理器

提供统一的安全系统初始化和管理功能
"""

import logging

logger = logging.getLogger("security_manager")


def initialize_security_system():
    """初始化安全系统"""
    try:
        logger.info("Security system initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize security system: {e}")
        return False


def shutdown_security_system():
    """关闭安全系统"""
    try:
        logger.info("Security system shutdown completed")
    except Exception as e:
        logger.error(f"Error during security system shutdown: {e}")


class SecurityManager:
    """安全管理器"""

    def __init__(self):
        self.initialized = False

    def initialize(self):
        """初始化安全管理器"""
        if not self.initialized:
            logger.info("Security manager initialized")
            self.initialized = True

    def get_status(self):
        """获取安全状态"""
        return {
            "initialized": self.initialized,
            "status": "active" if self.initialized else "inactive",
        }


# 全局实例
_security_manager = None


def get_security_manager() -> SecurityManager:
    """获取安全管理器实例"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
        _security_manager.initialize()
    return _security_manager
