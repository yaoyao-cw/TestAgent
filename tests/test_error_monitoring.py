#!/usr/bin/env python3
"""
错误监控系统测试

测试EnhancedMetricsCollector、ErrorReportGenerator和AlertManager的功能
"""

import asyncio
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.services.error_monitoring import (
    AlertManager,
    AlertRule,
    EnhancedMetricsCollector,
    ErrorCategory,
    ErrorReportGenerator,
    ErrorSeverity,
    NetworkErrorRecord,
)


class TestEnhancedMetricsCollector:
    """测试增强的指标收集器"""

    def setup_method(self):
        """设置测试"""
        self.collector = EnhancedMetricsCollector()

    def test_record_network_error(self):
        """测试记录网络错误"""
        error_id = str(uuid.uuid4())
        error_record = self.collector.record_network_error(
            error_id=error_id,
            error_type="ConnectionError",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            message="网络连接失败",
            service_name="test_service",
            endpoint="/api/test",
            response_time=5.0,
            status_code=500,
        )

        assert error_record.error_id == error_id
        assert error_record.category == ErrorCategory.NETWORK
        assert error_record.severity == ErrorSeverity.HIGH
        assert len(self.collector.error_records) == 1

    def test_record_error_recovery(self):
        """测试记录错误恢复"""
        # 先记录一个错误
        error_id = str(uuid.uuid4())
        self.collector.record_network_error(
            error_id=error_id,
            error_type="TimeoutError",
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            message="请求超时",
            service_name="test_service",
        )

        # 记录恢复
        recovery_time = 30.0
        self.collector.record_error_recovery(error_id, recovery_time, "retry")

        # 验证恢复记录
        error_record = list(self.collector.error_records)[0]
        assert error_record.recovery_time == recovery_time
        assert error_record.is_recovered
