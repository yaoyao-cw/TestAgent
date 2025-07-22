"""TestAgent异常定义模块"""

from typing import Optional, Any, Dict


class TestAgentException(Exception):
    """TestAgent基础异常类"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class ConfigurationException(TestAgentException):
    """配置异常"""
    pass


class PlanningException(TestAgentException):
    """规划阶段异常"""
    pass


class RAGServiceException(TestAgentException):
    """RAG服务异常"""
    pass


class CodeExecutionException(TestAgentException):
    """代码执行异常"""
    pass


class LLMServiceException(TestAgentException):
    """LLM服务异常"""
    pass


class MCPIntegrationException(TestAgentException):
    """MCP集成异常"""
    pass


class DocumentProcessingException(TestAgentException):
    """文档处理异常"""
    pass


class ValidationException(TestAgentException):
    """数据验证异常"""
    pass


class WorkflowException(TestAgentException):
    """工作流异常"""
    pass


class ToolException(TestAgentException):
    """工具执行异常"""
    pass


class APIException(TestAgentException):
    """API异常"""
    
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.status_code = status_code