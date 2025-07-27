#!/usr/bin/env python3
"""
TestAgent核心模块

提供错误处理、监控、恢复等核心功能
"""

from .agent_router import (AgentRouter, ConditionalRouter, Message,
                           RoutingRule, RoutingStrategy)
from .base_agent import (AgentInput, AgentOutput, AgentPhase, BaseAgent,
                         ReActAgent, SimpleAgent)
from .data_models import (APIResponse, ApplicationConfig, DatabaseConfig,
                          EnvironmentConfig, HealthCheckResponse, LLMConfig,
                          PathConfig, SystemInfo, get_global_config,
                          set_global_config)
from .dependencies import (DependencyChecker, ProjectInitializer,
                           VirtualEnvironmentManager,
                           check_system_requirements,
                           initialize_testagent_project)
from .error_handler import (ErrorHandler, error_context, get_error_handler,
                            handle_errors, safe_execute,
                            setup_global_exception_handler)
from .exceptions import (AuthenticationError, ConfigurationError,
                         ErrorCategory, ErrorSeverity, ExternalServiceError,
                         LLMError, MCPError, NetworkError, ProcessingError,
                         RAGError, ResourceError, StorageError,
                         TestAgentException, TimeoutError, UserInputError,
                         ValidationError, WorkflowError,
                         create_error_from_code, get_error_message)
from .monitoring import (HealthChecker, Metric, MetricsCollector,
                         PerformanceProfiler, PerformanceStats, SystemMonitor,
                         get_health_checker, get_metrics_collector,
                         get_profiler, get_system_monitor,
                         initialize_monitoring, monitor_performance,
                         record_metric, set_custom_metric, shutdown_monitoring)
from .recovery import (RecoveryAction, RecoveryManager, RecoveryStrategy,
                       ServiceLevel, get_recovery_manager,
                       initialize_recovery_system, with_recovery)
from .workspace import (FileNamingManager, TaskFileSystemManager,
                        workspace_manager)

__all__ = [
    # Exceptions
    "TestAgentException",
    "ErrorSeverity",
    "ErrorCategory",
    "ConfigurationError",
    "ValidationError",
    "NetworkError",
    "AuthenticationError",
    "ProcessingError",
    "StorageError",
    "ExternalServiceError",
    "LLMError",
    "RAGError",
    "MCPError",
    "WorkflowError",
    "UserInputError",
    "TimeoutError",
    "ResourceError",
    "get_error_message",
    "create_error_from_code",
    # Error Handler
    "ErrorHandler",
    "get_error_handler",
    "handle_errors",
    "safe_execute",
    "error_context",
    "setup_global_exception_handler",
    # Monitoring
    "Metric",
    "PerformanceStats",
    "MetricsCollector",
    "SystemMonitor",
    "HealthChecker",
    "PerformanceProfiler",
    "monitor_performance",
    "record_metric",
    "set_custom_metric",
    "get_metrics_collector",
    "get_system_monitor",
    "get_health_checker",
    "get_profiler",
    "initialize_monitoring",
    "shutdown_monitoring",
    # Recovery
    "ServiceLevel",
    "RecoveryAction",
    "RecoveryStrategy",
    "RecoveryManager",
    "get_recovery_manager",
    "with_recovery",
    "initialize_recovery_system",
    # 工作空间管理
    "TaskFileSystemManager",
    "FileNamingManager",
    "workspace_manager",
    # 智能体编排
    "BaseAgent",
    "SimpleAgent",
    "ReActAgent",
    "AgentInput",
    "AgentOutput",
    "AgentPhase",
    "AgentRouter",
    "RoutingRule",
    "Message",
    "RoutingStrategy",
    "ConditionalRouter",
    # 数据模型和配置
    "ApplicationConfig",
    "SystemInfo",
    "PathConfig",
    "EnvironmentConfig",
    "DatabaseConfig",
    "LLMConfig",
    "APIResponse",
    "HealthCheckResponse",
    "get_global_config",
    "set_global_config",
    # 依赖管理
    "VirtualEnvironmentManager",
    "DependencyChecker",
    "ProjectInitializer",
    "check_system_requirements",
    "initialize_testagent_project",
]


def initialize_core_systems():
    """初始化核心系统"""
    import logging

    logger = logging.getLogger("core_init")

    success = True

    try:
        # 设置全局异常处理器
        setup_global_exception_handler()
        logger.info("Global exception handler initialized")

        # 初始化监控系统
        if initialize_monitoring():
            logger.info("Monitoring system initialized")
        else:
            logger.warning("Monitoring system initialization failed")
            success = False

        # 初始化恢复系统
        if initialize_recovery_system():
            logger.info("Recovery system initialized")
        else:
            logger.warning("Recovery system initialization failed")
            success = False

        if success:
            logger.info("All core systems initialized successfully")
        else:
            logger.warning("Some core systems failed to initialize")

        return success

    except Exception as e:
        logger.error(f"Failed to initialize core systems: {e}")
        return False


def shutdown_core_systems():
    """关闭核心系统"""
    import logging

    logger = logging.getLogger("core_shutdown")

    try:
        # 关闭监控系统
        shutdown_monitoring()
        logger.info("Core systems shutdown completed")

    except Exception as e:
        logger.error(f"Error during core systems shutdown: {e}")


# 自动初始化标志
_initialized = False


def ensure_core_initialized():
    """确保核心系统已初始化"""
    global _initialized
    if not _initialized:
        _initialized = initialize_core_systems()
    return _initialized


# 在模块导入时自动初始化
ensure_core_initialized()
