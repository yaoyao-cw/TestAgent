#!/usr/bin/env python3
"""
缓存命中率监控服务

实现KV缓存命中率统计和监控、缓存性能分析和优化建议系统、
Session IDs管理，支持分布式节点一致路由
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

from .kv_cache_optimizer import get_kv_cache_optimizer, KVCacheHitMonitor

logger = logging.getLogger("cache_hit_monitor")


@dataclass
class MonitoringConfig:
    """监控配置"""

    enable_real_time_monitoring: bool = True
    stats_collection_interval: int = 60  # 秒
    performance_analysis_interval: int = 300  # 5分钟
    alert_threshold_hit_rate: float = 0.6  # 命中率低于60%时告警
    alert_threshold_prefix_hit_rate: float = 0.7  # 前缀命中率低于70%时告警
    max_history_records: int = 1000
    enable_alerts: bool = True


@dataclass
class PerformanceAlert:
    """性能告警"""

    alert_type: str
    severity: str  # low, medium, high, critical
    message: str
    metric_value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False


@dataclass
class HistoricalRecord:
    """历史记录"""

    timestamp: datetime
    hit_rate: float
    prefix_hit_rate: float
    session_hit_rate: float
    total_requests: int
    cache_hits: int
    cache_misses: int


class RealTimeMonitor:
    """实时监控器"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.kv_optimizer = get_kv_cache_optimizer()
        self.hit_monitor = self.kv_optimizer.hit_monitor

        self._monitoring = False
        self._monitor_thread = None
        self._analysis_thread = None

        # 历史数据
        self._history: deque = deque(maxlen=config.max_history_records)
        self._alerts: List[PerformanceAlert] = []

        # 回调函数
        self._alert_callbacks: List[Callable[[PerformanceAlert], None]] = []
        self._stats_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        self._lock = threading.RLock()

    def start_monitoring(self):
        """启动实时监控"""
        if self._monitoring:
            return

        self._monitoring = True

        # 启动统计收集线程
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self._monitor_thread.start()

        # 启动性能分析线程
        self._analysis_thread = threading.Thread(
            target=self._analysis_loop, daemon=True
        )
        self._analysis_thread.start()

        logger.info("Real-time cache monitoring started")

    def stop_monitoring(self):
        """停止实时监控"""
        self._monitoring = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

        if self._analysis_thread:
            self._analysis_thread.join(timeout=5)

        logger.info("Real-time cache monitoring stopped")

    def _monitoring_loop(self):
        """监控循环"""
        while self._monitoring:
            try:
                # 收集当前统计信息
                stats = self.hit_monitor.get_detailed_stats()
                overall_stats = stats.get("overall", {})

                # 创建历史记录
                record = HistoricalRecord(
                    timestamp=datetime.now(),
                    hit_rate=overall_stats.get("hit_rate", 0),
                    prefix_hit_rate=overall_stats.get("prefix_hit_rate", 0),
                    session_hit_rate=overall_stats.get("session_hit_rate", 0),
                    total_requests=overall_stats.get("total_requests", 0),
                    cache_hits=overall_stats.get("cache_hits", 0),
                    cache_misses=overall_stats.get("cache_misses", 0),
                )

                with self._lock:
                    self._history.append(record)

                # 检查告警条件
                if self.config.enable_alerts:
                    self._check_alerts(record)

                # 调用统计回调
                for callback in self._stats_callbacks:
                    try:
                        callback(stats)
                    except Exception as e:
                        logger.error(f"Error in stats callback: {e}")

                time.sleep(self.config.stats_collection_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)

    def _analysis_loop(self):
        """性能分析循环"""
        while self._monitoring:
            try:
                # 执行性能分析
                analysis = self.kv_optimizer.get_performance_analysis()

                # 记录分析结果
                logger.info(
                    f"Performance analysis: score={analysis.get('performance_score', 0):.1f}"
                )

                # 检查是否需要生成建议告警
                if analysis.get("performance_score", 100) < 70:
                    self._create_performance_alert(
                        "low_performance_score",
                        "medium",
                        f"缓存性能评分较低: {analysis.get('performance_score', 0):.1f}",
                        analysis.get("performance_score", 0),
                        70.0,
                    )

                time.sleep(self.config.performance_analysis_interval)

            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                time.sleep(30)

    def _check_alerts(self, record: HistoricalRecord):
        """检查告警条件"""
        # 检查总体命中率
        if record.hit_rate < self.config.alert_threshold_hit_rate:
            self._create_performance_alert(
                "low_hit_rate",
                "high",
                f"缓存命中率过低: {record.hit_rate:.1%}",
                record.hit_rate,
                self.config.alert_threshold_hit_rate,
            )

        # 检查前缀命中率
        if record.prefix_hit_rate < self.config.alert_threshold_prefix_hit_rate:
            self._create_performance_alert(
                "low_prefix_hit_rate",
                "medium",
                f"前缀缓存命中率过低: {record.prefix_hit_rate:.1%}",
                record.prefix_hit_rate,
                self.config.alert_threshold_prefix_hit_rate,
            )

        # 检查请求量异常
        if len(self._history) > 1:
            prev_record = self._history[-2]
            request_growth = (record.total_requests - prev_record.total_requests) / max(
                prev_record.total_requests, 1
            )

            if request_growth > 2.0:  # 请求量增长超过200%
                self._create_performance_alert(
                    "high_request_growth",
                    "medium",
                    f"请求量异常增长: {request_growth:.1%}",
                    request_growth,
                    2.0,
                )

    def _create_performance_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metric_value: float,
        threshold: float,
    ):
        """创建性能告警"""
        alert = PerformanceAlert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric_value=metric_value,
            threshold=threshold,
            timestamp=datetime.now(),
        )

        with self._lock:
            # 检查是否已存在相同类型的未解决告警
            existing_alert = next(
                (
                    a
                    for a in self._alerts
                    if a.alert_type == alert_type and not a.resolved
                ),
                None,
            )

            if not existing_alert:
                self._alerts.append(alert)
                logger.warning(f"Performance alert: {message}")

                # 调用告警回调
                for callback in self._alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")

    def resolve_alert(self, alert_type: str):
        """解决告警"""
        with self._lock:
            for alert in self._alerts:
                if alert.alert_type == alert_type and not alert.resolved:
                    alert.resolved = True
                    logger.info(f"Alert resolved: {alert_type}")

    def get_active_alerts(self) -> List[PerformanceAlert]:
        """获取活跃告警"""
        with self._lock:
            return [alert for alert in self._alerts if not alert.resolved]

    def get_historical_data(self, hours: int = 24) -> List[HistoricalRecord]:
        """获取历史数据"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            return [
                record for record in self._history if record.timestamp >= cutoff_time
            ]

    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """添加告警回调"""
        self._alert_callbacks.append(callback)

    def add_stats_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加统计回调"""
        self._stats_callbacks.append(callback)

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        with self._lock:
            active_alerts = self.get_active_alerts()
            recent_data = self.get_historical_data(1)  # 最近1小时

            if recent_data:
                avg_hit_rate = sum(r.hit_rate for r in recent_data) / len(recent_data)
                avg_prefix_hit_rate = sum(r.prefix_hit_rate for r in recent_data) / len(
                    recent_data
                )
                total_requests = sum(r.total_requests for r in recent_data)
            else:
                avg_hit_rate = avg_prefix_hit_rate = total_requests = 0

            return {
                "monitoring_status": "active" if self._monitoring else "inactive",
                "active_alerts_count": len(active_alerts),
                "recent_performance": {
                    "avg_hit_rate": avg_hit_rate,
                    "avg_prefix_hit_rate": avg_prefix_hit_rate,
                    "total_requests_last_hour": total_requests,
                },
                "history_records_count": len(self._history),
                "last_update": (
                    self._history[-1].timestamp.isoformat() if self._history else None
                ),
            }


