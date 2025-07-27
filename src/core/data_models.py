"""核心数据模型和类型定义

实现跨平台兼容的基础数据模型和类型定义，考虑平台差异。
"""

import os
import platform
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class PlatformType(Enum):
    """平台类型枚举"""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


class SystemInfo(BaseModel):
    """系统信息模型"""

    platform: PlatformType = Field(..., description="操作系统平台")
    python_version: str = Field(..., description="Python版本")
    architecture: str = Field(..., description="系统架构")
    hostname: str = Field(..., description="主机名")
    working_directory: str = Field(..., description="工作目录")

    @classmethod
    def get_current_system_info(cls) -> "SystemInfo":
        """获取当前系统信息"""
        system = platform.system().lower()

        if system == "windows":
            platform_type = PlatformType.WINDOWS
        elif system == "linux":
            platform_type = PlatformType.LINUX
        elif system == "darwin":
            platform_type = PlatformType.MACOS
        else:
            platform_type = PlatformType.UNKNOWN

        return cls(
            platform=platform_type,
            python_version=platform.python_version(),
            architecture=platform.machine(),
            hostname=platform.node(),
            working_directory=str(Path.cwd()),
        )


class PathConfig(BaseModel):
    """路径配置模型"""

    base_path: str = Field(..., description="基础路径")
    data_path: str = Field(..., description="数据路径")
    logs_path: str = Field(..., description="日志路径")
    temp_path: str = Field(..., description="临时文件路径")
    config_path: str = Field(..., description="配置文件路径")

    @validator("base_path", "data_path", "logs_path", "temp_path", "config_path")
    def normalize_path(cls, v):
        """标准化路径格式"""
        return str(Path(v).resolve())

    @classmethod
    def create_default_config(cls, base_dir: Optional[str] = None) -> "PathConfig":
        """创建默认路径配置"""
        if base_dir is None:
            base_dir = Path.cwd()
        else:
            base_dir = Path(base_dir)

        return cls(
            base_path=str(base_dir),
            data_path=str(base_dir / "data"),
            logs_path=str(base_dir / "logs"),
            temp_path=str(base_dir / "temp"),
            config_path=str(base_dir / "config"),
        )

    def ensure_directories(self):
        """确保所有目录存在"""
        for path_name in ["data_path", "logs_path", "temp_path", "config_path"]:
            path = Path(getattr(self, path_name))
            path.mkdir(parents=True, exist_ok=True)


class EnvironmentConfig(BaseModel):
    """环境配置模型"""

    environment: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")
    max_workers: int = Field(default=4, description="最大工作线程数")
    timeout: int = Field(default=300, description="超时时间（秒）")

    @validator("log_level")
    def validate_log_level(cls, v):
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"日志级别必须是: {', '.join(valid_levels)}")
        return v.upper()

    @validator("max_workers")
    def validate_max_workers(cls, v):
        """验证最大工作线程数"""
        if v < 1:
            raise ValueError("最大工作线程数必须大于0")
        return v


class DatabaseConfig(BaseModel):
    """数据库配置模型"""

    vector_db_url: str = Field(
        default="http://localhost:8001", description="向量数据库URL"
    )
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")
    collection_name: str = Field(default="testagent_documents", description="集合名称")

    @validator("vector_db_url", "redis_url")
    def validate_url(cls, v):
        """验证URL格式"""
        if not v.startswith(("http://", "https://", "redis://")):
            raise ValueError("URL格式不正确")
        return v


class LLMConfig(BaseModel):
    """LLM配置模型"""

    provider: str = Field(default="openai", description="LLM提供商")
    model: str = Field(default="gpt-3.5-turbo", description="模型名称")
    api_key: Optional[str] = Field(None, description="API密钥")
    base_url: Optional[str] = Field(None, description="基础URL")
    max_tokens: int = Field(default=2048, description="最大令牌数")
    temperature: float = Field(default=0.7, description="温度参数")

    @validator("temperature")
    def validate_temperature(cls, v):
        """验证温度参数"""
        if not 0 <= v <= 2:
            raise ValueError("温度参数必须在0-2之间")
        return v

    @validator("max_tokens")
    def validate_max_tokens(cls, v):
        """验证最大令牌数"""
        if v < 1:
            raise ValueError("最大令牌数必须大于0")
        return v


