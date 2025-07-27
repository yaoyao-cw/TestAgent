#!/usr/bin/env python3
"""
TestAgent Python客户端SDK
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx
import websockets
from pydantic import BaseModel


class TaskSubmissionRequest(BaseModel):
    """任务提交请求"""

    task_type: str
    task_topic: str
    context: Optional[str] = None
    code_snippets: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    locale: str = "zh-CN"
    timeout: Optional[int] = 300
    config: Optional[Dict[str, Any]] = None


class TaskResult(BaseModel):
    """任务结果"""

    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    created_at: str
    completed_at: Optional[str] = None


class TestAgentClient:
    """TestAgent客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # 创建HTTP客户端
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        self.client = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=timeout
        )

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        response = await self.client.get("/health")
        response.raise_for_status()
        return response.json()

    async def submit_task(self, request: TaskSubmissionRequest) -> str:
        """提交任务"""
        response = await self.client.post("/api/v1/tasks/submit", json=request.dict())
        response.raise_for_status()
        result = response.json()
        return result["task_id"]

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        response = await self.client.get(f"/api/v1/tasks/{task_id}/status")
        response.raise_for_status()
        return response.json()

    async def get_task_result(self, task_id: str, format: str = "json") -> Any:
        """获取任务结果"""
        response = await self.client.get(
            f"/api/v1/tasks/{task_id}/result", params={"format": format}
        )
        response.raise_for_status()

        if format == "json":
            return response.json()
        else:
            return response.text

    async def list_tasks(
        self, status: Optional[str] = None, page: int = 1, page_size: int = 10
    ) -> Dict[str, Any]:
        """列出任务"""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status

        response = await self.client.get("/api/v1/tasks/", params=params)
        response.raise_for_status()
        return response.json()

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """取消任务"""
        response = await self.client.delete(f"/api/v1/tasks/{task_id}")
        response.raise_for_status()
        return response.json()

    async def retry_task(self, task_id: str) -> str:
        """重试任务"""
        response = await self.client.post(f"/api/v1/tasks/{task_id}/retry")
        response.raise_for_status()
        result = response.json()
        return result["task_id"]

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: Optional[int] = None,
        poll_interval: int = 2,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> TaskResult:
        """等待任务完成"""
        start_time = time.time()
        timeout = timeout or self.timeout

        while True:
            # 检查超时
            if time.time() - start_time > timeout:
                raise TimeoutError(f"任务 {task_id} 执行超时")

            # 获取任务状态
            status = await self.get_task_status(task_id)

            # 调用进度回调
            if progress_callback:
                progress_callback(status)

            # 检查任务状态
            if status["status"] == "completed":
                return TaskResult(
                    task_id=task_id,
                    status="completed",
                    result=status.get("result"),
                    execution_time=status.get("execution_time"),
                    created_at=status["created_at"],
                    completed_at=status["updated_at"],
                )
            elif status["status"] == "failed":
                return TaskResult(
                    task_id=task_id,
                    status="failed",
                    error=status.get("error"),
                    execution_time=status.get("execution_time"),
                    created_at=status["created_at"],
                    completed_at=status["updated_at"],
                )
            elif status["status"] == "cancelled":
                return TaskResult(
                    task_id=task_id,
                    status="cancelled",
                    created_at=status["created_at"],
                    completed_at=status["updated_at"],
                )

            # 等待下次检查
            await asyncio.sleep(poll_interval)

    async def create_task(
        self,
        task_type: str,
        task_topic: str,
        context: Optional[str] = None,
        code_snippets: Optional[List[str]] = None,
        requirements: Optional[List[str]] = None,
        locale: str = "zh-CN",
        timeout: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建任务（便捷方法）"""
        request = TaskSubmissionRequest(
            task_type=task_type,
            task_topic=task_topic,
            context=context,
            code_snippets=code_snippets,
            requirements=requirements,
            locale=locale,
            timeout=timeout,
            config=config,
        )

        return await self.submit_task(request)

    async def execute_task(
        self,
        task_type: str,
        task_topic: str,
        context: Optional[str] = None,
        code_snippets: Optional[List[str]] = None,
        requirements: Optional[List[str]] = None,
        locale: str = "zh-CN",
        timeout: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> TaskResult:
        """执行任务并等待完成（便捷方法）"""
        # 创建任务
        task_id = await self.create_task(
            task_type=task_type,
            task_topic=task_topic,
            context=context,
            code_snippets=code_snippets,
            requirements=requirements,
            locale=locale,
            timeout=timeout,
            config=config,
        )

        # 等待完成
        return await self.wait_for_completion(
            task_id=task_id, timeout=timeout, progress_callback=progress_callback
        )

    # 文档管理方法
    async def upload_document(
        self,
        file_path: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """上传文档"""
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {}
            if description:
                data["description"] = description
            if tags:
                data["tags"] = ",".join(tags)

            response = await self.client.post(
                "/api/v1/documents/upload", files=files, data=data
            )
            response.raise_for_status()
            result = response.json()
            return result["document_id"]

    async def list_documents(
        self, page: int = 1, page_size: int = 10, status: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出文档"""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status

        response = await self.client.get("/api/v1/documents/", params=params)
        response.raise_for_status()
        return response.json()

    async def search_documents(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7,
        document_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """搜索文档"""
        request_data = {"query": query, "top_k": top_k, "threshold": threshold}
        if document_ids:
            request_data["document_ids"] = document_ids

        response = await self.client.post("/api/v1/documents/search", json=request_data)
        response.raise_for_status()
        return response.json()

    # 系统管理方法
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        response = await self.client.get("/api/v1/system/status")
        response.raise_for_status()
        return response.json()

    async def cleanup_system(
        self,
        older_than_days: int = 30,
        include_completed: bool = False,
        include_logs: bool = True,
        include_cache: bool = True,
    ) -> Dict[str, Any]:
        """清理系统"""
        request_data = {
            "older_than_days": older_than_days,
            "include_completed": include_completed,
            "include_logs": include_logs,
            "include_cache": include_cache,
        }

        response = await self.client.post("/api/v1/system/cleanup", json=request_data)
        response.raise_for_status()
        return response.json()


class TestAgentWebSocketClient:
    """TestAgent WebSocket客户端"""

    def __init__(
        self, base_url: str = "ws://localhost:8000", client_id: Optional[str] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id or f"client_{int(time.time())}"
        self.websocket = None
        self.message_handlers = {}

    async def connect(self):
        """连接WebSocket"""
        ws_url = f"{self.base_url}/ws/ws/{self.client_id}"
        self.websocket = await websockets.connect(ws_url)

    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def send_message(self, message: Dict[str, Any]):
        """发送消息"""
        if not self.websocket:
            raise RuntimeError("WebSocket未连接")

        await self.websocket.send(json.dumps(message))

    async def listen(self):
        """监听消息"""
        if not self.websocket:
            raise RuntimeError("WebSocket未连接")

        async for message in self.websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type")

                if message_type in self.message_handlers:
                    await self.message_handlers[message_type](data)
                else:
                    print(f"收到未处理的消息: {data}")

            except json.JSONDecodeError:
                print(f"收到无效JSON消息: {message}")
            except Exception as e:
                print(f"处理消息失败: {e}")

    def on_message(self, message_type: str):
        """消息处理装饰器"""

        def decorator(func):
            self.message_handlers[message_type] = func
            return func

        return decorator

    async def subscribe_task(self, task_id: str):
        """订阅任务更新"""
        await self.send_message({"type": "subscribe_task", "task_id": task_id})

    async def unsubscribe_task(self, task_id: str):
        """取消订阅任务更新"""
        await self.send_message({"type": "unsubscribe_task", "task_id": task_id})

    async def get_task_status(self, task_id: str):
        """获取任务状态"""
        await self.send_message({"type": "get_task_status", "task_id": task_id})

    async def ping(self):
        """发送心跳"""
        await self.send_message({"type": "ping"})


# 同步客户端包装器
class TestAgentSyncClient:
    """TestAgent同步客户端"""

    def __init__(self, *args, **kwargs):
        self._async_client = TestAgentClient(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.run(self._async_client.close())

    def _run_async(self, coro):
        """运行异步方法"""
        return asyncio.run(coro)

    def health_check(self):
        return self._run_async(self._async_client.health_check())

    def create_task(self, *args, **kwargs):
        return self._run_async(self._async_client.create_task(*args, **kwargs))

    def execute_task(self, *args, **kwargs):
        return self._run_async(self._async_client.execute_task(*args, **kwargs))

    def get_task_status(self, task_id: str):
        return self._run_async(self._async_client.get_task_status(task_id))

    def wait_for_completion(self, *args, **kwargs):
        return self._run_async(self._async_client.wait_for_completion(*args, **kwargs))

    def list_tasks(self, *args, **kwargs):
        return self._run_async(self._async_client.list_tasks(*args, **kwargs))

    def get_system_status(self):
        return self._run_async(self._async_client.get_system_status())
