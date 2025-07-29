#!/usr/bin/env python3
"""
API集成测试
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from src.server.main import app
from src.client.testagent_client import TestAgentClient, TestAgentSyncClient


@pytest.fixture
def test_client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
async def async_test_client():
    """创建异步测试客户端"""
    async with TestAgentClient(base_url="http://testserver") as client:
        yield client


class TestHealthAPI:
    """健康检查API测试"""

    def test_health_endpoint(self, test_client):
        """测试健康检查端点"""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "components" in data

    def test_root_endpoint(self, test_client):
        """测试根端点"""
        response = test_client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "TestAgent API"
        assert "version" in data
        assert "status" in data


class TestTasksAPI:
    """任务API测试"""

    @patch("src.server.routers.tasks.get_workflow_manager")
    def test_submit_task(self, mock_get_manager, test_client):
        """测试提交任务"""
        # 模拟工作流管理器
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        # 准备请求数据
        task_data = {
            "task_type": "test_case_generation",
            "task_topic": "用户登录功能测试",
            "context": "测试用户登录功能",
            "locale": "zh-CN",
        }

        response = test_client.post("/api/v1/tasks/submit", json=task_data)
        assert response.status_code == 200

        data = response.json()
        assert "task_id" in data
        assert data["status"] == "submitted"
        assert "message" in data

    @patch("src.server.routers.tasks.get_workflow_manager")
    def test_get_task_status(self, mock_get_manager, test_client):
        """测试获取任务状态"""
        # 模拟工作流管理器
        mock_manager = Mock()
        mock_manager.get_execution_status.return_value = {
            "status": "completed",
            "progress": 100.0,
            "start_time": "2023-01-01T00:00:00",
            "end_time": "2023-01-01T00:05:00",
            "duration_seconds": 300,
            "final_state": {
                "report": {"content": "测试报告"},
                "review": {"score": 0.9},
            },
        }
        mock_get_manager.return_value = mock_manager

        response = test_client.get("/api/v1/tasks/test_task_123/status")
        assert response.status_code == 200

        data = response.json()
        assert data["task_id"] == "test_task_123"
        assert data["status"] == "completed"
        assert data["progress"] == 100.0
        assert "result" in data

    @patch("src.server.routers.tasks.get_workflow_manager")
    def test_list_tasks(self, mock_get_manager, test_client):
        """测试列出任务"""
        # 模拟工作流管理器
        mock_manager = Mock()
        mock_manager.list_executions.return_value = [
            {
                "execution_id": "task_1",
                "status": "completed",
                "start_time": "2023-01-01T00:00:00",
                "duration_seconds": 300,
            },
            {
                "execution_id": "task_2",
                "status": "running",
                "start_time": "2023-01-01T01:00:00",
            },
        ]
        mock_get_manager.return_value = mock_manager

        response = test_client.get("/api/v1/tasks/?page=1&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert len(data["tasks"]) == 2

    def test_invalid_task_type(self, test_client):
        """测试无效任务类型"""
        task_data = {"task_type": "invalid_type", "task_topic": "测试任务"}

        response = test_client.post("/api/v1/tasks/submit", json=task_data)
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
        assert "无效的任务类型" in data["detail"]


class TestDocumentsAPI:
    """文档API测试"""

    @patch("src.server.routers.documents.get_document_manager")
    def test_upload_document(self, mock_get_manager, test_client):
        """测试上传文档"""
        # 模拟文档管理器
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # 准备测试文件
        test_file_content = b"This is a test document content"
        files = {"file": ("test.txt", test_file_content, "text/plain")}

        response = test_client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 200

        data = response.json()
        assert "document_id" in data
        assert data["filename"] == "test.txt"
        assert data["status"] == "uploaded"

    @patch("src.server.routers.documents.get_document_manager")
    def test_list_documents(self, mock_get_manager, test_client):
        """测试列出文档"""
        # 模拟文档管理器
        mock_manager = AsyncMock()
        mock_manager.list_documents.return_value = {
            "documents": [
                {
                    "document_id": "doc_1",
                    "status": "processed",
                    "chunk_count": 5,
                    "metadata": {
                        "filename": "test1.txt",
                        "content_type": "text/plain",
                        "file_size": 1024,
                        "upload_time": "2023-01-01T00:00:00",
                    },
                }
            ],
            "total": 1,
        }
        mock_get_manager.return_value = mock_manager

        response = test_client.get("/api/v1/documents/?page=1&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert len(data["documents"]) == 1


class TestSystemAPI:
    """系统API测试"""

    @patch("src.server.routers.system.get_workflow_manager_dep")
    @patch("src.server.routers.system.get_tool_manager_dep")
    @patch("src.server.routers.system.get_mcp_manager_dep")
    def test_system_status(self, mock_mcp, mock_tool, mock_workflow, test_client):
        """测试系统状态"""
        # 模拟各个管理器
        mock_workflow_manager = Mock()
        mock_workflow_manager.get_workflow_status.return_value = {"status": "ready"}
        mock_workflow_manager.list_executions.return_value = []
        mock_workflow.return_value = mock_workflow_manager

        mock_tool_manager = AsyncMock()
        mock_tool_manager.health_check.return_value = {"healthy": True}
        mock_tool.return_value = mock_tool_manager

        mock_mcp.return_value = None  # MCP管理器未启用

        response = test_client.get("/api/v1/system/status")
        assert response.status_code == 200

        data = response.json()
        assert "system" in data
        assert "components" in data
        assert "resources" in data
        assert "execution_stats" in data

    @patch("src.server.routers.system.get_workflow_manager_dep")
    def test_cleanup_system(self, mock_workflow, test_client):
        """测试系统清理"""
        # 模拟工作流管理器
        mock_workflow_manager = Mock()
        mock_workflow_manager.list_executions.return_value = []
        mock_workflow.return_value = mock_workflow_manager

        cleanup_data = {
            "older_than_days": 7,
            "include_completed": True,
            "include_logs": True,
            "include_cache": True,
        }

        response = test_client.post("/api/v1/system/cleanup", json=cleanup_data)
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert "cleaned_items" in data
        assert "freed_space" in data


class TestCollaborationAPI:
    """协作API测试"""

    @patch("src.server.routers.collaboration.get_plan_reviewer_dep")
    def test_submit_review(self, mock_reviewer, test_client):
        """测试提交审查"""
        # 模拟计划审查器
        mock_plan_reviewer = Mock()
        mock_plan_reviewer.submit_for_review.return_value = "review_123"
        mock_reviewer.return_value = mock_plan_reviewer

        review_data = {
            "plan_id": "plan_123",
            "plan_data": {"title": "测试计划", "steps": []},
            "task_type": "test_case_generation",
        }

        response = test_client.post(
            "/api/v1/collaboration/reviews/submit", json=review_data
        )
        assert response.status_code == 200

        data = response.json()
        assert "review_id" in data
        assert data["plan_id"] == "plan_123"
        assert data["status"] == "pending"

    @patch("src.server.routers.collaboration.get_feedback_processor_dep")
    def test_submit_feedback(self, mock_processor, test_client):
        """测试提交反馈"""
        # 模拟反馈处理器
        mock_feedback_processor = AsyncMock()
        mock_feedback_processor.submit_feedback.return_value = "feedback_123"
        mock_processor.return_value = mock_feedback_processor

        feedback_data = {
            "target_id": "task_123",
            "target_type": "report",
            "feedback": "报告需要更多细节",
            "feedback_type": "improvement",
        }

        response = test_client.post(
            "/api/v1/collaboration/feedback/submit", json=feedback_data
        )
        assert response.status_code == 200

        data = response.json()
        assert "feedback_id" in data
        assert data["status"] == "submitted"


class TestClientSDK:
    """客户端SDK测试"""

    @pytest.mark.asyncio
    async def test_async_client_health_check(self):
        """测试异步客户端健康检查"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"status": "healthy"}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            async with TestAgentClient() as client:
                result = await client.health_check()
                assert result["status"] == "healthy"

    def test_sync_client_health_check(self):
        """测试同步客户端健康检查"""
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = {"status": "healthy"}

            with TestAgentSyncClient() as client:
                result = client.health_check()
                assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_create_task(self):
        """测试创建任务"""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"task_id": "task_123"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            async with TestAgentClient() as client:
                task_id = await client.create_task(
                    task_type="test_case_generation", task_topic="测试任务"
                )
                assert task_id == "task_123"


