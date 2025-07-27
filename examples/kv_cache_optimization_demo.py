#!/usr/bin/env python3
"""
KV缓存优化系统演示

展示KV缓存优化系统的核心功能，包括：
1. 提示词前缀稳定性管理
2. 仅追加模式的上下文更新
3. 确定性序列化
4. 缓存命中率监控
5. 分布式会话管理
"""

import asyncio
import time
from datetime import datetime

from src.cache.kv_cache_optimizer import (
    get_kv_cache_optimizer,
    optimize_prompt_for_cache,
    serialize_deterministically,
)

from src.cache.cache_hit_monitor import (
    get_cache_hit_monitor_service,
    get_cache_dashboard_data,
)

from src.cache.session_manager import (
    get_distributed_session_manager,
    create_distributed_session,
)


def demo_deterministic_serialization():
    """演示确定性序列化"""
    print("=== 确定性序列化演示 ===")

    # 测试不同顺序的字典
    dict1 = {
        "temperature": 0.7,
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    dict2 = {
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "model": "gpt-4",
    }
    dict3 = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
    }

    # 序列化结果应该相同
    result1 = serialize_deterministically(dict1)
    result2 = serialize_deterministically(dict2)
    result3 = serialize_deterministically(dict3)

    print(f"字典1序列化: {result1}")
    print(f"字典2序列化: {result2}")
    print(f"字典3序列化: {result3}")
    print(f"序列化结果一致: {result1 == result2 == result3}")
    print()


def demo_prefix_stability():
    """演示提示词前缀稳定性"""
    print("=== 提示词前缀稳定性演示 ===")

    # 包含动态内容的提示词
    prompt_template = """You are a helpful AI assistant.
Please help the user with their request.

System Information:
- Current time: {current_time}
- Session ID: {session_id}
- Request ID: {request_id}

User Request: {user_request}"""

    # 生成不同时间的提示词
    prompts = []
    for i in range(3):
        prompt = prompt_template.format(
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session_id=f"session-{i}",
            request_id=f"req-{i}",
            user_request="Hello, how are you?",
        )
        prompts.append(prompt)
        time.sleep(0.1)  # 确保时间不同

    # 优化每个提示词
    for i, prompt in enumerate(prompts):
        result = optimize_prompt_for_cache(prompt)
        print(f"提示词 {i+1}:")
        print(f"  稳定前缀长度: {len(result['stable_prefix'])} 字符")
        print(f"  动态后缀长度: {len(result['dynamic_suffix'])} 字符")
        print(f"  前缀哈希: {result['prefix_hash'][:16]}...")
        print(f"  缓存键: {result['cache_key'][:16]}...")
        print()


def demo_context_management():
    """演示上下文管理"""
    print("=== 仅追加模式上下文管理演示 ===")

    optimizer = get_kv_cache_optimizer()

    # 初始化上下文
    context_id = "demo-context"
    initial_content = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]

    initial_hash = optimizer.initialize_context(context_id, initial_content)
    print(f"初始上下文哈希: {initial_hash[:16]}...")

    # 追加多个消息
    messages = [
        {"role": "assistant", "content": "Hello! How can I help you today?"},
        {"role": "user", "content": "What's the weather like?"},
        {
            "role": "assistant",
            "content": "I don't have access to current weather data.",
        },
        {"role": "user", "content": "That's okay, thanks!"},
    ]

    for i, message in enumerate(messages):
        new_hash = optimizer.append_to_context(context_id, message)
        print(f"追加消息 {i+1} 后的哈希: {new_hash[:16]}...")

    # 获取完整上下文
    full_context = optimizer.context_manager.get_context(context_id)
    print(f"最终上下文长度: {len(full_context)} 条消息")

    # 验证上下文完整性
    integrity_ok = optimizer.context_manager.validate_context_integrity(context_id)
    print(f"上下文完整性验证: {'通过' if integrity_ok else '失败'}")
    print()


def demo_session_management():
    """演示会话管理"""
    print("=== 分布式会话管理演示 ===")

    # 创建多个会话
    sessions = []
    for i in range(5):
        session_id, node_id = create_distributed_session(sticky=True)
        sessions.append((session_id, node_id))
        print(f"会话 {i+1}: {session_id[:16]}... -> 节点 {node_id}")

    # 获取集群状态
    cluster_status = get_distributed_session_manager().get_cluster_status()
    print(f"\n集群状态:")
    print(f"  总节点数: {cluster_status['cluster_info']['total_nodes']}")
    print(f"  健康节点数: {cluster_status['cluster_info']['healthy_nodes']}")
    print(f"  总会话数: {cluster_status['session_info']['total_sessions']}")
    print(f"  本地会话数: {cluster_status['session_info']['local_sessions']}")
    print()


