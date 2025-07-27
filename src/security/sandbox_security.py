#!/usr/bin/env python3
"""
沙盒安全管理器

提供沙盒环境的安全控制，包括资源限制、监控和审计
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import psutil

from ..config.logging_config import get_logger
from .audit_logger import SecurityAuditLogger
from .malicious_code_detector import MaliciousCodeDetector, ThreatLevel

logger = get_logger("sandbox_security")


class ResourceType(Enum):
    """资源类型"""

    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    EXECUTION_TIME = "execution_time"


@dataclass
class ResourceLimit:
    """资源限制配置"""

    cpu_percent: float = 80.0  # CPU使用率限制 (%)
    memory_mb: int = 512  # 内存限制 (MB)
    disk_mb: int = 100  # 磁盘使用限制 (MB)
    execution_time_seconds: int = 60  # 执行时间限制 (秒)
    network_enabled: bool = False  # 是否允许网络访问
    max_processes: int = 5  # 最大进程数
    max_threads: int = 10  # 最大线程数
    max_file_descriptors: int = 100  # 最大文件描述符数


@dataclass
class ResourceUsage:
    """资源使用情况"""

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    disk_mb: float = 0.0
    execution_time: float = 0.0
    process_count: int = 0
    thread_count: int = 0
    file_descriptor_count: int = 0
    network_connections: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SecurityViolation:
    """安全违规记录"""

    violation_type: str
    severity: str
    description: str
    resource_type: ResourceType
    current_value: Any
    limit_value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    action_taken: str = ""


class SandboxSecurityManager:
    """沙盒安全管理器"""

    def __init__(
        self,
        resource_limits: Optional[ResourceLimit] = None,
        malicious_detector: Optional[MaliciousCodeDetector] = None,
        audit_logger: Optional[SecurityAuditLogger] = None,
    ):
        self.resource_limits = resource_limits or ResourceLimit()
        self.malicious_detector = malicious_detector or MaliciousCodeDetector()
        self.audit_logger = audit_logger or SecurityAuditLogger()

        self.monitoring_active = False
        self.monitoring_thread = None
        self.resource_usage_history: List[ResourceUsage] = []
        self.security_violations: List[SecurityViolation] = []
        self.violation_callbacks: List[Callable] = []

        # 监控间隔
        self.monitoring_interval = 1.0  # 秒

        # 违规计数器
        self.violation_counts: Dict[str, int] = {}

        # 熔断器状态
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None

    def start_monitoring(self):
        """开始资源监控"""
        if self.monitoring_active:
            logger.warning("资源监控已经在运行")
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitoring_thread.start()

        logger.info("沙盒资源监控已启动")
        self.audit_logger.log_security_event(
            "monitoring_started",
            "info",
            "沙盒资源监控启动",
            {"limits": self.resource_limits.__dict__},
        )

    def stop_monitoring(self):
        """停止资源监控"""
        if not self.monitoring_active:
            return

        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)

        logger.info("沙盒资源监控已停止")
        self.audit_logger.log_security_event(
            "monitoring_stopped", "info", "沙盒资源监控停止"
        )

    def _monitoring_loop(self):
        """监控循环"""
        while self.monitoring_active:
            try:
                usage = self._collect_resource_usage()
                self.resource_usage_history.append(usage)

                # 保持历史记录在合理范围内
                if len(self.resource_usage_history) > 1000:
                    self.resource_usage_history = self.resource_usage_history[-500:]

                # 检查资源限制
                self._check_resource_limits(usage)

                time.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"资源监控异常: {e}")
                time.sleep(self.monitoring_interval)

    def _collect_resource_usage(self) -> ResourceUsage:
        """收集当前资源使用情况"""
        try:
            # 获取当前进程信息
            current_process = psutil.Process()

            # CPU使用率
            cpu_percent = current_process.cpu_percent()

            # 内存使用
            memory_info = current_process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            # 进程和线程数
            process_count = len(current_process.children(recursive=True)) + 1
            thread_count = current_process.num_threads()

            # 文件描述符数
            try:
                file_descriptor_count = current_process.num_fds()
            except (AttributeError, psutil.AccessDenied):
                file_descriptor_count = 0

            # 网络连接数
            try:
                network_connections = len(current_process.connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                network_connections = 0

            return ResourceUsage(
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                process_count=process_count,
                thread_count=thread_count,
                file_descriptor_count=file_descriptor_count,
                network_connections=network_connections,
            )

        except Exception as e:
            logger.error(f"收集资源使用情况失败: {e}")
            return ResourceUsage()

    def _check_resource_limits(self, usage: ResourceUsage):
        """检查资源限制"""
        violations = []

        # 检查CPU使用率
        if usage.cpu_percent > self.resource_limits.cpu_percent:
            violations.append(
                SecurityViolation(
                    violation_type="cpu_limit_exceeded",
                    severity="high",
                    description=f"CPU使用率超限: {usage.cpu_percent:.1f}% > {self.resource_limits.cpu_percent}%",
                    resource_type=ResourceType.CPU,
                    current_value=usage.cpu_percent,
                    limit_value=self.resource_limits.cpu_percent,
                )
            )

        # 检查内存使用
        if usage.memory_mb > self.resource_limits.memory_mb:
            violations.append(
                SecurityViolation(
                    violation_type="memory_limit_exceeded",
                    severity="high",
                    description=f"内存使用超限: {usage.memory_mb:.1f}MB > {self.resource_limits.memory_mb}MB",
                    resource_type=ResourceType.MEMORY,
                    current_value=usage.memory_mb,
                    limit_value=self.resource_limits.memory_mb,
                )
            )

        # 检查进程数
        if usage.process_count > self.resource_limits.max_processes:
            violations.append(
                SecurityViolation(
                    violation_type="process_limit_exceeded",
                    severity="medium",
                    description=f"进程数超限: {usage.process_count} > {self.resource_limits.max_processes}",
                    resource_type=ResourceType.CPU,
                    current_value=usage.process_count,
                    limit_value=self.resource_limits.max_processes,
                )
            )

        # 检查线程数
        if usage.thread_count > self.resource_limits.max_threads:
            violations.append(
                SecurityViolation(
                    violation_type="thread_limit_exceeded",
                    severity="medium",
                    description=f"线程数超限: {usage.thread_count} > {self.resource_limits.max_threads}",
                    resource_type=ResourceType.CPU,
                    current_value=usage.thread_count,
                    limit_value=self.resource_limits.max_threads,
                )
            )

        # 检查文件描述符数
        if usage.file_descriptor_count > self.resource_limits.max_file_descriptors:
            violations.append(
                SecurityViolation(
                    violation_type="fd_limit_exceeded",
                    severity="medium",
                    description=f"文件描述符数超限: {usage.file_descriptor_count} > {self.resource_limits.max_file_descriptors}",
                    resource_type=ResourceType.DISK,
                    current_value=usage.file_descriptor_count,
                    limit_value=self.resource_limits.max_file_descriptors,
                )
            )

        # 检查网络连接
        if not self.resource_limits.network_enabled and usage.network_connections > 0:
            violations.append(
                SecurityViolation(
                    violation_type="network_access_denied",
                    severity="high",
                    description=f"检测到未授权网络访问: {usage.network_connections} 个连接",
                    resource_type=ResourceType.NETWORK,
                    current_value=usage.network_connections,
                    limit_value=0,
                )
            )

        # 处理违规
        for violation in violations:
            self._handle_security_violation(violation)

    def _handle_security_violation(self, violation: SecurityViolation):
        """处理安全违规"""
        self.security_violations.append(violation)

        # 更新违规计数
        self.violation_counts[violation.violation_type] = (
            self.violation_counts.get(violation.violation_type, 0) + 1
        )

        # 记录审计日志
        self.audit_logger.log_security_event(
            "security_violation",
            violation.severity,
            violation.description,
            {
                "violation_type": violation.violation_type,
                "resource_type": violation.resource_type.value,
                "current_value": violation.current_value,
                "limit_value": violation.limit_value,
                "violation_count": self.violation_counts[violation.violation_type],
            },
        )

        # 执行违规回调
        for callback in self.violation_callbacks:
            try:
                callback(violation)
            except Exception as e:
                logger.error(f"违规回调执行失败: {e}")

        # 检查是否需要触发熔断器
        self._check_circuit_breaker(violation)

        logger.warning(f"安全违规: {violation.description}")

    def _check_circuit_breaker(self, violation: SecurityViolation):
        """检查是否需要触发熔断器"""
        # 严重违规立即触发熔断器
        if violation.severity == "critical":
            self._activate_circuit_breaker("critical_violation", 300)  # 5分钟
            return

        # 高频违规触发熔断器
        violation_count = self.violation_counts.get(violation.violation_type, 0)
        if violation_count >= 5:  # 5次违规
            self._activate_circuit_breaker(
                f"repeated_{violation.violation_type}", 180
            )  # 3分钟

    def _activate_circuit_breaker(self, reason: str, duration_seconds: int):
        """激活熔断器"""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + timedelta(
            seconds=duration_seconds
        )

        logger.critical(f"熔断器激活: {reason}, 持续时间: {duration_seconds}秒")
        self.audit_logger.log_security_event(
            "circuit_breaker_activated",
            "critical",
            f"熔断器激活: {reason}",
            {
                "reason": reason,
                "duration_seconds": duration_seconds,
                "until": self.circuit_breaker_until.isoformat(),
            },
        )

    def is_circuit_breaker_active(self) -> bool:
        """检查熔断器是否激活"""
        if not self.circuit_breaker_active:
            return False

        if datetime.now() > self.circuit_breaker_until:
            self.circuit_breaker_active = False
            self.circuit_breaker_until = None
            logger.info("熔断器已自动恢复")
            self.audit_logger.log_security_event(
                "circuit_breaker_recovered", "info", "熔断器自动恢复"
            )
            return False

        return True

    def validate_code_security(
        self, code: str, filename: str = "unknown"
    ) -> Dict[str, Any]:
        """验证代码安全性"""
        logger.info(f"开始验证代码安全性: {filename}")

        # 检测恶意代码
        threats = self.malicious_detector.detect_threats(code, filename)

        # 生成安全报告
        security_report = self.malicious_detector.generate_security_report(
            code, filename
        )

        # 记录审计日志
        self.audit_logger.log_security_event(
            "code_security_validation",
            "info" if security_report["is_safe"] else "warning",
            f"代码安全验证: {filename}",
            {
                "filename": filename,
                "total_threats": security_report["total_threats"],
                "security_score": security_report["security_score"],
                "is_safe": security_report["is_safe"],
            },
        )

        return security_report

    def can_execute_code(self, code: str, filename: str = "unknown") -> Dict[str, Any]:
        """检查是否可以执行代码"""
        # 检查熔断器状态
        if self.is_circuit_breaker_active():
            return {
                "can_execute": False,
                "reason": "circuit_breaker_active",
                "message": f"熔断器激活中，预计恢复时间: {self.circuit_breaker_until}",
                "security_report": None,
            }

        # 验证代码安全性
        security_report = self.validate_code_security(code, filename)

        # 判断是否可以执行
        can_execute = (
            security_report["is_safe"] and security_report["security_score"] >= 70
        )

        if not can_execute:
            reason = "security_threats_detected"
            message = f"检测到安全威胁，安全评分: {security_report['security_score']}"
        else:
            reason = "approved"
            message = "代码安全验证通过"

        return {
            "can_execute": can_execute,
            "reason": reason,
            "message": message,
            "security_report": security_report,
        }

    def add_violation_callback(self, callback: Callable[[SecurityViolation], None]):
        """添加违规回调函数"""
        self.violation_callbacks.append(callback)

    def get_resource_usage_stats(self) -> Dict[str, Any]:
        """获取资源使用统计"""
        if not self.resource_usage_history:
            return {"error": "没有资源使用历史数据"}

        recent_usage = self.resource_usage_history[-100:]  # 最近100条记录

        # 计算统计信息
        cpu_values = [u.cpu_percent for u in recent_usage]
        memory_values = [u.memory_mb for u in recent_usage]

        return {
            "current_usage": recent_usage[-1].__dict__ if recent_usage else None,
            "limits": self.resource_limits.__dict__,
            "statistics": {
                "cpu": {
                    "avg": sum(cpu_values) / len(cpu_values),
                    "max": max(cpu_values),
                    "min": min(cpu_values),
                },
                "memory": {
                    "avg": sum(memory_values) / len(memory_values),
                    "max": max(memory_values),
                    "min": min(memory_values),
                },
            },
            "violation_counts": self.violation_counts.copy(),
            "circuit_breaker_active": self.is_circuit_breaker_active(),
            "total_violations": len(self.security_violations),
        }

    def get_security_summary(self) -> Dict[str, Any]:
        """获取安全摘要"""
        recent_violations = [
            v
            for v in self.security_violations
            if v.timestamp > datetime.now() - timedelta(hours=1)
        ]

        return {
            "monitoring_active": self.monitoring_active,
            "circuit_breaker_active": self.is_circuit_breaker_active(),
            "total_violations": len(self.security_violations),
            "recent_violations": len(recent_violations),
            "violation_types": list(self.violation_counts.keys()),
            "resource_limits": self.resource_limits.__dict__,
            "last_check": (
                self.resource_usage_history[-1].timestamp.isoformat()
                if self.resource_usage_history
                else None
            ),
        }

    def reset_violations(self):
        """重置违规记录"""
        self.security_violations.clear()
        self.violation_counts.clear()
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None

        logger.info("安全违规记录已重置")
        self.audit_logger.log_security_event(
            "violations_reset", "info", "安全违规记录重置"
        )

    def update_resource_limits(self, new_limits: ResourceLimit):
        """更新资源限制"""
        old_limits = self.resource_limits.__dict__.copy()
        self.resource_limits = new_limits

        logger.info("资源限制已更新")
        self.audit_logger.log_security_event(
            "resource_limits_updated",
            "info",
            "资源限制配置更新",
            {"old_limits": old_limits, "new_limits": new_limits.__dict__},
        )


# 全局沙盒安全管理器实例
_sandbox_security_manager = None


def get_sandbox_security_manager() -> SandboxSecurityManager:
    """获取全局沙盒安全管理器"""
    global _sandbox_security_manager
    if _sandbox_security_manager is None:
        _sandbox_security_manager = SandboxSecurityManager()
    return _sandbox_security_manager


def initialize_sandbox_security(
    resource_limits: Optional[ResourceLimit] = None,
) -> bool:
    """初始化沙盒安全系统"""
    try:
        global _sandbox_security_manager
        _sandbox_security_manager = SandboxSecurityManager(resource_limits)
        _sandbox_security_manager.start_monitoring()

        logger.info("沙盒安全系统初始化成功")
        return True
    except Exception as e:
        logger.error(f"沙盒安全系统初始化失败: {e}")
        return False


def shutdown_sandbox_security():
    """关闭沙盒安全系统"""
    global _sandbox_security_manager
    if _sandbox_security_manager:
        _sandbox_security_manager.stop_monitoring()
        _sandbox_security_manager = None
        logger.info("沙盒安全系统已关闭")
