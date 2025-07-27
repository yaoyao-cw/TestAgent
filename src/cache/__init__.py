#!/usr/bin/env python3
"""
缓存模块

提供统一的缓存管理功能，包括：
- 通用缓存管理
- LLM响应缓存
- RAG检索结果缓存
- 向量化结果缓存
"""

from .cache_hit_monitor import (
    CacheHitMonitorService,
    CacheMetricsCollector,
    MonitoringConfig,
    PerformanceAlert,
    RealTimeMonitor,
    export_cache_metrics_prometheus,
    get_cache_dashboard_data,
    get_cache_historical_report,
    get_cache_hit_monitor_service,
    start_cache_monitoring,
)
from .cache_manager import (
    CacheBackend,
    CacheEntry,
    CacheManager,
    MemoryCache,
    RedisCache,
    cache,
    cache_key,
    get_cache_manager,
)
from .kv_cache_optimizer import (
    AppendOnlyContextManager,
    CachePerformanceAnalyzer,
    DeterministicSerializer,
    KVCacheHitMonitor,
    KVCacheOptimizer,
    PrefixStabilityManager,
    SessionManager,
    create_cache_session,
    get_cache_performance_stats,
    get_kv_cache_optimizer,
    kv_cache_optimized,
    optimize_prompt_for_cache,
    serialize_deterministically,
)
from .llm_cache import (
    LLMCache,
    cache_llm_response,
    clear_llm_cache,
    get_cached_llm_response,
    get_llm_cache,
    llm_cache,
)
from .rag_cache import (
    RAGCache,
    cache_retrieval_result,
    cache_vector_result,
    get_cached_retrieval,
    get_cached_vector_result,
    get_rag_cache,
    rag_retrieval_cache,
    vector_cache,
)
from .session_manager import (
    ConsistentHashRing,
    DistributedSessionManager,
    LoadBalancer,
    NodeInfo,
    SessionRoute,
    create_distributed_session,
    get_cluster_status,
    get_distributed_session_manager,
    get_session_node_route,
)

__all__ = [
    # Cache Manager
    "CacheBackend",
    "MemoryCache",
    "RedisCache",
    "CacheManager",
    "CacheEntry",
    "get_cache_manager",
    "cache",
    "cache_key",
    # LLM Cache
    "LLMCache",
    "get_llm_cache",
    "llm_cache",
    "cache_llm_response",
    "get_cached_llm_response",
    "clear_llm_cache",
    # RAG Cache
    "RAGCache",
    "get_rag_cache",
    "rag_retrieval_cache",
    "vector_cache",
    "cache_retrieval_result",
    "get_cached_retrieval",
    "cache_vector_result",
    "get_cached_vector_result",
    # KV Cache Optimizer
    "KVCacheOptimizer",
    "DeterministicSerializer",
    "PrefixStabilityManager",
    "AppendOnlyContextManager",
    "SessionManager",
    "KVCacheHitMonitor",
    "CachePerformanceAnalyzer",
    "get_kv_cache_optimizer",
    "kv_cache_optimized",
    "optimize_prompt_for_cache",
    "create_cache_session",
    "get_cache_performance_stats",
    "serialize_deterministically",
    # Cache Hit Monitor
    "CacheHitMonitorService",
    "RealTimeMonitor",
    "CacheMetricsCollector",
    "MonitoringConfig",
    "PerformanceAlert",
    "get_cache_hit_monitor_service",
    "start_cache_monitoring",
    "get_cache_dashboard_data",
    "get_cache_historical_report",
    "export_cache_metrics_prometheus",
    # Session Manager
    "DistributedSessionManager",
    "ConsistentHashRing",
    "LoadBalancer",
    "NodeInfo",
    "SessionRoute",
    "get_distributed_session_manager",
    "create_distributed_session",
    "get_session_node_route",
    "get_cluster_status",
]


def initialize_cache_system():
    """初始化缓存系统"""
    import logging

    logger = logging.getLogger("cache_init")

    try:
        # 初始化缓存管理器
        cache_manager = get_cache_manager()
        logger.info("Cache manager initialized")

        # 初始化LLM缓存
        llm_cache = get_llm_cache()
        logger.info("LLM cache initialized")

        # 初始化RAG缓存
        rag_cache = get_rag_cache()
        logger.info("RAG cache initialized")

        # 初始化KV缓存优化器
        kv_optimizer = get_kv_cache_optimizer()
        logger.info("KV cache optimizer initialized")

        # 初始化缓存命中率监控
        monitor_service = get_cache_hit_monitor_service()
        logger.info("Cache hit monitor service initialized")

        logger.info("Cache system initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize cache system: {e}")
        return False


def shutdown_cache_system():
    """关闭缓存系统"""
    import logging

    logger = logging.getLogger("cache_shutdown")

    try:
        # 这里可以添加缓存系统的清理逻辑
        logger.info("Cache system shutdown completed")

    except Exception as e:
        logger.error(f"Error during cache system shutdown: {e}")


# 自动初始化标志
_initialized = False


def ensure_cache_initialized():
    """确保缓存系统已初始化"""
    global _initialized
    if not _initialized:
        _initialized = initialize_cache_system()
    return _initialized


# 在模块导入时自动初始化
ensure_cache_initialized()