def demo_cache_hit_monitoring():
    """演示缓存命中率监控"""
    print("=== 缓存命中率监控演示 ===")

    optimizer = get_kv_cache_optimizer()

    # 生成一些缓存活动
    test_prompts = [
        "Hello, how are you?",
        "What's the weather like today?",
        "Hello, how are you?",  # 重复，应该命中
        "Can you help me with coding?",
        "What's the weather like today?",  # 重复，应该命中
        "Hello, how are you?",  # 再次重复，应该命中
    ]

    print("生成缓存活动...")
    for i, prompt in enumerate(test_prompts):
        result = optimizer.optimize_prompt(prompt)
        hit_status = (
            "命中" if (result["prefix_hit"] or result["session_hit"]) else "未命中"
        )
        print(f"  提示词 {i+1}: {hit_status}")

    # 获取性能分析
    analysis = optimizer.get_performance_analysis()
    print(f"\n性能分析:")
    print(f"  性能评分: {analysis['performance_score']:.1f}/100")
    print(f"  瓶颈数量: {len(analysis['bottlenecks'])}")
    print(f"  建议数量: {len(analysis['recommendations'])}")

    # 获取详细统计
    stats = optimizer.get_comprehensive_stats()
    hit_stats = stats["cache_hit_stats"]["overall"]
    print(f"\n缓存统计:")
    print(f"  总请求数: {hit_stats['total_requests']}")
    print(f"  缓存命中数: {hit_stats['cache_hits']}")
    print(f"  缓存未命中数: {hit_stats['cache_misses']}")
    print(f"  总体命中率: {hit_stats['hit_rate']:.1%}")
    print(f"  前缀命中率: {hit_stats['prefix_hit_rate']:.1%}")
    print()


async def demo_monitoring_service():
    """演示监控服务"""
    print("=== 监控服务演示 ===")

    # 获取仪表板数据
    dashboard_data = get_cache_dashboard_data()

    print("服务状态:")
    service_status = dashboard_data["service_status"]
    print(f"  运行状态: {'运行中' if service_status['running'] else '已停止'}")
    print(
        f"  监控启用: {'是' if service_status.get('monitoring_enabled', False) else '否'}"
    )

    print("\n监控摘要:")
    monitoring_summary = dashboard_data["monitoring_summary"]
    print(f"  监控状态: {monitoring_summary['monitoring_status']}")
    print(f"  活跃告警数: {monitoring_summary['active_alerts_count']}")

    recent_perf = monitoring_summary.get("recent_performance", {})
    if recent_perf:
        print(f"  最近平均命中率: {recent_perf.get('avg_hit_rate', 0):.1%}")
        print(f"  最近平均前缀命中率: {recent_perf.get('avg_prefix_hit_rate', 0):.1%}")

    print("\n性能分析:")
    perf_analysis = dashboard_data["performance_analysis"]
    print(f"  性能评分: {perf_analysis['performance_score']:.1f}/100")

    if perf_analysis["recommendations"]:
        print("  优化建议:")
        for rec in perf_analysis["recommendations"][:3]:  # 显示前3个建议
            print(f"    - {rec['title']}: {rec['description']}")

    print()


def demo_integration_workflow():
    """演示完整的集成工作流"""
    print("=== 完整集成工作流演示 ===")

    # 1. 创建会话
    session_id, node_id = create_distributed_session(sticky=True)
    print(f"1. 创建会话: {session_id[:16]}... -> {node_id}")

    # 2. 初始化上下文
    optimizer = get_kv_cache_optimizer()
    context_id = f"workflow-{session_id[:8]}"
    initial_context = [
        {"role": "system", "content": "You are a helpful coding assistant."}
    ]
    optimizer.initialize_context(context_id, initial_context)
    print(f"2. 初始化上下文: {context_id}")

    # 3. 模拟对话流程
    conversation = [
        {"role": "user", "content": "Hello, I need help with Python."},
        {
            "role": "assistant",
            "content": "I'd be happy to help you with Python! What specific topic or problem are you working on?",
        },
        {"role": "user", "content": "How do I create a class?"},
        {
            "role": "assistant",
            "content": "Here's how to create a basic class in Python:\n\nclass MyClass:\n    def __init__(self):\n        pass",
        },
        {"role": "user", "content": "Thanks! Can you show me inheritance?"},
    ]

    print("3. 模拟对话流程:")
    for i, message in enumerate(conversation):
        # 追加到上下文
        optimizer.append_to_context(context_id, message)

        # 如果是用户消息，优化提示词
        if message["role"] == "user":
            prompt = f"Context: {context_id}\nUser: {message['content']}"
            result = optimizer.optimize_prompt(prompt, session_id)
            hit_status = (
                "命中" if (result["prefix_hit"] or result["session_hit"]) else "未命中"
            )
            print(f"   消息 {i+1}: {message['role']} - 缓存{hit_status}")

    # 4. 获取最终统计
    stats = optimizer.get_comprehensive_stats()
    print(f"\n4. 最终统计:")
    print(f"   会话数: {stats['session_stats']['total_sessions']}")
    print(f"   上下文数: {stats['context_stats']['total_contexts']}")
    print(f"   总请求数: {stats['cache_hit_stats']['overall']['total_requests']}")
    print(f"   命中率: {stats['cache_hit_stats']['overall']['hit_rate']:.1%}")

    print()


async def main():
    """主演示函数"""
    print("KV缓存优化系统演示")
    print("=" * 50)

    # 1. 确定性序列化演示
    demo_deterministic_serialization()

    # 2. 前缀稳定性演示
    demo_prefix_stability()

    # 3. 上下文管理演示
    demo_context_management()

    # 4. 会话管理演示
    demo_session_management()

    # 5. 缓存命中率监控演示
    demo_cache_hit_monitoring()

    # 6. 监控服务演示
    await demo_monitoring_service()

    # 7. 完整集成工作流演示
    demo_integration_workflow()

    print("演示完成！")
    print("\n关键特性总结:")
    print("✓ 提示词前缀稳定性管理 - 避免动态内容破坏缓存")
    print("✓ 仅追加模式上下文更新 - 保持上下文完整性")
    print("✓ 确定性序列化系统 - 确保JSON对象键顺序固定")
    print("✓ KV缓存命中率监控 - 实时性能分析和优化建议")
    print("✓ 分布式会话管理 - 支持一致性路由和负载均衡")


if __name__ == "__main__":
    asyncio.run(main())
