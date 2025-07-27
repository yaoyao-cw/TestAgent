#!/usr/bin/env python3
"""
TestAgent异常处理模块

定义系统中使用的所有自定义异常类型
"""

from typing import Any, Dict, Optional, List
from enum import Enum


class ErrorSeverity(Enum):
    """错误严重程度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""

    CONFIGURATION = "configuration"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    PROCESSING = "processing"
    STORAGE = "storage"
    EXTERNAL_SERVICE = "external_service"
    SYSTEM = "system"
    USER_INPUT = "user_input"


class TestAgentException(Exception):
    """TestAgent基础异常类"""

    def __init__(
        self,
        message: str,
        error_code: str = None,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Dict[str, Any] = None,
        suggestions: List[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.suggestions = suggestions or []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "details": self.details,
            "suggestions": self.suggestions,
        }


class ConfigurationError(TestAgentException):
    """配置错误"""

    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
        if config_key:
            self.details["config_key"] = config_key


class ValidationError(TestAgentException):
    """验证错误"""

    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )
        if field:
            self.details["field"] = field
        if value is not None:
            self.details["value"] = str(value)


class NetworkError(TestAgentException):
    """网络错误"""

    def __init__(
        self, message: str, url: str = None, status_code: int = None, **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
        if url:
            self.details["url"] = url
        if status_code:
            self.details["status_code"] = status_code


class AuthenticationError(TestAgentException):
    """认证错误"""

    def __init__(self, message: str, service: str = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
        if service:
            self.details["service"] = service


class ProcessingError(TestAgentException):
    """处理错误"""

    def __init__(self, message: str, operation: str = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.PROCESSING,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )
        if operation:
            self.details["operation"] = operation


class StorageError(TestAgentException):
    """存储错误"""

    def __init__(
        self, message: str, storage_type: str = None, path: str = None, **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.STORAGE,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
        if storage_type:
            self.details["storage_type"] = storage_type
        if path:
            self.details["path"] = path


class ExternalServiceError(TestAgentException):
    """外部服务错误"""

    def __init__(self, message: str, service: str = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
        if service:
            self.details["service"] = service


class LLMError(ExternalServiceError):
    """LLM服务错误"""

    def __init__(self, message: str, provider: str = None, model: str = None, **kwargs):
        super().__init__(message, service="llm", **kwargs)
        if provider:
            self.details["provider"] = provider
        if model:
            self.details["model"] = model


class RAGError(ProcessingError):
    """RAG服务错误"""

    def __init__(self, message: str, operation: str = None, **kwargs):
        super().__init__(
            message, operation=f"rag_{operation}" if operation else "rag", **kwargs
        )


class MCPError(ExternalServiceError):
    """MCP工具错误"""

    def __init__(self, message: str, tool_name: str = None, **kwargs):
        super().__init__(message, service="mcp", **kwargs)
        if tool_name:
            self.details["tool_name"] = tool_name


class WorkflowError(ProcessingError):
    """工作流错误"""

    def __init__(self, message: str, node: str = None, step: str = None, **kwargs):
        super().__init__(message, operation="workflow", **kwargs)
        if node:
            self.details["node"] = node
        if step:
            self.details["step"] = step


class UserInputError(TestAgentException):
    """用户输入错误"""

    def __init__(self, message: str, input_type: str = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.USER_INPUT,
            severity=ErrorSeverity.LOW,
            **kwargs,
        )
        if input_type:
            self.details["input_type"] = input_type


class TimeoutError(TestAgentException):
    """超时错误"""

    def __init__(
        self,
        message: str,
        timeout_seconds: float = None,
        operation: str = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.PROCESSING,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds
        if operation:
            self.details["operation"] = operation


class ResourceError(TestAgentException):
    """资源错误"""

    def __init__(self, message: str, resource_type: str = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
        if resource_type:
            self.details["resource_type"] = resource_type


# 错误代码映射
ERROR_CODE_MAP = {
    "CONFIG_001": "配置文件不存在或无法读取",
    "CONFIG_002": "配置参数无效",
    "CONFIG_003": "必需的配置参数缺失",
    "NETWORK_001": "网络连接失败",
    "NETWORK_002": "请求超时",
    "NETWORK_003": "HTTP错误响应",
    "AUTH_001": "API密钥无效或缺失",
    "AUTH_002": "认证失败",
    "AUTH_003": "权限不足",
    "VALIDATION_001": "输入参数验证失败",
    "VALIDATION_002": "数据格式错误",
    "VALIDATION_003": "必需参数缺失",
    "PROCESSING_001": "数据处理失败",
    "PROCESSING_002": "任务执行失败",
    "PROCESSING_003": "结果解析失败",
    "STORAGE_001": "文件读取失败",
    "STORAGE_002": "文件写入失败",
    "STORAGE_003": "数据库操作失败",
    "LLM_001": "LLM服务不可用",
    "LLM_002": "模型调用失败",
    "LLM_003": "响应解析失败",
    "RAG_001": "文档解析失败",
    "RAG_002": "向量化失败",
    "RAG_003": "检索失败",
    "MCP_001": "MCP工具连接失败",
    "MCP_002": "MCP工具调用失败",
    "MCP_003": "MCP工具响应解析失败",
    "WORKFLOW_001": "工作流初始化失败",
    "WORKFLOW_002": "节点执行失败",
    "WORKFLOW_003": "状态转换失败",
}


def get_error_message(error_code: str) -> str:
    """根据错误代码获取错误消息"""
    return ERROR_CODE_MAP.get(error_code, "未知错误")


def create_error_from_code(
    error_code: str, details: Dict[str, Any] = None
) -> TestAgentException:
    """根据错误代码创建异常"""
    message = get_error_message(error_code)

    # 根据错误代码前缀确定异常类型
    if error_code.startswith("CONFIG_"):
        return ConfigurationError(message, error_code=error_code, details=details)
    elif error_code.startswith("NETWORK_"):
        return NetworkError(message, error_code=error_code, details=details)
    elif error_code.startswith("AUTH_"):
        return AuthenticationError(message, error_code=error_code, details=details)
    elif error_code.startswith("VALIDATION_"):
        return ValidationError(message, error_code=error_code, details=details)
    elif error_code.startswith("PROCESSING_"):
        return ProcessingError(message, error_code=error_code, details=details)
    elif error_code.startswith("STORAGE_"):
        return StorageError(message, error_code=error_code, details=details)
    elif error_code.startswith("LLM_"):
        return LLMError(message, error_code=error_code, details=details)
    elif error_code.startswith("RAG_"):
        return RAGError(message, error_code=error_code, details=details)
    elif error_code.startswith("MCP_"):
        return MCPError(message, error_code=error_code, details=details)
    elif error_code.startswith("WORKFLOW_"):
        return WorkflowError(message, error_code=error_code, details=details)
    else:
        return TestAgentException(message, error_code=error_code, details=details)