class TestErrorHandling:
    """错误处理测试"""

    def test_404_error(self, test_client):
        """测试404错误"""
        response = test_client.get("/api/v1/tasks/nonexistent_task/status")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data

    def test_400_error(self, test_client):
        """测试400错误"""
        # 发送无效数据
        response = test_client.post("/api/v1/tasks/submit", json={})
        assert response.status_code == 422  # FastAPI验证错误

    def test_rate_limiting(self, test_client):
        """测试速率限制"""
        # 这个测试需要实际的速率限制中间件配置
        # 这里只是示例结构
        pass


class TestWebSocketAPI:
    """WebSocket API测试"""

    def test_websocket_connection(self, test_client):
        """测试WebSocket连接"""
        with test_client.websocket_connect("/ws/ws/test_client") as websocket:
            # 发送ping消息
            websocket.send_json({"type": "ping"})

            # 接收pong响应
            data = websocket.receive_json()
            assert data["type"] == "pong"

    def test_task_subscription(self, test_client):
        """测试任务订阅"""
        with test_client.websocket_connect("/ws/ws/test_client") as websocket:
            # 订阅任务
            websocket.send_json({"type": "subscribe_task", "task_id": "task_123"})

            # 接收确认消息
            data = websocket.receive_json()
            assert data["type"] == "subscription_confirmed"
            assert data["task_id"] == "task_123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