class ApplicationConfig(BaseModel):
    """应用程序配置模型"""

    system_info: SystemInfo = Field(..., description="系统信息")
    path_config: PathConfig = Field(..., description="路径配置")
    environment_config: EnvironmentConfig = Field(..., description="环境配置")
    database_config: DatabaseConfig = Field(..., description="数据库配置")
    llm_config: LLMConfig = Field(..., description="LLM配置")

    @classmethod
    def create_default_config(cls) -> "ApplicationConfig":
        """创建默认配置"""
        system_info = SystemInfo.get_current_system_info()
        path_config = PathConfig.create_default_config()

        return cls(
            system_info=system_info,
            path_config=path_config,
            environment_config=EnvironmentConfig(),
            database_config=DatabaseConfig(),
            llm_config=LLMConfig(),
        )

    def initialize(self):
        """初始化配置"""
        # 确保目录存在
        self.path_config.ensure_directories()

        # 设置环境变量
        os.environ["TESTAGENT_ENV"] = self.environment_config.environment
        os.environ["TESTAGENT_DEBUG"] = str(self.environment_config.debug)
        os.environ["TESTAGENT_LOG_LEVEL"] = self.environment_config.log_level

    def is_windows(self) -> bool:
        """检查是否为Windows平台"""
        return self.system_info.platform == PlatformType.WINDOWS

    def is_linux(self) -> bool:
        """检查是否为Linux平台"""
        return self.system_info.platform == PlatformType.LINUX

    def is_macos(self) -> bool:
        """检查是否为macOS平台"""
        return self.system_info.platform == PlatformType.MACOS

    def get_platform_specific_config(self) -> Dict[str, Any]:
        """获取平台特定配置"""
        if self.is_windows():
            return {
                "shell": "cmd",
                "path_separator": "\\",
                "line_ending": "\r\n",
                "executable_extension": ".exe",
            }
        else:
            return {
                "shell": "bash",
                "path_separator": "/",
                "line_ending": "\n",
                "executable_extension": "",
            }


class APIResponse(BaseModel):
    """API响应基础模型"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: str = Field(..., description="时间戳")

    @classmethod
    def success_response(
        cls, message: str, data: Optional[Dict[str, Any]] = None
    ) -> "APIResponse":
        """创建成功响应"""
        from datetime import datetime

        return cls(
            success=True,
            message=message,
            data=data,
            timestamp=datetime.now().isoformat(),
        )

    @classmethod
    def error_response(cls, message: str, error: Optional[str] = None) -> "APIResponse":
        """创建错误响应"""
        from datetime import datetime

        return cls(
            success=False,
            message=message,
            error=error,
            timestamp=datetime.now().isoformat(),
        )


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""

    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
    uptime: float = Field(..., description="运行时间（秒）")
    system_info: SystemInfo = Field(..., description="系统信息")
    dependencies: Dict[str, str] = Field(..., description="依赖服务状态")


# 全局配置实例
_global_config: Optional[ApplicationConfig] = None


def get_global_config() -> ApplicationConfig:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = ApplicationConfig.create_default_config()
        _global_config.initialize()
    return _global_config


def set_global_config(config: ApplicationConfig):
    """设置全局配置实例"""
    global _global_config
    _global_config = config
    _global_config.initialize()


# 平台兼容性工具函数
def get_platform_path_separator() -> str:
    """获取平台路径分隔符"""
    config = get_global_config()
    return config.get_platform_specific_config()["path_separator"]


def get_platform_line_ending() -> str:
    """获取平台行结束符"""
    config = get_global_config()
    return config.get_platform_specific_config()["line_ending"]


def normalize_path_for_platform(path: str) -> str:
    """为当前平台标准化路径"""
    return str(Path(path).resolve())


def is_executable_file(file_path: str) -> bool:
    """检查文件是否为可执行文件"""
    path = Path(file_path)
    if not path.exists():
        return False

    config = get_global_config()
    if config.is_windows():
        # Windows下检查文件扩展名
        executable_extensions = [".exe", ".bat", ".cmd", ".com"]
        return path.suffix.lower() in executable_extensions
    else:
        # Unix-like系统检查执行权限
        return os.access(path, os.X_OK)


def create_cross_platform_command(command: str, args: List[str] = None) -> List[str]:
    """创建跨平台命令"""
    config = get_global_config()
    args = args or []

    if config.is_windows():
        # Windows下使用cmd执行
        return ["cmd", "/c", command] + args
    else:
        # Unix-like系统直接执行
        return [command] + args
