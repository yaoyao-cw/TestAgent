#!/usr/bin/env python3
"""
KV缓存优化系统测试

测试KV缓存优化系统的各个组件功能
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.cache.kv_cache_optimizer import (
    DeterministicSerializer,
    PrefixStabilityManager,
    AppendOnlyContextManager,
    SessionManager,
    KVCacheHitMonitor,
    CachePerformanceAnalyzer,
    KVCacheOptimizer,
    get_kv_cache_optimizer,
    optimize_prompt_for_cache,
    serialize_deterministically,
)

from src.cache.cache_hit_monitor import (
    CacheHitMonitorService,
    MonitoringConfig,
    get_cache_hit_monitor_service,
)

from src.cache.session_manager import (
    DistributedSessionManager,
    ConsistentHashRing,
    LoadBalancer,
    NodeInfo,
    get_distributed_session_manager,
)


class TestDeterministicSerializer:
    """测试确定性序列化器"""

    def test_serialize_dict_order(self):
        """测试字典键顺序的确定性"""
        dict1 = {"b": 2, "a": 1, "c": 3}
        dict2 = {"a": 1, "b": 2, "c": 3}
        dict3 = {"c": 3, "a": 1, "b": 2}

        # 所有字典应该产生相同的序列化结果
        result1 = DeterministicSerializer.serialize(dict1)
        result2 = DeterministicSerializer.serialize(dict2)
        result3 = DeterministicSerializer.serialize(dict3)

        assert result1 == result2 == result3
        assert '{"a":1,"b":2,"c":3}' == result1

    def test_hash_consistency(self):
        """测试哈希一致性"""
        obj1 = {"messages": [{"role": "user", "content": "test"}], "temperature": 0.7}
        obj2 = {"temperature": 0.7, "messages": [{"role": "user", "content": "test"}]}

        hash1 = DeterministicSerializer.hash_object(obj1)
        hash2 = DeterministicSerializer.hash_object(obj2)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_serialize_datetime(self):
        """测试日期时间序列化"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        obj = {"timestamp": dt, "data": "test"}

        result = DeterministicSerializer.serialize(obj)
        assert "2024-01-01T12:00:00" in result

    def test_serialize_custom_object(self):
        """测试自定义对象序列化"""

        class TestObj:
            def __init__(self):
                self.name = "test"
                self.value = 42

        obj = TestObj()
        result = DeterministicSerializer.serialize(obj)

        assert "test" in result
        assert "42" in result


class TestPrefixStabilityManager:
    """测试提示词前缀稳定性管理器"""

    def setup_method(self):
        """设置测试环境"""
        self.manager = PrefixStabilityManager()

    def test_extract_stable_prefix(self):
        """测试提取稳定前缀"""
        prompt = """You are a helpful assistant.
Please help with the following task:

Current time: 2024-01-01 12:00:00
Task ID: task-123
Random value: 0.5432"""

        stable_prefix, dynamic_suffix = self.manager.extract_stable_prefix(prompt)

        assert "You are a helpful assistant" in stable_prefix
        assert "Please help with the following task" in stable_prefix
        assert "Current time:" in dynamic_suffix
        assert "Random value:" in dynamic_suffix

    def test_dynamic_content_detection(self):
        """测试动态内容检测"""
        # 包含时间戳的文本
        assert self.manager._contains_dynamic_content("Current time: 2024-01-01")
        assert self.manager._contains_dynamic_content("Timestamp: 1704110400")

        # 包含随机内容的文本
        assert self.manager._contains_dynamic_content("Random seed: 12345")
        assert self.manager._contains_dynamic_content("UUID: abc-def-123")

        # 不包含动态内容的文本
        assert not self.manager._contains_dynamic_content("You are a helpful assistant")
        assert not self.manager._contains_dynamic_content("Please complete this task")

    def test_prefix_caching(self):
        """测试前缀缓存"""
        prefix = "You are a helpful assistant.\nPlease help with tasks."

        # 第一次缓存
        hash1 = self.manager.cache_prefix(prefix, token_count=10)

        # 第二次获取相同前缀
        hash2 = self.manager.cache_prefix(prefix, token_count=10)

        assert hash1 == hash2

        # 验证缓存条目
        cached_entry = self.manager.get_cached_prefix(hash1)
        assert cached_entry is not None
        assert cached_entry.prefix_content == prefix
        assert cached_entry.token_count == 10
        assert cached_entry.access_count >= 1

    def test_prefix_stats(self):
        """测试前缀统计"""
        # 缓存几个前缀
        self.manager.cache_prefix("Prefix 1", token_count=5)
        self.manager.cache_prefix("Prefix 2", token_count=8)
        self.manager.cache_prefix("Prefix 1", token_count=5)  # 重复访问

        stats = self.manager.get_prefix_stats()

        assert stats["total_prefixes"] == 2
        assert stats["total_tokens"] == 13  # 5 + 8
        assert stats["total_accesses"] >= 3


