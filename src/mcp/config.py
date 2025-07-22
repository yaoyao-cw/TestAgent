#!/usr/bin/env python3
"""
MCP配置管理
"""

import json
import logging
from typing import Dict, Any, List, Optional, Literal
from pathlib import Path
from pydantic import BaseModel, Field, validator

from ..exceptions import MCPIntegrationException

logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """MCP服务器配置"""
    # 连接类型：stdio（标准输入输出）或 sse（Server-Sent Events）
    connection_type: Literal["stdio", "sse"] = Field("stdio", description="连接类型")
    
    # stdio 配置
    command: Optional[str] = Field(None, description="启动命令（stdio模式）")
    args: List[str] = Field(default_factory=list, description="命令参数（stdio模式）")
    env: Dict[str, str] = Field(default_factory=dict, description="环境变量")
    
    # SSE 配置
    url: Optional[str] = Field(None, description="SSE服务器URL（sse模式）")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP请求头（sse模式）")
    
    # 通用配置
    disabled: bool = Field(False, description="是否禁用")
    timeout: int = Field(30, description="连接超时时间（秒）")
    retry_count: int = Field(3, description="重试次数")
    auto_restart: bool = Field(True, description="是否自动重启")
    
    @validator('command')
    def validate_command(cls, v, values):
        connection_type = values.get('connection_type', 'stdio')
        if connection_type == 'stdio':
            if not v or not v.strip():
                raise ValueError("stdio模式下命令不能为空")
            return v.strip() if v else None
        return v
    
    @validator('url')
    def validate_url(cls, v, values):
        connection_type = values.get('connection_type', 'stdio')
        if connection_type == 'sse':
            if not v or not v.strip():
                raise ValueError("sse模式下URL不能为空")
            if not v.startswith(('http://', 'https://')):
                raise ValueError("SSE URL必须以http://或https://开头")
            return v.strip() if v else None
        return v


class MCPConfig(BaseModel):
    """MCP配置"""
    mcp_servers: Dict[str, MCPServerConfig] = Field(default_factory=dict, description="MCP服务器配置")
    global_timeout: int = Field(60, description="全局超时时间（秒）")
    max_concurrent_connections: int = Field(10, description="最大并发连接数")
    enable_logging: bool = Field(True, description="是否启用日志")
    log_level: str = Field("INFO", description="日志级别")
    
    @classmethod
    def from_file(cls, config_path: str) -> "MCPConfig":
        """从文件加载配置"""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                logger.warning(f"MCP配置文件不存在: {config_path}，使用默认配置")
                return cls()
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 转换配置格式
            servers = {}
            if "mcpServers" in config_data:
                for name, server_config in config_data["mcpServers"].items():
                    servers[name] = MCPServerConfig(**server_config)
            
            return cls(
                mcp_servers=servers,
                global_timeout=config_data.get("global_timeout", 60),
                max_concurrent_connections=config_data.get("max_concurrent_connections", 10),
                enable_logging=config_data.get("enable_logging", True),
                log_level=config_data.get("log_level", "INFO")
            )
            
        except Exception as e:
            logger.error(f"加载MCP配置失败: {e}")
            raise MCPIntegrationException(f"加载MCP配置失败: {e}")
    
    def to_file(self, config_path: str):
        """保存配置到文件"""
        try:
            config_data = {
                "mcpServers": {
                    name: server.dict() for name, server in self.mcp_servers.items()
                },
                "global_timeout": self.global_timeout,
                "max_concurrent_connections": self.max_concurrent_connections,
                "enable_logging": self.enable_logging,
                "log_level": self.log_level
            }
            
            config_file = Path(config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"MCP配置已保存到: {config_path}")
            
        except Exception as e:
            logger.error(f"保存MCP配置失败: {e}")
            raise MCPIntegrationException(f"保存MCP配置失败: {e}")
    
    def add_server(self, name: str, server_config: MCPServerConfig):
        """添加服务器配置"""
        if name in self.mcp_servers:
            logger.warning(f"服务器 {name} 已存在，将被覆盖")
        
        self.mcp_servers[name] = server_config
        logger.info(f"已添加MCP服务器配置: {name}")
    
    def remove_server(self, name: str) -> bool:
        """移除服务器配置"""
        if name in self.mcp_servers:
            del self.mcp_servers[name]
            logger.info(f"已移除MCP服务器配置: {name}")
            return True
        return False
    
    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """获取服务器配置"""
        return self.mcp_servers.get(name)
    
    def list_servers(self) -> List[str]:
        """列出所有服务器名称"""
        return list(self.mcp_servers.keys())
    
    def get_enabled_servers(self) -> Dict[str, MCPServerConfig]:
        """获取启用的服务器配置"""
        return {
            name: config for name, config in self.mcp_servers.items()
            if not config.disabled
        }


def load_mcp_config(config_path: str = None) -> MCPConfig:
    """加载MCP配置"""
    if config_path is None:
        from ..config.settings import get_settings
        settings = get_settings()
        config_path = settings.mcp_servers_config
    
    return MCPConfig.from_file(config_path)


def save_mcp_config(config: MCPConfig, config_path: str = None):
    """保存MCP配置"""
    if config_path is None:
        from ..config.settings import get_settings
        settings = get_settings()
        config_path = settings.mcp_servers_config
    
    config.to_file(config_path)