#!/usr/bin/env python3
"""
错误监控和报告系统

实现网络错误监控、报告生成和告警管理功能
"""

import asyncio
import json
import logging
import smtplib
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from ..config.logging_config import get_logger
from ..core.monitoring import MetricsCollector, get_metrics_collector
from ..exceptions import TestAgentException

logger = get_logger("error_monitoring")


class ErrorSeverity(Enum):
    """错误严重程度枚举"""

    LOW = "low"
    """低严重程度"""

    MEDIUM = "medium"
    """中等严重程度"""

    HIGH = "high"
    """高严重程度"""

    CRITICAL = "critical"
    """严重程度"""


class ErrorCategory(Enum):
    """错误类别枚举"""

    NETWORK = "network"
    """网络错误"""

    TIMEOUT = "timeout"
    """超时错误"""

    CONNECTION = "connection"
    """连接错误"""

    SERVICE_UNAVAILABLE = "service_unavailable"
    """服务不可用"""

    AUTHENTICATION = "authentication"
    """认证错误"""

    AUTHORIZATION = "authorization"
    """授权错误"""

    VALIDATION = "validation"
    """验证错误"""

    SYSTEM = "system"
    """系统错误"""


@dataclass
class NetworkErrorRecord:
    """网络错误记录"""

    error_id: str
    timestamp: datetime
    error_type: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    service_name: str
    endpoint: Optional[str] = None
    response_time: Optional[float] = None
    status_code: Optional[int] = None
    retry_count: int = 0
    recovery_time: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None

    @property
    def is_recovered(self) -> bool:
        """是否已恢复"""
        return self.recovery_time is not None


@dataclass
class ErrorMetrics:
    """错误指标"""

    total_errors: int = 0
    error_rate: float = 0.0
    avg_recovery_time: float = 0.0
    success_rate: float = 100.0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    recent_errors: List[NetworkErrorRecord] = field(default_factory=list)

    def update_metrics(self, error_record: NetworkErrorRecord):
        """更新错误指标"""
        self.total_errors += 1

        # 更新分类统计
        category = error_record.category.value
        self.errors_by_category[category] = self.errors_by_category.get(category, 0) + 1

        # 更新严重程度统计
        severity = error_record.severity.value
        self.errors_by_severity[severity] = self.errors_by_severity.get(severity, 0) + 1

        # 添加到最近错误列表
        self.recent_errors.append(error_record)
        if len(self.recent_errors) > 100:  # 保持最近100个错误
            self.recent_errors.pop(0)