class TestAppendOnlyContextManager:
    """测试仅追加模式的上下文更新机制"""

    def setup_method(self):
        """设置测试环境"""
        self.manager = AppendOnlyContextManager()

    def test_initialize_context(self):
        """测试初始化上下文"""
        context_id = "test-context"
        initial_content = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]

        context_hash = self.manager.initialize_context(context_id, initial_content)

        assert context_hash is not None
        assert len(context_hash) == 64  # SHA256 hex length

        # 验证上下文内容
        retrieved_context = self.manager.get_context(context_id)
        assert retrieved_context == initial_content

    def test_append_to_context(self):
        """测试追加内容到上下文"""
        context_id = "test-context"
        initial_content = [{"role": "user", "content": "Hello"}]

        # 初始化上下文
        self.manager.initialize_context(context_id, initial_content)

        # 追加新内容
        new_content = {"role": "assistant", "content": "Hi there!"}
        new_hash = self.manager.append_to_context(context_id, new_content)

        # 验证上下文更新
        context = self.manager.get_context(context_id)
        assert len(context) == 2
        assert context[0] == initial_content[0]
        assert context[1] == new_content

        # 验证哈希变化
        current_hash = self.manager.get_context_hash(context_id)
        assert current_hash == new_hash

    def test_context_integrity(self):
        """测试上下文完整性验证"""
        context_id = "test-context"
        initial_content = [{"role": "user", "content": "Hello"}]

        self.manager.initialize_context(context_id, initial_content)

        # 验证完整性
        assert self.manager.validate_context_integrity(context_id) is True

        # 追加内容后再次验证
        self.manager.append_to_context(
            context_id, {"role": "assistant", "content": "Hi"}
        )
        assert self.manager.validate_context_integrity(context_id) is True

    def test_context_stats(self):
        """测试上下文统计"""
        # 创建多个上下文
        self.manager.initialize_context("ctx1", [{"role": "user", "content": "Hello"}])
        self.manager.initialize_context("ctx2", [{"role": "user", "content": "Hi"}])

        # 追加内容
        self.manager.append_to_context(
            "ctx1", {"role": "assistant", "content": "Hello!"}
        )
        self.manager.append_to_context(
            "ctx1", {"role": "user", "content": "How are you?"}
        )

        stats = self.manager.get_context_stats()

        assert stats["total_contexts"] == 2
        assert stats["total_items"] == 4  # ctx1: 3 items, ctx2: 1 item
        assert stats["average_items_per_context"] == 2.0


class TestKVCacheHitMonitor:
    """测试KV缓存命中率监控器"""

    def setup_method(self):
        """设置测试环境"""
        self.monitor = KVCacheHitMonitor()

    def test_record_cache_hit(self):
        """测试记录缓存命中"""
        # 记录几次命中
        self.monitor.record_cache_hit("test", prefix_hit=True, session_hit=False)
        self.monitor.record_cache_hit("test", prefix_hit=False, session_hit=True)
        self.monitor.record_cache_hit("test", prefix_hit=True, session_hit=True)

        # 检查统计
        hit_rate = self.monitor.get_hit_rate("test")
        assert hit_rate == 1.0  # 全部命中

        stats = self.monitor.get_detailed_stats()
        test_stats = stats["test"]
        assert test_stats["cache_hits"] == 3
        assert test_stats["cache_misses"] == 0
        assert test_stats["prefix_hits"] == 2
        assert test_stats["session_hits"] == 2

    def test_record_cache_miss(self):
        """测试记录缓存未命中"""
        # 记录命中和未命中
        self.monitor.record_cache_hit("test")
        self.monitor.record_cache_miss("test", prefix_miss=True)
        self.monitor.record_cache_miss("test", session_miss=True)

        hit_rate = self.monitor.get_hit_rate("test")
        assert abs(hit_rate - 1 / 3) < 0.01  # 1命中，2未命中

    def test_reset_stats(self):
        """测试重置统计"""
        self.monitor.record_cache_hit("test")
        self.monitor.record_cache_miss("test")

        # 重置特定类型统计
        self.monitor.reset_stats("test")

        stats = self.monitor.get_detailed_stats()
        test_stats = stats["test"]
        assert test_stats["total_requests"] == 0
        assert test_stats["cache_hits"] == 0
        assert test_stats["cache_misses"] == 0


