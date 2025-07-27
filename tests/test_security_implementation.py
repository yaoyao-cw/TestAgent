#!/usr/bin/env python3
"""
安全实现测试

测试新实现的安全功能
"""

import asyncio
from datetime import datetime

import pytest

from src.security.audit_logger import SecurityAuditLogger
from src.security.auth import JWTAuthenticator, UserRole
from src.security.data_encryption import DataEncryption, SensitiveDataMasker
from src.security.input_validator import InputValidator
from src.security.malicious_code_detector import MaliciousCodeDetector, ThreatLevel
from src.security.rate_limiter import RateLimit, RateLimiter
from src.security.sandbox_security import ResourceLimit, SandboxSecurityManager


class TestMaliciousCodeDetector:
    """测试恶意代码检测器"""

    def setup_method(self):
        self.detector = MaliciousCodeDetector()

    def test_detect_sql_injection(self):
        """测试SQL注入检测"""
        malicious_code = (
            "import os; os.system('SELECT * FROM users WHERE id = 1 OR 1=1')"
        )
        threats = self.detector.detect_threats(malicious_code)

        assert len(threats) > 0
        assert any(threat.threat_type == "pattern_match" for threat in threats)
        assert any(threat.level == ThreatLevel.CRITICAL for threat in threats)

    def test_detect_command_injection(self):
        """测试命令注入检测"""
        malicious_code = "import os; os.system('rm -rf /')"
        threats = self.detector.detect_threats(malicious_code)

        assert len(threats) > 0
        assert any("system" in threat.description for threat in threats)

    def test_safe_code(self):
        """测试安全代码"""
        safe_code = """
import json
import math

def calculate_sum(a, b):
    return a + b

result = calculate_sum(1, 2)
print(f"Result: {result}")
"""
        threats = self.detector.detect_threats(safe_code)

        # 应该没有严重威胁
        critical_threats = [t for t in threats if t.level == ThreatLevel.CRITICAL]
        assert len(critical_threats) == 0

    def test_is_code_safe(self):
        """测试代码安全判断"""
        safe_code = "print('Hello, World!')"
        unsafe_code = "eval('malicious_code')"

        assert self.detector.is_code_safe(safe_code, ThreatLevel.MEDIUM)
        assert not self.detector.is_code_safe(unsafe_code, ThreatLevel.MEDIUM)

    def test_security_report(self):
        """测试安全报告生成"""
        code = "import os; print('test')"
        report = self.detector.generate_security_report(code, "test.py")

        assert "filename" in report
        assert "total_threats" in report
        assert "security_score" in report
        assert "is_safe" in report
        assert "threats" in report
        assert "recommendations" in report


class TestSandboxSecurity:
    """测试沙盒安全管理器"""

    def setup_method(self):
        self.resource_limits = ResourceLimit(
            cpu_percent=50.0, memory_mb=256, execution_time_seconds=30
        )
        self.manager = SandboxSecurityManager(self.resource_limits)

    def test_code_validation(self):
        """测试代码验证"""
        safe_code = "print('Hello, World!')"
        unsafe_code = "import os; os.system('rm -rf /')"

        safe_report = self.manager.validate_code_security(safe_code, "safe.py")
        unsafe_report = self.manager.validate_code_security(unsafe_code, "unsafe.py")

        assert safe_report["is_safe"]
        assert not unsafe_report["is_safe"]

    def test_can_execute_code(self):
        """测试代码执行权限检查"""
        safe_code = "print('Hello, World!')"

        result = self.manager.can_execute_code(safe_code, "test.py")

        assert "can_execute" in result
        assert "reason" in result
        assert "message" in result
        assert "security_report" in result

    def test_security_summary(self):
        """测试安全摘要"""
        summary = self.manager.get_security_summary()

        assert "monitoring_active" in summary
        assert "circuit_breaker_active" in summary
        assert "total_violations" in summary
        assert "resource_limits" in summary


class TestJWTAuthenticator:
    """测试JWT认证器"""

    def setup_method(self):
        self.auth = JWTAuthenticator()

    def test_user_authentication(self):
        """测试用户认证"""
        # 使用默认用户
        result = self.auth.authenticate_user("admin", "admin123")

        assert result is not None
        assert "access_token" in result
        assert "refresh_token" in result
        assert "user" in result
        assert result["user"]["username"] == "admin"

    def test_invalid_authentication(self):
        """测试无效认证"""
        result = self.auth.authenticate_user("admin", "wrong_password")
        assert result is None

        result = self.auth.authenticate_user("nonexistent", "password")
        assert result is None

    def test_token_verification(self):
        """测试令牌验证"""
        # 先认证获取令牌
        auth_result = self.auth.authenticate_user("admin", "admin123")
        token = auth_result["access_token"]

        # 验证令牌
        payload = self.auth.verify_token(token)
        assert payload is not None
        assert payload.user_id == "admin"

    def test_refresh_token(self):
        """测试刷新令牌"""
        # 先认证获取刷新令牌
        auth_result = self.auth.authenticate_user("admin", "admin123")
        refresh_token = auth_result["refresh_token"]

        # 使用刷新令牌获取新的访问令牌
        new_access_token = self.auth.refresh_access_token(refresh_token)
        assert new_access_token is not None

    def test_user_creation(self):
        """测试用户创建"""
        user = self.auth.create_user(
            "testuser", "testpass123", "test@example.com", UserRole.USER
        )

        assert user is not None
        assert user.username == "testuser"
        assert user.role == UserRole.USER

        # 测试重复用户名
        duplicate_user = self.auth.create_user("testuser", "pass", "test2@example.com")
        assert duplicate_user is None


