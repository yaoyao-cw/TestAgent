#!/usr/bin/env python3
"""
环境变量管理器

提供环境变量的统一管理和验证
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union, get_type_hints

# 配置日志记录器
logger = logging.getLogger("env_manager")


class EnvVarError(Exception):
    """环境变量错误"""

    pass


class EnvManager:
    """环境变量管理器"""

    def __init__(self, env_file: Optional[str] = None):
        self.env_file = env_file
        self.loaded_vars: Dict[str, str] = {}
        self._load_env_file()

    def _load_env_file(self) -> None:
        """加载.env文件"""
        if self.env_file and os.path.exists(self.env_file):
            try:
                with open(self.env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            self.loaded_vars[key] = value
                            # 设置到环境变量中（如果不存在）
                            if key not in os.environ:
                                os.environ[key] = value
                logger.info(
                    f"Loaded {len(self.loaded_vars)} variables from {self.env_file}"
                )
            except Exception as e:
                logger.error(f"Error loading env file {self.env_file}: {e}")

    def get(
        self,
        key: str,
        default: Any = None,
        required: bool = False,
        var_type: Type = str,
    ) -> Any:
        """获取环境变量值"""
        # 首先从系统环境变量获取
        value = os.environ.get(key)

        # 如果系统环境变量中没有，从加载的文件中获取
        if value is None:
            value = self.loaded_vars.get(key)

        # 如果仍然没有值
        if value is None:
            if required:
                raise EnvVarError(f"Required environment variable '{key}' is not set")
            return default

        # 类型转换
        try:
            if var_type == bool:
                return value.lower() in ("true", "1", "yes", "on")
            elif var_type == int:
                return int(value)
            elif var_type == float:
                return float(value)
            elif var_type == list:
                # 支持逗号分隔的列表
                return [item.strip() for item in value.split(",") if item.strip()]
            else:
                return var_type(value)
        except (ValueError, TypeError) as e:
            logger.error(
                f"Error converting env var '{key}' to {var_type.__name__}: {e}"
            )
            if required:
                raise EnvVarError(
                    f"Invalid value for required environment variable '{key}': {value}"
                )
            return default

    def set(self, key: str, value: Any, persist: bool = False) -> None:
        """设置环境变量"""
        str_value = str(value)
        os.environ[key] = str_value
        self.loaded_vars[key] = str_value

        if persist and self.env_file:
            self._persist_to_file(key, str_value)

    def _persist_to_file(self, key: str, value: str) -> None:
        """持久化环境变量到文件"""
        try:
            # 读取现有内容
            lines = []
            if os.path.exists(self.env_file):
                with open(self.env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            # 查找并更新现有键，或添加新键
            key_found = False
            for i, line in enumerate(lines):
                if line.strip() and not line.strip().startswith("#") and "=" in line:
                    existing_key = line.split("=", 1)[0].strip()
                    if existing_key == key:
                        lines[i] = f"{key}={value}\n"
                        key_found = True
                        break

            if not key_found:
                lines.append(f"{key}={value}\n")

            # 写回文件
            os.makedirs(os.path.dirname(self.env_file), exist_ok=True)
            with open(self.env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

            logger.info(f"Persisted environment variable '{key}' to {self.env_file}")
        except Exception as e:
            logger.error(f"Error persisting env var '{key}' to file: {e}")

    def delete(self, key: str, persist: bool = False) -> bool:
        """删除环境变量"""
        removed = False

        # 从系统环境变量中删除
        if key in os.environ:
            del os.environ[key]
            removed = True

        # 从加载的变量中删除
        if key in self.loaded_vars:
            del self.loaded_vars[key]
            removed = True

        # 从文件中删除
        if persist and self.env_file and os.path.exists(self.env_file):
            try:
                with open(self.env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                # 过滤掉要删除的键
                new_lines = []
                for line in lines:
                    if (
                        line.strip()
                        and not line.strip().startswith("#")
                        and "=" in line
                    ):
                        existing_key = line.split("=", 1)[0].strip()
                        if existing_key != key:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

                # 写回文件
                with open(self.env_file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

                logger.info(
                    f"Removed environment variable '{key}' from {self.env_file}"
                )
            except Exception as e:
                logger.error(f"Error removing env var '{key}' from file: {e}")

        return removed

    def list_vars(self, prefix: Optional[str] = None) -> Dict[str, str]:
        """列出环境变量"""
        all_vars = {**self.loaded_vars, **dict(os.environ)}

        if prefix:
            return {k: v for k, v in all_vars.items() if k.startswith(prefix)}

        return all_vars

    def validate_required_vars(self, required_vars: List[str]) -> List[str]:
        """验证必需的环境变量"""
        missing_vars = []

        for var in required_vars:
            if not self.get(var):
                missing_vars.append(var)

        return missing_vars

    def export_to_dict(self) -> Dict[str, str]:
        """导出所有环境变量为字典"""
        return {**self.loaded_vars, **dict(os.environ)}

    def import_from_dict(self, env_dict: Dict[str, Any], persist: bool = False) -> None:
        """从字典导入环境变量"""
        for key, value in env_dict.items():
            self.set(key, value, persist=persist)

    def backup_to_file(self, backup_file: str) -> bool:
        """备份环境变量到文件"""
        try:
            env_dict = self.export_to_dict()

            # 确保目录存在
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)

            with open(backup_file, "w", encoding="utf-8") as f:
                for key, value in sorted(env_dict.items()):
                    f.write(f"{key}={value}\n")

            logger.info(
                f"Backed up {len(env_dict)} environment variables to {backup_file}"
            )
            return True
        except Exception as e:
            logger.error(f"Error backing up environment variables: {e}")
            return False

    def restore_from_file(self, backup_file: str) -> bool:
        """从备份文件恢复环境变量"""
        try:
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False

            with open(backup_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        self.set(key.strip(), value.strip())

            logger.info(f"Restored environment variables from {backup_file}")
            return True
        except Exception as e:
            logger.error(f"Error restoring environment variables: {e}")
            return False


class ConfigFromEnv:
    """从环境变量自动配置类"""

    def __init__(self, env_manager: Optional[EnvManager] = None, prefix: str = ""):
        self.env_manager = env_manager or get_env_manager()
        self.prefix = prefix
        self._load_from_env()

    def _load_from_env(self) -> None:
        """从环境变量加载配置"""
        # 获取类的类型注解
        type_hints = get_type_hints(self.__class__)

        for attr_name, attr_type in type_hints.items():
            if attr_name.startswith("_"):
                continue

            # 构造环境变量名
            env_key = (
                f"{self.prefix}{attr_name.upper()}"
                if self.prefix
                else attr_name.upper()
            )

            # 获取默认值
            default_value = getattr(self, attr_name, None)

            # 从环境变量获取值
            env_value = self.env_manager.get(
                env_key, default=default_value, var_type=attr_type
            )

            # 设置属性值
            setattr(self, attr_name, env_value)


# 全局环境变量管理器实例
_env_manager: Optional[EnvManager] = None


def get_env_manager(env_file: Optional[str] = None) -> EnvManager:
    """获取环境变量管理器单例"""
    global _env_manager
    if _env_manager is None:
        # 默认查找.env文件
        if env_file is None:
            project_root = Path(__file__).parent.parent.parent
            env_file = str(project_root / ".env")
        _env_manager = EnvManager(env_file)
    return _env_manager


def reload_env_manager(env_file: Optional[str] = None) -> EnvManager:
    """重新加载环境变量管理器"""
    global _env_manager
    _env_manager = None
    return get_env_manager(env_file)


# 便捷函数
def get_env(
    key: str, default: Any = None, required: bool = False, var_type: Type = str
) -> Any:
    """获取环境变量值的便捷函数"""
    return get_env_manager().get(key, default, required, var_type)


def set_env(key: str, value: Any, persist: bool = False) -> None:
    """设置环境变量的便捷函数"""
    get_env_manager().set(key, value, persist)


def delete_env(key: str, persist: bool = False) -> bool:
    """删除环境变量的便捷函数"""
    return get_env_manager().delete(key, persist)