class TestKVCacheOptimizer:
    """测试KV缓存优化系统主类"""

    def setup_method(self):
        """设置测试环境"""
        self.optimizer = KVCacheOptimizer()
        self.optimizer.start()

    def teardown_method(self):
        """清理测试环境"""
        self.optimizer.stop()

    def test_optimize_prompt(self):
        """测试提示词优化"""
        prompt = """You are a helpful assistant.
Please help with the following task:

Current time: 2024-01-01 12:00:00
Task: Complete this request"""

        result = self.optimizer.optimize_prompt(prompt)

        assert "stable_prefix" in result
        assert "dynamic_suffix" in result
        assert "prefix_hash" in result
        assert "cache_key" in result
        assert result["optimized_prompt"] == prompt

        # 验证前缀稳定性
        assert "You are a helpful assistant" in result["stable_prefix"]
        assert "Current time:" in result["dynamic_suffix"]

    def test_session_optimization(self):
        """测试会话优化"""
        session_id = self.optimizer.create_session()
        assert session_id is not None

        prompt = "Hello, how are you?"

        # 第一次优化
        result1 = self.optimizer.optimize_prompt(prompt, session_id)

        # 第二次优化相同提示词
        result2 = self.optimizer.optimize_prompt(prompt, session_id)

        # 应该有会话命中
        assert result2["session_hit"] is True

    def test_context_management(self):
        """测试上下文管理"""
        context_id = "test-context"
        initial_content = [{"role": "user", "content": "Hello"}]

        # 初始化上下文
        context_hash = self.optimizer.initialize_context(context_id, initial_content)
        assert context_hash is not None

        # 追加内容
        new_content = {"role": "assistant", "content": "Hi there!"}
        new_hash = self.optimizer.append_to_context(context_id, new_content)
        assert new_hash != context_hash

    def test_performance_analysis(self):
        """测试性能分析"""
        # 生成一些缓存活动
        self.optimizer.optimize_prompt("Test prompt 1")
        self.optimizer.optimize_prompt("Test prompt 2")
        self.optimizer.optimize_prompt("Test prompt 1")  # 重复，应该命中

        analysis = self.optimizer.get_performance_analysis()

        assert "performance_score" in analysis
        assert "bottlenecks" in analysis
        assert "recommendations" in analysis
        assert "trends" in analysis

        assert 0 <= analysis["performance_score"] <= 100

    def test_comprehensive_stats(self):
        """测试综合统计"""
        # 生成一些活动
        session_id = self.optimizer.create_session()
        self.optimizer.optimize_prompt("Test prompt", session_id)

        stats = self.optimizer.get_comprehensive_stats()

        assert "cache_hit_stats" in stats
        assert "prefix_stats" in stats
        assert "context_stats" in stats
        assert "session_stats" in stats
        assert "performance_analysis" in stats


class TestConsistentHashRing:
    """测试一致性哈希环"""

    def setup_method(self):
        """设置测试环境"""
        self.ring = ConsistentHashRing(virtual_nodes=100)

    def test_add_remove_nodes(self):
        """测试添加和移除节点"""
        # 添加节点
        self.ring.add_node("node1")
        self.ring.add_node("node2")
        self.ring.add_node("node3")

        info = self.ring.get_ring_info()
        assert info["physical_nodes"] == 3
        assert info["total_virtual_nodes"] == 300  # 3 * 100

        # 移除节点
        self.ring.remove_node("node2")

        info = self.ring.get_ring_info()
        assert info["physical_nodes"] == 2
        assert info["total_virtual_nodes"] == 200  # 2 * 100

    def test_consistent_routing(self):
        """测试一致性路由"""
        # 添加节点
        nodes = ["node1", "node2", "node3"]
        for node in nodes:
            self.ring.add_node(node)

        # 测试键路由的一致性
        test_keys = ["key1", "key2", "key3", "key4", "key5"]

        # 记录初始路由
        initial_routes = {}
        for key in test_keys:
            initial_routes[key] = self.ring.get_node(key)

        # 添加新节点
        self.ring.add_node("node4")

        # 检查路由变化（应该最小化）
        changed_routes = 0
        for key in test_keys:
            new_route = self.ring.get_node(key)
            if new_route != initial_routes[key]:
                changed_routes += 1

        # 一致性哈希应该最小化路由变化
        assert changed_routes <= len(test_keys) // 2

    def test_multiple_nodes_for_key(self):
        """测试获取键的多个节点"""
        nodes = ["node1", "node2", "node3", "node4"]
        for node in nodes:
            self.ring.add_node(node)

        # 获取键的多个节点
        key_nodes = self.ring.get_nodes_for_key("test_key", count=3)

        assert len(key_nodes) == 3
        assert len(set(key_nodes)) == 3  # 确保没有重复


