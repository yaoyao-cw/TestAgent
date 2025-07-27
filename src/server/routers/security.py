#!/usr/bin/env python3
"""
安全管理API路由
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ...config.logging_config import get_logger
from ...security.audit_logger import get_security_audit_logger
from ...security.auth import Permission, get_auth_manager
from ...security.malicious_code_detector import get_malicious_code_detector
from ...security.rate_limiter import get_rate_limiter
from ...security.sandbox_security import get_sandbox_security_manager
from ...security.security_manager import get_security_manager

logger = get_logger("security_routes")

router = APIRouter()


# 请求模型
class BlacklistIPRequest(BaseModel):
    ip: str
    reason: str = "manual"


class WhitelistIPRequest(BaseModel):
    ip: str


class CodeSecurityCheckRequest(BaseModel):
    code: str
    filename: str = "unknown"


# 响应模型
class SecurityStatusResponse(BaseModel):
    status: str
    components: Dict[str, Any]


@router.get("/status", response_model=SecurityStatusResponse)
async def get_security_status(
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取安全系统状态（需要管理员权限）"""

    security_manager = get_security_manager()
    status = security_manager.get_security_status()

    return SecurityStatusResponse(**status)


@router.get("/statistics")
async def get_security_statistics(
    hours: int = 24,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取安全统计信息（需要管理员权限）"""

    audit_logger = get_security_audit_logger()
    rate_limiter = get_rate_limiter()
    sandbox_manager = get_sandbox_security_manager()

    return {
        "audit_statistics": audit_logger.get_security_statistics(hours),
        "rate_limit_statistics": rate_limiter.get_statistics(hours),
        "sandbox_statistics": sandbox_manager.get_resource_usage_stats(),
        "abuse_patterns": rate_limiter.detect_abuse_patterns(),
    }


@router.get("/audit/events")
async def get_audit_events(
    limit: int = 100,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取审计事件（需要管理员权限）"""

    audit_logger = get_security_audit_logger()

    # 转换枚举类型
    from ...security.audit_logger import AuditEventType, AuditSeverity

    event_type_enum = None
    if event_type:
        try:
            event_type_enum = AuditEventType(event_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的事件类型: {event_type}",
            )

    severity_enum = None
    if severity:
        try:
            severity_enum = AuditSeverity(severity)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的严重程度: {severity}",
            )

    events = audit_logger.get_recent_events(
        limit=limit, event_type=event_type_enum, severity=severity_enum, user_id=user_id
    )

    return {
        "events": events,
        "total": len(events),
        "filters": {
            "event_type": event_type,
            "severity": severity,
            "user_id": user_id,
            "limit": limit,
        },
    }


@router.get("/rate-limit/statistics")
async def get_rate_limit_statistics(
    hours: int = 1,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取速率限制统计（需要管理员权限）"""

    rate_limiter = get_rate_limiter()

    return {
        "statistics": rate_limiter.get_statistics(hours),
        "abuse_patterns": rate_limiter.detect_abuse_patterns(),
    }


@router.post("/rate-limit/blacklist")
async def add_ip_to_blacklist(
    request: BlacklistIPRequest,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """将IP添加到黑名单（需要管理员权限）"""

    rate_limiter = get_rate_limiter()
    rate_limiter.add_to_blacklist(request.ip, request.reason)

    return {"message": f"IP {request.ip} 已添加到黑名单"}


@router.delete("/rate-limit/blacklist/{ip}")
async def remove_ip_from_blacklist(
    ip: str,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """从黑名单移除IP（需要管理员权限）"""

    rate_limiter = get_rate_limiter()
    rate_limiter.remove_from_blacklist(ip)

    return {"message": f"IP {ip} 已从黑名单移除"}


@router.post("/rate-limit/whitelist")
async def add_ip_to_whitelist(
    request: WhitelistIPRequest,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """将IP添加到白名单（需要管理员权限）"""

    rate_limiter = get_rate_limiter()
    rate_limiter.add_to_whitelist(request.ip)

    return {"message": f"IP {request.ip} 已添加到白名单"}


@router.post("/rate-limit/auto-blacklist")
async def trigger_auto_blacklist(
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """触发自动黑名单（需要管理员权限）"""

    rate_limiter = get_rate_limiter()
    rate_limiter.auto_blacklist_abusers()

    return {"message": "自动黑名单已触发"}


@router.get("/sandbox/status")
async def get_sandbox_security_status(
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取沙盒安全状态（需要管理员权限）"""

    sandbox_manager = get_sandbox_security_manager()

    return {
        "security_summary": sandbox_manager.get_security_summary(),
        "resource_usage": sandbox_manager.get_resource_usage_stats(),
    }


@router.post("/sandbox/reset-violations")
async def reset_sandbox_violations(
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """重置沙盒违规记录（需要管理员权限）"""

    sandbox_manager = get_sandbox_security_manager()
    sandbox_manager.reset_violations()

    return {"message": "沙盒违规记录已重置"}


@router.post("/code/security-check")
async def check_code_security(
    request: CodeSecurityCheckRequest,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.EXECUTE)
    ),
):
    """检查代码安全性（需要执行权限）"""

    detector = get_malicious_code_detector()
    sandbox_manager = get_sandbox_security_manager()

    # 使用恶意代码检测器
    security_report = detector.generate_security_report(request.code, request.filename)

    # 使用沙盒安全管理器验证
    sandbox_check = sandbox_manager.can_execute_code(request.code, request.filename)

    return {
        "malicious_code_report": security_report,
        "sandbox_check": sandbox_check,
        "overall_safe": security_report["is_safe"] and sandbox_check["can_execute"],
    }


@router.get("/compliance/report")
async def get_compliance_report(
    start_date: datetime,
    end_date: datetime,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取合规报告（需要管理员权限）"""

    audit_logger = get_security_audit_logger()

    report = audit_logger.generate_compliance_report(start_date, end_date)

    return report


@router.get("/threats/recent")
async def get_recent_threats(
    hours: int = 24,
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取最近的威胁（需要管理员权限）"""

    audit_logger = get_security_audit_logger()
    rate_limiter = get_rate_limiter()

    # 获取高风险审计事件
    from ...security.audit_logger import AuditSeverity

    high_risk_events = audit_logger.get_recent_events(
        limit=100, severity=AuditSeverity.ERROR
    )

    critical_events = audit_logger.get_recent_events(
        limit=50, severity=AuditSeverity.CRITICAL
    )

    # 获取滥用模式
    abuse_patterns = rate_limiter.detect_abuse_patterns()

    return {
        "high_risk_events": high_risk_events,
        "critical_events": critical_events,
        "abuse_patterns": abuse_patterns,
        "summary": {
            "high_risk_count": len(high_risk_events),
            "critical_count": len(critical_events),
            "abuse_patterns_count": len(abuse_patterns),
        },
    }


@router.post("/system/rotate-keys")
async def rotate_encryption_keys(
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """轮换加密密钥（需要管理员权限）"""

    from ...security.data_encryption import get_data_encryption

    data_encryption = get_data_encryption()
    data_encryption.rotate_keys()

    return {"message": "加密密钥已轮换"}


@router.get("/config")
async def get_security_config(
    current_user=Depends(
        lambda: get_auth_manager().require_permission(Permission.ADMIN)
    ),
):
    """获取安全配置（需要管理员权限）"""

    security_manager = get_security_manager()

    # 返回脱敏后的配置
    config = security_manager.config.copy()

    # 脱敏敏感信息
    if "jwt" in config and "secret_key" in config["jwt"]:
        config["jwt"]["secret_key"] = "***"

    return {"config": config}
