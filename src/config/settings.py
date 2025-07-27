#!/usr/bin/env python3
"""
TestAgent配置管理系统
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

from .logging_config import get_logger

logger = get_logger("config")


class LLMConfig(BaseModel):
    """LLM配置"""

    provider: str = Field(default="openai", description="LLM提供商")
    model: str = Field(default="gpt-3.5-turbo", description="默认模型")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    api_base: Optional[str] = Field(default=None, description="API基础URL")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(default=2000, ge=1, le=32000, description="最大令牌数")
    timeout: int = Field(default=60, ge=1, le=300, description="超时时间(秒)")
    retry_attempts: int = Field(default=3, ge=1, le=10, description="重试次数")

    @validator("provider")
    def validate_provider(cls, v):
        valid_providers = [
            "openai",
            "anthropic",
            "azure",
            "local",
            "kimi",
            "qwen",
            "deepseek",
        ]
        if v not in valid_providers:
            raise ValueError(f"Invalid provider: {v}. Must be one of {valid_providers}")
        return v


class RAGConfig(BaseModel):
    """RAG配置"""

    vector_db_type: str = Field(default="chroma", description="向量数据库类型")
    vector_db_path: str = Field(default="./data/vectordb", description="向量数据库路径")
    embedding_model: str = Field(
        default="text-embedding-ada-002", description="嵌入模型"
    )
    embedding_provider: str = Field(default="openai", description="嵌入提供商")
    chunk_size: int = Field(default=1000, ge=100, le=4000, description="文本块大小")
    chunk_overlap: int = Field(default=200, ge=0, le=1000, description="文本块重叠")
    top_k: int = Field(default=5, ge=1, le=20, description="检索结果数量")
    similarity_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="相似度阈值"
    )


class MCPServerConfig(BaseModel):
    """MCP服务器配置"""

    name: str = Field(..., description="服务器名称")
    connection_type: str = Field(..., description="连接类型: stdio, sse")
    command: Optional[str] = Field(default=None, description="启动命令")
    args: Optional[List[str]] = Field(default=None, description="命令参数")
    url: Optional[str] = Field(default=None, description="SSE连接URL")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP头")
    env: Optional[Dict[str, str]] = Field(default=None, description="环境变量")
    disabled: bool = Field(default=False, description="是否禁用")

    @validator("connection_type")
    def validate_connection_type(cls, v):
        if v not in ["stdio", "sse"]:
            raise ValueError("connection_type must be 'stdio' or 'sse'")
        return v


class MCPConfig(BaseModel):
    """MCP配置"""

    servers: Dict[str, MCPServerConfig] = Field(
        default_factory=dict, description="MCP服务器配置"
    )
    auto_discover: bool = Field(default=True, description="自动发现服务器")
    timeout: int = Field(default=30, ge=1, le=300, description="连接超时时间")


class CollaborationConfig(BaseModel):
    """协作配置"""

    auto_accept_mode: str = Field(default="conditional", description="自动接受模式")
    review_timeout: int = Field(
        default=3600, ge=60, le=86400, description="审查超时时间(秒)"
    )
    confidence_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="置信度阈值"
    )
    enable_human_feedback: bool = Field(default=True, description="启用人工反馈")

    @validator("auto_accept_mode")
    def validate_auto_accept_mode(cls, v):
        if v not in ["always", "never", "conditional"]:
            raise ValueError(
                "auto_accept_mode must be 'always', 'never', or 'conditional'"
            )
        return v


class WorkflowConfig(BaseModel):
    """工作流配置"""

    max_parallel_executions: int = Field(
        default=5, ge=1, le=20, description="最大并行执行数"
    )
    execution_timeout: int = Field(
        default=1800, ge=60, le=7200, description="执行超时时间(秒)"
    )
    checkpoint_enabled: bool = Field(default=True, description="启用检查点")
    retry_failed_tasks: bool = Field(default=True, description="重试失败任务")
    max_retry_attempts: int = Field(default=3, ge=1, le=10, description="最大重试次数")


class APIConfig(BaseModel):
    """API配置"""

    host: str = Field(default="0.0.0.0", description="服务器主机")
    port: int = Field(default=8000, ge=1, le=65535, description="服务器端口")
    workers: int = Field(default=1, ge=1, le=20, description="工作进程数")
    reload: bool = Field(default=False, description="自动重载")
    cors_origins: List[str] = Field(default=["*"], description="CORS允许的源")
    allowed_hosts: List[str] = Field(default=["*"], description="允许的主机")
    rate_limit_enabled: bool = Field(default=True, description="启用速率限制")
    rate_limit_calls_per_minute: int = Field(
        default=60, ge=1, le=1000, description="每分钟请求限制"
    )


class SecurityConfig(BaseModel):
    """安全配置"""

    api_key_required: bool = Field(default=False, description="需要API密钥")
    api_keys: List[str] = Field(default_factory=list, description="有效的API密钥")
    jwt_secret: Optional[str] = Field(default=None, description="JWT密钥")
    jwt_expire_hours: int = Field(
        default=24, ge=1, le=168, description="JWT过期时间(小时)"
    )
    enable_https: bool = Field(default=False, description="启用HTTPS")
    ssl_cert_path: Optional[str] = Field(default=None, description="SSL证书路径")
    ssl_key_path: Optional[str] = Field(default=None, description="SSL私钥路径")


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    file: Optional[str] = Field(
        default="./logs/testagent.log", description="日志文件路径"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式",
    )
    max_size: int = Field(
        default=10485760, ge=1048576, description="日志文件最大大小(字节)"
    )
    backup_count: int = Field(default=5, ge=1, le=20, description="日志备份数量")

    @validator("level")
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()


class SandboxConfig(BaseModel):
    """沙盒配置"""

    prefer_e2b: bool = Field(default=True, description="优先使用E2B沙盒")
    e2b_api_key: Optional[str] = Field(default=None, description="E2B API密钥")
    e2b_template_id: str = Field(default="python3", description="E2B模板ID")
    timeout: int = Field(default=60, ge=1, le=300, description="执行超时时间(秒)")
    memory_limit: str = Field(default="512m", description="内存限制")
    cpu_limit: float = Field(default=1.0, ge=0.1, le=8.0, description="CPU限制(核心数)")
    max_sandboxes: int = Field(default=3, ge=1, le=10, description="最大沙盒数量")
    enable_package_install: bool = Field(default=True, description="允许安装包")
    allowed_packages: List[str] = Field(
        default_factory=lambda: ["pytest", "requests", "numpy", "pandas"],
        description="允许安装的包",
    )


class TestAgentSettings(BaseSettings):
    """TestAgent主配置类"""

    # 基本配置
    debug: bool = Field(default=False, description="调试模式")
    testing: bool = Field(default=False, description="测试模式")
    version: str = Field(default="1.0.0", description="版本号")

    # E2B沙盒配置
    E2B_API_KEY: Optional[str] = Field(default=None, description="E2B API密钥")

    # 兼容性字段（从环境变量中读取但不验证）
    log_level: Optional[str] = Field(default=None, description="日志级别（兼容性）")
    vector_db_type: Optional[str] = Field(
        default=None, description="向量数据库类型（兼容性）"
    )
    vector_db_path: Optional[str] = Field(
        default=None, description="向量数据库路径（兼容性）"
    )
    cors_origins: Optional[str] = Field(default=None, description="CORS源（兼容性）")
    allowed_hosts: Optional[str] = Field(
        default=None, description="允许的主机（兼容性）"
    )

    # 各模块配置
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    collaboration: CollaborationConfig = Field(default_factory=CollaborationConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)

    # 便捷属性
    @property
    def chunk_size(self) -> int:
        return self.rag.chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self.rag.chunk_overlap

    @property
    def vector_db_persist_directory(self) -> str:
        return self.vector_db_path or self.rag.vector_db_path

    @property
    def default_collection_name(self) -> str:
        return "default"

    @property
    def max_search_results(self) -> int:
        return self.rag.top_k

    @property
    def embedding_model(self) -> str:
        return self.rag.embedding_model

    @property
    def openai_api_key(self) -> Optional[str]:
        return self.llm.api_key

    @property
    def openai_base_url(self) -> Optional[str]:
        return self.llm.api_base

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False
        extra = "allow"  # 允许额外字段


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path("config")
        self.config_dir.mkdir(exist_ok=True)
        self._settings: Optional[TestAgentSettings] = None
        self._config_files = {}

    def load_settings(self, reload: bool = False) -> TestAgentSettings:
        """加载配置"""
        if self._settings is None or reload:
            # 加载环境变量
            load_dotenv()

            # 创建基础配置
            self._settings = TestAgentSettings()

            # 加载配置文件
            self._load_config_files()

            logger.info("配置加载完成")

        return self._settings

    def _load_config_files(self):
        """加载配置文件"""
        config_files = [
            "llm.yaml",
            "rag.yaml",
            "mcp.json",
            "collaboration.yaml",
            "workflow.yaml",
            "api.yaml",
            "security.yaml",
            "logging.yaml",
        ]

        for config_file in config_files:
            config_path = self.config_dir / config_file
            if config_path.exists():
                try:
                    self._load_config_file(config_path)
                except Exception as e:
                    logger.warning(f"加载配置文件失败 {config_file}: {e}")

    def _load_config_file(self, config_path: Path):
        """加载单个配置文件"""
        with open(config_path, "r", encoding="utf-8") as f:
            if config_path.suffix.lower() == ".json":
                config_data = json.load(f)
            elif config_path.suffix.lower() in [".yaml", ".yml"]:
                config_data = yaml.safe_load(f)
            else:
                logger.warning(f"不支持的配置文件格式: {config_path}")
                return

        # 更新对应的配置
        config_name = config_path.stem
        if hasattr(self._settings, config_name):
            current_config = getattr(self._settings, config_name)
            if isinstance(current_config, BaseModel):
                # 更新Pydantic模型
                updated_config = current_config.copy(update=config_data)
                setattr(self._settings, config_name, updated_config)

        self._config_files[config_name] = config_data
        logger.debug(f"已加载配置文件: {config_path}")

    def save_config(self, config_name: str, config_data: Dict[str, Any]):
        """保存配置到文件"""
        config_path = self.config_dir / f"{config_name}.yaml"

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

            # 更新内存中的配置
            if hasattr(self._settings, config_name):
                current_config = getattr(self._settings, config_name)
                if isinstance(current_config, BaseModel):
                    updated_config = current_config.copy(update=config_data)
                    setattr(self._settings, config_name, updated_config)

            self._config_files[config_name] = config_data
            logger.info(f"配置已保存: {config_path}")

        except Exception as e:
            logger.error(f"保存配置失败 {config_name}: {e}")
            raise

    def get_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """获取配置"""
        if config_name in self._config_files:
            return self._config_files[config_name]

        if hasattr(self._settings, config_name):
            config_obj = getattr(self._settings, config_name)
            if isinstance(config_obj, BaseModel):
                return config_obj.dict()

        return None

    def update_config(self, config_name: str, updates: Dict[str, Any]):
        """更新配置"""
        current_config = self.get_config(config_name) or {}
        current_config.update(updates)
        self.save_config(config_name, current_config)

    def validate_config(self, config_name: str, config_data: Dict[str, Any]) -> bool:
        """验证配置"""
        try:
            if config_name == "llm":
                LLMConfig(**config_data)
            elif config_name == "rag":
                RAGConfig(**config_data)
            elif config_name == "mcp":
                MCPConfig(**config_data)
            elif config_name == "collaboration":
                CollaborationConfig(**config_data)
            elif config_name == "workflow":
                WorkflowConfig(**config_data)
            elif config_name == "api":
                APIConfig(**config_data)
            elif config_name == "security":
                SecurityConfig(**config_data)
            elif config_name == "logging":
                LoggingConfig(**config_data)
            else:
                logger.warning(f"未知的配置类型: {config_name}")
                return False

            return True
        except Exception as e:
            logger.error(f"配置验证失败 {config_name}: {e}")
            return False

    def export_config(self, output_path: Optional[Path] = None) -> Path:
        """导出完整配置"""
        if output_path is None:
            output_path = Path("testagent_config_export.yaml")

        full_config = {}
        if self._settings:
            full_config = self._settings.dict()

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(full_config, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"配置已导出到: {output_path}")
        return output_path

    def import_config(self, config_path: Path):
        """导入配置"""
        with open(config_path, "r", encoding="utf-8") as f:
            if config_path.suffix.lower() == ".json":
                imported_config = json.load(f)
            else:
                imported_config = yaml.safe_load(f)

        # 验证并更新各个配置模块
        for config_name, config_data in imported_config.items():
            if self.validate_config(config_name, config_data):
                self.save_config(config_name, config_data)

        # 重新加载配置
        self.load_settings(reload=True)
        logger.info(f"配置已从 {config_path} 导入")


# 全局配置管理器实例
_config_manager = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_settings() -> TestAgentSettings:
    """获取配置设置"""
    return get_config_manager().load_settings()


def reload_settings() -> TestAgentSettings:
    """重新加载配置设置"""
    return get_config_manager().load_settings(reload=True)


# 为了兼容性，创建别名
Settings = TestAgentSettings
LoggingSettings = TestAgentSettings
LLMSettings = TestAgentSettings
VectorDBSettings = TestAgentSettings
MCPSettings = TestAgentSettings
CollaborationSettings = TestAgentSettings
APISettings = TestAgentSettings
CacheSettings = TestAgentSettings

settings = get_settings()
