#!/usr/bin/env python3
"""
输入验证器

提供全面的输入验证和清理功能，防止注入攻击和恶意输入
"""

import base64
import html
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

import bleach

from ..config.logging_config import get_logger
from .audit_logger import SecurityAuditLogger, get_security_audit_logger

logger = get_logger("input_validator")


class ValidationSeverity(Enum):
    """验证严重程度"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    cleaned_value: Any
    issues: List[Dict[str, Any]]
    severity: ValidationSeverity


class InputValidator:
    """输入验证器"""

    def __init__(self):
        self.audit_logger = get_security_audit_logger()

        # SQL注入模式
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(--|#|/\*|\*/)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
            r"(;\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC))",
            r"(\bUNION\s+(ALL\s+)?SELECT)",
        ]

        # XSS模式
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>.*?</iframe>",
            r"<object[^>]*>.*?</object>",
            r"<embed[^>]*>.*?</embed>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"<style[^>]*>.*?</style>",
        ]

        # 命令注入模式
        self.command_injection_patterns = [
            r"[;&|`$(){}[\]\\]",
            r"\b(cat|ls|pwd|whoami|id|uname|ps|netstat|ifconfig|ping|wget|curl|nc|telnet|ssh|ftp)\b",
            r"(>|<|>>|<<|\|)",
            r"(\$\(|\`)",
        ]

        # 路径遍历模式
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e\\",
            r"\.\.%2f",
            r"\.\.%5c",
        ]

        # LDAP注入模式
        self.ldap_injection_patterns = [
            r"[()&|!*]",
            r"\\[0-9a-fA-F]{2}",
        ]

        # 允许的HTML标签（用于富文本）
        self.allowed_html_tags = [
            "p",
            "br",
            "strong",
            "em",
            "u",
            "ol",
            "ul",
            "li",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "blockquote",
            "a",
            "img",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
        ]

        # 允许的HTML属性
        self.allowed_html_attributes = {
            "a": ["href", "title"],
            "img": ["src", "alt", "width", "height"],
            "table": ["class"],
            "th": ["scope"],
            "td": ["colspan", "rowspan"],
        }

    def validate_string(
        self,
        value: str,
        max_length: Optional[int] = None,
        min_length: Optional[int] = None,
        pattern: Optional[str] = None,
        allow_html: bool = False,
        check_injections: bool = True,
    ) -> ValidationResult:
        """验证字符串输入"""
        issues = []
        cleaned_value = value
        severity = ValidationSeverity.INFO

        # 基本类型检查
        if not isinstance(value, str):
            issues.append(
                {
                    "type": "type_error",
                    "message": f"期望字符串类型，得到 {type(value).__name__}",
                    "severity": "error",
                }
            )
            return ValidationResult(False, None, issues, ValidationSeverity.ERROR)

        # 长度检查
        if max_length and len(value) > max_length:
            issues.append(
                {
                    "type": "length_exceeded",
                    "message": f"字符串长度 {len(value)} 超过最大限制 {max_length}",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        if min_length and len(value) < min_length:
            issues.append(
                {
                    "type": "length_insufficient",
                    "message": f"字符串长度 {len(value)} 低于最小要求 {min_length}",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        # 模式匹配
        if pattern and not re.match(pattern, value):
            issues.append(
                {
                    "type": "pattern_mismatch",
                    "message": f"字符串不匹配要求的模式: {pattern}",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        # 注入攻击检查
        if check_injections:
            injection_issues = self._check_injections(value)
            issues.extend(injection_issues)
            if injection_issues:
                severity = ValidationSeverity.CRITICAL

        # HTML处理
        if allow_html:
            cleaned_value = self._sanitize_html(value)
        else:
            # 转义HTML字符
            cleaned_value = html.escape(value)

        # 记录严重问题
        if severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
            self.audit_logger.log_security_event(
                "input_validation_failed",
                severity.value,
                f"输入验证失败: {issues[0]['type'] if issues else 'unknown'}",
                {
                    "value_length": len(value),
                    "issues": issues,
                    "validation_type": "string",
                },
                result="failure",
            )

        is_valid = severity not in [
            ValidationSeverity.ERROR,
            ValidationSeverity.CRITICAL,
        ]
        return ValidationResult(is_valid, cleaned_value, issues, severity)

    def validate_email(self, email: str) -> ValidationResult:
        """验证邮箱地址"""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        result = self.validate_string(
            email,
            max_length=254,  # RFC 5321 限制
            pattern=email_pattern,
            check_injections=True,
        )

        if result.is_valid:
            # 额外的邮箱验证
            domain = email.split("@")[1] if "@" in email else ""
            if len(domain) > 253:  # 域名长度限制
                result.issues.append(
                    {
                        "type": "domain_too_long",
                        "message": "邮箱域名过长",
                        "severity": "error",
                    }
                )
                result.is_valid = False
                result.severity = ValidationSeverity.ERROR

        return result

    def validate_url(
        self, url: str, allowed_schemes: Optional[List[str]] = None
    ) -> ValidationResult:
        """验证URL"""
        if allowed_schemes is None:
            allowed_schemes = ["http", "https"]

        issues = []
        severity = ValidationSeverity.INFO

        try:
            parsed = urlparse(url)

            # 检查协议
            if parsed.scheme not in allowed_schemes:
                issues.append(
                    {
                        "type": "invalid_scheme",
                        "message": f"不允许的URL协议: {parsed.scheme}",
                        "severity": "error",
                    }
                )
                severity = ValidationSeverity.ERROR

            # 检查主机名
            if not parsed.netloc:
                issues.append(
                    {
                        "type": "missing_host",
                        "message": "URL缺少主机名",
                        "severity": "error",
                    }
                )
                severity = ValidationSeverity.ERROR

            # 检查危险字符
            dangerous_chars = ["<", ">", '"', "'", "`"]
            if any(char in url for char in dangerous_chars):
                issues.append(
                    {
                        "type": "dangerous_characters",
                        "message": "URL包含危险字符",
                        "severity": "warning",
                    }
                )
                severity = max(severity, ValidationSeverity.WARNING)

        except Exception as e:
            issues.append(
                {
                    "type": "parse_error",
                    "message": f"URL解析失败: {str(e)}",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        # 基本字符串验证
        string_result = self.validate_string(
            url, max_length=2048, check_injections=True
        )
        issues.extend(string_result.issues)
        severity = max(severity, string_result.severity)

        is_valid = severity not in [
            ValidationSeverity.ERROR,
            ValidationSeverity.CRITICAL,
        ]
        return ValidationResult(is_valid, url, issues, severity)

    def validate_json(
        self, json_str: str, max_depth: int = 10, max_size: int = 1024 * 1024
    ) -> ValidationResult:
        """验证JSON输入"""
        issues = []
        severity = ValidationSeverity.INFO
        cleaned_value = None

        # 大小检查
        if len(json_str) > max_size:
            issues.append(
                {
                    "type": "size_exceeded",
                    "message": f"JSON大小 {len(json_str)} 超过限制 {max_size}",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        try:
            # 解析JSON
            parsed_json = json.loads(json_str)

            # 深度检查
            depth = self._get_json_depth(parsed_json)
            if depth > max_depth:
                issues.append(
                    {
                        "type": "depth_exceeded",
                        "message": f"JSON深度 {depth} 超过限制 {max_depth}",
                        "severity": "error",
                    }
                )
                severity = ValidationSeverity.ERROR

            # 检查危险内容
            dangerous_content = self._check_json_content(parsed_json)
            if dangerous_content:
                issues.extend(dangerous_content)
                severity = ValidationSeverity.WARNING

            cleaned_value = parsed_json

        except json.JSONDecodeError as e:
            issues.append(
                {
                    "type": "json_decode_error",
                    "message": f"JSON解析失败: {str(e)}",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        is_valid = severity not in [
            ValidationSeverity.ERROR,
            ValidationSeverity.CRITICAL,
        ]
        return ValidationResult(is_valid, cleaned_value, issues, severity)

    def validate_file_upload(
        self,
        filename: str,
        content: bytes,
        allowed_extensions: Optional[List[str]] = None,
        max_size: int = 10 * 1024 * 1024,  # 10MB
        check_content: bool = True,
    ) -> ValidationResult:
        """验证文件上传"""
        issues = []
        severity = ValidationSeverity.INFO

        # 文件名验证
        filename_result = self.validate_filename(filename)
        issues.extend(filename_result.issues)
        severity = max(severity, filename_result.severity)

        # 扩展名检查
        if allowed_extensions:
            file_ext = filename.lower().split(".")[-1] if "." in filename else ""
            if file_ext not in [ext.lower() for ext in allowed_extensions]:
                issues.append(
                    {
                        "type": "invalid_extension",
                        "message": f"不允许的文件扩展名: {file_ext}",
                        "severity": "error",
                    }
                )
                severity = ValidationSeverity.ERROR

        # 大小检查
        if len(content) > max_size:
            issues.append(
                {
                    "type": "file_too_large",
                    "message": f"文件大小 {len(content)} 超过限制 {max_size}",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        # 内容检查
        if check_content:
            content_issues = self._check_file_content(content, filename)
            issues.extend(content_issues)
            if content_issues:
                severity = max(severity, ValidationSeverity.WARNING)

        is_valid = severity not in [
            ValidationSeverity.ERROR,
            ValidationSeverity.CRITICAL,
        ]
        return ValidationResult(is_valid, content, issues, severity)

    def validate_filename(self, filename: str) -> ValidationResult:
        """验证文件名"""
        issues = []
        severity = ValidationSeverity.INFO

        # 基本字符串验证
        string_result = self.validate_string(
            filename, max_length=255, check_injections=True
        )
        issues.extend(string_result.issues)
        severity = max(severity, string_result.severity)

        # 危险字符检查
        dangerous_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|", "\0"]
        found_dangerous = [char for char in dangerous_chars if char in filename]
        if found_dangerous:
            issues.append(
                {
                    "type": "dangerous_filename_chars",
                    "message": f"文件名包含危险字符: {found_dangerous}",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        # 保留名称检查（Windows）
        reserved_names = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        ]
        base_name = filename.split(".")[0].upper()
        if base_name in reserved_names:
            issues.append(
                {
                    "type": "reserved_filename",
                    "message": f"文件名使用了保留名称: {base_name}",
                    "severity": "warning",
                }
            )
            severity = max(severity, ValidationSeverity.WARNING)

        # 路径遍历检查
        if ".." in filename or filename.startswith("."):
            issues.append(
                {
                    "type": "path_traversal_attempt",
                    "message": "文件名可能包含路径遍历尝试",
                    "severity": "error",
                }
            )
            severity = ValidationSeverity.ERROR

        # 清理文件名
        cleaned_filename = re.sub(r"[^\w\-_\.]", "_", filename)

        is_valid = severity not in [
            ValidationSeverity.ERROR,
            ValidationSeverity.CRITICAL,
        ]
        return ValidationResult(is_valid, cleaned_filename, issues, severity)

    def _check_injections(self, value: str) -> List[Dict[str, Any]]:
        """检查各种注入攻击"""
        issues = []

        # SQL注入检查
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                issues.append(
                    {
                        "type": "sql_injection_attempt",
                        "message": f"检测到可能的SQL注入: {pattern}",
                        "severity": "critical",
                    }
                )
                break

        # XSS检查
        for pattern in self.xss_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                issues.append(
                    {
                        "type": "xss_attempt",
                        "message": f"检测到可能的XSS攻击: {pattern}",
                        "severity": "critical",
                    }
                )
                break

        # 命令注入检查
        for pattern in self.command_injection_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                issues.append(
                    {
                        "type": "command_injection_attempt",
                        "message": f"检测到可能的命令注入: {pattern}",
                        "severity": "critical",
                    }
                )
                break

        # 路径遍历检查
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                issues.append(
                    {
                        "type": "path_traversal_attempt",
                        "message": f"检测到可能的路径遍历: {pattern}",
                        "severity": "error",
                    }
                )
                break

        # LDAP注入检查
        for pattern in self.ldap_injection_patterns:
            if re.search(pattern, value):
                issues.append(
                    {
                        "type": "ldap_injection_attempt",
                        "message": f"检测到可能的LDAP注入: {pattern}",
                        "severity": "error",
                    }
                )
                break

        return issues

    def _sanitize_html(self, html_content: str) -> str:
        """清理HTML内容"""
        return bleach.clean(
            html_content,
            tags=self.allowed_html_tags,
            attributes=self.allowed_html_attributes,
            strip=True,
        )

    def _get_json_depth(self, obj: Any, current_depth: int = 0) -> int:
        """获取JSON对象的深度"""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._get_json_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._get_json_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth

    def _check_json_content(self, obj: Any) -> List[Dict[str, Any]]:
        """检查JSON内容中的危险元素"""
        issues = []

        def check_recursive(item, path=""):
            if isinstance(item, dict):
                for key, value in item.items():
                    current_path = f"{path}.{key}" if path else key

                    # 检查键名
                    if isinstance(key, str):
                        key_issues = self._check_injections(key)
                        for issue in key_issues:
                            issues.append(
                                {
                                    "type": f"json_key_{issue['type']}",
                                    "message": f"JSON键 '{current_path}' 中{issue['message']}",
                                    "severity": "warning",
                                }
                            )

                    check_recursive(value, current_path)

            elif isinstance(item, list):
                for i, value in enumerate(item):
                    check_recursive(value, f"{path}[{i}]")

            elif isinstance(item, str):
                string_issues = self._check_injections(item)
                for issue in string_issues:
                    issues.append(
                        {
                            "type": f"json_value_{issue['type']}",
                            "message": f"JSON值 '{path}' 中{issue['message']}",
                            "severity": "warning",
                        }
                    )

        check_recursive(obj)
        return issues

    def _check_file_content(
        self, content: bytes, filename: str
    ) -> List[Dict[str, Any]]:
        """检查文件内容"""
        issues = []

        # 检查文件头（魔数）
        file_signatures = {
            b"\x89PNG\r\n\x1a\n": "PNG",
            b"\xff\xd8\xff": "JPEG",
            b"GIF87a": "GIF87a",
            b"GIF89a": "GIF89a",
            b"%PDF": "PDF",
            b"PK\x03\x04": "ZIP",
            b"\x50\x4b\x03\x04": "ZIP",
        }

        detected_type = None
        for signature, file_type in file_signatures.items():
            if content.startswith(signature):
                detected_type = file_type
                break

        # 检查文件扩展名与实际类型是否匹配
        if detected_type:
            expected_extensions = {
                "PNG": [".png"],
                "JPEG": [".jpg", ".jpeg"],
                "GIF87a": [".gif"],
                "GIF89a": [".gif"],
                "PDF": [".pdf"],
                "ZIP": [".zip", ".jar", ".war"],
            }

            file_ext = "." + filename.lower().split(".")[-1] if "." in filename else ""
            expected = expected_extensions.get(detected_type, [])

            if expected and file_ext not in expected:
                issues.append(
                    {
                        "type": "file_type_mismatch",
                        "message": f"文件类型不匹配：检测到 {detected_type}，但扩展名为 {file_ext}",
                        "severity": "warning",
                    }
                )

        # 检查可执行文件头
        executable_signatures = [
            b"MZ",  # Windows PE
            b"\x7fELF",  # Linux ELF
            b"\xfe\xed\xfa\xce",  # Mach-O (macOS)
            b"\xfe\xed\xfa\xcf",  # Mach-O (macOS)
        ]

        for signature in executable_signatures:
            if content.startswith(signature):
                issues.append(
                    {
                        "type": "executable_file_detected",
                        "message": "检测到可执行文件",
                        "severity": "error",
                    }
                )
                break

        # 检查脚本内容
        try:
            text_content = content.decode("utf-8", errors="ignore")[
                :1024
            ]  # 只检查前1KB
            script_patterns = [
                r"<script[^>]*>",
                r"javascript:",
                r"eval\s*\(",
                r"exec\s*\(",
                r"system\s*\(",
                r"shell_exec\s*\(",
            ]

            for pattern in script_patterns:
                if re.search(pattern, text_content, re.IGNORECASE):
                    issues.append(
                        {
                            "type": "script_content_detected",
                            "message": f"检测到可能的脚本内容: {pattern}",
                            "severity": "warning",
                        }
                    )
                    break
        except:
            pass  # 忽略解码错误

        return issues

    def create_validator_middleware(self):
        """创建验证中间件"""

        async def validator_middleware(request, call_next):
            # 这里可以添加全局输入验证逻辑
            response = await call_next(request)
            return response

        return validator_middleware


# 全局输入验证器实例
_input_validator = None


def get_input_validator() -> InputValidator:
    """获取全局输入验证器"""
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator
