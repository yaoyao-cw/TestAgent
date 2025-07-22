"""性能监控工具函数"""

import time
import asyncio
from functools import wraps
from typing import Callable, Any, Dict, Optional

from ..config.logging_config import get_logger

logger = get_logger("performance")


def monitor_performance(func: Callable) -> Callable:
    """同步函数性能监控装饰器
    
    Args:
        func: 要监控的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        func_name = f"{func.__module__}.{func.__name__}"
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func_name} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func_name} failed after {execution_time:.3f}s: {e}")
            raise
    
    return wrapper


def async_monitor_performance(func: Callable) -> Callable:
    """异步函数性能监控装饰器
    
    Args:
        func: 要监控的异步函数
        
    Returns:
        装饰后的异步函数
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        func_name = f"{func.__module__}.{func.__name__}"
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func_name} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func_name} failed after {execution_time:.3f}s: {e}")
            raise
    
    return wrapper


class PerformanceTracker:
    """性能追踪器"""
    
    def __init__(self):
        self.metrics: Dict[str, list] = {}
    
    def record(self, operation: str, duration: float, success: bool = True):
        """记录操作性能
        
        Args:
            operation: 操作名称
            duration: 执行时间
            success: 是否成功
        """
        if operation not in self.metrics:
            self.metrics[operation] = []
        
        self.metrics[operation].append({
            'duration': duration,
            'success': success,
            'timestamp': time.time()
        })
    
    def get_stats(self, operation: str) -> Optional[Dict[str, Any]]:
        """获取操作统计信息
        
        Args:
            operation: 操作名称
            
        Returns:
            统计信息字典
        """
        if operation not in self.metrics:
            return None
        
        records = self.metrics[operation]
        durations = [r['duration'] for r in records if r['success']]
        
        if not durations:
            return None
        
        return {
            'count': len(records),
            'success_count': len(durations),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'success_rate': len(durations) / len(records)
        }
    
    def clear(self):
        """清除所有统计数据"""
        self.metrics.clear()


# 全局性能追踪器实例
performance_tracker = PerformanceTracker()


class TimerContext:
    """计时器上下文管理器"""
    
    def __init__(self, operation: str, tracker: Optional[PerformanceTracker] = None):
        self.operation = operation
        self.tracker = tracker or performance_tracker
        self.start_time = 0
        self.success = True
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.success = exc_type is None
        self.tracker.record(self.operation, duration, self.success)
        
        if self.success:
            logger.debug(f"{self.operation} completed in {duration:.3f}s")
        else:
            logger.error(f"{self.operation} failed after {duration:.3f}s")


def timer(operation: str) -> TimerContext:
    """创建计时器上下文
    
    Args:
        operation: 操作名称
        
    Returns:
        计时器上下文管理器
    """
    return TimerContext(operation)