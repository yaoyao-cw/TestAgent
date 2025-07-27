#!/usr/bin/env python3
"""
分布式会话管理系统

支持分布式节点一致路由的Session IDs管理，确保会话在分布式环境中的一致性
"""

import asyncio
import hashlib
import logging
import threading
import time
import uuid
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json

logger = logging.getLogger("session_manager")


@dataclass
class NodeInfo:
    """节点信息"""

    node_id: str
    host: str
    port: int
    status: str  # active, inactive, maintenance
    load: float = 0.0  # 负载指标 0.0-1.0
    last_heartbeat: datetime = field(default_factory=datetime.now)
    capabilities: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_healthy(self, heartbeat_timeout: int = 300) -> bool:
        """检查节点是否健康"""
        if self.status != "active":
            return False

        timeout_threshold = datetime.now() - timedelta(seconds=heartbeat_timeout)
        return self.last_heartbeat > timeout_threshold


@dataclass
class SessionRoute:
    """会话路由信息"""

    session_id: str
    node_id: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    sticky: bool = True  # 是否粘性会话
    priority: int = 0  # 路由优先级
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self):
        """更新访问时间和计数"""
        self.last_accessed = datetime.now()
        self.access_count += 1


class ConsistentHashRing:
    """一致性哈希环

    用于实现分布式节点的一致性路由
    """

    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self.ring: Dict[int, str] = {}
        self.nodes: Set[str] = set()
        self._lock = threading.RLock()

    def _hash(self, key: str) -> int:
        """计算哈希值"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node_id: str):
        """添加节点到哈希环"""
        with self._lock:
            if node_id in self.nodes:
                return

            self.nodes.add(node_id)

            # 为每个物理节点创建多个虚拟节点
            for i in range(self.virtual_nodes):
                virtual_key = f"{node_id}:{i}"
                hash_value = self._hash(virtual_key)
                self.ring[hash_value] = node_id

    def remove_node(self, node_id: str):
        """从哈希环移除节点"""
        with self._lock:
            if node_id not in self.nodes:
                return

            self.nodes.remove(node_id)

            # 移除所有虚拟节点
            keys_to_remove = [k for k, v in self.ring.items() if v == node_id]
            for key in keys_to_remove:
                del self.ring[key]

    def get_node(self, key: str) -> Optional[str]:
        """根据键获取对应的节点"""
        with self._lock:
            if not self.ring:
                return None

            hash_value = self._hash(key)

            # 在哈希环上顺时针查找第一个节点
            sorted_hashes = sorted(self.ring.keys())

            for ring_hash in sorted_hashes:
                if hash_value <= ring_hash:
                    return self.ring[ring_hash]

            # 如果没找到，返回第一个节点（环形结构）
            return self.ring[sorted_hashes[0]]

    def get_nodes_for_key(self, key: str, count: int = 3) -> List[str]:
        """获取键对应的多个节点（用于副本）"""
        with self._lock:
            if not self.ring or count <= 0:
                return []

            hash_value = self._hash(key)
            sorted_hashes = sorted(self.ring.keys())

            # 找到起始位置
            start_idx = 0
            for i, ring_hash in enumerate(sorted_hashes):
                if hash_value <= ring_hash:
                    start_idx = i
                    break

            # 收集节点，避免重复
            nodes = []
            seen_nodes = set()

            for i in range(len(sorted_hashes)):
                idx = (start_idx + i) % len(sorted_hashes)
                node_id = self.ring[sorted_hashes[idx]]

                if node_id not in seen_nodes:
                    nodes.append(node_id)
                    seen_nodes.add(node_id)

                    if len(nodes) >= count:
                        break

            return nodes

    def get_ring_info(self) -> Dict[str, Any]:
        """获取哈希环信息"""
        with self._lock:
            node_distribution = defaultdict(int)
            for node_id in self.ring.values():
                node_distribution[node_id] += 1

            return {
                "total_virtual_nodes": len(self.ring),
                "physical_nodes": len(self.nodes),
                "node_distribution": dict(node_distribution),
                "nodes": list(self.nodes),
            }


class LoadBalancer:
    """负载均衡器"""

    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}
        self._lock = threading.RLock()

    def add_node(self, node_info: NodeInfo):
        """添加节点"""
        with self._lock:
            self.nodes[node_info.node_id] = node_info

    def remove_node(self, node_id: str):
        """移除节点"""
        with self._lock:
            self.nodes.pop(node_id, None)

    def update_node_load(self, node_id: str, load: float):
        """更新节点负载"""
        with self._lock:
            if node_id in self.nodes:
                self.nodes[node_id].load = load

    def get_least_loaded_node(
        self, capabilities: Optional[Set[str]] = None
    ) -> Optional[str]:
        """获取负载最低的节点"""
        with self._lock:
            available_nodes = [
                node
                for node in self.nodes.values()
                if node.is_healthy()
                and (not capabilities or capabilities.issubset(node.capabilities))
            ]

            if not available_nodes:
                return None

            # 选择负载最低的节点
            return min(available_nodes, key=lambda n: n.load).node_id

    def get_node_by_weight(
        self, capabilities: Optional[Set[str]] = None
    ) -> Optional[str]:
        """基于权重选择节点"""
        with self._lock:
            available_nodes = [
                node
                for node in self.nodes.values()
                if node.is_healthy()
                and (not capabilities or capabilities.issubset(node.capabilities))
            ]

            if not available_nodes:
                return None

            # 计算权重（负载越低权重越高）
            total_weight = sum(1.0 - node.load for node in available_nodes)
            if total_weight <= 0:
                return available_nodes[0].node_id

            # 随机选择
            import random

            target = random.uniform(0, total_weight)
            current = 0

            for node in available_nodes:
                current += 1.0 - node.load
                if current >= target:
                    return node.node_id

            return available_nodes[-1].node_id

    def get_healthy_nodes(self) -> List[NodeInfo]:
        """获取健康节点列表"""
        with self._lock:
            return [node for node in self.nodes.values() if node.is_healthy()]

    def get_load_stats(self) -> Dict[str, Any]:
        """获取负载统计"""
        with self._lock:
            healthy_nodes = self.get_healthy_nodes()

            if not healthy_nodes:
                return {"error": "No healthy nodes"}

            loads = [node.load for node in healthy_nodes]

            return {
                "total_nodes": len(self.nodes),
                "healthy_nodes": len(healthy_nodes),
                "average_load": sum(loads) / len(loads),
                "min_load": min(loads),
                "max_load": max(loads),
                "node_loads": {node.node_id: node.load for node in healthy_nodes},
            }


class DistributedSessionManager:
    """分布式会话管理器"""

    def __init__(self, node_id: str, heartbeat_interval: int = 60):
        self.node_id = node_id
        self.heartbeat_interval = heartbeat_interval

        # 核心组件
        self.hash_ring = ConsistentHashRing()
        self.load_balancer = LoadBalancer()

        # 会话数据
        self.sessions: Dict[str, SessionRoute] = {}
        self.local_sessions: Set[str] = set()  # 本节点的会话

        # 节点管理
        self.nodes: Dict[str, NodeInfo] = {}

        # 线程控制
        self._running = False
        self._heartbeat_thread = None
        self._cleanup_thread = None
        self._lock = threading.RLock()

        # 配置
        self.session_timeout = 3600  # 1小时
        self.cleanup_interval = 300  # 5分钟

    def start(self):
        """启动会话管理器"""
        if self._running:
            return

        self._running = True

        # 注册本节点
        self.register_node(
            NodeInfo(
                node_id=self.node_id,
                host="localhost",  # 可以从配置获取
                port=8000,  # 可以从配置获取
                status="active",
            )
        )

        # 启动心跳线程
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

        logger.info(f"Distributed session manager started for node {self.node_id}")

    def stop(self):
        """停止会话管理器"""
        self._running = False

        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)

        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

        logger.info(f"Distributed session manager stopped for node {self.node_id}")

    def register_node(self, node_info: NodeInfo):
        """注册节点"""
        with self._lock:
            self.nodes[node_info.node_id] = node_info
            self.hash_ring.add_node(node_info.node_id)
            self.load_balancer.add_node(node_info)

        logger.info(f"Node registered: {node_info.node_id}")

    def unregister_node(self, node_id: str):
        """注销节点"""
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                self.hash_ring.remove_node(node_id)
                self.load_balancer.remove_node(node_id)

                # 迁移该节点的会话
                self._migrate_sessions_from_node(node_id)

        logger.info(f"Node unregistered: {node_id}")

    def create_session(
        self, sticky: bool = True, capabilities: Optional[Set[str]] = None
    ) -> Tuple[str, str]:
        """创建会话

        Returns:
            (session_id, assigned_node_id)
        """
        session_id = str(uuid.uuid4())

        # 选择节点
        if sticky:
            # 粘性会话使用一致性哈希
            assigned_node = self.hash_ring.get_node(session_id)
        else:
            # 非粘性会话使用负载均衡
            assigned_node = self.load_balancer.get_least_loaded_node(capabilities)

        if not assigned_node:
            raise RuntimeError("No available nodes for session creation")

        # 创建会话路由
        session_route = SessionRoute(
            session_id=session_id,
            node_id=assigned_node,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            sticky=sticky,
        )

        with self._lock:
            self.sessions[session_id] = session_route

            # 如果分配到本节点，添加到本地会话集合
            if assigned_node == self.node_id:
                self.local_sessions.add(session_id)

        logger.debug(f"Session created: {session_id} -> {assigned_node}")
        return session_id, assigned_node

    def get_session_node(self, session_id: str) -> Optional[str]:
        """获取会话对应的节点"""
        with self._lock:
            session_route = self.sessions.get(session_id)
            if session_route:
                session_route.touch()

                # 检查节点是否健康
                node_info = self.nodes.get(session_route.node_id)
                if node_info and node_info.is_healthy():
                    return session_route.node_id
                else:
                    # 节点不健康，重新路由
                    return self._reroute_session(session_id)

            return None

    def _reroute_session(self, session_id: str) -> Optional[str]:
        """重新路由会话"""
        with self._lock:
            session_route = self.sessions.get(session_id)
            if not session_route:
                return None

            # 选择新节点
            if session_route.sticky:
                # 粘性会话尝试使用一致性哈希的下一个节点
                candidate_nodes = self.hash_ring.get_nodes_for_key(session_id, 3)
                new_node = None
                for node_id in candidate_nodes:
                    node_info = self.nodes.get(node_id)
                    if node_info and node_info.is_healthy():
                        new_node = node_id
                        break
            else:
                # 非粘性会话使用负载均衡
                new_node = self.load_balancer.get_least_loaded_node()

            if not new_node:
                logger.error(f"Failed to reroute session {session_id}")
                return None

            # 更新路由
            old_node = session_route.node_id
            session_route.node_id = new_node
            session_route.last_accessed = datetime.now()

            # 更新本地会话集合
            if old_node == self.node_id:
                self.local_sessions.discard(session_id)
            if new_node == self.node_id:
                self.local_sessions.add(session_id)

            logger.info(f"Session rerouted: {session_id} from {old_node} to {new_node}")
            return new_node

    def _migrate_sessions_from_node(self, failed_node_id: str):
        """迁移失败节点的会话"""
        with self._lock:
            sessions_to_migrate = [
                session_id
                for session_id, route in self.sessions.items()
                if route.node_id == failed_node_id
            ]

            for session_id in sessions_to_migrate:
                self._reroute_session(session_id)

            logger.info(
                f"Migrated {len(sessions_to_migrate)} sessions from failed node {failed_node_id}"
            )

    def update_node_heartbeat(
        self, node_id: str, load: float = 0.0, metadata: Optional[Dict[str, Any]] = None
    ):
        """更新节点心跳"""
        with self._lock:
            node_info = self.nodes.get(node_id)
            if node_info:
                node_info.last_heartbeat = datetime.now()
                node_info.load = load
                if metadata:
                    node_info.metadata.update(metadata)

                # 更新负载均衡器
                self.load_balancer.update_node_load(node_id, load)

    def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            try:
                # 发送本节点心跳
                current_load = self._calculate_current_load()
                self.update_node_heartbeat(self.node_id, current_load)

                # 检查其他节点健康状态
                self._check_node_health()

                time.sleep(self.heartbeat_interval)

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                time.sleep(10)

    def _cleanup_loop(self):
        """清理循环"""
        while self._running:
            try:
                self._cleanup_expired_sessions()
                time.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                time.sleep(60)

    def _calculate_current_load(self) -> float:
        """计算当前节点负载"""
        with self._lock:
            # 基于本地会话数量计算负载
            local_session_count = len(self.local_sessions)
            # 可以根据实际情况调整负载计算逻辑
            return min(1.0, local_session_count / 100.0)

    def _check_node_health(self):
        """检查节点健康状态"""
        with self._lock:
            unhealthy_nodes = [
                node_id
                for node_id, node_info in self.nodes.items()
                if not node_info.is_healthy() and node_id != self.node_id
            ]

            for node_id in unhealthy_nodes:
                logger.warning(
                    f"Node {node_id} appears unhealthy, initiating migration"
                )
                self._migrate_sessions_from_node(node_id)
                # 可以选择是否立即移除节点，或者等待恢复

    def _cleanup_expired_sessions(self):
        """清理过期会话"""
        cutoff_time = datetime.now() - timedelta(seconds=self.session_timeout)

        with self._lock:
            expired_sessions = [
                session_id
                for session_id, route in self.sessions.items()
                if route.last_accessed < cutoff_time
            ]

            for session_id in expired_sessions:
                route = self.sessions.pop(session_id, None)
                if route and route.node_id == self.node_id:
                    self.local_sessions.discard(session_id)

            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

    def get_cluster_status(self) -> Dict[str, Any]:
        """获取集群状态"""
        with self._lock:
            healthy_nodes = [node for node in self.nodes.values() if node.is_healthy()]

            return {
                "cluster_info": {
                    "total_nodes": len(self.nodes),
                    "healthy_nodes": len(healthy_nodes),
                    "current_node": self.node_id,
                },
                "session_info": {
                    "total_sessions": len(self.sessions),
                    "local_sessions": len(self.local_sessions),
                    "session_distribution": self._get_session_distribution(),
                },
                "load_balancer_stats": self.load_balancer.get_load_stats(),
                "hash_ring_info": self.hash_ring.get_ring_info(),
                "nodes": [
                    {
                        "node_id": node.node_id,
                        "host": node.host,
                        "port": node.port,
                        "status": node.status,
                        "load": node.load,
                        "last_heartbeat": node.last_heartbeat.isoformat(),
                        "is_healthy": node.is_healthy(),
                    }
                    for node in self.nodes.values()
                ],
            }

    def _get_session_distribution(self) -> Dict[str, int]:
        """获取会话分布"""
        distribution = defaultdict(int)
        for route in self.sessions.values():
            distribution[route.node_id] += 1
        return dict(distribution)


# 全局分布式会话管理器实例
_distributed_session_manager: Optional[DistributedSessionManager] = None


def get_distributed_session_manager(
    node_id: Optional[str] = None,
) -> DistributedSessionManager:
    """获取全局分布式会话管理器实例"""
    global _distributed_session_manager
    if _distributed_session_manager is None:
        if not node_id:
            node_id = f"node-{uuid.uuid4().hex[:8]}"
        _distributed_session_manager = DistributedSessionManager(node_id)
        _distributed_session_manager.start()
    return _distributed_session_manager


# 便捷函数
def create_distributed_session(
    sticky: bool = True, capabilities: Optional[Set[str]] = None
) -> Tuple[str, str]:
    """创建分布式会话的便捷函数"""
    manager = get_distributed_session_manager()
    return manager.create_session(sticky, capabilities)


def get_session_node_route(session_id: str) -> Optional[str]:
    """获取会话节点路由的便捷函数"""
    manager = get_distributed_session_manager()
    return manager.get_session_node(session_id)


def get_cluster_status() -> Dict[str, Any]:
    """获取集群状态的便捷函数"""
    manager = get_distributed_session_manager()
    return manager.get_cluster_status()
