#!/usr/bin/env python3
"""
RAG知识库接入中间层使用示例

演示如何使用统一的RAG服务接口和管理器
"""

import asyncio
import os
from pathlib import Path

# 添加项目根目录到Python路径
import sys

sys.path.append(str(Path(__file__).parent.parent))

from src.rag.config_manager import RAGConfigManager
from src.rag.service_manager import RAGServiceManager
from src.rag.interfaces import Document


async def basic_usage_example():
    """基本使用示例"""
    print("=== RAG知识库接入中间层基本使用示例 ===\n")

    # 1. 创建配置管理器
    config_manager = RAGConfigManager("config/rag_services.yaml")

    try:
        # 2. 加载配置
        print("1. 加载配置...")
        config = config_manager.load_config()
        print(f"   加载了 {len(config.services)} 个服务配置")

        # 3. 创建服务管理器
        print("\n2. 创建服务管理器...")
        service_manager = await config_manager.create_service_manager()

        # 4. 查看服务状态
        print("\n3. 服务状态:")
        stats = service_manager.get_manager_stats()
        print(f"   总服务数: {stats['total_services']}")
        print(f"   可用服务数: {stats['available_services']}")
        print(f"   健康服务数: {stats['healthy_services']}")

        # 5. 添加测试文档
        print("\n4. 添加测试文档...")
        test_document = Document(
            id="test_doc_001",
            content="这是一个测试文档，用于演示RAG知识库接入中间层的功能。",
            metadata={
                "title": "测试文档",
                "author": "TestAgent",
                "category": "示例",
                "created_at": "2024-01-01",
            },
        )

        try:
            doc_id = await service_manager.add_document(test_document)
            print(f"   文档添加成功，ID: {doc_id}")
        except Exception as e:
            print(f"   文档添加失败: {e}")

        # 6. 检索文档
        print("\n5. 检索文档...")
        try:
            results = await service_manager.retrieve("测试文档", top_k=3)
            print(f"   检索到 {len(results)} 个结果:")

            for i, result in enumerate(results, 1):
                print(f"   结果 {i}:")
                print(f"     相似度: {result.similarity_score:.3f}")
                print(f"     内容: {result.document.content[:50]}...")
                print(
                    f"     服务: {result.document.metadata.get('rag_service', 'unknown')}"
                )
        except Exception as e:
            print(f"   检索失败: {e}")

        # 7. 显示统计信息
        print("\n6. 最终统计信息:")
        final_stats = service_manager.get_manager_stats()
        print(f"   总请求数: {final_stats['total_requests']}")
        print(f"   成功请求数: {final_stats['successful_requests']}")
        print(f"   失败请求数: {final_stats['failed_requests']}")
        print(f"   成功率: {final_stats['success_rate']:.1f}%")

    except Exception as e:
        print(f"示例执行失败: {e}")

    finally:
        # 清理资源
        if "service_manager" in locals():
            await service_manager.stop_health_checks()


async def failover_example():
    """故障转移示例"""
    print("\n=== 故障转移示例 ===\n")

    # 创建一个包含多个服务的配置
    config_data = {
        "services": {
            "primary_service": {
                "name": "primary_service",
                "service_type": "chromadb",
                "priority": "primary",
                "enabled": True,
                "config": {
                    "persist_directory": "./data/vectordb_primary",
                    "collection_name": "test_primary",
                },
            },
            "fallback_service": {
                "name": "fallback_service",
                "service_type": "chromadb",
                "priority": "fallback",
                "enabled": True,
                "config": {
                    "persist_directory": "./data/vectordb_fallback",
                    "collection_name": "test_fallback",
                },
            },
        },
        "global_settings": {"enable_auto_failover": True},
    }

    # 创建临时配置文件
    import tempfile
    import yaml

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        temp_config_path = f.name

    try:
        config_manager = RAGConfigManager(temp_config_path)
        config = config_manager.load_config()
        service_manager = await config_manager.create_service_manager()

        print("1. 服务状态:")
        for service_name in service_manager.services.keys():
            status = service_manager.get_service_status(service_name)
            print(f"   {service_name}: {'可用' if status['available'] else '不可用'}")

        # 添加文档到主服务
        print("\n2. 添加文档...")
        test_doc = Document(
            id="failover_test",
            content="故障转移测试文档",
            metadata={"test": "failover"},
        )

        doc_id = await service_manager.add_document(test_doc)
        print(f"   文档添加成功: {doc_id}")

        # 检索文档
        print("\n3. 检索文档...")
        results = await service_manager.retrieve("故障转移", top_k=1)
        if results:
            service_used = results[0].document.metadata.get("rag_service", "unknown")
            print(f"   使用的服务: {service_used}")

    except Exception as e:
        print(f"故障转移示例失败: {e}")

    finally:
        # 清理
        os.unlink(temp_config_path)
        if "service_manager" in locals():
            await service_manager.stop_health_checks()


