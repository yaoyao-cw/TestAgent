#!/usr/bin/env python3
"""
性能优化模块

提供性能优化功能，包括：
- 并发处理优化
- 异步执行优化
- 资源管理和监控
- 内存优化
"""

from .optimizer import (
    PerformanceConfig,
    ResourceMonitor,
    ConcurrencyManager,
    MemoryManager,
    PerformanceOptimizer,
    get_performance_optimizer,
    optimize_performance,
    batch_process,
    memory_optimized,
    run_concurrent_tasks,
    run_with_timeout,
    optimize_memory,
    get_performance_stats
)

__all__ = [
    # Core Classes
    "PerformanceConfig",
    "ResourceMonitor",
    "ConcurrencyManager", 
    "MemoryManager",
    "PerformanceOptimizer",
    
    # Functions
    "get_performance_optimizer",
    "optimize_performance",
    "batch_process",
    "memory_optimized",
    "run_concurrent_tasks",
    "run_with_timeout",
    "optimize_memory",
    "get_performance_stats"
]


def initialize_performance_system():
    """初始化性能优化系统"""
    import logging
    logger = logging.getLogger("performance_init")
    
    try:
        # 初始化性能优化器
        optimizer = get_performance_optimizer()
        logger.info("Performance optimizer initialized")
        
        logger.info("Performance optimization system initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize performance system: {e}")
        return False


def shutdown_performance_system():
    """关闭性能优化系统"""
    import logging
    logger = logging.getLogger("performance_shutdown")
    
    try:
        # 关闭性能优化器
        optimizer = get_performance_optimizer()
        if optimizer:
            optimizer.shutdown()
        
        logger.info("Performance optimization system shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during performance system shutdown: {e}")


# 自动初始化标志
_initialized = False


def ensure_performance_initialized():
    """确保性能优化系统已初始化"""
    global _initialized
    if not _initialized:
        _initialized = initialize_performance_system()
    return _initialized


# 在模块导入时自动初始化
ensure_performance_initialized()