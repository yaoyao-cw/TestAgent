"""工具装饰器模块"""

import functools
import asyncio
import time
from typing import Any, Callable, Dict, Optional, Union
import inspect
from dataclasses import dataclass, field
from datetime import datetime

from ..config.logging_config import get_logger
from ..exceptions import ToolException
from ..utils.performance import async_monitor_performance

logger = get_logger("tool_decorators")


@dataclass
class ToolMetrics:
    """工具执行指标"""
    name: str
    call_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    success_count: int = 0
    error_count: int = 0
    last_called: Optional[datetime] = None
    errors: list = field(default_factory=list)


class ToolRegistry:
    """工具注册表，管理所有工具的元数据和指标"""
    
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.metrics: Dict[str, ToolMetrics] = {}
        self._lock = asyncio.Lock()
    
    def register_tool(
        self, 
        name: str, 
        func: Callable, 
        description: str = "",
        category: str = "general",
        tags: list = None
    ):
        """注册工具"""
        self.tools[name] = {
            "function": func,
            "description": description,
            "category": category,
            "tags": tags or [],
            "signature": str(inspect.signature(func)),
            "is_async": asyncio.iscoroutinefunction(func),
            "registered_at": datetime.now()
        }
        
        self.metrics[name] = ToolMetrics(name=name)
        logger.info(f"Registered tool: {name}")
    
    async def update_metrics(
        self, 
        name: str, 
        execution_time: float, 
        success: bool, 
        error: Optional[str] = None
    ):
        """更新工具执行指标"""
        async with self._lock:
            if name not in self.metrics:
                self.metrics[name] = ToolMetrics(name=name)
            
            metrics = self.metrics[name]
            metrics.call_count += 1
            metrics.total_time += execution_time
            metrics.avg_time = metrics.total_time / metrics.call_count
            metrics.min_time = min(metrics.min_time, execution_time)
            metrics.max_time = max(metrics.max_time, execution_time)
            metrics.last_called = datetime.now()
            
            if success:
                metrics.success_count += 1
            else:
                metrics.error_count += 1
                if error:
                    metrics.errors.append({
                        "error": error,
                        "timestamp": datetime.now()
                    })
                    # 只保留最近的10个错误
                    if len(metrics.errors) > 10:
                        metrics.errors = metrics.errors[-10:]
    
    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        if name in self.tools:
            tool_info = self.tools[name].copy()
            if name in self.metrics:
                tool_info["metrics"] = self.metrics[name]
            return tool_info
        return None
    
    def list_tools(self, category: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """列出所有工具"""
        if category:
            return {
                name: info for name, info in self.tools.items() 
                if info["category"] == category
            }
        return self.tools.copy()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        total_calls = sum(m.call_count for m in self.metrics.values())
        total_errors = sum(m.error_count for m in self.metrics.values())
        
        return {
            "total_tools": len(self.tools),
            "total_calls": total_calls,
            "total_errors": total_errors,
            "success_rate": (total_calls - total_errors) / total_calls if total_calls > 0 else 0,
            "tools_by_category": self._get_tools_by_category(),
            "most_used_tools": self._get_most_used_tools(),
            "slowest_tools": self._get_slowest_tools()
        }
    
    def _get_tools_by_category(self) -> Dict[str, int]:
        """按类别统计工具数量"""
        categories = {}
        for tool_info in self.tools.values():
            category = tool_info["category"]
            categories[category] = categories.get(category, 0) + 1
        return categories
    
    def _get_most_used_tools(self, limit: int = 5) -> list:
        """获取使用最多的工具"""
        sorted_metrics = sorted(
            self.metrics.values(), 
            key=lambda m: m.call_count, 
            reverse=True
        )
        return [
            {"name": m.name, "call_count": m.call_count} 
            for m in sorted_metrics[:limit]
        ]
    
    def _get_slowest_tools(self, limit: int = 5) -> list:
        """获取最慢的工具"""
        sorted_metrics = sorted(
            self.metrics.values(), 
            key=lambda m: m.avg_time, 
            reverse=True
        )
        return [
            {"name": m.name, "avg_time": m.avg_time} 
            for m in sorted_metrics[:limit] if m.call_count > 0
        ]


# 全局工具注册表
tool_registry = ToolRegistry()


def tool(
    name: Optional[str] = None,
    description: str = "",
    category: str = "general",
    tags: Optional[list] = None,
    timeout: Optional[float] = None,
    retry_count: int = 0,
    cache_ttl: Optional[int] = None
):
    """工具装饰器
    
    Args:
        name: 工具名称
        description: 工具描述
        category: 工具类别
        tags: 工具标签
        timeout: 超时时间（秒）
        retry_count: 重试次数
        cache_ttl: 缓存TTL（秒）
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        
        # 注册工具
        tool_registry.register_tool(
            name=tool_name,
            func=func,
            description=description,
            category=category,
            tags=tags
        )
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error_msg = None
                
                try:
                    # 应用超时
                    if timeout:
                        result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                    else:
                        result = await func(*args, **kwargs)
                    
                    return result
                    
                except asyncio.TimeoutError:
                    success = False
                    error_msg = f"Tool '{tool_name}' timed out after {timeout} seconds"
                    logger.error(error_msg)
                    raise ToolException(error_msg)
                    
                except Exception as e:
                    success = False
                    error_msg = str(e)
                    logger.error(f"Tool '{tool_name}' failed: {error_msg}")
                    
                    # 重试逻辑
                    if retry_count > 0:
                        for attempt in range(retry_count):
                            try:
                                logger.info(f"Retrying tool '{tool_name}', attempt {attempt + 1}/{retry_count}")
                                await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
                                
                                if timeout:
                                    result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                                else:
                                    result = await func(*args, **kwargs)
                                
                                success = True
                                error_msg = None
                                return result
                                
                            except Exception as retry_e:
                                error_msg = str(retry_e)
                                if attempt == retry_count - 1:  # 最后一次重试
                                    logger.error(f"Tool '{tool_name}' failed after {retry_count} retries: {error_msg}")
                                    raise ToolException(error_msg)
                    else:
                        raise ToolException(error_msg)
                        
                finally:
                    execution_time = time.time() - start_time
                    await tool_registry.update_metrics(tool_name, execution_time, success, error_msg)
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error_msg = None
                
                try:
                    result = func(*args, **kwargs)
                    return result
                    
                except Exception as e:
                    success = False
                    error_msg = str(e)
                    logger.error(f"Tool '{tool_name}' failed: {error_msg}")
                    
                    # 重试逻辑
                    if retry_count > 0:
                        for attempt in range(retry_count):
                            try:
                                logger.info(f"Retrying tool '{tool_name}', attempt {attempt + 1}/{retry_count}")
                                time.sleep(0.5 * (attempt + 1))  # 指数退避
                                
                                result = func(*args, **kwargs)
                                success = True
                                error_msg = None
                                return result
                                
                            except Exception as retry_e:
                                error_msg = str(retry_e)
                                if attempt == retry_count - 1:  # 最后一次重试
                                    logger.error(f"Tool '{tool_name}' failed after {retry_count} retries: {error_msg}")
                                    raise ToolException(error_msg)
                    else:
                        raise ToolException(error_msg)
                        
                finally:
                    execution_time = time.time() - start_time
                    # 对于同步函数，需要在事件循环中更新指标
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(
                            tool_registry.update_metrics(tool_name, execution_time, success, error_msg)
                        )
                    except RuntimeError:
                        # 如果没有事件循环，跳过指标更新
                        pass
            
            return sync_wrapper
    
    return decorator


def rate_limit(calls_per_minute: int = 60):
    """速率限制装饰器
    
    Args:
        calls_per_minute: 每分钟允许的调用次数
    """
    def decorator(func: Callable) -> Callable:
        call_times = []
        lock = asyncio.Lock()
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with lock:
                    now = time.time()
                    # 清理超过1分钟的调用记录
                    call_times[:] = [t for t in call_times if now - t < 60]
                    
                    if len(call_times) >= calls_per_minute:
                        wait_time = 60 - (now - call_times[0])
                        raise ToolException(f"Rate limit exceeded. Please wait {wait_time:.1f} seconds.")
                    
                    call_times.append(now)
                
                return await func(*args, **kwargs)
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # 对于同步函数，使用简单的时间检查
                now = time.time()
                call_times[:] = [t for t in call_times if now - t < 60]
                
                if len(call_times) >= calls_per_minute:
                    wait_time = 60 - (now - call_times[0])
                    raise ToolException(f"Rate limit exceeded. Please wait {wait_time:.1f} seconds.")
                
                call_times.append(now)
                return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def validate_input(**validators):
    """输入验证装饰器
    
    Args:
        **validators: 参数验证器字典
    """
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 绑定参数
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # 验证参数
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    
                    if callable(validator):
                        if not validator(value):
                            raise ToolException(f"Parameter '{param_name}' validation failed")
                    elif isinstance(validator, type):
                        if not isinstance(value, validator):
                            raise ToolException(f"Parameter '{param_name}' must be of type {validator.__name__}")
                    elif isinstance(validator, dict):
                        # 复杂验证规则
                        if 'type' in validator and not isinstance(value, validator['type']):
                            raise ToolException(f"Parameter '{param_name}' must be of type {validator['type'].__name__}")
                        
                        if 'min_length' in validator and len(value) < validator['min_length']:
                            raise ToolException(f"Parameter '{param_name}' must have at least {validator['min_length']} characters")
                        
                        if 'max_length' in validator and len(value) > validator['max_length']:
                            raise ToolException(f"Parameter '{param_name}' must have at most {validator['max_length']} characters")
                        
                        if 'pattern' in validator:
                            import re
                            if not re.match(validator['pattern'], str(value)):
                                raise ToolException(f"Parameter '{param_name}' does not match required pattern")
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def cache_result(ttl: int = 300, key_func: Optional[Callable] = None):
    """结果缓存装饰器
    
    Args:
        ttl: 缓存生存时间（秒）
        key_func: 自定义缓存键生成函数
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        def default_key_func(*args, **kwargs):
            return str(hash((args, tuple(sorted(kwargs.items())))))
        
        key_generator = key_func or default_key_func
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = key_generator(*args, **kwargs)
            now = time.time()
            
            # 检查缓存
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if now - timestamp < ttl:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return result
                else:
                    del cache[cache_key]
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[cache_key] = (result, now)
            logger.debug(f"Cache miss for {func.__name__}, result cached")
            
            return result
        
        return wrapper
    
    return decorator


# 工具管理函数
def get_tool_registry() -> ToolRegistry:
    """获取工具注册表"""
    return tool_registry


def list_available_tools(category: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """列出可用工具"""
    return tool_registry.list_tools(category)


def get_tool_metrics() -> Dict[str, Any]:
    """获取工具指标摘要"""
    return tool_registry.get_metrics_summary()


def get_tool_info(name: str) -> Optional[Dict[str, Any]]:
    """获取特定工具的信息"""
    return tool_registry.get_tool_info(name)