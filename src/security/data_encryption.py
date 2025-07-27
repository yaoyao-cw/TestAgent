#!/usr/bin/env python3
"""
数据加密和敏感信息脱敏

提供数据加密、解密和敏感信息脱敏功能
"""

import base64
import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..config.logging_config import get_logger
from .audit_logger import SecurityAuditLogger, get_security_audit_logger

logger = get_logger("data_encryption")


class EncryptionLevel(Enum):
    """加密级别"""

    NONE = "none"
    BASIC = "basic"
    STANDARD = "standard"
    HIGH = "high"


@dataclass
class EncryptionConfig:
    """加密配置"""

    level: EncryptionLevel
    key_derivation_iterations: int = 100000
    salt_length: int = 32
    key_length: int = 32


class DataEncryption:
    """数据加密器"""

    def __init__(self, master_key: Optional[str] = None):
        self.audit_logger = get_security_audit_logger()

        # 主密钥
        self.master_key = master_key or self._generate_master_key()

        # Fernet实例（用于对称加密）
        self.fernet = Fernet(self._derive_fernet_key(self.master_key))

        # 加密配置
        self.config = EncryptionConfig(EncryptionLevel.STANDARD)

        # 密钥存储（实际应用中应该使用安全的密钥管理系统）
        self.derived_keys: Dict[str, bytes] = {}

    def _generate_master_key(self) -> str:
        """生成主密钥"""
        key = secrets.token_urlsafe(32)

        self.audit_logger.log_security_event(
            "master_key_generated",
            "info",
            "主密钥已生成",
            {"key_length": len(key)},
            result="success",
        )

        return key

    def _derive_fernet_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """派生Fernet密钥"""
        if salt is None:
            salt = b"testagent_default_salt"  # 实际应用中应该使用随机盐

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.config.key_derivation_iterations,
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def derive_key(self, context: str, salt: Optional[bytes] = None) -> bytes:
        """为特定上下文派生密钥"""
        if context in self.derived_keys:
            return self.derived_keys[context]

        if salt is None:
            salt = hashlib.sha256(context.encode()).digest()[:16]

        key = self._derive_fernet_key(f"{self.master_key}:{context}", salt)
        self.derived_keys[context] = key

        return key

    def encrypt_data(self, data: Union[str, bytes], context: str = "default") -> str:
        """加密数据"""
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            # 根据上下文使用不同的密钥
            if context != "default":
                key = self.derive_key(context)
                fernet = Fernet(key)
            else:
                fernet = self.fernet

            encrypted_data = fernet.encrypt(data)
            encoded_data = base64.urlsafe_b64encode(encrypted_data).decode("utf-8")

            self.audit_logger.log_security_event(
                "data_encrypted",
                "info",
                f"数据已加密: {context}",
                {
                    "context": context,
                    "data_length": len(data),
                    "encrypted_length": len(encoded_data),
                },
                result="success",
            )

            return encoded_data

        except Exception as e:
            self.audit_logger.log_security_event(
                "encryption_failed",
                "error",
                f"数据加密失败: {str(e)}",
                {"context": context, "error": str(e)},
                result="failure",
            )
            raise

    def decrypt_data(self, encrypted_data: str, context: str = "default") -> bytes:
        """解密数据"""
        try:
            # 解码base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode("utf-8"))

            # 根据上下文使用不同的密钥
            if context != "default":
                key = self.derive_key(context)
                fernet = Fernet(key)
            else:
                fernet = self.fernet

            decrypted_data = fernet.decrypt(encrypted_bytes)

            self.audit_logger.log_security_event(
                "data_decrypted",
                "info",
                f"数据已解密: {context}",
                {
                    "context": context,
                    "encrypted_length": len(encrypted_data),
                    "decrypted_length": len(decrypted_data),
                },
                result="success",
            )

            return decrypted_data

        except Exception as e:
            self.audit_logger.log_security_event(
                "decryption_failed",
                "error",
                f"数据解密失败: {str(e)}",
                {"context": context, "error": str(e)},
                result="failure",
            )
            raise

    def encrypt_dict(
        self, data_dict: Dict[str, Any], sensitive_keys: List[str]
    ) -> Dict[str, Any]:
        """加密字典中的敏感字段"""
        encrypted_dict = data_dict.copy()

        for key in sensitive_keys:
            if key in encrypted_dict:
                value = encrypted_dict[key]
                if value is not None:
                    encrypted_dict[key] = self.encrypt_data(
                        str(value), f"dict_field_{key}"
                    )

        return encrypted_dict

    def decrypt_dict(
        self, encrypted_dict: Dict[str, Any], sensitive_keys: List[str]
    ) -> Dict[str, Any]:
        """解密字典中的敏感字段"""
        decrypted_dict = encrypted_dict.copy()

        for key in sensitive_keys:
            if key in decrypted_dict:
                encrypted_value = decrypted_dict[key]
                if encrypted_value is not None:
                    try:
                        decrypted_bytes = self.decrypt_data(
                            encrypted_value, f"dict_field_{key}"
                        )
                        decrypted_dict[key] = decrypted_bytes.decode("utf-8")
                    except Exception as e:
                        logger.warning(f"解密字段 {key} 失败: {e}")
                        decrypted_dict[key] = "[DECRYPTION_FAILED]"

        return decrypted_dict

    def hash_data(self, data: str, salt: Optional[str] = None) -> str:
        """哈希数据（不可逆）"""
        if salt is None:
            salt = secrets.token_hex(16)

        combined = f"{data}:{salt}"
        hash_obj = hashlib.sha256(combined.encode())
        hashed = hash_obj.hexdigest()

        return f"{salt}:{hashed}"

    def verify_hash(self, data: str, hashed_data: str) -> bool:
        """验证哈希"""
        try:
            salt, expected_hash = hashed_data.split(":", 1)
            combined = f"{data}:{salt}"
            actual_hash = hashlib.sha256(combined.encode()).hexdigest()
            return actual_hash == expected_hash
        except Exception:
            return False

    def rotate_keys(self):
        """轮换密钥"""
        old_master_key = self.master_key

        # 生成新的主密钥
        self.master_key = self._generate_master_key()
        self.fernet = Fernet(self._derive_fernet_key(self.master_key))

        # 清空派生密钥缓存
        self.derived_keys.clear()

        self.audit_logger.log_security_event(
            "keys_rotated",
            "info",
            "加密密钥已轮换",
            {"old_key_hash": hashlib.sha256(old_master_key.encode()).hexdigest()[:16]},
            result="success",
        )

        logger.info("加密密钥已轮换")


