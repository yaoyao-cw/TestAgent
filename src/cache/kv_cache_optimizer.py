#!/usr/bin/env python3
"""
KV缓存优化系统

实现提示词前缀稳定性管理、仅追加模式的上下文更新机制、确定性序列化系统
以及KV缓存命中率监控，围绕KV缓存命中率进行设计优化
"""

import json
import hashlib
import logging
import threading
import time
import uuid
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import OrderedDict, defaultdict
from functools import wraps
import weakref

logger = logging.getLogger("kv_cache_optimizer")


@dataclass
class CacheHitStats:
    """缓存命中统计"""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    prefix_hits: int = 0
    prefix_misses: int = 0
    session_hits: int = 0
    session_misses: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def hit_rate(self) -> float:
        """总体命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    @property
    def prefix_hit_rate(self) -> float:
        """前缀命中率"""
        total_prefix = self.prefix_hits + self.prefix_misses
        if total_prefix == 0:
            return 0.0
        return self.prefix_hits / total_prefix

    @property
    def session_hit_rate(self) -> float:
        """会话命中率"""
        total_session = self.session_hits + self.session_misses
        if total_session == 0:
            return 0.0
        return self.session_hits / total_session


@dataclass
class PrefixCacheEntry:
    """前缀缓存条目"""

    prefix_hash: str
    prefix_content: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    token_count: int = 0

    def touch(self):
        """更新访问时间和计数"""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class SessionContext:
    """会话上下文"""

    session_id: str
    prefix_hash: str
    context_history: List[Dict[str, Any]]
    created_at: datetime
    last_accessed: datetime
    token_count: int = 0

    def touch(self):
        """更新访问时间"""
        self.last_accessed = datetime.now()


class DeterministicSerializer:
    """确定性序列化器

    确保JSON对象键顺序固定，避免因键顺序变化导致的缓存失效
    """

    @staticmethod
    def serialize(obj: Any) -> str:
        """确定性序列化对象"""
        return json.dumps(
            obj,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=DeterministicSerializer._default_handler,
        )

    @staticmethod
    def _default_handler(obj):
        """处理不可序列化的对象"""
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        elif hasattr(obj, "isoformat"):  # datetime对象
            return obj.isoformat()
        else:
            return str(obj)

    @staticmethod
    def hash_object(obj: Any) -> str:
        """生成对象的确定性哈希"""
        serialized = DeterministicSerializer.serialize(obj)
        return hashlib.sha256(serialized.encode()).hexdigest()


class PrefixStabilityManager:
    """提示词前缀稳定性管理器

    避免动态内容破坏缓存，保持前缀稳定性
    """

    def __init__(self):
        self._stable_prefixes: Dict[str, PrefixCacheEntry] = {}
        self._dynamic_patterns = {
            "timestamp",
            "current_time",
            "now",
            "today",
            "random",
            "uuid",
            "session_id",
            "request_id",
        }
        self._lock = threading.RLock()

    def extract_stable_prefix(self, prompt: str) -> Tuple[str, str]:
        """提取稳定前缀和动态后缀

        Args:
            prompt: 完整提示词

        Returns:
            (stable_prefix, dynamic_suffix)
        """
        lines = prompt.split("\n")
        stable_lines = []
        dynamic_start_idx = len(lines)

        for i, line in enumerate(lines):
            # 检查是否包含动态内容
            if self._contains_dynamic_content(line):
                dynamic_start_idx = i
                break
            stable_lines.append(line)

        stable_prefix = "\n".join(stable_lines)
        dynamic_suffix = (
            "\n".join(lines[dynamic_start_idx:])
            if dynamic_start_idx < len(lines)
            else ""
        )

        return stable_prefix, dynamic_suffix

    def _contains_dynamic_content(self, text: str) -> bool:
        """检查文本是否包含动态内容"""
        text_lower = text.lower()

        # 检查动态模式
        for pattern in self._dynamic_patterns:
            if pattern in text_lower:
                return True

        # 检查时间戳格式
        import re

        timestamp_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # 日期
            r"\d{2}:\d{2}:\d{2}",  # 时间
            r"\d{13}",  # 毫秒时间戳
            r"\d{10}",  # 秒时间戳
        ]

        for pattern in timestamp_patterns:
            if re.search(pattern, text):
                return True

        return False

    def get_prefix_hash(self, stable_prefix: str) -> str:
        """获取稳定前缀的哈希值"""
        return DeterministicSerializer.hash_object(stable_prefix)

    def cache_prefix(self, stable_prefix: str, token_count: int = 0) -> str:
        """缓存稳定前缀"""
        prefix_hash = self.get_prefix_hash(stable_prefix)

        with self._lock:
            if prefix_hash in self._stable_prefixes:
                self._stable_prefixes[prefix_hash].touch()
            else:
                self._stable_prefixes[prefix_hash] = PrefixCacheEntry(
                    prefix_hash=prefix_hash,
                    prefix_content=stable_prefix,
                    created_at=datetime.now(),
                    last_accessed=datetime.now(),
                    token_count=token_count,
                )

        return prefix_hash

    def get_cached_prefix(self, prefix_hash: str) -> Optional[PrefixCacheEntry]:
        """获取缓存的前缀"""
        with self._lock:
            entry = self._stable_prefixes.get(prefix_hash)
            if entry:
                entry.touch()
            return entry

    def get_prefix_stats(self) -> Dict[str, Any]:
        """获取前缀缓存统计"""
        with self._lock:
            total_entries = len(self._stable_prefixes)
            total_tokens = sum(
                entry.token_count for entry in self._stable_prefixes.values()
            )
            total_accesses = sum(
                entry.access_count for entry in self._stable_prefixes.values()
            )

            return {
                "total_prefixes": total_entries,
                "total_tokens": total_tokens,
                "total_accesses": total_accesses,
                "average_access_per_prefix": (
                    total_accesses / total_entries if total_entries > 0 else 0
                ),
            }


class AppendOnlyContextManager:
    """仅追加模式的上下文更新机制

    避免修改之前的动作或观测结果，只允许追加新内容
    """

    def __init__(self):
        self._contexts: Dict[str, List[Dict[str, Any]]] = {}
        self._context_hashes: Dict[str, List[str]] = {}
        self._lock = threading.RLock()

    def initialize_context(
        self, context_id: str, initial_content: List[Dict[str, Any]]
    ) -> str:
        """初始化上下文"""
        with self._lock:
            self._contexts[context_id] = initial_content.copy()
            self._context_hashes[context_id] = [
                DeterministicSerializer.hash_object(item) for item in initial_content
            ]

            return self._get_context_hash(context_id)

    def append_to_context(self, context_id: str, new_content: Dict[str, Any]) -> str:
        """追加内容到上下文"""
        with self._lock:
            if context_id not in self._contexts:
                raise ValueError(f"Context {context_id} not found")

            # 追加新内容
            self._contexts[context_id].append(new_content)

            # 计算新内容的哈希
            content_hash = DeterministicSerializer.hash_object(new_content)
            self._context_hashes[context_id].append(content_hash)

            return self._get_context_hash(context_id)

    def get_context(self, context_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取完整上下文"""
        with self._lock:
            return self._contexts.get(context_id, []).copy()

    def get_context_hash(self, context_id: str) -> Optional[str]:
        """获取上下文哈希"""
        with self._lock:
            return self._get_context_hash(context_id)

    def _get_context_hash(self, context_id: str) -> str:
        """计算上下文哈希"""
        if context_id not in self._context_hashes:
            return ""

        # 使用所有内容哈希的组合来生成上下文哈希
        combined_hash = "".join(self._context_hashes[context_id])
        return hashlib.sha256(combined_hash.encode()).hexdigest()

    def validate_context_integrity(self, context_id: str) -> bool:
        """验证上下文完整性"""
        with self._lock:
            if context_id not in self._contexts:
                return False

            context = self._contexts[context_id]
            stored_hashes = self._context_hashes[context_id]

            if len(context) != len(stored_hashes):
                return False

            # 重新计算哈希并比较
            for i, item in enumerate(context):
                calculated_hash = DeterministicSerializer.hash_object(item)
                if calculated_hash != stored_hashes[i]:
                    return False

            return True

    def get_context_stats(self) -> Dict[str, Any]:
        """获取上下文统计"""
        with self._lock:
            total_contexts = len(self._contexts)
            total_items = sum(len(context) for context in self._contexts.values())

            return {
                "total_contexts": total_contexts,
                "total_items": total_items,
                "average_items_per_context": (
                    total_items / total_contexts if total_contexts > 0 else 0
                ),
            }