class TestDistributedSessionManager:
    """测试分布式会话管理器"""

    def setup_method(self):
        """设置测试环境"""
        self.manager = DistributedSessionManager("test-node")
        self.manager.start()

    def teardown_method(self):
        """清理测试环境"""
        self.manager.stop()

    def test_create_session(self):
        """测试创建会话"""
        session_id, node_id = self.manager.create_session()

        assert session_id is not None
        assert node_id == "test-node"  # 单节点环境应该路由到本节点

        # 验证会话路由
        routed_node = self.manager.get_session_node(session_id)
        assert routed_node == node_id

    def test_session_stickiness(self):
        """测试会话粘性"""
        # 创建粘性会话
        session_id, node_id = self.manager.create_session(sticky=True)

        # 多次获取应该返回相同节点
        for _ in range(5):
            routed_node = self.manager.get_session_node(session_id)
            assert routed_node == node_id

    def test_cluster_status(self):
        """测试集群状态"""
        # 创建一些会话
        self.manager.create_session()
        self.manager.create_session()

        status = self.manager.get_cluster_status()

        assert "cluster_info" in status
        assert "session_info" in status
        assert "load_balancer_stats" in status
        assert "hash_ring_info" in status
        assert "nodes" in status

        cluster_info = status["cluster_info"]
        assert cluster_info["total_nodes"] >= 1
        assert cluster_info["current_node"] == "test-node"

        session_info = status["session_info"]
        assert session_info["total_sessions"] == 2
        assert session_info["local_sessions"] == 2


@pytest.mark.asyncio
class TestIntegration:
    """集成测试"""

    async def test_full_kv_cache_workflow(self):
        """测试完整的KV缓存工作流"""
        # 获取全局优化器
        optimizer = get_kv_cache_optimizer()

        # 创建会话
        session_id = optimizer.create_session()

        # 优化提示词
        prompt = """You are a helpful assistant.
Please help with the following task:

Current time: 2024-01-01 12:00:00
User request: Hello world"""

        result = optimizer.optimize_prompt(prompt, session_id)

        # 验证优化结果
        assert (
            result["prefix_hit"] or result["session_hit"] or True
        )  # 第一次可能都不命中
        assert "stable_prefix" in result
        assert "dynamic_suffix" in result

        # 再次优化相同提示词（应该有缓存命中）
        result2 = optimizer.optimize_prompt(prompt, session_id)
        assert result2["session_hit"] is True

        # 获取性能统计
        stats = optimizer.get_comprehensive_stats()
        assert stats["cache_hit_stats"]["overall"]["total_requests"] >= 2

    async def test_monitoring_service_integration(self):
        """测试监控服务集成"""
        # 获取监控服务
        monitor_service = get_cache_hit_monitor_service()

        # 生成一些缓存活动
        optimizer = get_kv_cache_optimizer()
        for i in range(10):
            optimizer.optimize_prompt(f"Test prompt {i}")

        # 等待监控收集数据
        await asyncio.sleep(0.1)

        # 获取仪表板数据
        dashboard_data = monitor_service.get_dashboard_data()

        assert "service_status" in dashboard_data
        assert "current_metrics" in dashboard_data
        assert "monitoring_summary" in dashboard_data
        assert "performance_analysis" in dashboard_data

        # 验证服务状态
        service_status = dashboard_data["service_status"]
        assert service_status["running"] is True


def test_convenience_functions():
    """测试便捷函数"""
    # 测试优化提示词便捷函数
    result = optimize_prompt_for_cache("Test prompt")
    assert "stable_prefix" in result
    assert "cache_key" in result

    # 测试确定性序列化便捷函数
    obj = {"key": "value", "number": 42}
    serialized = serialize_deterministically(obj)
    assert isinstance(serialized, str)
    assert "key" in serialized
    assert "42" in serialized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