class EnhancedMetricsCollector(MetricsCollector):
    """扩展的指标收集器，专门收集网络错误和恢复相关指标"""

    def __init__(self, max_metrics: int = 10000):
        super().__init__(max_metrics)
        self.error_records: deque = deque(maxlen=max_metrics)
        self.error_metrics_by_service: Dict[str, ErrorMetrics] = defaultdict(
            ErrorMetrics
        )
        self.recovery_metrics: Dict[str, List[float]] = defaultdict(list)
        self.network_latency_history: deque = deque(maxlen=1000)
        self.service_availability: Dict[str, float] = {}
        self.error_patterns: Dict[str, int] = defaultdict(int)

    def record_network_error(
        self,
        error_id: str,
        error_type: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        message: str,
        service_name: str,
        endpoint: Optional[str] = None,
        response_time: Optional[float] = None,
        status_code: Optional[int] = None,
        context: Dict[str, Any] = None,
    ):
        """记录网络错误"""
        error_record = NetworkErrorRecord(
            error_id=error_id,
            timestamp=datetime.now(),
            error_type=error_type,
            category=category,
            severity=severity,
            message=message,
            service_name=service_name,
            endpoint=endpoint,
            response_time=response_time,
            status_code=status_code,
            context=context or {},
        )

        # 添加到错误记录
        self.error_records.append(error_record)

        # 更新服务错误指标
        self.error_metrics_by_service[service_name].update_metrics(error_record)

        # 记录错误模式
        error_pattern = f"{error_type}:{category.value}"
        self.error_patterns[error_pattern] += 1

        # 记录到基础指标系统
        self.record_metric(
            f"network.error.{category.value}",
            1,
            tags={
                "service": service_name,
                "severity": severity.value,
                "error_type": error_type,
            },
            unit="count",
        )

        logger.warning(f"网络错误记录: {service_name} - {message}")
        return error_record

    def record_error_recovery(
        self, error_id: str, recovery_time: float, recovery_method: str = "unknown"
    ):
        """记录错误恢复"""
        # 查找对应的错误记录
        for error_record in reversed(self.error_records):
            if error_record.error_id == error_id:
                error_record.recovery_time = recovery_time

                # 记录恢复指标
                service_name = error_record.service_name
                self.recovery_metrics[service_name].append(recovery_time)

                # 限制恢复时间历史记录数量
                if len(self.recovery_metrics[service_name]) > 100:
                    self.recovery_metrics[service_name].pop(0)

                # 记录到基础指标系统
                self.record_metric(
                    f"network.recovery.time",
                    recovery_time,
                    tags={
                        "service": service_name,
                        "method": recovery_method,
                        "category": error_record.category.value,
                    },
                    unit="seconds",
                )

                logger.info(f"错误恢复记录: {error_id} - {recovery_time:.2f}s")
                break

    def record_network_latency(self, service_name: str, latency: float):
        """记录网络延迟"""
        self.network_latency_history.append(
            {"service": service_name, "latency": latency, "timestamp": datetime.now()}
        )

        self.record_metric(
            f"network.latency",
            latency,
            tags={"service": service_name},
            unit="milliseconds",
        )

    def update_service_availability(self, service_name: str, availability: float):
        """更新服务可用性"""
        self.service_availability[service_name] = availability

        self.record_metric(
            f"service.availability",
            availability,
            tags={"service": service_name},
            unit="percentage",
        )

    def get_error_metrics(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """获取错误指标"""
        if service_name:
            metrics = self.error_metrics_by_service.get(service_name, ErrorMetrics())
            return {
                "service": service_name,
                "total_errors": metrics.total_errors,
                "error_rate": metrics.error_rate,
                "avg_recovery_time": metrics.avg_recovery_time,
                "success_rate": metrics.success_rate,
                "errors_by_category": metrics.errors_by_category,
                "errors_by_severity": metrics.errors_by_severity,
                "recent_errors_count": len(metrics.recent_errors),
            }
        else:
            # 返回所有服务的汇总指标
            total_errors = sum(
                m.total_errors for m in self.error_metrics_by_service.values()
            )
            all_categories = defaultdict(int)
            all_severities = defaultdict(int)

            for metrics in self.error_metrics_by_service.values():
                for category, count in metrics.errors_by_category.items():
                    all_categories[category] += count
                for severity, count in metrics.errors_by_severity.items():
                    all_severities[severity] += count

            return {
                "total_errors": total_errors,
                "services_count": len(self.error_metrics_by_service),
                "errors_by_category": dict(all_categories),
                "errors_by_severity": dict(all_severities),
                "error_patterns": dict(self.error_patterns),
                "avg_service_availability": (
                    sum(self.service_availability.values())
                    / len(self.service_availability)
                    if self.service_availability
                    else 0
                ),
            }

    def get_recovery_statistics(
        self, service_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取恢复统计信息"""
        if service_name:
            recovery_times = self.recovery_metrics.get(service_name, [])
            if recovery_times:
                return {
                    "service": service_name,
                    "total_recoveries": len(recovery_times),
                    "avg_recovery_time": sum(recovery_times) / len(recovery_times),
                    "min_recovery_time": min(recovery_times),
                    "max_recovery_time": max(recovery_times),
                    "recent_recovery_times": recovery_times[-10:],  # 最近10次恢复
                }
            else:
                return {
                    "service": service_name,
                    "total_recoveries": 0,
                    "avg_recovery_time": 0,
                    "min_recovery_time": 0,
                    "max_recovery_time": 0,
                    "recent_recovery_times": [],
                }
        else:
            # 返回所有服务的恢复统计
            all_recovery_times = []
            for times in self.recovery_metrics.values():
                all_recovery_times.extend(times)

            if all_recovery_times:
                return {
                    "total_recoveries": len(all_recovery_times),
                    "avg_recovery_time": sum(all_recovery_times)
                    / len(all_recovery_times),
                    "min_recovery_time": min(all_recovery_times),
                    "max_recovery_time": max(all_recovery_times),
                    "services_with_recoveries": len(self.recovery_metrics),
                }
            else:
                return {
                    "total_recoveries": 0,
                    "avg_recovery_time": 0,
                    "min_recovery_time": 0,
                    "max_recovery_time": 0,
                    "services_with_recoveries": 0,
                }


class ErrorReportGenerator:
    """错误报告生成器，生成详细的错误分析报告"""

    def __init__(self, metrics_collector: EnhancedMetricsCollector):
        self.metrics_collector = metrics_collector

    def generate_error_summary_report(
        self, time_range_hours: int = 24, service_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成错误摘要报告"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_range_hours)

        # 过滤时间范围内的错误
        filtered_errors = [
            error
            for error in self.metrics_collector.error_records
            if start_time <= error.timestamp <= end_time
            and (service_name is None or error.service_name == service_name)
        ]

        if not filtered_errors:
            return {
                "report_type": "error_summary",
                "time_range": f"{time_range_hours} hours",
                "service": service_name or "all",
                "total_errors": 0,
                "message": "No errors found in the specified time range",
            }

        # 统计分析
        total_errors = len(filtered_errors)
        errors_by_hour = defaultdict(int)
        errors_by_service = defaultdict(int)
        errors_by_category = defaultdict(int)
        errors_by_severity = defaultdict(int)
        recovery_times = []

        for error in filtered_errors:
            hour_key = error.timestamp.strftime("%Y-%m-%d %H:00")
            errors_by_hour[hour_key] += 1
            errors_by_service[error.service_name] += 1
            errors_by_category[error.category.value] += 1
            errors_by_severity[error.severity.value] += 1

            if error.recovery_time:
                recovery_times.append(error.recovery_time)

        # 计算错误率趋势
        error_rate_trend = []
        for i in range(time_range_hours):
            hour = end_time - timedelta(hours=i)
            hour_key = hour.strftime("%Y-%m-%d %H:00")
            error_rate_trend.append(
                {"hour": hour_key, "error_count": errors_by_hour.get(hour_key, 0)}
            )

        # 生成报告
        report = {
            "report_type": "error_summary",
            "generated_at": end_time.isoformat(),
            "time_range": f"{time_range_hours} hours",
            "service": service_name or "all",
            "summary": {
                "total_errors": total_errors,
                "error_rate": total_errors / time_range_hours,
                "recovered_errors": len(recovery_times),
                "recovery_rate": (
                    len(recovery_times) / total_errors * 100 if total_errors > 0 else 0
                ),
                "avg_recovery_time": (
                    sum(recovery_times) / len(recovery_times) if recovery_times else 0
                ),
            },
            "breakdown": {
                "by_service": dict(errors_by_service),
                "by_category": dict(errors_by_category),
                "by_severity": dict(errors_by_severity),
            },
            "trends": {
                "hourly_errors": error_rate_trend,
                "peak_error_hour": (
                    max(errors_by_hour.items(), key=lambda x: x[1])[0]
                    if errors_by_hour
                    else None
                ),
            },
            "top_errors": [
                {
                    "service": error.service_name,
                    "category": error.category.value,
                    "severity": error.severity.value,
                    "message": error.message,
                    "timestamp": error.timestamp.isoformat(),
                    "recovery_time": error.recovery_time,
                }
                for error in sorted(
                    filtered_errors, key=lambda x: x.severity.value, reverse=True
                )[:10]
            ],
        }

        return report

    def generate_service_health_report(self, service_name: str) -> Dict[str, Any]:
        """生成服务健康报告"""
        service_errors = [
            error
            for error in self.metrics_collector.error_records
            if error.service_name == service_name
        ]

        if not service_errors:
            return {
                "report_type": "service_health",
                "service": service_name,
                "status": "healthy",
                "message": "No errors recorded for this service",
            }

        # 最近24小时的错误
        recent_errors = [
            error
            for error in service_errors
            if error.timestamp >= datetime.now() - timedelta(hours=24)
        ]

        # 计算健康指标
        total_errors = len(service_errors)
        recent_error_count = len(recent_errors)
        recovery_times = [e.recovery_time for e in service_errors if e.recovery_time]

        # 确定健康状态
        if recent_error_count == 0:
            health_status = "healthy"
        elif recent_error_count <= 5:
            health_status = "warning"
        else:
            health_status = "unhealthy"

        # 错误模式分析
        error_patterns = defaultdict(int)
        for error in recent_errors:
            pattern = f"{error.category.value}:{error.error_type}"
            error_patterns[pattern] += 1

        report = {
            "report_type": "service_health",
            "service": service_name,
            "generated_at": datetime.now().isoformat(),
            "health_status": health_status,
            "metrics": {
                "total_errors": total_errors,
                "recent_errors_24h": recent_error_count,
                "recovery_rate": (
                    len(recovery_times) / total_errors * 100 if total_errors > 0 else 0
                ),
                "avg_recovery_time": (
                    sum(recovery_times) / len(recovery_times) if recovery_times else 0
                ),
                "availability": self.metrics_collector.service_availability.get(
                    service_name, 0
                ),
            },
            "error_patterns": dict(error_patterns),
            "recommendations": self._generate_health_recommendations(
                health_status, recent_error_count, error_patterns
            ),
            "recent_critical_errors": [
                {
                    "timestamp": error.timestamp.isoformat(),
                    "category": error.category.value,
                    "severity": error.severity.value,
                    "message": error.message,
                    "recovered": error.is_recovered,
                }
                for error in recent_errors
                if error.severity == ErrorSeverity.CRITICAL
            ],
        }

        return report

    def _generate_health_recommendations(
        self,
        health_status: str,
        recent_error_count: int,
        error_patterns: Dict[str, int],
    ) -> List[str]:
        """生成健康建议"""
        recommendations = []

        if health_status == "unhealthy":
            recommendations.append("服务健康状况不佳，建议立即检查服务状态")
            recommendations.append("考虑重启服务或检查网络连接")

        if recent_error_count > 10:
            recommendations.append("错误频率过高，建议启用熔断器保护")

        # 基于错误模式的建议
        for pattern, count in error_patterns.items():
            if "timeout" in pattern and count > 3:
                recommendations.append(
                    "检测到多次超时错误，建议增加超时时间或优化服务性能"
                )
            elif "connection" in pattern and count > 3:
                recommendations.append(
                    "检测到多次连接错误，建议检查网络配置和防火墙设置"
                )
            elif "authentication" in pattern and count > 2:
                recommendations.append("检测到认证错误，建议检查API密钥和认证配置")

        if not recommendations:
            recommendations.append("服务运行正常，继续监控")

        return recommendations


@dataclass
class AlertRule:
    """告警规则"""

    rule_id: str
    name: str
    condition: str  # 告警条件描述
    threshold: float
    time_window_minutes: int
    severity: ErrorSeverity
    enabled: bool = True
    notification_channels: List[str] = field(default_factory=list)

    def evaluate(self, metrics: Dict[str, Any]) -> bool:
        """评估告警条件"""
        # 这里可以实现更复杂的条件评估逻辑
        # 目前简化为基于阈值的判断
        if "error_rate" in self.condition:
            return metrics.get("error_rate", 0) > self.threshold
        elif "recovery_time" in self.condition:
            return metrics.get("avg_recovery_time", 0) > self.threshold
        elif "availability" in self.condition:
            return metrics.get("availability", 100) < self.threshold
        return False


@dataclass
class Alert:
    """告警信息"""

    alert_id: str
    rule_id: str
    service_name: str
    severity: ErrorSeverity
    title: str
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    notification_sent: bool = False

    @property
    def is_active(self) -> bool:
        """是否为活跃告警"""
        return self.resolved_at is None

    @property
    def duration(self) -> timedelta:
        """告警持续时间"""
        end_time = self.resolved_at or datetime.now()
        return end_time - self.triggered_at


class AlertManager:
    """告警管理器，在错误频率超过阈值时发送告警"""

    def __init__(self, metrics_collector: EnhancedMetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.notification_handlers: Dict[str, Callable] = {}
        self.check_interval = 60  # 检查间隔（秒）
        self.monitoring_task: Optional[asyncio.Task] = None
        self._initialize_default_rules()

    def _initialize_default_rules(self):
        """初始化默认告警规则"""
        # 错误率告警
        self.add_alert_rule(
            AlertRule(
                rule_id="high_error_rate",
                name="高错误率告警",
                condition="error_rate > threshold",
                threshold=10.0,  # 每小时10个错误
                time_window_minutes=60,
                severity=ErrorSeverity.HIGH,
                notification_channels=["email", "webhook"],
            )
        )

        # 服务可用性告警
        self.add_alert_rule(
            AlertRule(
                rule_id="low_availability",
                name="服务可用性低告警",
                condition="availability < threshold",
                threshold=95.0,  # 可用性低于95%
                time_window_minutes=30,
                severity=ErrorSeverity.CRITICAL,
                notification_channels=["email", "sms", "webhook"],
            )
        )

        # 恢复时间过长告警
        self.add_alert_rule(
            AlertRule(
                rule_id="slow_recovery",
                name="恢复时间过长告警",
                condition="recovery_time > threshold",
                threshold=300.0,  # 恢复时间超过5分钟
                time_window_minutes=15,
                severity=ErrorSeverity.MEDIUM,
                notification_channels=["email"],
            )
        )

    def add_alert_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.alert_rules[rule.rule_id] = rule
        logger.info(f"添加告警规则: {rule.name}")

    def remove_alert_rule(self, rule_id: str):
        """移除告警规则"""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.info(f"移除告警规则: {rule_id}")

    def add_notification_handler(self, channel: str, handler: Callable):
        """添加通知处理器"""
        self.notification_handlers[channel] = handler
        logger.info(f"添加通知处理器: {channel}")

    async def start_monitoring(self):
        """开始监控"""
        if self.monitoring_task:
            logger.warning("告警监控已在运行")
            return

        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("告警监控已启动")

    async def stop_monitoring(self):
        """停止监控"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
        logger.info("告警监控已停止")

    async def _monitoring_loop(self):
        """监控循环"""
        while True:
            try:
                await self._check_alert_conditions()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"告警监控循环错误: {e}")
                await asyncio.sleep(self.check_interval)

    async def _check_alert_conditions(self):
        """检查告警条件"""
        # 获取所有服务的指标
        all_services = set()
        for error in self.metrics_collector.error_records:
            all_services.add(error.service_name)

        for service_name in all_services:
            await self._check_service_alerts(service_name)

    async def _check_service_alerts(self, service_name: str):
        """检查单个服务的告警条件"""
        # 获取服务指标
        error_metrics = self.metrics_collector.get_error_metrics(service_name)
        recovery_stats = self.metrics_collector.get_recovery_statistics(service_name)
        availability = self.metrics_collector.service_availability.get(
            service_name, 100
        )

        # 合并指标
        combined_metrics = {
            **error_metrics,
            **recovery_stats,
            "availability": availability,
        }

        # 检查每个告警规则
        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue

            alert_key = f"{rule.rule_id}:{service_name}"

            if rule.evaluate(combined_metrics):
                # 条件满足，触发告警
                if alert_key not in self.active_alerts:
                    await self._trigger_alert(rule, service_name, combined_metrics)
            else:
                # 条件不满足，解决告警
                if alert_key in self.active_alerts:
                    await self._resolve_alert(alert_key)

    async def _trigger_alert(
        self, rule: AlertRule, service_name: str, metrics: Dict[str, Any]
    ):
        """触发告警"""
        alert_id = f"{rule.rule_id}:{service_name}:{int(time.time())}"
        alert_key = f"{rule.rule_id}:{service_name}"

        # 生成告警消息
        title = f"[{rule.severity.value.upper()}] {rule.name}"
        message = self._generate_alert_message(rule, service_name, metrics)

        # 创建告警
        alert = Alert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            service_name=service_name,
            severity=rule.severity,
            title=title,
            message=message,
            triggered_at=datetime.now(),
        )

        # 保存告警
        self.active_alerts[alert_key] = alert
        self.alert_history.append(alert)

        # 发送通知
        await self._send_alert_notifications(alert, rule.notification_channels)

        logger.warning(f"触发告警: {title} - {service_name}")

    async def _resolve_alert(self, alert_key: str):
        """解决告警"""
        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            alert.resolved_at = datetime.now()
            del self.active_alerts[alert_key]

            # 发送解决通知
            await self._send_resolution_notification(alert)

            logger.info(f"解决告警: {alert.title} - {alert.service_name}")

    def _generate_alert_message(
        self, rule: AlertRule, service_name: str, metrics: Dict[str, Any]
    ) -> str:
        """生成告警消息"""
        message_parts = [
            f"服务: {service_name}",
            f"告警规则: {rule.name}",
            f"触发条件: {rule.condition}",
            f"阈值: {rule.threshold}",
            f"当前指标:",
        ]

        # 添加相关指标信息
        if "error_rate" in rule.condition:
            message_parts.append(f"  - 错误率: {metrics.get('error_rate', 0):.2f}/小时")
        if "recovery_time" in rule.condition:
            message_parts.append(
                f"  - 平均恢复时间: {metrics.get('avg_recovery_time', 0):.2f}秒"
            )
        if "availability" in rule.condition:
            message_parts.append(f"  - 可用性: {metrics.get('availability', 0):.2f}%")

        message_parts.extend(
            [
                f"触发时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "请及时处理此告警。",
            ]
        )

        return "\n".join(message_parts)

    async def _send_alert_notifications(self, alert: Alert, channels: List[str]):
        """发送告警通知"""
        for channel in channels:
            if channel in self.notification_handlers:
                try:
                    handler = self.notification_handlers[channel]
                    notification_data = {
                        "alert_id": alert.alert_id,
                        "title": alert.title,
                        "message": alert.message,
                        "severity": alert.severity.value,
                        "service": alert.service_name,
                        "timestamp": alert.triggered_at.isoformat(),
                    }

                    if asyncio.iscoroutinefunction(handler):
                        await handler(notification_data)
                    else:
                        handler(notification_data)

                    alert.notification_sent = True
                    logger.info(f"告警通知已发送: {channel}")

                except Exception as e:
                    logger.error(f"发送告警通知失败 ({channel}): {e}")

    async def _send_resolution_notification(self, alert: Alert):
        """发送告警解决通知"""
        resolution_data = {
            "alert_id": alert.alert_id,
            "title": f"[已解决] {alert.title}",
            "message": f"告警已解决\n\n原始告警:\n{alert.message}\n\n解决时间: {alert.resolved_at.strftime('%Y-%m-%d %H:%M:%S')}\n持续时间: {alert.duration}",
            "severity": "resolved",
            "service": alert.service_name,
            "timestamp": alert.resolved_at.isoformat(),
        }

        # 发送到所有配置的通知渠道
        rule = self.alert_rules.get(alert.rule_id)
        if rule:
            for channel in rule.notification_channels:
                if channel in self.notification_handlers:
                    try:
                        handler = self.notification_handlers[channel]
                        if asyncio.iscoroutinefunction(handler):
                            await handler(resolution_data)
                        else:
                            handler(resolution_data)
                    except Exception as e:
                        logger.error(f"发送解决通知失败 ({channel}): {e}")

    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return list(self.active_alerts.values())

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        return sorted(self.alert_history, key=lambda x: x.triggered_at, reverse=True)[
            :limit
        ]

    def get_alert_statistics(self) -> Dict[str, Any]:
        """获取告警统计信息"""
        total_alerts = len(self.alert_history)
        active_alerts = len(self.active_alerts)

        # 按严重程度统计
        severity_stats = defaultdict(int)
        for alert in self.alert_history:
            severity_stats[alert.severity.value] += 1

        # 按服务统计
        service_stats = defaultdict(int)
        for alert in self.alert_history:
            service_stats[alert.service_name] += 1

        # 计算平均解决时间
        resolved_alerts = [a for a in self.alert_history if a.resolved_at]
        avg_resolution_time = 0
        if resolved_alerts:
            total_duration = sum(
                (a.duration.total_seconds() for a in resolved_alerts), 0
            )
            avg_resolution_time = total_duration / len(resolved_alerts)

        return {
            "total_alerts": total_alerts,
            "active_alerts": active_alerts,
            "resolved_alerts": len(resolved_alerts),
            "avg_resolution_time_seconds": avg_resolution_time,
            "alerts_by_severity": dict(severity_stats),
            "alerts_by_service": dict(service_stats),
            "alert_rules_count": len(self.alert_rules),
            "enabled_rules_count": sum(
                1 for rule in self.alert_rules.values() if rule.enabled
            ),
        }