class SessionManager:
    """会话管理器

    支持分布式节点一致路由的Session IDs管理
    """

    def __init__(self):
        self._sessions: Dict[str, SessionContext] = {}
        self._session_routes: Dict[str, str] = {}  # session_id -> node_id
        self._lock = threading.RLock()

    def create_session(self, node_id: Optional[str] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())

        with self._lock:
            self._sessions[session_id] = SessionContext(
                session_id=session_id,
                prefix_hash="",
                context_history=[],
                created_at=datetime.now(),
                last_accessed=datetime.now(),
            )

            if node_id:
                self._session_routes[session_id] = node_id

        return session_id

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """获取会话"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.touch()
            return session

    def update_session_context(
        self, session_id: str, prefix_hash: str, context_item: Dict[str, Any]
    ):
        """更新会话上下文"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.prefix_hash = prefix_hash
                session.context_history.append(context_item)
                session.touch()

    def get_session_route(self, session_id: str) -> Optional[str]:
        """获取会话路由的节点ID"""
        with self._lock:
            return self._session_routes.get(session_id)

    def set_session_route(self, session_id: str, node_id: str):
        """设置会话路由"""
        with self._lock:
            self._session_routes[session_id] = node_id

    def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """清理过期会话"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        with self._lock:
            expired_sessions = [
                session_id
                for session_id, session in self._sessions.items()
                if session.last_accessed < cutoff_time
            ]

            for session_id in expired_sessions:
                del self._sessions[session_id]
                self._session_routes.pop(session_id, None)

        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        return len(expired_sessions)

    def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计"""
        with self._lock:
            total_sessions = len(self._sessions)
            total_routes = len(self._session_routes)

            # 按节点统计会话分布
            node_distribution = defaultdict(int)
            for node_id in self._session_routes.values():
                node_distribution[node_id] += 1

            return {
                "total_sessions": total_sessions,
                "total_routes": total_routes,
                "node_distribution": dict(node_distribution),
                "average_context_length": (
                    sum(len(s.context_history) for s in self._sessions.values())
                    / total_sessions
                    if total_sessions > 0
                    else 0
                ),
            }