class CacheMetricsCollector:
    """缓存指标收集器"""

    def __init__(self):
        self.kv_optimizer = get_kv_cache_optimizer()
        self._custom_metrics: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def collect_system_metrics(self) -> Dict[str, Any]:
        """收集系统指标"""
        try:
            import psutil

            # 系统资源指标
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()

            # 进程指标
            process = psutil.Process()
            process_memory = process.memory_info()

            return {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available": memory.available,
                    "memory_used": memory.used,
                },
                "process": {
                    "memory_rss": process_memory.rss,
                    "memory_vms": process_memory.vms,
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads(),
                },
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}

    def collect_cache_metrics(self) -> Dict[str, Any]:
        """收集缓存指标"""
        return self.kv_optimizer.get_comprehensive_stats()

    def add_custom_metric(
        self, name: str, value: Any, tags: Optional[Dict[str, str]] = None
    ):
        """添加自定义指标"""
        with self._lock:
            self._custom_metrics[name] = {
                "value": value,
                "tags": tags or {},
                "timestamp": datetime.now().isoformat(),
            }

    def get_custom_metrics(self) -> Dict[str, Any]:
        """获取自定义指标"""
        with self._lock:
            return self._custom_metrics.copy()

    def collect_all_metrics(self) -> Dict[str, Any]:
        """收集所有指标"""
        return {
            "timestamp": datetime.now().isoformat(),
            "system_metrics": self.collect_system_metrics(),
            "cache_metrics": self.collect_cache_metrics(),
            "custom_metrics": self.get_custom_metrics(),
        }


