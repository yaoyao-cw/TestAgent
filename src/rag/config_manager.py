"""知识库配置管理系统

实现知识库配置文件解析和验证、服务健康检查和故障转移机制、
动态配置更新和服务重载功能
"""

import os
import json
import yaml
import asyncio
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

from ..config.logging_config import get_logger
from ..exceptions import RAGServiceException
from .service_manager import RAGServiceManager, ServiceConfig, ServicePriority

logger = get_logger("rag_config_manager")


class RAGServiceConfigModel(BaseModel):
    """RAG服务配置模型"""
    name: str = Field(..., description="服务名称")
    service_type: str = Field(..., description="服务类型")
    priority: str = Field(default="fallback", description="服务优先级")
    enabled: bool = Field(default=True, description="是否启用")
    config: Dict[str, Any] = Field(default_factory=dict, description="服务配置")
    health_check_interval: int = Field(default=60, ge=10, le=3600, description="健康检查间隔（秒）")
    max_failures: int = Field(default=3, ge=1, le=10, description="最大失败次数")
    failure_timeout: int = Field(default=300, ge=60, le=3600, description="失败后的超时时间（秒）")
    
    @validator('service_type')
    def validate_service_type(cls, v):
        valid_types = ['chromadb', 'ragflow', 'qanything', 'custom', 'custom_rag']
        if v.lower() not in valid_types:
            raise ValueError(f"不支持的服务类型: {v}. 支持的类型: {valid_types}")
        return v.lower()
    
    @validator('priority')
    def validate_priority(cls, v):
        valid_priorities = ['primary', 'secondary', 'fallback']
        if v.lower() not in valid_priorities:
            raise ValueError(f"无效的优先级: {v}. 支持的优先级: {valid_priorities}")
        return v.lower()


class RAGConfigModel(BaseModel):
    """RAG配置模型"""
    services: Dict[str, RAGServiceConfigModel] = Field(default_factory=dict, description="RAG服务配置")
    global_settings: Dict[str, Any] = Field(default_factory=dict, description="全局设置")
    
    @validator('services')
    def validate_services(cls, v):
        if not v:
            raise ValueError("至少需要配置一个RAG服务")
        
        # 检查是否有主服务
        has_primary = any(service.priority == "primary" for service in v.values())
        if not has_primary:
            logger.warning("没有配置主服务，建议至少配置一个primary服务")
        
        return v


