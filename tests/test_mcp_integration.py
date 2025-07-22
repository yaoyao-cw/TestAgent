#!/usr/bin/env python3
"""
MCP集成单元测试
"""

import pytest
import asyncio
import json
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from src.mcp.config import MCPConfig, MCPServerConfig, load_mcp_config, save_mcp_config
from src.mcp.client import MCPClient, create_mcp_client
from src.mcp.sse_client import MCPSSEClient
from src.mcp.server_manager import MCPServerManager
from src.mcp.tool_adapter import MCPToolAdapter
from src.exceptions import MCPIntegrationException


class TestMCPConfig:
    """MCP配置测试"""
    
    def test_server_config_creation(self):
        """测试服务器配置创建"""
        # 测试stdio配置
        stdio_config = MCPServerConfig(
            connection_type="stdio",
            command="uvx",
            args=["example-server"],
            env={"LOG_LEVEL": "INFO"},
            timeout=30
        )
        
        assert stdio_config.connection_type == "stdio"
        assert stdio_config.command == "uvx"
        assert stdio_config.args == ["example-server"]
        assert stdio_config.env == {"LOG_LEVEL": "INFO"}
        assert stdio_config.timeout == 30
        assert not stdio_config.disabled
        
        # 测试SSE配置
        sse_config = MCPServerConfig(
            connection_type="sse",
            url="https://api.example.com/mcp/sse",
            headers={"Authorization": "Bearer token"},
            timeout=30
        )
        
        assert sse_config.connection_type == "sse"
        assert sse_config.url == "https://api.example.com/mcp/sse"
        assert sse_config.headers == {"Authorization": "Bearer token"}
        assert sse_config.timeout == 30
        assert not sse_config.disabled
    
    def test_server_config_validation(self):
        """测试服务器配置验证"""
        # 测试stdio模式下空命令
        with pytest.raises(ValueError):
            MCPServerConfig(connection_type="stdio", command="")
        
        # 测试stdio模式正常配置
        config = MCPServerConfig(connection_type="stdio", command="  uvx  ")
        assert config.command == "uvx"
        
        # 测试SSE模式下空URL
        with pytest.raises(ValueError):
            MCPServerConfig(connection_type="sse", url="")
        
        # 测试SSE模式下无效URL
        with pytest.raises(ValueError):
            MCPServerConfig(connection_type="sse", url="invalid-url")
        
        # 测试SSE模式正常配置
        sse_config = MCPServerConfig(
            connection_type="sse", 
            url="https://api.example.com/mcp"
        )
        assert sse_config.url == "https://api.example.com/mcp"
    
    def test_mcp_config_creation(self):
        """测试MCP配置创建"""
        server_config = MCPServerConfig(command="uvx", args=["test-server"])
        config = MCPConfig(mcp_servers={"test": server_config})
        
        assert "test" in config.mcp_servers
        assert config.mcp_servers["test"].command == "uvx"
    
    def test_config_file_operations(self):
        """测试配置文件操作"""
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "mcpServers": {
                    "test-server": {
                        "command": "uvx",
                        "args": ["test-server"],
                        "env": {"LOG_LEVEL": "INFO"},
                        "disabled": False
                    }
                },
                "global_timeout": 60
            }
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            # 测试加载配置
            config = MCPConfig.from_file(config_path)
            assert "test-server" in config.mcp_servers
            assert config.mcp_servers["test-server"].command == "uvx"
            assert config.global_timeout == 60
            
            # 测试保存配置
            config.add_server("new-server", MCPServerConfig(command="python", args=["-m", "server"]))
            config.to_file(config_path)
            
            # 重新加载验证
            reloaded_config = MCPConfig.from_file(config_path)
            assert "new-server" in reloaded_config.mcp_servers
            
        finally:
            Path(config_path).unlink()
    
    def test_config_server_management(self):
        """测试配置服务器管理"""
        config = MCPConfig()
        
        # 添加服务器
        server_config = MCPServerConfig(command="uvx", args=["test"])
        config.add_server("test", server_config)
        assert "test" in config.mcp_servers
        
        # 获取服务器
        retrieved = config.get_server("test")
        assert retrieved is not None
        assert retrieved.command == "uvx"
        
        # 移除服务器
        assert config.remove_server("test")
        assert "test" not in config.mcp_servers
        assert not config.remove_server("nonexistent")
    
    def test_enabled_servers(self):
        """测试启用的服务器"""
        config = MCPConfig()
        
        # 添加启用的服务器
        config.add_server("enabled", MCPServerConfig(command="uvx", disabled=False))
        
        # 添加禁用的服务器
        config.add_server("disabled", MCPServerConfig(command="uvx", disabled=True))
        
        enabled = config.get_enabled_servers()
        assert "enabled" in enabled
        assert "disabled" not in enabled