class CacheHitMonitorService:
    """缓存命中率监控服务主类"""

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self.real_time_monitor = RealTimeMonitor(self.config)
        self.metrics_collector = CacheMetricsCollector()
        self._service_running = False

    def start_service(self):
        """启动监控服务"""
        if self._service_running:
            return

        self._service_running = True

        if self.config.enable_real_time_monitoring:
            self.real_time_monitor.start_monitoring()

        logger.info("Cache hit monitor service started")

    def stop_service(self):
        """停止监控服务"""
        if not self._service_running:
            return

        self._service_running = False
        self.real_time_monitor.stop_monitoring()

        logger.info("Cache hit monitor service stopped")

    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表板数据"""
        return {
            "service_status": {
                "running": self._service_running,
                "monitoring_enabled": self.config.enable_real_time_monitoring,
            },
            "current_metrics": self.metrics_collector.collect_all_metrics(),
            "monitoring_summary": self.real_time_monitor.get_monitoring_summary(),
            "active_alerts": [
                {
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                }
                for alert in self.real_time_monitor.get_active_alerts()
            ],
            "performance_analysis": self.metrics_collector.kv_optimizer.get_performance_analysis(),
        }

    def get_historical_report(self, hours: int = 24) -> Dict[str, Any]:
        """获取历史报告"""
        historical_data = self.real_time_monitor.get_historical_data(hours)

        if not historical_data:
            return {"error": "No historical data available"}

        # 计算统计信息
        hit_rates = [r.hit_rate for r in historical_data]
        prefix_hit_rates = [r.prefix_hit_rate for r in historical_data]
        request_counts = [r.total_requests for r in historical_data]

        return {
            "time_range_hours": hours,
            "data_points": len(historical_data),
            "statistics": {
                "hit_rate": {
                    "min": min(hit_rates),
                    "max": max(hit_rates),
                    "avg": sum(hit_rates) / len(hit_rates),
                    "current": hit_rates[-1] if hit_rates else 0,
                },
                "prefix_hit_rate": {
                    "min": min(prefix_hit_rates),
                    "max": max(prefix_hit_rates),
                    "avg": sum(prefix_hit_rates) / len(prefix_hit_rates),
                    "current": prefix_hit_rates[-1] if prefix_hit_rates else 0,
                },
                "total_requests": sum(request_counts),
                "avg_requests_per_hour": (
                    sum(request_counts) / hours if hours > 0 else 0
                ),
            },
            "timeline": [
                {
                    "timestamp": record.timestamp.isoformat(),
                    "hit_rate": record.hit_rate,
                    "prefix_hit_rate": record.prefix_hit_rate,
                    "session_hit_rate": record.session_hit_rate,
                    "total_requests": record.total_requests,
                }
                for record in historical_data
            ],
        }

    def add_alert_handler(self, handler: Callable[[PerformanceAlert], None]):
        """添加告警处理器"""
        self.real_time_monitor.add_alert_callback(handler)

    def add_metrics_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """添加指标处理器"""
        self.real_time_monitor.add_stats_callback(handler)

    def export_metrics_prometheus(self) -> str:
        """导出Prometheus格式的指标"""
        metrics = self.metrics_collector.collect_all_metrics()
        cache_metrics = metrics.get("cache_metrics", {})
        hit_stats = cache_metrics.get("cache_hit_stats", {}).get("overall", {})

        prometheus_metrics = []

        # 缓存命中率指标
        prometheus_metrics.append(f'cache_hit_rate {hit_stats.get("hit_rate", 0)}')
        prometheus_metrics.append(
            f'cache_prefix_hit_rate {hit_stats.get("prefix_hit_rate", 0)}'
        )
        prometheus_metrics.append(
            f'cache_session_hit_rate {hit_stats.get("session_hit_rate", 0)}'
        )
        prometheus_metrics.append(
            f'cache_total_requests {hit_stats.get("total_requests", 0)}'
        )
        prometheus_metrics.append(f'cache_hits {hit_stats.get("cache_hits", 0)}')
        prometheus_metrics.append(f'cache_misses {hit_stats.get("cache_misses", 0)}')

        # 系统指标
        system_metrics = metrics.get("system_metrics", {})
        if system_metrics:
            system = system_metrics.get("system", {})
            process = system_metrics.get("process", {})

            prometheus_metrics.append(
                f'system_cpu_percent {system.get("cpu_percent", 0)}'
            )
            prometheus_metrics.append(
                f'system_memory_percent {system.get("memory_percent", 0)}'
            )
            prometheus_metrics.append(
                f'process_memory_rss {process.get("memory_rss", 0)}'
            )
            prometheus_metrics.append(
                f'process_cpu_percent {process.get("cpu_percent", 0)}'
            )

        return "\n".join(prometheus_metrics)


# 全局监控服务实例
_cache_hit_monitor_service: Optional[CacheHitMonitorService] = None


def get_cache_hit_monitor_service() -> CacheHitMonitorService:
    """获取全局缓存命中率监控服务实例"""
    global _cache_hit_monitor_service
    if _cache_hit_monitor_service is None:
        _cache_hit_monitor_service = CacheHitMonitorService()
        _cache_hit_monitor_service.start_service()
    return _cache_hit_monitor_service


# 便捷函数
def start_cache_monitoring():
    """启动缓存监控的便捷函数"""
    service = get_cache_hit_monitor_service()
    service.start_service()


def get_cache_dashboard_data() -> Dict[str, Any]:
    """获取缓存仪表板数据的便捷函数"""
    service = get_cache_hit_monitor_service()
    return service.get_dashboard_data()


def get_cache_historical_report(hours: int = 24) -> Dict[str, Any]:
    """获取缓存历史报告的便捷函数"""
    service = get_cache_hit_monitor_service()
    return service.get_historical_report(hours)


def export_cache_metrics_prometheus() -> str:
    """导出Prometheus格式缓存指标的便捷函数"""
    service = get_cache_hit_monitor_service()
    return service.export_metrics_prometheus()