# 默认通知处理器
async def email_notification_handler(notification_data: Dict[str, Any]):
    """邮件通知处理器"""
    try:
        # 这里应该实现实际的邮件发送逻辑
        # 目前只是记录日志
        logger.info(f"邮件通知: {notification_data['title']}")
        logger.debug(f"邮件内容: {notification_data['message']}")
    except Exception as e:
        logger.error(f"邮件通知发送失败: {e}")


def webhook_notification_handler(notification_data: Dict[str, Any]):
    """Webhook通知处理器"""
    try:
        # 这里应该实现实际的Webhook调用逻辑
        # 目前只是记录日志
        logger.info(f"Webhook通知: {notification_data['title']}")
        logger.debug(
            f"Webhook数据: {json.dumps(notification_data, ensure_ascii=False)}"
        )
    except Exception as e:
        logger.error(f"Webhook通知发送失败: {e}")


def sms_notification_handler(notification_data: Dict[str, Any]):
    """短信通知处理器"""
    try:
        # 这里应该实现实际的短信发送逻辑
        # 目前只是记录日志
        logger.info(f"短信通知: {notification_data['title']}")
    except Exception as e:
        logger.error(f"短信通知发送失败: {e}")


# 全局实例
_enhanced_metrics_collector: Optional[EnhancedMetricsCollector] = None
_error_report_generator: Optional[ErrorReportGenerator] = None
_alert_manager: Optional[AlertManager] = None


