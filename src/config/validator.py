#!/usr/bin/env python3
"""
配置验证器

提供配置验证、自动修复和健康检查功能
"""

import os
import json
import logging
from typing import Dict, List, Any, Tuple, Optional, Callable
from pathlib import Path

try:
    from .settings import Settings, get_settings
    from .manager import get_config_manager
except ImportError:
    # 如果无法导入，提供模拟实现
    Settings = None
    get_settings = None
    get_config_manager = None

# 配置日志记录器
logger = logging.getLogger("config_validator")


class ValidationResult:
    """验证结果"""
    def __init__(self, key: str, message: str, severity: str = "error", auto_fixable: bool = False):
        self.key = key
        self.message = message
        self.severity = severity  # error, warning, info
        self.auto_fixable = auto_fixable
    
    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.key}: {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "message": self.message,
            "severity": self.severity,
            "auto_fixable": self.auto_fixable
        }


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or (get_settings() if get_settings else None)
        self.validation_rules: Dict[str, List[Callable]] = {}
        self._register_default_rules()
    
    def _register_default_rules(self) -> None:
        """注册默认验证规则"""
        if not self.settings:
            return
        
        # LLM配置验证规则
        self.add_rule("llm", self._validate_llm_provider)
        self.add_rule("llm", self._validate_llm_api_keys)
        self.add_rule("llm", self._validate_llm_parameters)
        
        # 向量数据库配置验证规则
        self.add_rule("vector_db", self._validate_vector_db_type)
        self.add_rule("vector_db", self._validate_vector_db_path)
        self.add_rule("vector_db", self._validate_embedding_config)
        
        # API配置验证规则
        self.add_rule("api", self._validate_api_port)
        self.add_rule("api", self._validate_api_security)
        self.add_rule("api", self._validate_rate_limiting)
        
        # MCP配置验证规则
        self.add_rule("mcp", self._validate_mcp_servers_config)
        self.add_rule("mcp", self._validate_mcp_parameters)
        
        # 日志配置验证规则
        self.add_rule("logging", self._validate_logging_level)
        self.add_rule("logging", self._validate_logging_file)
        
        # 缓存配置验证规则
        self.add_rule("cache", self._validate_cache_config)
        
        # 通用验证规则
        self.add_rule("general", self._validate_directories)
        self.add_rule("general", self._validate_permissions)
    
    def add_rule(self, category: str, rule_func: Callable) -> None:
        """添加验证规则"""
        if category not in self.validation_rules:
            self.validation_rules[category] = []
        self.validation_rules[category].append(rule_func)
    
    def validate_all(self) -> List[ValidationResult]:
        """验证所有配置"""
        results = []
        
        for category, rules in self.validation_rules.items():
            for rule in rules:
                try:
                    rule_results = rule()
                    if isinstance(rule_results, list):
                        results.extend(rule_results)
                    elif rule_results:
                        results.append(rule_results)
                except Exception as e:
                    logger.error(f"Error running validation rule in {category}: {e}")
                    results.append(ValidationResult(
                        f"{category}__validation_error",
                        f"Validation rule failed: {str(e)}",
                        "error"
                    ))
        
        return results
    
    def validate_category(self, category: str) -> List[ValidationResult]:
        """验证特定类别的配置"""
        results = []
        
        if category in self.validation_rules:
            for rule in self.validation_rules[category]:
                try:
                    rule_results = rule()
                    if isinstance(rule_results, list):
                        results.extend(rule_results)
                    elif rule_results:
                        results.append(rule_results)
                except Exception as e:
                    logger.error(f"Error running validation rule in {category}: {e}")
                    results.append(ValidationResult(
                        f"{category}__validation_error",
                        f"Validation rule failed: {str(e)}",
                        "error"
                    ))
        
        return results
    
    def auto_fix(self) -> Tuple[List[str], List[ValidationResult]]:
        """自动修复配置问题"""
        fixed = []
        remaining_errors = []
        
        # 验证配置
        results = self.validate_all()
        
        for result in results:
            if result.auto_fixable:
                try:
                    if self._apply_auto_fix(result):
                        fixed.append(f"Fixed: {result.message}")
                        continue
                except Exception as e:
                    logger.error(f"Error applying auto-fix for {result.key}: {e}")
            
            # 添加到剩余错误列表
            remaining_errors.append(result)
        
        return fixed, remaining_errors
    
    def _apply_auto_fix(self, result: ValidationResult) -> bool:
        """应用自动修复"""
        if not self.settings:
            return False
        
        try:
            if result.key == "logging__file":
                # 创建日志目录
                if hasattr(self.settings, 'logging') and self.settings.logging.file:
                    log_dir = os.path.dirname(self.settings.logging.file)
                    if log_dir:
                        os.makedirs(log_dir, exist_ok=True)
                        return True
            
            elif result.key == "cache__dir":
                # 创建缓存目录
                if hasattr(self.settings, 'cache') and self.settings.cache.dir:
                    os.makedirs(self.settings.cache.dir, exist_ok=True)
                    return True
            
            elif result.key == "mcp__servers_config":
                # 创建空的MCP服务器配置文件
                if hasattr(self.settings, 'mcp') and self.settings.mcp.servers_config:
                    config_path = self.settings.mcp.servers_config
                    config_dir = os.path.dirname(config_path)
                    if config_dir:
                        os.makedirs(config_dir, exist_ok=True)
                    
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump({"mcpServers": {}}, f, indent=2)
                    return True
            
            elif result.key == "vector_db__path":
                # 创建向量数据库目录
                if hasattr(self.settings, 'vector_db') and self.settings.vector_db.path:
                    os.makedirs(self.settings.vector_db.path, exist_ok=True)
                    return True
        
        except Exception as e:
            logger.error(f"Error in auto-fix for {result.key}: {e}")
        
        return False
    
    # 具体的验证规则方法
    def _validate_llm_provider(self) -> List[ValidationResult]:
        """验证LLM提供商配置"""
        results = []
        if not self.settings or not hasattr(self.settings, 'llm'):
            return results
        
        llm = self.settings.llm
        valid_providers = ["openai", "anthropic", "azure", "local"]
        
        if llm.provider not in valid_providers:
            results.append(ValidationResult(
                "llm__provider",
                f"Invalid LLM provider: {llm.provider}. Valid providers: {', '.join(valid_providers)}",
                "error"
            ))
        
        return results
    
    def _validate_llm_api_keys(self) -> List[ValidationResult]:
        """验证LLM API密钥"""
        results = []
        if not self.settings or not hasattr(self.settings, 'llm'):
            return results
        
        llm = self.settings.llm
        
        if llm.provider == "openai" and not llm.openai_api_key:
            results.append(ValidationResult(
                "llm__openai_api_key",
                "OpenAI API key is required when using OpenAI provider",
                "error"
            ))
        
        if llm.provider == "anthropic" and not llm.anthropic_api_key:
            results.append(ValidationResult(
                "llm__anthropic_api_key",
                "Anthropic API key is required when using Anthropic provider",
                "error"
            ))
        
        if llm.provider == "azure":
            if not llm.azure_openai_api_key:
                results.append(ValidationResult(
                    "llm__azure_openai_api_key",
                    "Azure OpenAI API key is required when using Azure provider",
                    "error"
                ))
            if not llm.azure_openai_endpoint:
                results.append(ValidationResult(
                    "llm__azure_openai_endpoint",
                    "Azure OpenAI endpoint is required when using Azure provider",
                    "error"
                ))
        
        return results
    
    def _validate_llm_parameters(self) -> List[ValidationResult]:
        """验证LLM参数"""
        results = []
        if not self.settings or not hasattr(self.settings, 'llm'):
            return results
        
        llm = self.settings.llm
        
        if not 0 <= llm.temperature <= 2:
            results.append(ValidationResult(
                "llm__temperature",
                f"Temperature must be between 0 and 2, got {llm.temperature}",
                "error"
            ))
        
        if llm.max_tokens <= 0:
            results.append(ValidationResult(
                "llm__max_tokens",
                f"Max tokens must be positive, got {llm.max_tokens}",
                "error"
            ))
        
        if llm.timeout <= 0:
            results.append(ValidationResult(
                "llm__timeout",
                f"Timeout must be positive, got {llm.timeout}",
                "error"
            ))
        
        return results
    
    def _validate_vector_db_type(self) -> List[ValidationResult]:
        """验证向量数据库类型"""
        results = []
        if not self.settings or not hasattr(self.settings, 'vector_db'):
            return results
        
        vector_db = self.settings.vector_db
        valid_types = ["chroma", "faiss", "milvus", "pinecone", "qdrant"]
        
        if vector_db.type not in valid_types:
            results.append(ValidationResult(
                "vector_db__type",
                f"Invalid vector database type: {vector_db.type}. Valid types: {', '.join(valid_types)}",
                "error"
            ))
        
        return results
    
    def _validate_vector_db_path(self) -> List[ValidationResult]:
        """验证向量数据库路径"""
        results = []
        if not self.settings or not hasattr(self.settings, 'vector_db'):
            return results
        
        vector_db = self.settings.vector_db
        
        if vector_db.type in ["chroma", "faiss"] and not vector_db.path:
            results.append(ValidationResult(
                "vector_db__path",
                f"Path is required for {vector_db.type} database",
                "error"
            ))
        elif vector_db.path and not os.path.exists(vector_db.path):
            results.append(ValidationResult(
                "vector_db__path",
                f"Vector database directory does not exist: {vector_db.path}",
                "warning",
                auto_fixable=True
            ))
        
        return results
    
    def _validate_embedding_config(self) -> List[ValidationResult]:
        """验证嵌入配置"""
        results = []
        if not self.settings or not hasattr(self.settings, 'vector_db'):
            return results
        
        vector_db = self.settings.vector_db
        
        if not vector_db.embedding_model:
            results.append(ValidationResult(
                "vector_db__embedding_model",
                "Embedding model is required",
                "error"
            ))
        
        valid_providers = ["openai", "huggingface", "cohere", "local"]
        if vector_db.embedding_provider not in valid_providers:
            results.append(ValidationResult(
                "vector_db__embedding_provider",
                f"Invalid embedding provider: {vector_db.embedding_provider}. Valid providers: {', '.join(valid_providers)}",
                "warning"
            ))
        
        return results
    
    def _validate_api_port(self) -> List[ValidationResult]:
        """验证API端口"""
        results = []
        if not self.settings or not hasattr(self.settings, 'api'):
            return results
        
        api = self.settings.api
        
        if not 1 <= api.port <= 65535:
            results.append(ValidationResult(
                "api__port",
                f"Port must be between 1 and 65535, got {api.port}",
                "error"
            ))
        
        if api.workers <= 0:
            results.append(ValidationResult(
                "api__workers",
                f"Workers must be positive, got {api.workers}",
                "error"
            ))
        
        return results
    
    def _validate_api_security(self) -> List[ValidationResult]:
        """验证API安全配置"""
        results = []
        if not self.settings or not hasattr(self.settings, 'api'):
            return results
        
        api = self.settings.api
        
        if api.api_key_required and not api.api_keys:
            results.append(ValidationResult(
                "api__api_keys",
                "API keys are required when api_key_required is true",
                "error"
            ))
        
        return results
    
    def _validate_rate_limiting(self) -> List[ValidationResult]:
        """验证速率限制配置"""
        results = []
        if not self.settings or not hasattr(self.settings, 'api'):
            return results
        
        api = self.settings.api
        
        if api.rate_limit_enabled and api.rate_limit_calls_per_minute <= 0:
            results.append(ValidationResult(
                "api__rate_limit_calls_per_minute",
                f"Rate limit calls per minute must be positive, got {api.rate_limit_calls_per_minute}",
                "error"
            ))
        
        return results
    
    def _validate_mcp_servers_config(self) -> List[ValidationResult]:
        """验证MCP服务器配置"""
        results = []
        if not self.settings or not hasattr(self.settings, 'mcp'):
            return results
        
        mcp = self.settings.mcp
        
        if not os.path.exists(mcp.servers_config):
            results.append(ValidationResult(
                "mcp__servers_config",
                f"MCP servers config file not found: {mcp.servers_config}",
                "warning",
                auto_fixable=True
            ))
        
        return results
    
    def _validate_mcp_parameters(self) -> List[ValidationResult]:
        """验证MCP参数"""
        results = []
        if not self.settings or not hasattr(self.settings, 'mcp'):
            return results
        
        mcp = self.settings.mcp
        
        if mcp.timeout <= 0:
            results.append(ValidationResult(
                "mcp__timeout",
                f"Timeout must be positive, got {mcp.timeout}",
                "error"
            ))
        
        if mcp.max_retries < 0:
            results.append(ValidationResult(
                "mcp__max_retries",
                f"Max retries must be non-negative, got {mcp.max_retries}",
                "error"
            ))
        
        return results
    
    def _validate_logging_level(self) -> List[ValidationResult]:
        """验证日志级别"""
        results = []
        if not self.settings or not hasattr(self.settings, 'logging'):
            return results
        
        logging_config = self.settings.logging
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        if logging_config.level.upper() not in valid_levels:
            results.append(ValidationResult(
                "logging__level",
                f"Invalid log level: {logging_config.level}. Valid levels: {', '.join(valid_levels)}",
                "warning"
            ))
        
        return results
    
    def _validate_logging_file(self) -> List[ValidationResult]:
        """验证日志文件配置"""
        results = []
        if not self.settings or not hasattr(self.settings, 'logging'):
            return results
        
        logging_config = self.settings.logging
        
        if logging_config.file:
            log_dir = os.path.dirname(logging_config.file)
            if log_dir and not os.path.exists(log_dir):
                results.append(ValidationResult(
                    "logging__file",
                    f"Log directory does not exist: {log_dir}",
                    "warning",
                    auto_fixable=True
                ))
        
        return results
    
    def _validate_cache_config(self) -> List[ValidationResult]:
        """验证缓存配置"""
        results = []
        if not self.settings or not hasattr(self.settings, 'cache'):
            return results
        
        cache = self.settings.cache
        
        if cache.ttl <= 0:
            results.append(ValidationResult(
                "cache__ttl",
                f"Cache TTL must be positive, got {cache.ttl}",
                "error"
            ))
        
        if cache.redis_url and not cache.redis_url.startswith("redis://"):
            results.append(ValidationResult(
                "cache__redis_url",
                f"Invalid Redis URL: {cache.redis_url}. Must start with 'redis://'",
                "error"
            ))
        
        if cache.enabled and not cache.redis_url and not os.path.exists(cache.dir):
            results.append(ValidationResult(
                "cache__dir",
                f"Cache directory does not exist: {cache.dir}",
                "warning",
                auto_fixable=True
            ))
        
        return results
    
    def _validate_directories(self) -> List[ValidationResult]:
        """验证目录配置"""
        results = []
        if not self.settings:
            return results
        
        # 检查各种目录是否存在
        directories_to_check = []
        
        if hasattr(self.settings, 'vector_db') and self.settings.vector_db.path:
            directories_to_check.append(("vector_db__path", self.settings.vector_db.path))
        
        if hasattr(self.settings, 'cache') and self.settings.cache.dir:
            directories_to_check.append(("cache__dir", self.settings.cache.dir))
        
        for key, directory in directories_to_check:
            if not os.path.exists(directory):
                results.append(ValidationResult(
                    key,
                    f"Directory does not exist: {directory}",
                    "warning",
                    auto_fixable=True
                ))
        
        return results
    
    def _validate_permissions(self) -> List[ValidationResult]:
        """验证文件权限"""
        results = []
        if not self.settings:
            return results
        
        # 检查关键文件和目录的权限
        files_to_check = []
        
        if hasattr(self.settings, 'logging') and self.settings.logging.file:
            log_dir = os.path.dirname(self.settings.logging.file)
            if log_dir and os.path.exists(log_dir):
                files_to_check.append(("logging__file_dir", log_dir))
        
        if hasattr(self.settings, 'mcp') and os.path.exists(self.settings.mcp.servers_config):
            files_to_check.append(("mcp__servers_config", self.settings.mcp.servers_config))
        
        for key, file_path in files_to_check:
            if not os.access(file_path, os.R_OK):
                results.append(ValidationResult(
                    f"{key}__read_permission",
                    f"No read permission for: {file_path}",
                    "error"
                ))
            
            if not os.access(file_path, os.W_OK):
                results.append(ValidationResult(
                    f"{key}__write_permission",
                    f"No write permission for: {file_path}",
                    "warning"
                ))
        
        return results


def validate_config(settings: Optional[Any] = None) -> List[ValidationResult]:
    """验证配置的便捷函数"""
    validator = ConfigValidator(settings)
    return validator.validate_all()


def auto_fix_config(settings: Optional[Any] = None) -> Tuple[List[str], List[ValidationResult]]:
    """自动修复配置的便捷函数"""
    validator = ConfigValidator(settings)
    return validator.auto_fix()