class TestMCPClient:
    """MCP客户端测试"""
    
    @pytest.fixture
    def stdio_server_config(self):
        """stdio服务器配置fixture"""
        return MCPServerConfig(
            connection_type="stdio",
            command="uvx",
            args=["test-server"],
            env={"LOG_LEVEL": "INFO"}
        )
    
    @pytest.fixture
    def sse_server_config(self):
        """SSE服务器配置fixture"""
        return MCPServerConfig(
            connection_type="sse",
            url="https://api.example.com/mcp/sse",
            headers={"Authorization": "Bearer token"},
            timeout=30
        )
    
    @pytest.fixture
    def mock_session(self):
        """模拟会话fixture"""
        session = AsyncMock()
        
        # 模拟工具列表
        tools_result = Mock()
        tools_result.tools = [
            Mock(name="test_tool", description="测试工具", inputSchema={"type": "object"})
        ]
        session.list_tools.return_value = tools_result
        
        # 模拟资源列表
        resources_result = Mock()
        resources_result.resources = [
            Mock(uri="test://resource", name="测试资源", description="测试资源", mimeType="text/plain")
        ]
        session.list_resources.return_value = resources_result
        
        # 模拟工具调用
        tool_result = Mock()
        tool_result.content = [{"type": "text", "text": "工具执行结果"}]
        session.call_tool.return_value = tool_result
        
        # 模拟资源读取
        resource_result = Mock()
        resource_result.contents = [{"type": "text", "text": "资源内容"}]
        session.read_resource.return_value = resource_result
        
        return session
    
    def test_client_factory(self, stdio_server_config, sse_server_config):
        """测试客户端工厂函数"""
        # 测试创建stdio客户端
        stdio_client = create_mcp_client("stdio-server", stdio_server_config)
        assert stdio_client.__class__.__name__ in ["MCPStdioClient", "MCPClient"]
        
        # 测试创建SSE客户端
        sse_client = create_mcp_client("sse-server", sse_server_config)
        assert sse_client.__class__.__name__ == "MCPSSEClient"
        
        # 测试不支持的连接类型（Pydantic会在配置创建时就验证）
        with pytest.raises(ValueError):
            # 这里会在配置创建时就抛出ValidationError，被pytest捕获为ValueError
            MCPServerConfig(connection_type="invalid")
    
    def test_stdio_client_creation(self, stdio_server_config):
        """测试stdio客户端创建"""
        client = create_mcp_client("test-server", stdio_server_config)
        
        assert client.server_name == "test-server"
        assert client.server_config.connection_type == "stdio"
        assert client.server_config.command == "uvx"
        assert not client.connected
    
    @pytest.mark.asyncio
    async def test_client_tool_call(self, stdio_server_config, mock_session):
        """测试客户端工具调用"""
        client = create_mcp_client("test-server", stdio_server_config)
        client.session = mock_session
        client.connected = True
        client.tools = {"test_tool": {"name": "test_tool", "description": "测试工具"}}
        
        result = await client.call_tool("test_tool", {"param": "value"})
        
        assert result["success"]
        assert result["tool_name"] == "test_tool"
        assert "result" in result
        
        # 测试不存在的工具
        result = await client.call_tool("nonexistent", {})
        assert not result["success"]
        assert "不存在" in result["error"]
    
    @pytest.mark.asyncio
    async def test_client_resource_read(self, stdio_server_config, mock_session):
        """测试客户端资源读取"""
        client = create_mcp_client("test-server", stdio_server_config)
        client.session = mock_session
        client.connected = True
        client.resources = {"test://resource": {"uri": "test://resource"}}
        
        result = await client.read_resource("test://resource")
        
        assert result["success"]
        assert result["uri"] == "test://resource"
        assert "content" in result
    
    def test_client_info_methods(self, stdio_server_config):
        """测试客户端信息方法"""
        client = create_mcp_client("test-server", stdio_server_config)
        client.tools = {"tool1": {}, "tool2": {}}
        client.resources = {"res1": {}, "res2": {}}
        
        assert len(client.list_tools()) == 2
        assert len(client.list_resources()) == 2
        
        status = client.get_status()
        assert status["server_name"] == "test-server"
        assert status["tools_count"] == 2
        assert status["resources_count"] == 2