@dataclass
class ConfigValidationResult:
    """配置验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    validated_config: Optional[RAGConfigModel] = None


class RAGConfigManager:
    """RAG配置管理器
    
    负责RAG服务配置的加载、验证、更新和管理
    """
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path) if config_path else Path("config/rag_services.yaml")
        self.config: Optional[RAGConfigModel] = None
        self.service_manager: Optional[RAGServiceManager] = None
        self.last_modified: Optional[datetime] = None
        self.auto_reload_enabled = False
        self.auto_reload_task: Optional[asyncio.Task] = None
        
        # 确保配置目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"RAG配置管理器初始化，配置文件: {self.config_path}")
    
    def load_config(self, config_path: Optional[Union[str, Path]] = None) -> RAGConfigModel:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            RAGConfigModel: 加载的配置
        """
        if config_path:
            self.config_path = Path(config_path)
        
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}，创建默认配置")
            self._create_default_config()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix.lower() == '.json':
                    config_data = json.load(f)
                else:
                    config_data = yaml.safe_load(f)
            
            # 验证配置
            validation_result = self.validate_config(config_data)
            if not validation_result.is_valid:
                raise RAGServiceException(f"配置验证失败: {validation_result.errors}")
            
            self.config = validation_result.validated_config
            self.last_modified = datetime.fromtimestamp(self.config_path.stat().st_mtime)
            
            logger.info(f"配置加载成功，包含 {len(self.config.services)} 个服务")
            return self.config
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise RAGServiceException(f"加载配置失败: {e}")
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            "services": {
                "chromadb_primary": {
                    "name": "chromadb_primary",
                    "service_type": "chromadb",
                    "priority": "primary",
                    "enabled": True,
                    "config": {
                        "persist_directory": "./data/vectordb",
                        "collection_name": "default",
                        "embedding_model": "text-embedding-ada-002",
                        "embedding_provider": "openai"
                    },
                    "health_check_interval": 60,
                    "max_failures": 3,
                    "failure_timeout": 300
                },
                "ragflow_secondary": {
                    "name": "ragflow_secondary",
                    "service_type": "ragflow",
                    "priority": "secondary",
                    "enabled": False,
                    "config": {
                        "api_url": "http://localhost:9380",
                        "api_key": "${RAGFLOW_API_KEY}",
                        "dataset_id": "default",
                        "timeout": 30,
                        "max_retries": 3
                    },
                    "health_check_interval": 120,
                    "max_failures": 2,
                    "failure_timeout": 600
                },
                "qanything_fallback": {
                    "name": "qanything_fallback",
                    "service_type": "qanything",
                    "priority": "fallback",
                    "enabled": False,
                    "config": {
                        "api_url": "http://localhost:8777",
                        "api_key": "${QANYTHING_API_KEY}",
                        "knowledge_base_id": "default",
                        "timeout": 30,
                        "max_retries": 3
                    },
                    "health_check_interval": 180,
                    "max_failures": 2,
                    "failure_timeout": 900
                }
            },
            "global_settings": {
                "default_top_k": 5,
                "default_similarity_threshold": 0.7,
                "enable_auto_failover": True,
                "enable_health_checks": True,
                "log_level": "INFO"
            }
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            logger.info(f"默认配置文件已创建: {self.config_path}")
            
        except Exception as e:
            logger.error(f"创建默认配置文件失败: {e}")
            raise RAGServiceException(f"创建默认配置文件失败: {e}")
    
    def validate_config(self, config_data: Dict[str, Any]) -> ConfigValidationResult:
        """验证配置数据
        
        Args:
            config_data: 配置数据
            
        Returns:
            ConfigValidationResult: 验证结果
        """
        errors = []
        warnings = []
        
        try:
            # 解析服务配置
            services = {}
            services_data = config_data.get("services", {})
            
            for service_name, service_data in services_data.items():
                try:
                    # 确保服务名称一致
                    service_data["name"] = service_name
                    service_config = RAGServiceConfigModel(**service_data)
                    services[service_name] = service_config
                except Exception as e:
                    errors.append(f"服务 {service_name} 配置无效: {e}")
            
            if not services:
                errors.append("没有有效的服务配置")
            
            # 创建完整配置模型
            rag_config = RAGConfigModel(
                services=services,
                global_settings=config_data.get("global_settings", {})
            )
            
            # 额外验证
            self._validate_service_dependencies(rag_config, warnings)
            self._validate_environment_variables(rag_config, warnings)
            
            return ConfigValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                validated_config=rag_config if len(errors) == 0 else None
            )
            
        except Exception as e:
            errors.append(f"配置解析失败: {e}")
            return ConfigValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
    
    def _validate_service_dependencies(self, config: RAGConfigModel, warnings: List[str]):
        """验证服务依赖"""
        for service_name, service_config in config.services.items():
            if service_config.service_type == "chromadb":
                # 检查ChromaDB依赖
                persist_dir = service_config.config.get("persist_directory")
                if persist_dir and not os.path.exists(persist_dir):
                    warnings.append(f"服务 {service_name}: 持久化目录不存在 {persist_dir}")
            
            elif service_config.service_type in ["ragflow", "qanything", "custom"]:
                # 检查API配置
                api_url = service_config.config.get("api_url")
                if not api_url:
                    warnings.append(f"服务 {service_name}: 缺少API URL配置")
                
                api_key = service_config.config.get("api_key")
                if not api_key:
                    warnings.append(f"服务 {service_name}: 缺少API密钥配置")
    
    def _validate_environment_variables(self, config: RAGConfigModel, warnings: List[str]):
        """验证环境变量"""
        for service_name, service_config in config.services.items():
            for key, value in service_config.config.items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    if not os.getenv(env_var):
                        warnings.append(f"服务 {service_name}: 环境变量 {env_var} 未设置")
    
    def save_config(self, config: Optional[RAGConfigModel] = None, config_path: Optional[Union[str, Path]] = None):
        """保存配置文件
        
        Args:
            config: 要保存的配置
            config_path: 保存路径
        """
        if config_path:
            self.config_path = Path(config_path)
        
        config = config or self.config
        if not config:
            raise RAGServiceException("没有可保存的配置")
        
        try:
            # 转换为字典格式
            config_dict = {
                "services": {},
                "global_settings": config.global_settings
            }
            
            for service_name, service_config in config.services.items():
                config_dict["services"][service_name] = {
                    "name": service_config.name,
                    "service_type": service_config.service_type,
                    "priority": service_config.priority,
                    "enabled": service_config.enabled,
                    "config": service_config.config,
                    "health_check_interval": service_config.health_check_interval,
                    "max_failures": service_config.max_failures,
                    "failure_timeout": service_config.failure_timeout
                }
            
            # 保存文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.suffix.lower() == '.json':
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            self.last_modified = datetime.now()
            logger.info(f"配置已保存到: {self.config_path}")
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            raise RAGServiceException(f"保存配置失败: {e}")
    
    async def create_service_manager(self, config: Optional[RAGConfigModel] = None) -> RAGServiceManager:
        """创建服务管理器
        
        Args:
            config: RAG配置
            
        Returns:
            RAGServiceManager: 服务管理器实例
        """
        config = config or self.config
        if not config:
            raise RAGServiceException("没有可用的配置")
        
        # 创建服务管理器
        manager = RAGServiceManager(config.global_settings)
        
        # 添加服务
        for service_name, service_config in config.services.items():
            if service_config.enabled:
                # 解析环境变量
                resolved_config = self._resolve_environment_variables(service_config.config)
                
                # 创建服务配置
                manager_service_config = ServiceConfig(
                    name=service_config.name,
                    service_type=service_config.service_type,
                    priority=ServicePriority(service_config.priority),
                    enabled=service_config.enabled,
                    config=resolved_config,
                    health_check_interval=service_config.health_check_interval,
                    max_failures=service_config.max_failures,
                    failure_timeout=service_config.failure_timeout
                )
                
                manager.add_service(manager_service_config)
        
        # 初始化所有服务
        await manager.initialize_all_services()
        
        self.service_manager = manager
        logger.info("服务管理器创建成功")
        return manager
    
    def _resolve_environment_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解析环境变量
        
        Args:
            config: 原始配置
            
        Returns:
            Dict[str, Any]: 解析后的配置
        """
        resolved_config = {}
        
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                resolved_value = os.getenv(env_var)
                if resolved_value is not None:
                    resolved_config[key] = resolved_value
                else:
                    logger.warning(f"环境变量 {env_var} 未设置，使用原始值")
                    resolved_config[key] = value
            elif isinstance(value, dict):
                resolved_config[key] = self._resolve_environment_variables(value)
            else:
                resolved_config[key] = value
        
        return resolved_config
    
    async def update_service_config(self, service_name: str, new_config: Dict[str, Any]) -> bool:
        """更新服务配置
        
        Args:
            service_name: 服务名称
            new_config: 新配置
            
        Returns:
            bool: 更新是否成功
        """
        if not self.config:
            raise RAGServiceException("配置未加载")
        
        if service_name not in self.config.services:
            raise RAGServiceException(f"服务 {service_name} 不存在")
        
        try:
            # 更新配置
            service_config = self.config.services[service_name]
            service_config.config.update(new_config)
            
            # 保存配置
            self.save_config()
            
            # 如果服务管理器存在，重载服务
            if self.service_manager:
                success = await self.service_manager.reload_service(service_name, new_config)
                if success:
                    logger.info(f"服务 {service_name} 配置更新并重载成功")
                else:
                    logger.error(f"服务 {service_name} 重载失败")
                return success
            
            logger.info(f"服务 {service_name} 配置更新成功")
            return True
            
        except Exception as e:
            logger.error(f"更新服务配置失败: {e}")
            return False
    
    async def enable_auto_reload(self, check_interval: int = 10):
        """启用自动重载
        
        Args:
            check_interval: 检查间隔（秒）
        """
        if self.auto_reload_enabled:
            return
        
        self.auto_reload_enabled = True
        self.auto_reload_task = asyncio.create_task(
            self._auto_reload_loop(check_interval)
        )
        
        logger.info(f"自动重载已启用，检查间隔: {check_interval}秒")
    
    async def disable_auto_reload(self):
        """禁用自动重载"""
        self.auto_reload_enabled = False
        
        if self.auto_reload_task:
            self.auto_reload_task.cancel()
            try:
                await self.auto_reload_task
            except asyncio.CancelledError:
                pass
            self.auto_reload_task = None
        
        logger.info("自动重载已禁用")
    
    async def _auto_reload_loop(self, check_interval: int):
        """自动重载循环"""
        while self.auto_reload_enabled:
            try:
                if self.config_path.exists():
                    current_modified = datetime.fromtimestamp(self.config_path.stat().st_mtime)
                    
                    if self.last_modified and current_modified > self.last_modified:
                        logger.info("检测到配置文件变更，重新加载配置")
                        
                        try:
                            # 重新加载配置
                            new_config = self.load_config()
                            
                            # 重新创建服务管理器
                            if self.service_manager:
                                await self.service_manager.stop_health_checks()
                            
                            self.service_manager = await self.create_service_manager(new_config)
                            
                            logger.info("配置重载成功")
                            
                        except Exception as e:
                            logger.error(f"配置重载失败: {e}")
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"自动重载循环异常: {e}")
                await asyncio.sleep(check_interval)
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息
        
        Returns:
            Dict[str, Any]: 配置信息
        """
        if not self.config:
            return {"error": "配置未加载"}
        
        return {
            "config_path": str(self.config_path),
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "auto_reload_enabled": self.auto_reload_enabled,
            "services_count": len(self.config.services),
            "enabled_services": sum(1 for s in self.config.services.values() if s.enabled),
            "services": {
                name: {
                    "type": service.service_type,
                    "priority": service.priority,
                    "enabled": service.enabled
                }
                for name, service in self.config.services.items()
            },
            "global_settings": self.config.global_settings
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not self.config:
            self.load_config()
        
        if not self.service_manager:
            await self.create_service_manager()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disable_auto_reload()
        
        if self.service_manager:
            await self.service_manager.stop_health_checks()