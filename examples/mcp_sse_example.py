#!/usr/bin/env python3
"""
MCP SSE支持示例
展示如何配置和使用SSE类型的MCP服务器
"""

import asyncio
import json
from pathlib import Path

from src.mcp.config import MCPConfig, MCPServerConfig
from src.mcp.server_manager import MCPServerManager
from src.mcp.tool_adapter import MCPToolAdapter


async def main():
    """主函数"""
    print("=== MCP SSE支持示例 ===\n")
    
    # 1. 创建SSE服务器配置
    print("1. 创建MCP服务器配置（包含stdio和sse类型）")
    
    # stdio服务器配置
    stdio_config = MCPServerConfig(
        connection_type="stdio",
        command="uvx",
        args=["example-mcp-server"],
        env={"LOG_LEVEL": "INFO"},
        disabled=True  # 禁用以避免实际连接
    )
    
    # SSE服务器配置
    sse_config = MCPServerConfig(
        connection_type="sse",
        url="https://api.example.com/mcp/sse",
        headers={
            "Authorization": "Bearer your-token-here",
            "Content-Type": "application/json"
        },
        disabled=True  # 禁用以避免实际连接
    )
    
    print(f"  - stdio服务器: {stdio_config.command} {' '.join(stdio_config.args)}")
    print(f"  - SSE服务器: {sse_config.url}")
    
    # 2. 创建MCP配置
    print("\n2. 创建MCP配置")
    config = MCPConfig()
    config.add_server("stdio-server", stdio_config)
    config.add_server("sse-server", sse_config)
    
    print(f"  - 配置的服务器数量: {len(config.mcp_servers)}")
    print(f"  - 启用的服务器数量: {len(config.get_enabled_servers())}")
    
    # 3. 保存配置到文件
    print("\n3. 保存配置到文件")
    config_path = Path("examples/mcp_sse_config.json")
    config_path.parent.mkdir(exist_ok=True)
    config.to_file(str(config_path))
    print(f"  - 配置已保存到: {config_path}")
    
    # 4. 从文件加载配置
    print("\n4. 从文件加载配置")
    loaded_config = MCPConfig.from_file(str(config_path))
    print(f"  - 加载的服务器: {list(loaded_config.mcp_servers.keys())}")
    
    # 5. 展示配置详情
    print("\n5. 配置详情:")
    for name, server_config in loaded_config.mcp_servers.items():
        print(f"  - {name}:")
        print(f"    类型: {server_config.connection_type}")
        if server_config.connection_type == "stdio":
            print(f"    命令: {server_config.command}")
            print(f"    参数: {server_config.args}")
        elif server_config.connection_type == "sse":
            print(f"    URL: {server_config.url}")
            print(f"    请求头: {server_config.headers}")
        print(f"    状态: {'禁用' if server_config.disabled else '启用'}")
        print(f"    超时: {server_config.timeout}秒")
    
    # 6. 创建服务器管理器（不启动，避免实际连接）
    print("\n6. 创建服务器管理器")
    manager = MCPServerManager(loaded_config)
    print(f"  - 管理器状态: {'运行中' if manager.running else '未启动'}")
    print(f"  - 配置的服务器: {manager.list_all_servers()}")
    
    # 7. 创建工具适配器
    print("\n7. 创建工具适配器")
    adapter = MCPToolAdapter(manager)
    print(f"  - 可用工具数量: {len(adapter.get_available_tools())}")
    
    # 8. 展示统计信息
    print("\n8. 统计信息:")
    stats = adapter.get_statistics()
    print(f"  - 总工具数: {stats['total_tools']}")
    print(f"  - 总服务器数: {stats['total_servers']}")
    print(f"  - 服务器列表: {stats['servers']}")
    
    # 清理临时文件
    if config_path.exists():
        config_path.unlink()
        print(f"\n清理临时文件: {config_path}")
    
    print("\n=== 示例完成 ===")


if __name__ == "__main__":
    asyncio.run(main())