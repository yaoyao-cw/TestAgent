#!/usr/bin/env python3
"""
安全审计日志记录器

记录所有安全相关事件，支持合规检查和安全分析
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.logging_config import get_logger
from ..config.settings import get_settings

logger = get_logger("security_audit")


class AuditEventType(Enum):
    """审计事件类型"""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CODE_EXECUTION = "code_execution"
    RESOURCE_ACCESS = "resource_access"
    SECURITY_VIOLATION = "security_violation"
    CONFIGURATION_CHANGE = "configuration_change"
    DATA_ACCESS = "data_access"
    SYSTEM_EVENT = "system_event"


class AuditSeverity(Enum):
    """审计严重程度"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """审计事件"""

    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: datetime
    user_id: Optional[str]
    session_id: Optional[str]
    source_ip: Optional[str]
    user_agent: Optional[str]
    action: str
    resource: Optional[str]
    description: str
    details: Dict[str, Any]
    result: str  # success, failure, blocked
    risk_score: int  # 0-100
    compliance_tags: List[str]


class SecurityAuditLogger:
    """安全审计日志记录器"""

    def __init__(self, log_directory: Optional[str] = None):
        self.settings = get_settings()
        self.log_directory = Path(log_directory or "logs/security")
        self.log_directory.mkdir(parents=True, exist_ok=True)

        # 审计日志文件
        self.audit_log_file = self.log_directory / "security_audit.log"
        self.compliance_log_file = self.log_directory / "compliance.log"
        self.threat_log_file = self.log_directory / "threats.log"

        # 配置专用的审计日志记录器
        self.audit_logger = self._setup_audit_logger()
        self.compliance_logger = self._setup_compliance_logger()
        self.threat_logger = self._setup_threat_logger()

        # 事件缓存（用于实时分析）
        self.recent_events: List[AuditEvent] = []
        self.max_recent_events = 1000

        # 风险评分规则
        self.risk_scoring_rules = {
            AuditEventType.AUTHENTICATION: {"success": 0, "failure": 30, "blocked": 50},
            AuditEventType.AUTHORIZATION: {"success": 0, "failure": 40, "blocked": 60},
            AuditEventType.CODE_EXECUTION: {
                "success": 10,
                "failure": 20,
                "blocked": 80,
            },
            AuditEventType.SECURITY_VIOLATION: {
                "success": 0,
                "failure": 70,
                "blocked": 90,
            },
        }

    def _setup_audit_logger(self) -> logging.Logger:
        """设置审计日志记录器"""
        audit_logger = logging.getLogger("security_audit_log")
        audit_logger.setLevel(logging.INFO)

        # 避免重复添加处理器
        if not audit_logger.handlers:
            handler = logging.FileHandler(self.audit_log_file, encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            audit_logger.addHandler(handler)
            audit_logger.propagate = False

        return audit_logger

    def _setup_compliance_logger(self) -> logging.Logger:
        """设置合规日志记录器"""
        compliance_logger = logging.getLogger("compliance_log")
        compliance_logger.setLevel(logging.INFO)

        if not compliance_logger.handlers:
            handler = logging.FileHandler(self.compliance_log_file, encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s | COMPLIANCE | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            compliance_logger.addHandler(handler)
            compliance_logger.propagate = False

        return compliance_logger

    def _setup_threat_logger(self) -> logging.Logger:
        """设置威胁日志记录器"""
        threat_logger = logging.getLogger("threat_log")
        threat_logger.setLevel(logging.WARNING)

        if not threat_logger.handlers:
            handler = logging.FileHandler(self.threat_log_file, encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s | THREAT | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            threat_logger.addHandler(handler)
            threat_logger.propagate = False

        return threat_logger

    def log_security_event(
        self,
        action: str,
        severity: str = "info",
        description: str = "",
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource: Optional[str] = None,
        result: str = "success",
        event_type: Optional[AuditEventType] = None,
        compliance_tags: Optional[List[str]] = None,
    ):
        """记录安全事件"""

        # 生成事件ID
        event_id = self._generate_event_id(action, user_id, session_id)

        # 确定事件类型
        if event_type is None:
            event_type = self._determine_event_type(action)

        # 转换严重程度
        try:
            severity_enum = AuditSeverity(severity.lower())
        except ValueError:
            severity_enum = AuditSeverity.INFO

        # 计算风险评分
        risk_score = self._calculate_risk_score(event_type, result, severity_enum)

        # 创建审计事件
        audit_event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity_enum,
            timestamp=datetime.now(),
            user_id=user_id,
            session_id=session_id,
            source_ip=source_ip,
            user_agent=user_agent,
            action=action,
            resource=resource,
            description=description,
            details=details or {},
            result=result,
            risk_score=risk_score,
            compliance_tags=compliance_tags or [],
        )

        # 记录到各个日志
        self._write_audit_log(audit_event)

        # 如果是合规相关事件，记录到合规日志
        if compliance_tags:
            self._write_compliance_log(audit_event)

        # 如果是威胁相关事件，记录到威胁日志
        if severity_enum in [
            AuditSeverity.WARNING,
            AuditSeverity.ERROR,
            AuditSeverity.CRITICAL,
        ]:
            self._write_threat_log(audit_event)

        # 添加到最近事件缓存
        self._add_to_recent_events(audit_event)

        # 实时威胁检测
        self._check_threat_patterns(audit_event)

    def _generate_event_id(
        self, action: str, user_id: Optional[str], session_id: Optional[str]
    ) -> str:
        """生成事件ID"""
        timestamp = datetime.now().isoformat()
        content = f"{timestamp}:{action}:{user_id or 'anonymous'}:{session_id or 'no_session'}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _determine_event_type(self, action: str) -> AuditEventType:
        """根据动作确定事件类型"""
        action_lower = action.lower()

        if any(
            keyword in action_lower for keyword in ["login", "logout", "auth", "token"]
        ):
            return AuditEventType.AUTHENTICATION
        elif any(
            keyword in action_lower for keyword in ["permission", "access", "authorize"]
        ):
            return AuditEventType.AUTHORIZATION
        elif any(keyword in action_lower for keyword in ["execute", "run", "code"]):
            return AuditEventType.CODE_EXECUTION
        elif any(
            keyword in action_lower for keyword in ["violation", "threat", "malicious"]
        ):
            return AuditEventType.SECURITY_VIOLATION
        elif any(
            keyword in action_lower for keyword in ["config", "setting", "update"]
        ):
            return AuditEventType.CONFIGURATION_CHANGE
        elif any(
            keyword in action_lower for keyword in ["read", "write", "delete", "file"]
        ):
            return AuditEventType.DATA_ACCESS
        else:
            return AuditEventType.SYSTEM_EVENT

    def _calculate_risk_score(
        self, event_type: AuditEventType, result: str, severity: AuditSeverity
    ) -> int:
        """计算风险评分"""
        base_score = self.risk_scoring_rules.get(event_type, {}).get(result, 0)

        # 根据严重程度调整评分
        severity_multiplier = {
            AuditSeverity.INFO: 1.0,
            AuditSeverity.WARNING: 1.5,
            AuditSeverity.ERROR: 2.0,
            AuditSeverity.CRITICAL: 3.0,
        }

        final_score = int(base_score * severity_multiplier.get(severity, 1.0))
        return min(100, max(0, final_score))

    def _write_audit_log(self, event: AuditEvent):
        """写入审计日志"""
        log_entry = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat(),
            "user_id": event.user_id,
            "session_id": event.session_id,
            "source_ip": event.source_ip,
            "user_agent": event.user_agent,
            "action": event.action,
            "resource": event.resource,
            "description": event.description,
            "details": event.details,
            "result": event.result,
            "risk_score": event.risk_score,
            "compliance_tags": event.compliance_tags,
        }

        self.audit_logger.info(json.dumps(log_entry, ensure_ascii=False))

    def _write_compliance_log(self, event: AuditEvent):
        """写入合规日志"""
        compliance_entry = {
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "compliance_tags": event.compliance_tags,
            "action": event.action,
            "result": event.result,
            "user_id": event.user_id,
            "description": event.description,
        }

        self.compliance_logger.info(json.dumps(compliance_entry, ensure_ascii=False))

    def _write_threat_log(self, event: AuditEvent):
        """写入威胁日志"""
        threat_entry = {
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "severity": event.severity.value,
            "risk_score": event.risk_score,
            "action": event.action,
            "description": event.description,
            "source_ip": event.source_ip,
            "user_id": event.user_id,
            "details": event.details,
        }

        if event.severity == AuditSeverity.CRITICAL:
            self.threat_logger.critical(json.dumps(threat_entry, ensure_ascii=False))
        elif event.severity == AuditSeverity.ERROR:
            self.threat_logger.error(json.dumps(threat_entry, ensure_ascii=False))
        else:
            self.threat_logger.warning(json.dumps(threat_entry, ensure_ascii=False))

    def _add_to_recent_events(self, event: AuditEvent):
        """添加到最近事件缓存"""
        self.recent_events.append(event)

        # 保持缓存大小
        if len(self.recent_events) > self.max_recent_events:
            self.recent_events = self.recent_events[-self.max_recent_events // 2 :]

    def _check_threat_patterns(self, event: AuditEvent):
        """检查威胁模式"""
        # 检查短时间内的重复失败
        if event.result == "failure":
            recent_failures = [
                e
                for e in self.recent_events[-50:]  # 最近50个事件
                if e.action == event.action
                and e.result == "failure"
                and e.timestamp > datetime.now() - timedelta(minutes=5)
                and e.user_id == event.user_id
            ]

            if len(recent_failures) >= 5:
                self.log_security_event(
                    "repeated_failures_detected",
                    "critical",
                    f"检测到重复失败模式: {event.action}",
                    {
                        "failure_count": len(recent_failures),
                        "time_window": "5_minutes",
                        "original_action": event.action,
                        "user_id": event.user_id,
                    },
                    user_id=event.user_id,
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    compliance_tags=["threat_detection", "brute_force"],
                )

        # 检查高风险评分事件
        if event.risk_score >= 80:
            self.log_security_event(
                "high_risk_event_detected",
                "error",
                f"检测到高风险事件: {event.action}",
                {
                    "risk_score": event.risk_score,
                    "original_event_id": event.event_id,
                    "original_action": event.action,
                },
                user_id=event.user_id,
                event_type=AuditEventType.SECURITY_VIOLATION,
                compliance_tags=["high_risk", "automated_detection"],
            )

    def get_recent_events(
        self,
        limit: int = 100,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditSeverity] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取最近的审计事件"""
        events = self.recent_events[-limit:]

        # 应用过滤器
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if severity:
            events = [e for e in events if e.severity == severity]

        if user_id:
            events = [e for e in events if e.user_id == user_id]

        # 转换为字典格式
        return [asdict(event) for event in events]

    def get_security_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取安全统计信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_events = [e for e in self.recent_events if e.timestamp > cutoff_time]

        if not recent_events:
            return {"error": "没有最近的事件数据"}

        # 按事件类型统计
        event_type_counts = {}
        for event in recent_events:
            event_type_counts[event.event_type.value] = (
                event_type_counts.get(event.event_type.value, 0) + 1
            )

        # 按严重程度统计
        severity_counts = {}
        for event in recent_events:
            severity_counts[event.severity.value] = (
                severity_counts.get(event.severity.value, 0) + 1
            )

        # 按结果统计
        result_counts = {}
        for event in recent_events:
            result_counts[event.result] = result_counts.get(event.result, 0) + 1

        # 计算平均风险评分
        risk_scores = [e.risk_score for e in recent_events]
        avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0

        # 找出高风险事件
        high_risk_events = [e for e in recent_events if e.risk_score >= 70]

        return {
            "time_period_hours": hours,
            "total_events": len(recent_events),
            "event_type_distribution": event_type_counts,
            "severity_distribution": severity_counts,
            "result_distribution": result_counts,
            "average_risk_score": round(avg_risk_score, 2),
            "high_risk_events": len(high_risk_events),
            "top_users": self._get_top_users(recent_events),
            "top_actions": self._get_top_actions(recent_events),
        }

    def _get_top_users(
        self, events: List[AuditEvent], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """获取最活跃的用户"""
        user_counts = {}
        for event in events:
            if event.user_id:
                user_counts[event.user_id] = user_counts.get(event.user_id, 0) + 1

        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {"user_id": user, "event_count": count}
            for user, count in sorted_users[:limit]
        ]

    def _get_top_actions(
        self, events: List[AuditEvent], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """获取最频繁的动作"""
        action_counts = {}
        for event in events:
            action_counts[event.action] = action_counts.get(event.action, 0) + 1

        sorted_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {"action": action, "count": count}
            for action, count in sorted_actions[:limit]
        ]

    def generate_compliance_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """生成合规报告"""
        compliance_events = [
            e
            for e in self.recent_events
            if e.compliance_tags and start_date <= e.timestamp <= end_date
        ]

        # 按合规标签分组
        compliance_by_tag = {}
        for event in compliance_events:
            for tag in event.compliance_tags:
                if tag not in compliance_by_tag:
                    compliance_by_tag[tag] = []
                compliance_by_tag[tag].append(event)

        return {
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_compliance_events": len(compliance_events),
            "compliance_tags": list(compliance_by_tag.keys()),
            "events_by_tag": {
                tag: len(events) for tag, events in compliance_by_tag.items()
            },
            "compliance_violations": len(
                [e for e in compliance_events if e.result in ["failure", "blocked"]]
            ),
            "compliance_score": self._calculate_compliance_score(compliance_events),
        }

    def _calculate_compliance_score(self, events: List[AuditEvent]) -> float:
        """计算合规评分"""
        if not events:
            return 100.0

        successful_events = len([e for e in events if e.result == "success"])
        return (successful_events / len(events)) * 100


# 全局安全审计日志记录器实例
_security_audit_logger = None


def get_security_audit_logger() -> SecurityAuditLogger:
    """获取全局安全审计日志记录器"""
    global _security_audit_logger
    if _security_audit_logger is None:
        _security_audit_logger = SecurityAuditLogger()
    return _security_audit_logger
