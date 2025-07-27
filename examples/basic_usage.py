#!/usr/bin/env python3
"""
TestAgent基本使用示例
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.client.testagent_client import TestAgentClient, TestAgentSyncClient


async def async_example():
    """异步客户端示例"""
    print("🚀 异步客户端示例")

    async with TestAgentClient(base_url="http://localhost:8000") as client:
        # 1. 健康检查
        print("\n1. 检查系统健康状态...")
        try:
            health = await client.health_check()
            print(f"✅ 系统状态: {health['status']}")
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
            return

        # 2. 创建测试用例生成任务
        print("\n2. 创建测试用例生成任务...")
        try:
            task_id = await client.create_task(
                task_type="test_case_generation",
                task_topic="用户登录功能测试",
                context="需要测试用户登录功能，包括正常登录、错误密码、账号锁定等场景",
                code_snippets=[
                    """
def login(username, password):
    if not username or not password:
        return False, "用户名和密码不能为空"
    
    if username == "admin" and password == "password123":
        return True, "登录成功"
    else:
        return False, "用户名或密码错误"
"""
                ],
                locale="zh-CN",
            )
            print(f"✅ 任务已创建: {task_id}")
        except Exception as e:
            print(f"❌ 创建任务失败: {e}")
            return

        # 3. 等待任务完成（带进度回调）
        print("\n3. 等待任务完成...")

        def progress_callback(status):
            progress = status.get("progress", 0)
            current_step = status.get("current_step", "未知")
            print(f"📊 进度: {progress:.1f}% - {current_step}")

        try:
            result = await client.wait_for_completion(
                task_id=task_id, timeout=300, progress_callback=progress_callback
            )

            if result.status == "completed":
                print(f"✅ 任务完成! 执行时间: {result.execution_time:.2f}秒")

                # 获取详细结果
                detailed_result = await client.get_task_result(task_id)
                report = detailed_result.get("result", {}).get("report", {})
                print(f"📄 报告内容预览: {report.get('content', '无内容')[:200]}...")

            else:
                print(f"❌ 任务失败: {result.error}")

        except Exception as e:
            print(f"❌ 等待任务完成失败: {e}")

        # 4. 列出所有任务
        print("\n4. 列出最近的任务...")
        try:
            tasks = await client.list_tasks(page=1, page_size=5)
            print(f"📋 共有 {tasks['total']} 个任务:")

            for task in tasks["tasks"]:
                print(
                    f"  - {task['task_id']}: {task['status']} ({task.get('execution_time', 0):.1f}s)"
                )

        except Exception as e:
            print(f"❌ 列出任务失败: {e}")

        # 5. 系统状态
        print("\n5. 获取系统状态...")
        try:
            system_status = await client.get_system_status()
            print(f"🖥️  系统状态: {system_status['system']['status']}")
            print(f"💾 内存使用: {system_status['resources']['memory_usage']:.1f}%")
            print(
                f"🔧 活跃组件: {sum(1 for c in system_status['components'] if c['healthy'])}/{len(system_status['components'])}"
            )

        except Exception as e:
            print(f"❌ 获取系统状态失败: {e}")


def sync_example():
    """同步客户端示例"""
    print("\n🔄 同步客户端示例")

    with TestAgentSyncClient(base_url="http://localhost:8000") as client:
        # 1. 健康检查
        print("\n1. 检查系统健康状态...")
        try:
            health = client.health_check()
            print(f"✅ 系统状态: {health['status']}")
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
            return

        # 2. 执行简单任务
        print("\n2. 执行测试分析任务...")
        try:
            result = client.execute_task(
                task_type="test_analysis",
                task_topic="代码质量分析",
                context="分析给定代码的质量和潜在问题",
                code_snippets=[
                    """