class SensitiveDataMasker:
    """敏感数据脱敏器"""

    def __init__(self):
        self.audit_logger = get_security_audit_logger()

        # 敏感数据模式
        self.patterns = {
            "email": {
                "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "replacement": lambda m: self._mask_email(m.group(0)),
            },
            "phone": {
                "pattern": r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
                "replacement": lambda m: f"***-***-{m.group(3)}",
            },
            "ssn": {
                "pattern": r"\b\d{3}-?\d{2}-?\d{4}\b",
                "replacement": "***-**-****",
            },
            "credit_card": {
                "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
                "replacement": lambda m: f"****-****-****-{m.group(0)[-4:]}",
            },
            "ip_address": {
                "pattern": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
                "replacement": lambda m: ".".join(m.group(0).split(".")[:-1] + ["***"]),
            },
            "api_key": {
                "pattern": r"\b[A-Za-z0-9]{32,}\b",
                "replacement": lambda m: f"{m.group(0)[:8]}{'*' * (len(m.group(0)) - 12)}{m.group(0)[-4:]}",
            },
            "password": {
                "pattern": r"(?i)(password|pwd|pass)\s*[:=]\s*[^\s]+",
                "replacement": lambda m: f"{m.group(0).split(':')[0] if ':' in m.group(0) else m.group(0).split('=')[0]}:***",
            },
            "token": {
                "pattern": r"(?i)(token|jwt|bearer)\s*[:=]\s*[^\s]+",
                "replacement": lambda m: f"{m.group(0).split(':')[0] if ':' in m.group(0) else m.group(0).split('=')[0]}:***",
            },
        }

    def _mask_email(self, email: str) -> str:
        """脱敏邮箱地址"""
        local, domain = email.split("@")
        if len(local) <= 2:
            masked_local = "*" * len(local)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]

        domain_parts = domain.split(".")
        if len(domain_parts[0]) <= 2:
            masked_domain = "*" * len(domain_parts[0])
        else:
            masked_domain = (
                domain_parts[0][0]
                + "*" * (len(domain_parts[0]) - 2)
                + domain_parts[0][-1]
            )

        return f"{masked_local}@{masked_domain}.{'.'.join(domain_parts[1:])}"

    def mask_text(self, text: str, patterns: Optional[List[str]] = None) -> str:
        """脱敏文本中的敏感信息"""
        if patterns is None:
            patterns = list(self.patterns.keys())

        masked_text = text
        masked_count = 0

        for pattern_name in patterns:
            if pattern_name in self.patterns:
                pattern_info = self.patterns[pattern_name]
                pattern = pattern_info["pattern"]
                replacement = pattern_info["replacement"]

                # 计算匹配数量
                matches = re.findall(pattern, masked_text)
                if matches:
                    masked_count += len(matches)

                    # 执行替换
                    if callable(replacement):
                        masked_text = re.sub(pattern, replacement, masked_text)
                    else:
                        masked_text = re.sub(pattern, replacement, masked_text)

        if masked_count > 0:
            self.audit_logger.log_security_event(
                "sensitive_data_masked",
                "info",
                f"敏感数据已脱敏: {masked_count} 项",
                {
                    "masked_count": masked_count,
                    "patterns_used": patterns,
                    "original_length": len(text),
                    "masked_length": len(masked_text),
                },
                result="success",
            )

        return masked_text

    def mask_dict(
        self, data_dict: Dict[str, Any], sensitive_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """脱敏字典中的敏感数据"""
        if sensitive_keys is None:
            # 默认敏感键名
            sensitive_keys = [
                "password",
                "pwd",
                "pass",
                "secret",
                "token",
                "key",
                "email",
                "phone",
                "ssn",
                "credit_card",
                "api_key",
            ]

        masked_dict = {}

        for key, value in data_dict.items():
            if isinstance(value, dict):
                # 递归处理嵌套字典
                masked_dict[key] = self.mask_dict(value, sensitive_keys)
            elif isinstance(value, list):
                # 处理列表
                masked_dict[key] = [
                    (
                        self.mask_dict(item, sensitive_keys)
                        if isinstance(item, dict)
                        else (
                            self.mask_text(str(item)) if isinstance(item, str) else item
                        )
                    )
                    for item in value
                ]
            elif isinstance(value, str):
                # 检查键名是否敏感
                if any(
                    sensitive_key.lower() in key.lower()
                    for sensitive_key in sensitive_keys
                ):
                    masked_dict[key] = "***"
                else:
                    # 脱敏文本内容
                    masked_dict[key] = self.mask_text(value)
            else:
                masked_dict[key] = value

        return masked_dict

    def mask_json(
        self, json_str: str, sensitive_keys: Optional[List[str]] = None
    ) -> str:
        """脱敏JSON字符串"""
        try:
            import json

            data = json.loads(json_str)
            masked_data = self.mask_dict(data, sensitive_keys)
            return json.dumps(masked_data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            # 如果不是有效JSON，直接脱敏文本
            return self.mask_text(json_str)

    def mask_log_message(self, message: str) -> str:
        """脱敏日志消息"""
        # 专门用于日志的脱敏，更加严格
        log_patterns = [
            "email",
            "phone",
            "ssn",
            "credit_card",
            "ip_address",
            "api_key",
            "password",
            "token",
        ]
        return self.mask_text(message, log_patterns)

    def add_custom_pattern(
        self, name: str, pattern: str, replacement: Union[str, callable]
    ):
        """添加自定义脱敏模式"""
        self.patterns[name] = {"pattern": pattern, "replacement": replacement}

        self.audit_logger.log_security_event(
            "custom_masking_pattern_added",
            "info",
            f"添加自定义脱敏模式: {name}",
            {"pattern_name": name},
            result="success",
        )

    def remove_pattern(self, name: str):
        """移除脱敏模式"""
        if name in self.patterns:
            del self.patterns[name]

            self.audit_logger.log_security_event(
                "masking_pattern_removed",
                "info",
                f"移除脱敏模式: {name}",
                {"pattern_name": name},
                result="success",
            )

    def get_masking_statistics(self) -> Dict[str, Any]:
        """获取脱敏统计信息"""
        return {
            "available_patterns": list(self.patterns.keys()),
            "pattern_count": len(self.patterns),
            "patterns": {
                name: {"pattern": info["pattern"]}
                for name, info in self.patterns.items()
            },
        }


# 全局实例
_data_encryption = None
_sensitive_data_masker = None


def get_data_encryption() -> DataEncryption:
    """获取全局数据加密器"""
    global _data_encryption
    if _data_encryption is None:
        _data_encryption = DataEncryption()
    return _data_encryption


def get_sensitive_data_masker() -> SensitiveDataMasker:
    """获取全局敏感数据脱敏器"""
    global _sensitive_data_masker
    if _sensitive_data_masker is None:
        _sensitive_data_masker = SensitiveDataMasker()
    return _sensitive_data_masker


# 便捷函数
def encrypt_sensitive_data(data: str, context: str = "default") -> str:
    """加密敏感数据的便捷函数"""
    return get_data_encryption().encrypt_data(data, context)


def decrypt_sensitive_data(encrypted_data: str, context: str = "default") -> str:
    """解密敏感数据的便捷函数"""
    decrypted_bytes = get_data_encryption().decrypt_data(encrypted_data, context)
    return decrypted_bytes.decode("utf-8")


def mask_sensitive_text(text: str) -> str:
    """脱敏敏感文本的便捷函数"""
    return get_sensitive_data_masker().mask_text(text)
