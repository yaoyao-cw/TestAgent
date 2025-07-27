#!/usr/bin/env python3
"""
安全管理器

统一管理所有安全组件的初始化和配置
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ..config.logging_config import get_logger
from .audit_logger import get_security_audit_logger
from .auth import get_auth_manager, get_jwt_authenticator
from .data_encryption import get_data_encryption, get_sensitive_data_masker
from .input_validator import get_input_validator
from .malicious_code_detector import get_malicious_code_detector
from .rate_limiter import get_rate_limiter
from .sandbox_security import (ResourceLimit, get_sandbox_security_manager,
                               initialize_sandbox_security)

logger = get_logger("security_manager")


class SecurityManager:
    """安全管理器"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/security.yaml"
        self.config = self._load_config()
        self.initialized = False

    def _load_config(self) -> Dict[str, Any]:
        """加载安全配置"""
        config_file = Path(self.config_path)

        if not config_file.exists():
            # 尝试加载示例配置
            example_config = Path("config/security.example.yaml")
            if example_config.exists():
                logger.warning(f"安全配置文件不存在，使用示例配置: {example_config}")
                config_file = example_config
            else:
                logger.warning("未找到安全配置文件，使用默认配置")
                return self._get_default_config()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.info(f"已加载安全配置: {config_file}")
                return config
        except Exception as e:
            logger.error(f"加载安全配置失败: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认安全配置"""
        return {
            "jwt": {
                "secret_key": "default-secret-key-change-in-production",
                "algorithm": "HS256",
                "access_token_expire_minutes": 30,
                "refresh_token_expire_days": 7,
                "max_failed_attempts": 5,
                "lockout_duration_minutes": 15,
            },
            "rate_limiting": {
                "global": {"requests_per_minute": 100, "burst_capacity": 20},
                "per_ip": {"requests_per_minute": 60, "burst_capacity": 10},
                "per_user": {"requests_per_minute": 120, "burst_capacity": 30},
            },
            "sandbox_security": {
                "resource_limits": {
                    "cpu_percent": 80.0,
                    "memory_mb": 512,
                    "disk_mb": 100,
                    "execution_time_seconds": 60,
                    "network_enabled": False,
                    "max_processes": 5,
                    "max_threads": 10,
                    "max_file_descriptors": 100,
                }
            },
            "input_validation": {
                "max_string_length": 10000,
                "max_json_size": 1048576,
                "max_json_depth": 10,
                "injection_detection": {"enabled": True, "strict_mode": False},
            },
            "encryption": {"level": "standard", "key_derivation_iterations": 100000},
            "audit_logging": {
                "enabled": True,
                "log_directory": "logs/security",
                "max_recent_events": 1000,
            },
            "malicious_code_detection": {"enabled": True, "max_threat_level": "medium"},
        }

    def initialize(self) -> bool:
        """初始化所有安全组件"""
        try:
            logger.info("开始初始化安全系统")

            # 初始化审计日志
            self._initialize_audit_logging()

            # 初始化JWT认证
            self._initialize_jwt_auth()

            # 初始化速率限制
            self._initialize_rate_limiting()

            # 初始化输入验证
            self._initialize_input_validation()

            # 初始化数据加密
            self._initialize_data_encryption()

            # 初始化恶意代码检测
            self._initialize_malicious_code_detection()

            # 初始化沙盒安全
            self._initialize_sandbox_security()

            self.initialized = True
            logger.info("安全系统初始化完成")

            # 记录初始化事件
            audit_logger = get_security_audit_logger()
            audit_logger.log_security_event(
                "security_system_initialized",
                "info",
                "安全系统初始化完成",
                {
                    "components": [
                        "audit_logging",
                        "jwt_auth",
                        "rate_limiting",
                        "input_validation",
                        "data_encryption",
                        "malicious_code_detection",
                        "sandbox_security",
                    ]
                },
                result="success",
            )

            return True

        except Exception as e:
            logger.error(f"安全系统初始化失败: {e}")
            return False

    def _initialize_audit_logging(self):
        """初始化审计日志"""
        audit_config = self.config.get("audit_logging", {})

        if audit_config.get("enabled", True):
            audit_logger = get_security_audit_logger()
            logger.info("审计日志系统已初始化")

    def _initialize_jwt_auth(self):
        """初始化JWT认证"""
        jwt_config = self.config.get("jwt", {})

        jwt_auth = get_jwt_authenticator()

        # 更新配置
        if "secret_key" in jwt_config:
            jwt_auth.secret_key = jwt_config["secret_key"]
            jwt_auth.fernet = jwt_auth._derive_fernet_key(jwt_auth.secret_key)

        if "access_token_expire_minutes" in jwt_config:
            jwt_auth.access_token_expire_minutes = jwt_config[
                "access_token_expire_minutes"
            ]

        if "refresh_token_expire_days" in jwt_config:
            jwt_auth.refresh_token_expire_days = jwt_config["refresh_token_expire_days"]

        if "max_failed_attempts" in jwt_config:
            jwt_auth.max_failed_attempts = jwt_config["max_failed_attempts"]

        if "lockout_duration_minutes" in jwt_config:
            jwt_auth.lockout_duration_minutes = jwt_config["lockout_duration_minutes"]

        logger.info("JWT认证系统已初始化")

    def _initialize_rate_limiting(self):
        """初始化速率限制"""
        rate_config = self.config.get("rate_limiting", {})

        rate_limiter = get_rate_limiter()

        # 更新默认限制
        if "global" in rate_config:
            global_config = rate_config["global"]
            rate_limiter.default_limits["global"].requests = global_config.get(
                "requests_per_minute", 100
            )
            rate_limiter.default_limits["global"].window = 60
            rate_limiter.default_limits["global"].burst = global_config.get(
                "burst_capacity", 20
            )

        if "per_ip" in rate_config:
            ip_config = rate_config["per_ip"]
            rate_limiter.default_limits["per_ip"].requests = ip_config.get(
                "requests_per_minute", 60
            )
            rate_limiter.default_limits["per_ip"].burst = ip_config.get(
                "burst_capacity", 10
            )

        if "per_user" in rate_config:
            user_config = rate_config["per_user"]
            rate_limiter.default_limits["per_user"].requests = user_config.get(
                "requests_per_minute", 120
            )
            rate_limiter.default_limits["per_user"].burst = user_config.get(
                "burst_capacity", 30
            )

        # 更新端点限制
        if "endpoints" in rate_config:
            for endpoint, config in rate_config["endpoints"].items():
                from ..security.rate_limiter import RateLimit

                rate_limiter.endpoint_limits[endpoint] = RateLimit(
                    requests=config.get("requests_per_minute", 30),
                    window=60,
                    burst=config.get("burst_capacity", 5),
                )

        logger.info("速率限制系统已初始化")

    def _initialize_input_validation(self):
        """初始化输入验证"""
        validation_config = self.config.get("input_validation", {})

        input_validator = get_input_validator()

        # 可以根据配置调整验证器设置
        logger.info("输入验证系统已初始化")

    def _initialize_data_encryption(self):
        """初始化数据加密"""
        encryption_config = self.config.get("encryption", {})

        data_encryption = get_data_encryption()
        sensitive_masker = get_sensitive_data_masker()

        # 更新加密配置
        if "key_derivation_iterations" in encryption_config:
            data_encryption.config.key_derivation_iterations = encryption_config[
                "key_derivation_iterations"
            ]

        logger.info("数据加密系统已初始化")

    def _initialize_malicious_code_detection(self):
        """初始化恶意代码检测"""
        detection_config = self.config.get("malicious_code_detection", {})

        if detection_config.get("enabled", True):
            detector = get_malicious_code_detector()

            # 添加自定义模式
            custom_patterns = detection_config.get("custom_patterns", [])
            for pattern_config in custom_patterns:
                # 这里可以添加自定义模式的逻辑
                pass

            logger.info("恶意代码检测系统已初始化")

    def _initialize_sandbox_security(self):
        """初始化沙盒安全"""
        sandbox_config = self.config.get("sandbox_security", {})

        if sandbox_config:
            resource_config = sandbox_config.get("resource_limits", {})

            resource_limits = ResourceLimit(
                cpu_percent=resource_config.get("cpu_percent", 80.0),
                memory_mb=resource_config.get("memory_mb", 512),
                disk_mb=resource_config.get("disk_mb", 100),
                execution_time_seconds=resource_config.get(
                    "execution_time_seconds", 60
                ),
                network_enabled=resource_config.get("network_enabled", False),
                max_processes=resource_config.get("max_processes", 5),
                max_threads=resource_config.get("max_threads", 10),
                max_file_descriptors=resource_config.get("max_file_descriptors", 100),
            )

            initialize_sandbox_security(resource_limits)
            logger.info("沙盒安全系统已初始化")

    def get_security_status(self) -> Dict[str, Any]:
        """获取安全系统状态"""
        if not self.initialized:
            return {"status": "not_initialized"}

        try:
            # 获取各组件状态
            rate_limiter = get_rate_limiter()
            audit_logger = get_security_audit_logger()
            sandbox_manager = get_sandbox_security_manager()

            return {
                "status": "initialized",
                "components": {
                    "jwt_auth": {"status": "active"},
                    "rate_limiting": {
                        "status": "active",
                        "statistics": rate_limiter.get_statistics(hours=1),
                    },
                    "input_validation": {"status": "active"},
                    "data_encryption": {"status": "active"},
                    "audit_logging": {
                        "status": "active",
                        "statistics": audit_logger.get_security_statistics(hours=24),
                    },
                    "malicious_code_detection": {"status": "active"},
                    "sandbox_security": {
                        "status": "active",
                        "summary": sandbox_manager.get_security_summary(),
                    },
                },
            }
        except Exception as e:
            logger.error(f"获取安全状态失败: {e}")
            return {"status": "error", "error": str(e)}

    def shutdown(self):
        """关闭安全系统"""
        try:
            # 关闭沙盒安全监控
            from .sandbox_security import shutdown_sandbox_security

            shutdown_sandbox_security()

            self.initialized = False
            logger.info("安全系统已关闭")

        except Exception as e:
            logger.error(f"关闭安全系统失败: {e}")


# 全局安全管理器实例
_security_manager = None


def get_security_manager() -> SecurityManager:
    """获取全局安全管理器"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


def initialize_security_system() -> bool:
    """初始化安全系统"""
    security_manager = get_security_manager()
    return security_manager.initialize()


def shutdown_security_system():
    """关闭安全系统"""
    security_manager = get_security_manager()
    security_manager.shutdown()
