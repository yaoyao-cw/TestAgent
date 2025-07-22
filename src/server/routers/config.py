#!/usr/bin/env python3
"""
配置管理API路由
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field

try:
    from ...config.settings import get_settings, reload_settings
    from ...config.manager import get_config_manager
    from ...config.env_manager import get_env_manager
    from ...config.validator import validate_config, auto_fix_config
    from ...config.logging_config import get_logger
except ImportError as e:
    # 如果导入失败，提供模拟实现
    def get_settings():
        return {}
    def reload_settings():
        return {}
    def get_config_manager():
        return None
    def get_env_manager():
        return None
    def validate_config(config):
        return []
    def auto_fix_config(config):
        return [], []
    def get_logger(name):
        import logging
        return logging.getLogger(name)

logger = get_logger("config_api")

router = APIRouter()


# 请求和响应模型
class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    key: str = Field(..., description="配置键")
    value: Any = Field(..., description="配置值")
    persist: bool = Field(False, description="是否持久化")


class ConfigValidationResponse(BaseModel):
    """配置验证响应"""
    is_valid: bool = Field(..., description="是否有效")
    errors: List[Dict[str, Any]] = Field(..., description="错误列表")
    warnings: List[Dict[str, Any]] = Field(..., description="警告列表")


class EnvironmentVariableRequest(BaseModel):
    """环境变量请求"""
    key: str = Field(..., description="环境变量名")
    value: str = Field(..., description="环境变量值")
    persist: bool = Field(False, description="是否持久化")


class ConfigExportResponse(BaseModel):
    """配置导出响应"""
    config_data: str = Field(..., description="配置数据")
    format: str = Field(..., description="导出格式")
    timestamp: str = Field(..., description="导出时间")


class ConfigImportRequest(BaseModel):
    """配置导入请求"""
    config_data: str = Field(..., description="配置数据")
    format: str = Field("yaml", description="配置格式")
    persist: bool = Field(False, description="是否持久化")


# 依赖注入
def get_config_manager_dep():
    """获取配置管理器依赖"""
    return get_config_manager()


def get_env_manager_dep():
    """获取环境变量管理器依赖"""
    return get_env_manager()


@router.get("/settings")
async def get_current_settings():
    """获取当前配置设置"""
    try:
        settings = get_settings()
        if hasattr(settings, 'model_dump'):
            return settings.model_dump()
        elif hasattr(settings, 'dict'):
            return settings.dict()
        else:
            return {}
    except Exception as e:
        logger.error(f"获取配置设置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取配置设置失败: {str(e)}"
        )


@router.get("/settings/{config_key}")
async def get_config_value(
    config_key: str,
    config_manager = Depends(get_config_manager_dep)
):
    """获取特定配置值"""
    try:
        if not config_manager:
            raise HTTPException(status_code=503, detail="配置管理器不可用")
        
        config_value = config_manager.get_value(config_key)
        
        return {
            "key": config_key,
            "value": config_value,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取配置值失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取配置值失败: {str(e)}"
        )


@router.post("/settings")
async def update_config_value(
    request: ConfigUpdateRequest,
    config_manager = Depends(get_config_manager_dep)
):
    """更新配置值"""
    try:
        if not config_manager:
            raise HTTPException(status_code=503, detail="配置管理器不可用")
        
        # 更新配置
        success = config_manager.set_value(request.key, request.value, persist=request.persist)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"无法更新配置键: {request.key}"
            )
        
        logger.info(f"配置已更新: {request.key}")
        
        return {
            "success": True,
            "message": "配置更新成功",
            "key": request.key,
            "value": request.value,
            "persisted": request.persist,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"更新配置失败: {str(e)}"
        )


@router.post("/settings/validate")
async def validate_current_config():
    """验证当前配置"""
    try:
        settings = get_settings()
        validation_results = validate_config(settings)
        
        errors = [result.to_dict() for result in validation_results if result.severity == "error"]
        warnings = [result.to_dict() for result in validation_results if result.severity == "warning"]
        
        return ConfigValidationResponse(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
        
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"配置验证失败: {str(e)}"
        )


@router.post("/settings/auto-fix")
async def auto_fix_configuration():
    """自动修复配置问题"""
    try:
        settings = get_settings()
        fixed_issues, remaining_errors = auto_fix_config(settings)
        
        return {
            "success": True,
            "message": "自动修复完成",
            "fixed_issues": fixed_issues,
            "remaining_errors": [error.to_dict() for error in remaining_errors],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"自动修复配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"自动修复配置失败: {str(e)}"
        )


@router.post("/settings/reload")
async def reload_configuration():
    """重新加载配置"""
    try:
        settings = reload_settings()
        
        logger.info("配置已重新加载")
        
        return {
            "success": True,
            "message": "配置重新加载成功",
            "timestamp": datetime.now().isoformat(),
            "version": settings.version
        }
        
    except Exception as e:
        logger.error(f"重新加载配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"重新加载配置失败: {str(e)}"
        )


@router.get("/settings/export")
async def export_configuration(
    format: str = "yaml",
    config_manager = Depends(get_config_manager_dep)
):
    """导出配置"""
    try:
        if not config_manager:
            raise HTTPException(status_code=503, detail="配置管理器不可用")
        
        config_data = config_manager.export_config(format=format)
        
        return ConfigExportResponse(
            config_data=config_data,
            format=format,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"导出配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"导出配置失败: {str(e)}"
        )


@router.post("/settings/import")
async def import_configuration(
    request: ConfigImportRequest,
    config_manager = Depends(get_config_manager_dep)
):
    """导入配置"""
    try:
        if not config_manager:
            raise HTTPException(status_code=503, detail="配置管理器不可用")
        
        success = config_manager.import_config(
            request.config_data, 
            format=request.format, 
            persist=request.persist
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="配置导入失败"
            )
        
        logger.info("配置已导入")
        
        return {
            "success": True,
            "message": "配置导入成功",
            "format": request.format,
            "persisted": request.persist,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导入配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"导入配置失败: {str(e)}"
        )


@router.get("/environment")
async def get_environment_variables(
    prefix: Optional[str] = None,
    env_manager = Depends(get_env_manager_dep)
):
    """获取环境变量"""
    try:
        if not env_manager:
            raise HTTPException(status_code=503, detail="环境变量管理器不可用")
        
        env_vars = env_manager.list_vars(prefix=prefix)
        
        # 屏蔽敏感信息
        sensitive_keys = ["api_key", "password", "secret", "token"]
        masked_vars = {}
        for key, value in env_vars.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                masked_vars[key] = "***"
            else:
                masked_vars[key] = value
        
        return {
            "environment_variables": masked_vars,
            "count": len(masked_vars),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取环境变量失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取环境变量失败: {str(e)}"
        )


@router.post("/environment")
async def set_environment_variable(
    request: EnvironmentVariableRequest,
    env_manager = Depends(get_env_manager_dep)
):
    """设置环境变量"""
    try:
        if not env_manager:
            raise HTTPException(status_code=503, detail="环境变量管理器不可用")
        
        env_manager.set(request.key, request.value, persist=request.persist)
        
        logger.info(f"环境变量已设置: {request.key}")
        
        return {
            "success": True,
            "message": "环境变量设置成功",
            "key": request.key,
            "persisted": request.persist,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"设置环境变量失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"设置环境变量失败: {str(e)}"
        )


@router.delete("/environment/{key}")
async def delete_environment_variable(
    key: str,
    persist: bool = False,
    env_manager = Depends(get_env_manager_dep)
):
    """删除环境变量"""
    try:
        if not env_manager:
            raise HTTPException(status_code=503, detail="环境变量管理器不可用")
        
        success = env_manager.delete(key, persist=persist)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"环境变量不存在: {key}"
            )
        
        logger.info(f"环境变量已删除: {key}")
        
        return {
            "success": True,
            "message": "环境变量删除成功",
            "key": key,
            "persisted": persist,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除环境变量失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"删除环境变量失败: {str(e)}"
        )


@router.post("/environment/backup")
async def backup_environment_variables(
    backup_file: Optional[str] = None,
    env_manager = Depends(get_env_manager_dep)
):
    """备份环境变量"""
    try:
        if not env_manager:
            raise HTTPException(status_code=503, detail="环境变量管理器不可用")
        
        if not backup_file:
            backup_file = f"./backups/env_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.env"
        
        success = env_manager.backup_to_file(backup_file)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="备份失败"
            )
        
        return {
            "success": True,
            "message": "环境变量备份成功",
            "backup_path": backup_file,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"备份环境变量失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"备份环境变量失败: {str(e)}"
        )


@router.post("/environment/restore")
async def restore_environment_variables(
    backup_file: str = Body(..., embed=True),
    env_manager = Depends(get_env_manager_dep)
):
    """恢复环境变量"""
    try:
        if not env_manager:
            raise HTTPException(status_code=503, detail="环境变量管理器不可用")
        
        success = env_manager.restore_from_file(backup_file)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="恢复失败"
            )
        
        return {
            "success": True,
            "message": "环境变量恢复成功",
            "backup_file": backup_file,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复环境变量失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"恢复环境变量失败: {str(e)}"
        )


@router.get("/schema")
async def get_configuration_schema():
    """获取配置模式"""
    try:
        settings = get_settings()
        
        if hasattr(settings, 'model_json_schema'):
            schema = settings.model_json_schema()
        elif hasattr(settings, 'schema'):
            schema = settings.schema()
        else:
            schema = {"type": "object", "properties": {}}
        
        return {
            "schema": schema,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取配置模式失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取配置模式失败: {str(e)}"
        )