async def config_management_example():
    """配置管理示例"""
    print("\n=== 配置管理示例 ===\n")

    config_manager = RAGConfigManager()

    # 1. 创建默认配置
    print("1. 创建默认配置...")
    try:
        config = config_manager.load_config()
        print("   默认配置加载成功")
    except Exception as e:
        print(f"   配置加载失败: {e}")
        return

    # 2. 显示配置信息
    print("\n2. 配置信息:")
    config_info = config_manager.get_config_info()
    print(f"   配置文件: {config_info['config_path']}")
    print(f"   服务总数: {config_info['services_count']}")
    print(f"   启用服务数: {config_info['enabled_services']}")

    # 3. 验证配置
    print("\n3. 配置验证:")
    validation_result = config_manager.validate_config(
        {
            "services": {
                "test_service": {
                    "name": "test_service",
                    "service_type": "chromadb",
                    "priority": "primary",
                    "enabled": True,
                    "config": {},
                }
            }
        }
    )

    print(f"   验证结果: {'通过' if validation_result.is_valid else '失败'}")
    if validation_result.errors:
        print(f"   错误: {validation_result.errors}")
    if validation_result.warnings:
        print(f"   警告: {validation_result.warnings}")


async def adapter_direct_usage_example():
    """适配器直接使用示例"""
    print("\n=== 适配器直接使用示例 ===\n")

    from src.rag.adapters import ChromaDBAdapter

    # 1. 创建ChromaDB适配器
    print("1. 创建ChromaDB适配器...")
    adapter = ChromaDBAdapter(
        service_name="direct_chromadb",
        config={
            "persist_directory": "./data/vectordb_direct",
            "collection_name": "direct_test",
            "embedding_model": "text-embedding-ada-002",
            "embedding_provider": "openai",
        },
    )

    try:
        # 2. 初始化适配器
        print("2. 初始化适配器...")
        success = await adapter.initialize()
        if not success:
            print("   适配器初始化失败")
            return
        print("   适配器初始化成功")

        # 3. 健康检查
        print("\n3. 健康检查...")
        health_info = await adapter.health_check()
        print(f"   状态: {health_info.status.value}")
        print(f"   响应时间: {health_info.response_time_ms:.2f}ms")

        # 4. 获取服务信息
        print("\n4. 服务信息:")
        service_info = await adapter.get_service_info()
        print(f"   服务类型: {service_info['service_type']}")
        print(f"   默认集合: {service_info['default_collection']}")
        print(f"   嵌入模型: {service_info['embedding_model']}")

        # 5. 添加文档
        print("\n5. 添加文档...")
        test_doc = Document(
            id="direct_test_001",
            content="这是直接使用适配器的测试文档。",
            metadata={"source": "direct_usage", "type": "test"},
        )

        doc_id = await adapter.add_document(test_doc)
        print(f"   文档添加成功: {doc_id}")

        # 6. 检索文档
        print("\n6. 检索文档...")
        results = await adapter.retrieve("直接使用", top_k=1)
        if results:
            print(f"   检索到 {len(results)} 个结果")
            print(f"   相似度: {results[0].similarity_score:.3f}")
        else:
            print("   未检索到结果")

    except Exception as e:
        print(f"适配器使用失败: {e}")


async def main():
    """主函数"""
    print("RAG知识库接入中间层使用示例\n")

    # 设置环境变量（如果需要）
    os.environ.setdefault("OPENAI_API_KEY", "your-openai-api-key")

    try:
        # 运行各种示例
        await basic_usage_example()
        await failover_example()
        await config_management_example()
        await adapter_direct_usage_example()

    except KeyboardInterrupt:
        print("\n示例被用户中断")
    except Exception as e:
        print(f"\n示例执行异常: {e}")

    print("\n示例执行完成")


if __name__ == "__main__":
    asyncio.run(main())