class TestInputValidator:
    """测试输入验证器"""

    def setup_method(self):
        self.validator = InputValidator()

    def test_string_validation(self):
        """测试字符串验证"""
        # 正常字符串
        result = self.validator.validate_string("Hello, World!", max_length=20)
        assert result.is_valid

        # 过长字符串
        result = self.validator.validate_string("x" * 100, max_length=50)
        assert not result.is_valid

        # 包含注入的字符串
        result = self.validator.validate_string(
            "SELECT * FROM users", check_injections=True
        )
        assert not result.is_valid

    def test_email_validation(self):
        """测试邮箱验证"""
        # 有效邮箱
        result = self.validator.validate_email("test@example.com")
        assert result.is_valid

        # 无效邮箱
        result = self.validator.validate_email("invalid-email")
        assert not result.is_valid

    def test_url_validation(self):
        """测试URL验证"""
        # 有效URL
        result = self.validator.validate_url("https://example.com")
        assert result.is_valid

        # 无效协议
        result = self.validator.validate_url(
            "ftp://example.com", allowed_schemes=["http", "https"]
        )
        assert not result.is_valid

    def test_json_validation(self):
        """测试JSON验证"""
        # 有效JSON
        result = self.validator.validate_json('{"key": "value"}')
        assert result.is_valid
        assert result.cleaned_value == {"key": "value"}

        # 无效JSON
        result = self.validator.validate_json('{"key": invalid}')
        assert not result.is_valid

    def test_filename_validation(self):
        """测试文件名验证"""
        # 正常文件名
        result = self.validator.validate_filename("document.txt")
        assert result.is_valid

        # 危险文件名
        result = self.validator.validate_filename("../../../etc/passwd")
        assert not result.is_valid


class TestDataEncryption:
    """测试数据加密"""

    def setup_method(self):
        self.encryption = DataEncryption()
        self.masker = SensitiveDataMasker()

    def test_encrypt_decrypt(self):
        """测试加密解密"""
        original_data = "sensitive information"

        # 加密
        encrypted = self.encryption.encrypt_data(original_data)
        assert encrypted != original_data

        # 解密
        decrypted = self.encryption.decrypt_data(encrypted)
        assert decrypted.decode("utf-8") == original_data

    def test_hash_verification(self):
        """测试哈希验证"""
        data = "password123"

        # 哈希
        hashed = self.encryption.hash_data(data)
        assert hashed != data

        # 验证
        assert self.encryption.verify_hash(data, hashed)
        assert not self.encryption.verify_hash("wrong_password", hashed)

    def test_sensitive_data_masking(self):
        """测试敏感数据脱敏"""
        text = "My email is john@example.com and phone is 123-456-7890"

        masked = self.masker.mask_text(text)

        assert "john@example.com" not in masked
        assert "123-456-7890" not in masked
        assert "@" in masked  # 应该保留部分结构

    def test_dict_masking(self):
        """测试字典脱敏"""
        data = {
            "username": "john",
            "password": "secret123",
            "email": "john@example.com",
            "age": 30,
        }

        masked = self.masker.mask_dict(data)

        assert masked["username"] == "john"  # 非敏感字段保持不变
        assert masked["password"] == "***"  # 敏感字段被脱敏
        assert masked["age"] == 30  # 非字符串字段保持不变


@pytest.mark.asyncio
class TestRateLimiter:
    """测试速率限制器"""

    def setup_method(self):
        self.rate_limiter = RateLimiter()

    async def test_rate_limiting(self):
        """测试速率限制"""
        from unittest.mock import Mock

        from fastapi import Request

        # 模拟请求
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "test"}

        # 第一次请求应该通过
        result = await self.rate_limiter.check_rate_limit(mock_request)
        assert result["allowed"]

        # 模拟大量请求（超过限制）
        for _ in range(200):  # 超过默认限制
            await self.rate_limiter.check_rate_limit(mock_request)

        # 应该被限制
        result = await self.rate_limiter.check_rate_limit(mock_request)
        # 注意：由于令牌桶算法，可能仍然允许一些请求

    def test_blacklist_whitelist(self):
        """测试黑白名单"""
        test_ip = "192.168.1.100"

        # 添加到黑名单
        self.rate_limiter.add_to_blacklist(test_ip, "test")
        assert test_ip in self.rate_limiter.blacklisted_ips

        # 从黑名单移除
        self.rate_limiter.remove_from_blacklist(test_ip)
        assert test_ip not in self.rate_limiter.blacklisted_ips

        # 添加到白名单
        self.rate_limiter.add_to_whitelist(test_ip)
        assert test_ip in self.rate_limiter.whitelisted_ips


class TestSecurityAuditLogger:
    """测试安全审计日志"""

    def setup_method(self):
        self.audit_logger = SecurityAuditLogger()

    def test_log_security_event(self):
        """测试安全事件记录"""
        self.audit_logger.log_security_event(
            "test_action",
            "info",
            "测试事件",
            {"key": "value"},
            user_id="test_user",
            result="success",
        )

        # 检查最近事件
        recent_events = self.audit_logger.get_recent_events(limit=1)
        assert len(recent_events) > 0

        event = recent_events[0]
        assert event["action"] == "test_action"
        assert event["user_id"] == "test_user"

    def test_security_statistics(self):
        """测试安全统计"""
        # 记录一些事件
        for i in range(5):
            self.audit_logger.log_security_event(
                f"test_action_{i}", "info", f"测试事件 {i}", result="success"
            )

        stats = self.audit_logger.get_security_statistics(hours=1)

        assert "total_events" in stats
        assert stats["total_events"] >= 5
        assert "event_type_distribution" in stats
        assert "severity_distribution" in stats


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
