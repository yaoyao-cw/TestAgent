"""TestAgent服务模块

提供各种服务组件，包括错误监控、健康检查、任务监控等
"""

from .error_monitoring import (
    AlertManager,
    EnhancedMetricsCollector,
    ErrorCategory,
    ErrorReportGenerator,
    ErrorSeverity,
    NetworkErrorRecord,
    get_alert_manager,
    get_enhanced_metrics_collector,
    get_error_report_generator,
    initialize_error_monitoring,
    record_error_recovery,
    record_network_error,
    shutdown_error_monitoring,
)

# 只有在模块存在时才导入
try:
    from .health_monitor import (
        HealthChecker,
        HealthStatus,
        ServiceHealthMonitor,
        get_health_monitor,
        register_health_check,
    )
except ImportError:
    pass

try:
    from .task_creation_monitor import (
        TaskCreationMonitor,
        get_task_creation_monitor,
    )
except ImportError:
    pass

try:
    from .task_status_notifier import (
        NotificationChannel,
        TaskStatusNotifier,
        get_task_status_notifier,
    )
except ImportError:
    pass

__all__ = [
    # 错误监控
    "EnhancedMetricsCollector",
    "ErrorReportGenerator",
    "AlertManager",
    "ErrorCategory",
    "ErrorSeverity",
    "NetworkErrorRecord",
    "get_enhanced_metrics_collector",
    "get_error_report_generator",
    "get_alert_manager",
    "record_network_error",
    "record_error_recovery",
    "initialize_error_monitoring",
    "shutdown_error_monitoring",
]