def calculate_average(numbers):
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)
"""
                ],
            )

            if result.status == "completed":
                print(f"✅ 分析完成! 执行时间: {result.execution_time:.2f}秒")
            else:
                print(f"❌ 分析失败: {result.error}")

        except Exception as e:
            print(f"❌ 执行任务失败: {e}")


async def document_example():
    """文档管理示例"""
    print("\n📄 文档管理示例")

    async with TestAgentClient(base_url="http://localhost:8000") as client:
        # 1. 创建示例文档
        example_doc_path = "example_document.txt"
        with open(example_doc_path, "w", encoding="utf-8") as f:
            f.write(
                """
# 用户登录功能需求文档

## 功能描述
用户登录功能允许用户通过用户名和密码访问系统。

## 需求列表
1. 用户必须提供有效的用户名和密码
2. 系统应验证用户凭据
3. 登录失败时应显示错误消息
4. 连续失败3次后应锁定账户
5. 成功登录后应重定向到主页

## 测试场景
- 正常登录流程
- 错误密码处理
- 空字段验证
- 账户锁定机制
"""
            )

        try:
            # 2. 上传文档
            print("📤 上传文档...")
            document_id = await client.upload_document(
                file_path=example_doc_path,
                description="用户登录功能需求文档",
                tags=["需求", "登录", "测试"],
            )
            print(f"✅ 文档已上传: {document_id}")

            # 3. 搜索文档
            print("\n🔍 搜索文档...")
            search_results = await client.search_documents(
                query="登录失败处理", top_k=3
            )

            print(f"📋 找到 {len(search_results['results'])} 个相关结果:")
            for result in search_results["results"]:
                print(f"  - {result['filename']}: {result['score']:.3f}")
                print(f"    内容: {result['content'][:100]}...")

            # 4. 列出文档
            print("\n📚 列出所有文档...")
            documents = await client.list_documents()
            print(f"📋 共有 {documents['total']} 个文档")

        except Exception as e:
            print(f"❌ 文档操作失败: {e}")

        finally:
            # 清理示例文档
            import os

            if os.path.exists(example_doc_path):
                os.remove(example_doc_path)


async def websocket_example():
    """WebSocket示例"""
    print("\n🔌 WebSocket示例")

    try:
        from src.client.testagent_client import TestAgentWebSocketClient

        # 创建WebSocket客户端
        ws_client = TestAgentWebSocketClient(base_url="ws://localhost:8000")

        # 定义消息处理器
        @ws_client.on_message("task_update")
        async def handle_task_update(data):
            task_id = data.get("task_id")
            status = data.get("data", {}).get("status")
            print(f"📡 任务更新: {task_id} -> {status}")

        @ws_client.on_message("pong")
        async def handle_pong(data):
            print("💓 心跳响应")

        # 连接并监听
        await ws_client.connect()
        print("🔌 WebSocket已连接")

        # 发送心跳
        await ws_client.ping()

        # 订阅任务更新（如果有活跃任务）
        # await ws_client.subscribe_task("some_task_id")

        # 监听消息（这里只监听几秒钟作为示例）
        print("👂 监听消息中...")
        try:
            await asyncio.wait_for(ws_client.listen(), timeout=5.0)
        except asyncio.TimeoutError:
            print("⏰ 监听超时，断开连接")

        await ws_client.disconnect()
        print("🔌 WebSocket已断开")

    except Exception as e:
        print(f"❌ WebSocket示例失败: {e}")


def main():
    """主函数"""
    print("🎯 TestAgent客户端使用示例")
    print("=" * 50)

    # 检查服务器是否运行
    print("🔍 检查服务器连接...")
    try:
        import requests

        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ 服务器连接正常")
        else:
            print("❌ 服务器响应异常")
            return
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        print("💡 请确保API服务器正在运行: python run_api_server.py")
        return

    # 运行示例
    try:
        # 异步示例
        asyncio.run(async_example())

        # 同步示例
        sync_example()

        # 文档管理示例
        asyncio.run(document_example())

        # WebSocket示例
        asyncio.run(websocket_example())

    except KeyboardInterrupt:
        print("\n👋 示例已中断")
    except Exception as e:
        print(f"\n❌ 示例执行失败: {e}")

    print("\n🎉 示例执行完成!")


if __name__ == "__main__":
    main()