class TestMCPServerManager:
    """MCP服务器管理器测试"""
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置fixture"""
        config = MCPConfig()
        config.add_server("server1", MCPServerConfig(command="uvx", args=["server1"]))
        config.add_server("server2", MCPServerConfig(command="uvx", args=["server2"], disabled=True))
        return config
    
    @pytest.fixture
    def mock_client(self):
        """模拟客户端fixture"""
        client = Mock(spec=MCPClient)
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.connected = True
        client.list_tools.return_value = ["tool1", "tool2"]
        client.list_resources.return_value = ["res1"]
        client.get_status.return_value = {"status": "connected"}
        client.health_check = AsyncMock(return_value=True)
        client.call_tool = AsyncMock(return_value={"success": True, "result": "test"})
        return client
    
    @pytest.mark.asyncio
    async def test_manager_start_stop(self, mock_config):
        """测试管理器启动停止"""
        manager = MCPServerManager(mock_config)
        
        with patch.object(manager, 'connect_all_servers', new_callable=AsyncMock):
            await manager.start()
            assert manager.running
            
            await manager.stop()
            assert not manager.running
    
    @pytest.mark.asyncio
    async def test_server_connection(self, mock_config, mock_client):
        """测试服务器连接"""
        manager = MCPServerManager(mock_config)
        
        with patch('src.mcp.server_manager.create_mcp_client', return_value=mock_client):
            success = await manager._connect_server("server1", mock_config.get_server("server1"))
            
            assert success
            assert "server1" in manager.clients
            mock_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tool_call(self, mock_config, mock_client):
        """测试工具调用"""
        manager = MCPServerManager(mock_config)
        manager.clients["server1"] = mock_client
        
        result = await manager.call_tool("server1", "test_tool", {"param": "value"})
        
        mock_client.call_tool.assert_called_once_with("test_tool", {"param": "value"})
    
    @pytest.mark.asyncio
    async def test_reconnection(self, mock_config, mock_client):
        """测试重连功能"""
        manager = MCPServerManager(mock_config)
        
        with patch('src.mcp.server_manager.create_mcp_client', return_value=mock_client):
            success = await manager.reconnect_server("server1")
            assert success
    
    def test_status_methods(self, mock_config, mock_client):
        """测试状态方法"""
        manager = MCPServerManager(mock_config)
        manager.clients["server1"] = mock_client
        
        # 测试获取可用工具
        tools = manager.get_available_tools()
        assert "server1" in tools
        
        # 测试获取服务器状态
        status = manager.get_server_status("server1")
        assert status is not None
        
        # 测试列出连接的服务器
        connected = manager.list_connected_servers()
        assert "server1" in connected


class TestMCPToolAdapter:
    """MCP工具适配器测试"""
    
    @pytest.fixture
    def mock_manager(self):
        """模拟管理器fixture"""
        manager = Mock(spec=MCPServerManager)
        manager.get_available_tools.return_value = {
            "server1": ["tool1", "tool2"]
        }
        manager.get_tool_info.return_value = {
            "name": "tool1",
            "description": "测试工具",
            "inputSchema": {
                "type": "object",
                "properties": {"param": {"type": "string"}},
                "required": ["param"]
            }
        }
        manager.call_tool = AsyncMock(return_value={
            "success": True,
            "result": "test result",
            "timestamp": "2024-01-01T00:00:00"
        })
        return manager
    
    def test_adapter_initialization(self, mock_manager):
        """测试适配器初始化"""
        adapter = MCPToolAdapter(mock_manager)
        assert adapter.manager == mock_manager
    
    def test_get_available_tools(self, mock_manager):
        """测试获取可用工具"""
        adapter = MCPToolAdapter(mock_manager)
        tools = adapter.get_available_tools()
        
        assert len(tools) == 2
        assert any(tool["tool_name"] == "tool1" for tool in tools)
    
    def test_get_tool_by_name(self, mock_manager):
        """测试根据名称获取工具"""
        adapter = MCPToolAdapter(mock_manager)
        
        # 测试完整名称
        tool = adapter.get_tool_by_name("server1.tool1")
        assert tool is not None
        assert tool["tool_name"] == "tool1"
        
        # 测试简单名称
        tool = adapter.get_tool_by_name("tool1")
        assert tool is not None
        
        # 测试不存在的工具
        tool = adapter.get_tool_by_name("nonexistent")
        assert tool is None
    
    def test_search_tools(self, mock_manager):
        """测试搜索工具"""
        adapter = MCPToolAdapter(mock_manager)
        
        # 搜索工具名称
        results = adapter.search_tools("tool1")
        assert len(results) >= 1
        
        # 搜索描述
        results = adapter.search_tools("测试")
        assert len(results) >= 1
    
    @pytest.mark.asyncio
    async def test_call_tool(self, mock_manager):
        """测试调用工具"""
        adapter = MCPToolAdapter(mock_manager)
        
        result = await adapter.call_tool("tool1", {"param": "value"})
        
        assert result["success"]
        assert result["tool_name"] == "tool1"
        mock_manager.call_tool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self, mock_manager):
        """测试调用不存在的工具"""
        adapter = MCPToolAdapter(mock_manager)
        
        result = await adapter.call_tool("nonexistent", {})
        
        assert not result["success"]
        assert "不存在" in result["error"]
    
    def test_create_tool_function(self, mock_manager):
        """测试创建工具函数"""
        adapter = MCPToolAdapter(mock_manager)
        
        tool_func = adapter.create_tool_function("tool1")
        assert callable(tool_func)
        assert tool_func.__name__ == "tool1"
    
    def test_get_tools_for_llm(self, mock_manager):
        """测试获取LLM工具描述"""
        adapter = MCPToolAdapter(mock_manager)
        
        tools = adapter.get_tools_for_llm()
        assert len(tools) == 2
        
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
    
    def test_get_statistics(self, mock_manager):
        """测试获取统计信息"""
        adapter = MCPToolAdapter(mock_manager)
        
        stats = adapter.get_statistics()
        assert "total_tools" in stats
        assert "total_servers" in stats
        assert stats["total_tools"] == 2
        assert stats["total_servers"] == 1


class TestSSEClient:
    """SSE客户端测试"""
    
    def test_sse_client_creation(self):
        """测试SSE客户端创建"""
        sse_config = MCPServerConfig(
            connection_type="sse",
            url="https://api.example.com/mcp/sse",
            headers={"Authorization": "Bearer token"}
        )
        
        from src.mcp.sse_client import MCPSSEClient
        client = MCPSSEClient("sse-server", sse_config)
        
        assert client.server_name == "sse-server"
        assert client.server_config.connection_type == "sse"
        assert client.server_config.url == "https://api.example.com/mcp/sse"
        assert not client.connected
    
    def test_sse_client_status(self):
        """测试SSE客户端状态"""
        sse_config = MCPServerConfig(
            connection_type="sse",
            url="https://api.example.com/mcp/sse"
        )
        
        from src.mcp.sse_client import MCPSSEClient
        client = MCPSSEClient("sse-server", sse_config)
        
        status = client.get_status()
        assert status["server_name"] == "sse-server"
        assert status["connection_type"] == "sse"
        assert status["url"] == "https://api.example.com/mcp/sse"
        assert not status["connected"]


class TestMCPIntegration:
    """MCP集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_integration_flow(self):
        """测试完整集成流程"""
        # 创建临时配置
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "mcpServers": {
                    "stdio-server": {
                        "connection_type": "stdio",
                        "command": "echo",
                        "args": ["test"],
                        "disabled": True  # 禁用以避免实际连接
                    },
                    "sse-server": {
                        "connection_type": "sse",
                        "url": "https://api.example.com/mcp/sse",
                        "disabled": True  # 禁用以避免实际连接
                    }
                }
            }
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            # 加载配置
            config = load_mcp_config(config_path)
            assert "stdio-server" in config.mcp_servers
            assert "sse-server" in config.mcp_servers
            
            # 验证配置类型
            assert config.mcp_servers["stdio-server"].connection_type == "stdio"
            assert config.mcp_servers["sse-server"].connection_type == "sse"
            
            # 创建管理器
            manager = MCPServerManager(config)
            
            # 创建适配器
            adapter = MCPToolAdapter(manager)
            
            # 验证初始状态
            assert not manager.running
            assert len(adapter.get_available_tools()) == 0
            
        finally:
            Path(config_path).unlink()
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效服务器配置
        with pytest.raises(ValueError):
            MCPServerConfig(command="")
        
        # 测试无效配置文件路径（这个不会抛出异常，而是返回默认配置）
        config = MCPConfig.from_file("/nonexistent/path")
        assert isinstance(config, MCPConfig)
        assert len(config.mcp_servers) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])