def get_enhanced_metrics_collector() -> EnhancedMetricsCollector:
    """获取增强的指标收集器实例"""
    global _enhanced_metrics_collector
    if _enhanced_metrics_collector is None:
        _enhanced_metrics_collector = EnhancedMetricsCollector()
    return _enhanced_metrics_collector


def get_error_report_generator() -> ErrorReportGenerator:
    """获取错误报告生成器实例"""
    global _error_report_generator
    if _error_report_generator is None:
        collector = get_enhanced_metrics_collector()
        _error_report_generator = ErrorReportGenerator(collector)
    return _error_report_generator


def get_alert_manager() -> AlertManager:
    """获取告警管理器实例"""
    global _alert_manager
    if _alert_manager is None:
        collector = get_enhanced_metrics_collector()
        _alert_manager = AlertManager(collector)

        # 注册默认通知处理器
        _alert_manager.add_notification_handler("email", email_notification_handler)
        _alert_manager.add_notification_handler("webhook", webhook_notification_handler)
        _alert_manager.add_notification_handler("sms", sms_notification_handler)

    return _alert_manager


# 便捷函数
def record_network_error(
    error_id: str,
    error_type: str,
    category: ErrorCategory,
    severity: ErrorSeverity,
    message: str,
    service_name: str,
    **kwargs,
) -> NetworkErrorRecord:
    """记录网络错误的便捷函数"""
    collector = get_enhanced_metrics_collector()
    return collector.record_network_error(
        error_id, error_type, category, severity, message, service_name, **kwargs
    )


def record_error_recovery(
    error_id: str, recovery_time: float, recovery_method: str = "unknown"
):
    """记录错误恢复的便捷函数"""
    collector = get_enhanced_metrics_collector()
    collector.record_error_recovery(error_id, recovery_time, recovery_method)


async def initialize_error_monitoring():
    """初始化错误监控系统"""
    try:
        # 启动告警监控
        alert_manager = get_alert_manager()
        await alert_manager.start_monitoring()

        logger.info("错误监控系统初始化成功")
        return True
    except Exception as e:
        logger.error(f"错误监控系统初始化失败: {e}")
        return False


async def shutdown_error_monitoring():
    """关闭错误监控系统"""
    try:
        if _alert_manager:
            await _alert_manager.stop_monitoring()
        logger.info("错误监控系统已关闭")
    except Exception as e:
        logger.error(f"关闭错误监控系统时发生错误: {e}")
