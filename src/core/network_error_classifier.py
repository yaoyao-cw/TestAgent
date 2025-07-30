#!/usr/bin/env python3
"""
网络错误分类器

用于分类和处理网络相关错误
"""

import logging
from typing import Dict, Optional, Tuple, Any
from enum import Enum

logger = logging.getLogger(__name__)


class NetworkErrorType(Enum):
    """网络错误类型"""
    CONNECTION_TIMEOUT = "connection_timeout"
    CONNECTION_REFUSED = "connection_refused"
    DNS_RESOLUTION = "dns_resolution"
    SSL_ERROR = "ssl_error"
    HTTP_ERROR = "http_error"
    NETWORK_UNREACHABLE = "network_unreachable"
    UNKNOWN = "unknown"


class NetworkErrorClassifier:
    """网络错误分类器"""
    
    def __init__(self):
        self.error_patterns = {
            NetworkErrorType.CONNECTION_TIMEOUT: [
                "timeout", "timed out", "connection timeout"
            ],
            NetworkErrorType.CONNECTION_REFUSED: [
                "connection refused", "refused", "connection reset"
            ],
            NetworkErrorType.DNS_RESOLUTION: [
                "dns", "name resolution", "getaddrinfo failed"
            ],
            NetworkErrorType.SSL_ERROR: [
                "ssl", "certificate", "handshake"
            ],
            NetworkErrorType.HTTP_ERROR: [
                "http", "status code", "bad request"
            ],
            NetworkErrorType.NETWORK_UNREACHABLE: [
                "network unreachable", "no route to host"
            ]
        }
    
    def classify_error(self, error_message: str) -> NetworkErrorType:
        """分类网络错误"""
        if not error_message:
            return NetworkErrorType.UNKNOWN
            
        error_lower = error_message.lower()
        
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if pattern in error_lower:
                    return error_type
                    
        return NetworkErrorType.UNKNOWN
    
    def get_recovery_suggestion(self, error_type: NetworkErrorType) -> str:
        """获取恢复建议"""
        suggestions = {
            NetworkErrorType.CONNECTION_TIMEOUT: "增加超时时间或检查网络连接",
            NetworkErrorType.CONNECTION_REFUSED: "检查目标服务是否运行",
            NetworkErrorType.DNS_RESOLUTION: "检查DNS设置或使用IP地址",
            NetworkErrorType.SSL_ERROR: "检查SSL证书或使用HTTP",
            NetworkErrorType.HTTP_ERROR: "检查请求格式和参数",
            NetworkErrorType.NETWORK_UNREACHABLE: "检查网络连接和路由",
            NetworkErrorType.UNKNOWN: "检查网络连接和错误日志"
        }
        return suggestions.get(error_type, "未知错误类型")


# 全局实例
_classifier = None


def get_network_error_classifier() -> NetworkErrorClassifier:
    """获取网络错误分类器实例"""
    global _classifier
    if _classifier is None:
        _classifier = NetworkErrorClassifier()
    return _classifier


def classify_network_error(error_message: str) -> Tuple[NetworkErrorType, str]:
    """分类网络错误并获取建议"""
    classifier = get_network_error_classifier()
    error_type = classifier.classify_error(error_message)
    suggestion = classifier.get_recovery_suggestion(error_type)
    return error_type, suggestion