class KVCacheHitMonitor:
    """KV缓存命中率监控器"""

    def __init__(self):
        self._stats = CacheHitStats()
        self._detailed_stats: Dict[str, CacheHitStats] = defaultdict(CacheHitStats)
        self._lock = threading.RLock()
        self._monitoring_enabled = True

    def record_cache_hit(
        self,
        cache_type: str = "general",
        prefix_hit: bool = False,
        session_hit: bool = False,
    ):
        """记录缓存命中"""
        if not self._monitoring_enabled:
            return

        with self._lock:
            # 更新总体统计
            self._stats.total_requests += 1
            self._stats.cache_hits += 1
            self._stats.last_updated = datetime.now()

            if prefix_hit:
                self._stats.prefix_hits += 1

            if session_hit:
                self._stats.session_hits += 1

            # 更新详细统计
            detailed_stat = self._detailed_stats[cache_type]
            detailed_stat.total_requests += 1
            detailed_stat.cache_hits += 1
            detailed_stat.last_updated = datetime.now()

            if prefix_hit:
                detailed_stat.prefix_hits += 1

            if session_hit:
                detailed_stat.session_hits += 1

    def record_cache_miss(
        self,
        cache_type: str = "general",
        prefix_miss: bool = False,
        session_miss: bool = False,
    ):
        """记录缓存未命中"""
        if not self._monitoring_enabled:
            return

        with self._lock:
            # 更新总体统计
            self._stats.total_requests += 1
            self._stats.cache_misses += 1
            self._stats.last_updated = datetime.now()

            if prefix_miss:
                self._stats.prefix_misses += 1

            if session_miss:
                self._stats.session_misses += 1

            # 更新详细统计
            detailed_stat = self._detailed_stats[cache_type]
            detailed_stat.total_requests += 1
            detailed_stat.cache_misses += 1
            detailed_stat.last_updated = datetime.now()

            if prefix_miss:
                detailed_stat.prefix_misses += 1

            if session_miss:
                detailed_stat.session_misses += 1

    def get_hit_rate(self, cache_type: Optional[str] = None) -> float:
        """获取命中率"""
        with self._lock:
            if cache_type:
                return self._detailed_stats[cache_type].hit_rate
            else:
                return self._stats.hit_rate

    def get_detailed_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取详细统计信息"""
        with self._lock:
            result = {
                "overall": {
                    "hit_rate": self._stats.hit_rate,
                    "prefix_hit_rate": self._stats.prefix_hit_rate,
                    "session_hit_rate": self._stats.session_hit_rate,
                    "total_requests": self._stats.total_requests,
                    "cache_hits": self._stats.cache_hits,
                    "cache_misses": self._stats.cache_misses,
                    "last_updated": self._stats.last_updated.isoformat(),
                }
            }

            for cache_type, stats in self._detailed_stats.items():
                result[cache_type] = {
                    "hit_rate": stats.hit_rate,
                    "prefix_hit_rate": stats.prefix_hit_rate,
                    "session_hit_rate": stats.session_hit_rate,
                    "total_requests": stats.total_requests,
                    "cache_hits": stats.cache_hits,
                    "cache_misses": stats.cache_misses,
                    "last_updated": stats.last_updated.isoformat(),
                }

            return result

    def reset_stats(self, cache_type: Optional[str] = None):
        """重置统计信息"""
        with self._lock:
            if cache_type:
                self._detailed_stats[cache_type] = CacheHitStats()
            else:
                self._stats = CacheHitStats()
                self._detailed_stats.clear()

    def enable_monitoring(self):
        """启用监控"""
        self._monitoring_enabled = True

    def disable_monitoring(self):
        """禁用监控"""
        self._monitoring_enabled = False


class CachePerformanceAnalyzer:
    """缓存性能分析和优化建议系统"""

    def __init__(self, monitor: KVCacheHitMonitor):
        self.monitor = monitor

    def analyze_performance(self) -> Dict[str, Any]:
        """分析缓存性能"""
        stats = self.monitor.get_detailed_stats()
        overall_stats = stats.get("overall", {})

        analysis = {
            "performance_score": self._calculate_performance_score(overall_stats),
            "bottlenecks": self._identify_bottlenecks(stats),
            "recommendations": self._generate_recommendations(stats),
            "trends": self._analyze_trends(stats),
        }

        return analysis

    def _calculate_performance_score(self, stats: Dict[str, Any]) -> float:
        """计算性能评分 (0-100)"""
        hit_rate = stats.get("hit_rate", 0)
        prefix_hit_rate = stats.get("prefix_hit_rate", 0)
        session_hit_rate = stats.get("session_hit_rate", 0)

        # 加权计算性能评分
        score = (
            hit_rate * 0.5  # 总体命中率权重50%
            + prefix_hit_rate * 0.3  # 前缀命中率权重30%
            + session_hit_rate * 0.2  # 会话命中率权重20%
        ) * 100

        return min(100, max(0, score))

    def _identify_bottlenecks(self, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别性能瓶颈"""
        bottlenecks = []
        overall_stats = stats.get("overall", {})

        # 检查总体命中率
        if overall_stats.get("hit_rate", 0) < 0.7:
            bottlenecks.append(
                {
                    "type": "low_hit_rate",
                    "severity": "high",
                    "description": f"总体缓存命中率过低: {overall_stats.get('hit_rate', 0):.1%}",
                    "threshold": 0.7,
                }
            )

        # 检查前缀命中率
        if overall_stats.get("prefix_hit_rate", 0) < 0.8:
            bottlenecks.append(
                {
                    "type": "low_prefix_hit_rate",
                    "severity": "medium",
                    "description": f"前缀缓存命中率过低: {overall_stats.get('prefix_hit_rate', 0):.1%}",
                    "threshold": 0.8,
                }
            )

        # 检查会话命中率
        if overall_stats.get("session_hit_rate", 0) < 0.6:
            bottlenecks.append(
                {
                    "type": "low_session_hit_rate",
                    "severity": "medium",
                    "description": f"会话缓存命中率过低: {overall_stats.get('session_hit_rate', 0):.1%}",
                    "threshold": 0.6,
                }
            )

        return bottlenecks

    def _generate_recommendations(self, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成优化建议"""
        recommendations = []
        overall_stats = stats.get("overall", {})

        # 基于命中率的建议
        if overall_stats.get("hit_rate", 0) < 0.7:
            recommendations.append(
                {
                    "type": "improve_hit_rate",
                    "priority": "high",
                    "title": "提升缓存命中率",
                    "description": "当前缓存命中率较低，建议优化缓存策略",
                    "actions": [
                        "检查提示词前缀稳定性",
                        "优化上下文管理策略",
                        "增加缓存TTL时间",
                        "使用更细粒度的缓存键",
                    ],
                }
            )

        # 基于前缀命中率的建议
        if overall_stats.get("prefix_hit_rate", 0) < 0.8:
            recommendations.append(
                {
                    "type": "optimize_prefix_caching",
                    "priority": "medium",
                    "title": "优化前缀缓存",
                    "description": "前缀缓存命中率有待提升",
                    "actions": [
                        "减少提示词中的动态内容",
                        "将时间戳等动态信息移到后缀",
                        "使用模板化的提示词结构",
                        "启用前缀缓存预热",
                    ],
                }
            )

        # 基于会话命中率的建议
        if overall_stats.get("session_hit_rate", 0) < 0.6:
            recommendations.append(
                {
                    "type": "improve_session_management",
                    "priority": "medium",
                    "title": "改进会话管理",
                    "description": "会话缓存效果不佳",
                    "actions": [
                        "优化会话路由策略",
                        "增加会话保持时间",
                        "实现会话预热机制",
                        "优化节点间会话分布",
                    ],
                }
            )

        return recommendations

    def _analyze_trends(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """分析性能趋势"""
        # 这里可以扩展为基于历史数据的趋势分析
        # 目前返回基本的趋势信息
        overall_stats = stats.get("overall", {})

        return {
            "current_performance": (
                "good"
                if overall_stats.get("hit_rate", 0) > 0.8
                else "needs_improvement"
            ),
            "recommendation_priority": (
                "high" if overall_stats.get("hit_rate", 0) < 0.6 else "medium"
            ),
            "optimization_potential": max(0, 1.0 - overall_stats.get("hit_rate", 0)),
        }


class KVCacheOptimizer:
    """KV缓存优化系统主类"""

    def __init__(self):
        self.prefix_manager = PrefixStabilityManager()
        self.context_manager = AppendOnlyContextManager()
        self.session_manager = SessionManager()
        self.hit_monitor = KVCacheHitMonitor()
        self.performance_analyzer = CachePerformanceAnalyzer(self.hit_monitor)
        self._cleanup_thread = None
        self._cleanup_interval = 3600  # 1小时
        self._running = False

    def start(self):
        """启动KV缓存优化系统"""
        if self._running:
            return

        self._running = True
        self.hit_monitor.enable_monitoring()

        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

        logger.info("KV Cache Optimizer started")

    def stop(self):
        """停止KV缓存优化系统"""
        self._running = False
        self.hit_monitor.disable_monitoring()

        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

        logger.info("KV Cache Optimizer stopped")

    def _cleanup_loop(self):
        """清理循环"""
        while self._running:
            try:
                # 清理过期会话
                self.session_manager.cleanup_expired_sessions()
                time.sleep(self._cleanup_interval)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                time.sleep(60)  # 出错时等待1分钟再重试

    def optimize_prompt(
        self, prompt: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """优化提示词以提高KV缓存命中率"""
        # 提取稳定前缀
        stable_prefix, dynamic_suffix = self.prefix_manager.extract_stable_prefix(
            prompt
        )

        # 缓存前缀
        prefix_hash = self.prefix_manager.cache_prefix(stable_prefix)

        # 检查前缀缓存命中
        cached_prefix = self.prefix_manager.get_cached_prefix(prefix_hash)
        prefix_hit = cached_prefix is not None

        # 会话管理
        session_hit = False
        if session_id:
            session = self.session_manager.get_session(session_id)
            if session and session.prefix_hash == prefix_hash:
                session_hit = True
            elif session:
                self.session_manager.update_session_context(
                    session_id,
                    prefix_hash,
                    {"prompt": prompt, "timestamp": datetime.now().isoformat()},
                )

        # 记录统计
        if prefix_hit or session_hit:
            self.hit_monitor.record_cache_hit("prompt", prefix_hit, session_hit)
        else:
            self.hit_monitor.record_cache_miss(
                "prompt", not prefix_hit, not session_hit
            )

        return {
            "stable_prefix": stable_prefix,
            "dynamic_suffix": dynamic_suffix,
            "prefix_hash": prefix_hash,
            "prefix_hit": prefix_hit,
            "session_hit": session_hit,
            "optimized_prompt": prompt,  # 可以在这里进一步优化
            "cache_key": DeterministicSerializer.hash_object(
                {"prefix_hash": prefix_hash, "dynamic_content": dynamic_suffix}
            ),
        }

    def create_session(self, node_id: Optional[str] = None) -> str:
        """创建优化会话"""
        return self.session_manager.create_session(node_id)

    def initialize_context(
        self, context_id: str, initial_content: List[Dict[str, Any]]
    ) -> str:
        """初始化仅追加上下文"""
        return self.context_manager.initialize_context(context_id, initial_content)

    def append_to_context(self, context_id: str, new_content: Dict[str, Any]) -> str:
        """追加内容到上下文"""
        return self.context_manager.append_to_context(context_id, new_content)

    def get_performance_analysis(self) -> Dict[str, Any]:
        """获取性能分析报告"""
        return self.performance_analyzer.analyze_performance()

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        return {
            "cache_hit_stats": self.hit_monitor.get_detailed_stats(),
            "prefix_stats": self.prefix_manager.get_prefix_stats(),
            "context_stats": self.context_manager.get_context_stats(),
            "session_stats": self.session_manager.get_session_stats(),
            "performance_analysis": self.performance_analyzer.analyze_performance(),
        }


# 全局KV缓存优化器实例
_kv_cache_optimizer: Optional[KVCacheOptimizer] = None


def get_kv_cache_optimizer() -> KVCacheOptimizer:
    """获取全局KV缓存优化器实例"""
    global _kv_cache_optimizer
    if _kv_cache_optimizer is None:
        _kv_cache_optimizer = KVCacheOptimizer()
        _kv_cache_optimizer.start()
    return _kv_cache_optimizer


def kv_cache_optimized(session_aware: bool = True):
    """KV缓存优化装饰器"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            optimizer = get_kv_cache_optimizer()

            # 提取提示词参数
            prompt = kwargs.get("prompt") or (args[0] if args else "")
            session_id = kwargs.get("session_id") if session_aware else None

            if prompt:
                # 优化提示词
                optimization_result = optimizer.optimize_prompt(prompt, session_id)
                kwargs["prompt"] = optimization_result["optimized_prompt"]
                kwargs["_cache_info"] = optimization_result

            # 调用原函数
            result = await func(*args, **kwargs)

            return result

        return wrapper

    return decorator


# 便捷函数
def optimize_prompt_for_cache(
    prompt: str, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """优化提示词以提高缓存命中率的便捷函数"""
    optimizer = get_kv_cache_optimizer()
    return optimizer.optimize_prompt(prompt, session_id)


def create_cache_session(node_id: Optional[str] = None) -> str:
    """创建缓存会话的便捷函数"""
    optimizer = get_kv_cache_optimizer()
    return optimizer.create_session(node_id)


def get_cache_performance_stats() -> Dict[str, Any]:
    """获取缓存性能统计的便捷函数"""
    optimizer = get_kv_cache_optimizer()
    return optimizer.get_comprehensive_stats()


def serialize_deterministically(obj: Any) -> str:
    """确定性序列化的便捷函数"""
    return DeterministicSerializer.serialize(obj)
