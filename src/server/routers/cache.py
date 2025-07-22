#!/usr/bin/env python3
"""
缓存管理API路由
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

try:
    from ...cache.cache_manager import get_cache_manager
    from ...cache.llm_cache import get_llm_cache
    from ...cache.rag_cache import get_rag_cache
    from ...performance.optimizer import get_performance_optimizer
    from ...config.logging_config import get_logger
except ImportError as e:
    # 如果导入失败，提供模拟实现
    def get_cache_manager():
        return None
    def get_llm_cache():
        return None
    def get_rag_cache():
        return None
    def get_performance_optimizer():
        return None
    def get_logger(name):
        import logging
        return logging.getLogger(name)

logger = get_logger("cache_api")

router = APIRouter()


# 请求和响应模型
class CacheStatsResponse(BaseModel):
    """缓存统计响应"""
    cache_stats: Dict[str, Any] = Field(..., description="缓存统计信息")
    llm_cache_stats: Dict[str, Any] = Field(..., description="LLM缓存统计")
    rag_cache_stats: Dict[str, Any] = Field(..., description="RAG缓存统计")
    timestamp: str = Field(..., description="统计时间")


class PerformanceStatsResponse(BaseModel):
    """性能统计响应"""
    performance_stats: Dict[str, Any] = Field(..., description="性能统计信息")
    timestamp: str = Field(..., description="统计时间")


class CacheKeyRequest(BaseModel):
    """缓存键请求"""
    key: str = Field(..., description="缓存键")


class CacheSetRequest(BaseModel):
    """缓存设置请求"""
    key: str = Field(..., description="缓存键")
    value: Any = Field(..., description="缓存值")
    ttl: Optional[int] = Field(None, description="过期时间（秒）")


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """获取缓存统计信息"""
    try:
        cache_manager = get_cache_manager()
        llm_cache = get_llm_cache()
        rag_cache = get_rag_cache()
        
        # 获取各种缓存统计
        cache_stats = {}
        llm_cache_stats = {}
        rag_cache_stats = {}
        
        if cache_manager:
            cache_stats = await cache_manager.stats()
        
        if llm_cache:
            llm_cache_stats = await llm_cache.get_cache_stats()
        
        if rag_cache:
            rag_cache_stats = await rag_cache.get_cache_stats()
        
        return CacheStatsResponse(
            cache_stats=cache_stats,
            llm_cache_stats=llm_cache_stats,
            rag_cache_stats=rag_cache_stats,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取缓存统计失败: {str(e)}"
        )


@router.get("/performance", response_model=PerformanceStatsResponse)
async def get_performance_stats():
    """获取性能统计信息"""
    try:
        optimizer = get_performance_optimizer()
        
        if not optimizer:
            raise HTTPException(status_code=503, detail="性能优化器不可用")
        
        performance_stats = optimizer.get_performance_stats()
        
        return PerformanceStatsResponse(
            performance_stats=performance_stats,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"获取性能统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取性能统计失败: {str(e)}"
        )


@router.get("/keys")
async def get_cache_keys(
    pattern: str = Query("*", description="键名模式"),
    limit: int = Query(100, description="返回数量限制", ge=1, le=1000)
):
    """获取缓存键列表"""
    try:
        cache_manager = get_cache_manager()
        
        if not cache_manager:
            raise HTTPException(status_code=503, detail="缓存管理器不可用")
        
        keys = await cache_manager.keys(pattern)
        
        # 限制返回数量
        if len(keys) > limit:
            keys = keys[:limit]
        
        return {
            "keys": keys,
            "count": len(keys),
            "pattern": pattern,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取缓存键失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取缓存键失败: {str(e)}"
        )


@router.get("/get/{key}")
async def get_cache_value(key: str):
    """获取缓存值"""
    try:
        cache_manager = get_cache_manager()
        
        if not cache_manager:
            raise HTTPException(status_code=503, detail="缓存管理器不可用")
        
        value = await cache_manager.get(key)
        
        if value is None:
            raise HTTPException(
                status_code=404,
                detail=f"缓存键不存在: {key}"
            )
        
        return {
            "key": key,
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取缓存值失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取缓存值失败: {str(e)}"
        )


@router.post("/set")
async def set_cache_value(request: CacheSetRequest):
    """设置缓存值"""
    try:
        cache_manager = get_cache_manager()
        
        if not cache_manager:
            raise HTTPException(status_code=503, detail="缓存管理器不可用")
        
        success = await cache_manager.set(request.key, request.value, request.ttl)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="设置缓存值失败"
            )
        
        return {
            "success": True,
            "message": "缓存值设置成功",
            "key": request.key,
            "ttl": request.ttl,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置缓存值失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"设置缓存值失败: {str(e)}"
        )


@router.delete("/delete/{key}")
async def delete_cache_value(key: str):
    """删除缓存值"""
    try:
        cache_manager = get_cache_manager()
        
        if not cache_manager:
            raise HTTPException(status_code=503, detail="缓存管理器不可用")
        
        success = await cache_manager.delete(key)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"缓存键不存在: {key}"
            )
        
        return {
            "success": True,
            "message": "缓存值删除成功",
            "key": key,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除缓存值失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"删除缓存值失败: {str(e)}"
        )


@router.post("/clear")
async def clear_cache():
    """清空所有缓存"""
    try:
        cache_manager = get_cache_manager()
        
        if not cache_manager:
            raise HTTPException(status_code=503, detail="缓存管理器不可用")
        
        success = await cache_manager.clear()
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="清空缓存失败"
            )
        
        return {
            "success": True,
            "message": "缓存已清空",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清空缓存失败: {str(e)}"
        )


@router.post("/llm/clear")
async def clear_llm_cache(
    provider: Optional[str] = Body(None, embed=True),
    model: Optional[str] = Body(None, embed=True)
):
    """清空LLM缓存"""
    try:
        llm_cache = get_llm_cache()
        
        if not llm_cache:
            raise HTTPException(status_code=503, detail="LLM缓存不可用")
        
        count = await llm_cache.invalidate_cache(provider, model)
        
        return {
            "success": True,
            "message": f"已清除 {count} 个LLM缓存条目",
            "provider": provider,
            "model": model,
            "cleared_count": count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"清空LLM缓存失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清空LLM缓存失败: {str(e)}"
        )


@router.post("/rag/clear")
async def clear_rag_cache(
    cache_type: str = Body("all", embed=True),  # all, retrieval, vector, document
    model: Optional[str] = Body(None, embed=True),
    document_id: Optional[str] = Body(None, embed=True)
):
    """清空RAG缓存"""
    try:
        rag_cache = get_rag_cache()
        
        if not rag_cache:
            raise HTTPException(status_code=503, detail="RAG缓存不可用")
        
        total_count = 0
        
        if cache_type in ["all", "retrieval"]:
            count = await rag_cache.invalidate_retrieval_cache()
            total_count += count
        
        if cache_type in ["all", "vector"]:
            count = await rag_cache.invalidate_vector_cache(model)
            total_count += count
        
        if cache_type in ["all", "document"]:
            count = await rag_cache.invalidate_document_cache(document_id)
            total_count += count
        
        return {
            "success": True,
            "message": f"已清除 {total_count} 个RAG缓存条目",
            "cache_type": cache_type,
            "model": model,
            "document_id": document_id,
            "cleared_count": total_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"清空RAG缓存失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清空RAG缓存失败: {str(e)}"
        )


@router.post("/optimize/memory")
async def optimize_memory():
    """优化内存使用"""
    try:
        optimizer = get_performance_optimizer()
        
        if not optimizer:
            raise HTTPException(status_code=503, detail="性能优化器不可用")
        
        # 获取优化前的内存使用情况
        before_stats = optimizer.memory_manager.get_memory_usage()
        
        # 执行内存优化
        optimizer.memory_manager.optimize_memory()
        
        # 获取优化后的内存使用情况
        after_stats = optimizer.memory_manager.get_memory_usage()
        
        return {
            "success": True,
            "message": "内存优化完成",
            "before_stats": before_stats,
            "after_stats": after_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"内存优化失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内存优化失败: {str(e)}"
        )


@router.get("/health")
async def cache_health_check():
    """缓存系统健康检查"""
    try:
        cache_manager = get_cache_manager()
        llm_cache = get_llm_cache()
        rag_cache = get_rag_cache()
        optimizer = get_performance_optimizer()
        
        health_status = {
            "cache_manager": cache_manager is not None and cache_manager.is_enabled(),
            "llm_cache": llm_cache is not None,
            "rag_cache": rag_cache is not None,
            "performance_optimizer": optimizer is not None,
            "timestamp": datetime.now().isoformat()
        }
        
        # 测试缓存基本功能
        if cache_manager and cache_manager.is_enabled():
            test_key = "health_check_test"
            test_value = "test_value"
            
            # 测试设置和获取
            await cache_manager.set(test_key, test_value, 60)
            retrieved_value = await cache_manager.get(test_key)
            
            health_status["cache_test"] = retrieved_value == test_value
            
            # 清理测试数据
            await cache_manager.delete(test_key)
        else:
            health_status["cache_test"] = False
        
        overall_healthy = all([
            health_status["cache_manager"],
            health_status["llm_cache"],
            health_status["rag_cache"],
            health_status["performance_optimizer"],
            health_status["cache_test"]
        ])
        
        health_status["overall_healthy"] = overall_healthy
        
        return health_status
        
    except Exception as e:
        logger.error(f"缓存健康检查失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"缓存健康检查失败: {str(e)}"
        )