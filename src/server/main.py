#!/usr/bin/env python3
"""
TestAgent Web API服务主应用
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..cache import initialize_cache_system, shutdown_cache_system
from ..config.logging_config import get_logger
from ..config.settings import get_settings
from ..core import initialize_core_systems, shutdown_core_systems
from ..core.exceptions import TestAgentException
from ..performance import (initialize_performance_system,
                           shutdown_performance_system)
from ..security.security_manager import (initialize_security_system,
                                         shutdown_security_system)
from .middleware import (AuthenticationMiddleware, InputValidationMiddleware,
                         LoggingMiddleware, RateLimitMiddleware,
                         SecurityMiddleware)
from .routers import (auth, cache, collaboration, config, documents,
                      monitoring, security, system, tasks, websocket)

logger = get_logger("api_server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("启动TestAgent Web API服务")

    # 初始化核心系统（错误处理、监控、恢复）
    if not initialize_core_systems():
        logger.error("核心系统初始化失败")

    # 初始化缓存系统
    if not initialize_cache_system():
        logger.error("缓存系统初始化失败")

    # 初始化性能优化系统
    if not initialize_performance_system():
        logger.error("性能优化系统初始化失败")

    # 初始化安全系统
    if not initialize_security_system():
        logger.error("安全系统初始化失败")

    # 初始化工具管理器
    try:
        from ..tools.tool_manager import get_tool_manager

        tool_manager = get_tool_manager()
        await tool_manager.initialize_tools()
        logger.info("工具管理器初始化成功")
    except Exception as e:
        logger.warning(f"工具管理器初始化失败: {e}")

    # 初始化MCP管理器
    try:
        from ..mcp.server_manager import get_mcp_manager

        mcp_manager = get_mcp_manager()
        await mcp_manager.start()
        logger.info("MCP管理器启动成功")
    except Exception as e:
        logger.warning(f"MCP管理器启动失败: {e}")

    yield

    # 关闭时清理
    logger.info("关闭TestAgent Web API服务")

    # 关闭工具管理器
    try:
        await tool_manager.shutdown()
        logger.info("工具管理器关闭成功")
    except Exception as e:
        logger.warning(f"工具管理器关闭失败: {e}")

    # 关闭MCP管理器
    try:
        await mcp_manager.stop()
        logger.info("MCP管理器关闭成功")
    except Exception as e:
        logger.warning(f"MCP管理器关闭失败: {e}")

    # 关闭安全系统
    shutdown_security_system()

    # 关闭性能优化系统
    shutdown_performance_system()

    # 关闭缓存系统
    shutdown_cache_system()

    # 关闭核心系统
    shutdown_core_systems()


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    settings = get_settings()

    # 创建应用
    app = FastAPI(
        title="TestAgent API",
        description="TestAgent智能测试代理系统API",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # 配置中间件
    setup_middleware(app, settings)

    # 配置路由
    setup_routers(app)

    # 配置异常处理
    setup_exception_handlers(app)

    # 配置静态文件
    setup_static_files(app)

    return app


def setup_middleware(app: FastAPI, settings):
    """配置中间件"""
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 受信任主机中间件
    if not settings.debug:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    # 自定义中间件（注意顺序很重要）
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(InputValidationMiddleware)
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(LoggingMiddleware)


def setup_routers(app: FastAPI):
    """配置路由"""
    # 认证路由（公开）
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])

    # API路由（需要认证）
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])

    app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])

    app.include_router(
        collaboration.router, prefix="/api/v1/collaboration", tags=["collaboration"]
    )

    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])

    # 配置管理路由
    app.include_router(config.router, prefix="/api/v1/config", tags=["config"])

    # 监控路由
    app.include_router(
        monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"]
    )

    # 缓存管理路由
    app.include_router(cache.router, prefix="/api/v1/cache", tags=["cache"])

    # 安全管理路由
    app.include_router(security.router, prefix="/api/v1/security", tags=["security"])

    # WebSocket路由
    app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


def setup_exception_handlers(app: FastAPI):
    """配置异常处理"""
    from ..core.error_handler import get_error_handler

    error_handler = get_error_handler()

    @app.exception_handler(TestAgentException)
    async def test_agent_exception_handler(request: Request, exc: TestAgentException):
        """处理TestAgent异常"""
        # 使用错误处理器处理异常
        context = {
            "request_url": str(request.url),
            "request_method": request.method,
            "user_agent": request.headers.get("user-agent", ""),
        }

        error_result = error_handler.handle_error(exc, context)

        # 根据严重程度确定HTTP状态码
        status_code = 500
        if exc.severity.value == "low":
            status_code = 400
        elif exc.severity.value == "medium":
            status_code = 422
        elif exc.severity.value == "high":
            status_code = 500
        elif exc.severity.value == "critical":
            status_code = 503

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.message,
                "error_code": exc.error_code,
                "category": exc.category.value,
                "severity": exc.severity.value,
                "details": exc.details,
                "suggestions": exc.suggestions,
                "timestamp": datetime.now().isoformat(),
                "request_id": context.get("request_id"),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理HTTP异常"""
        logger.error(f"HTTP异常: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "type": "HTTPException",
                "timestamp": datetime.now().isoformat(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理通用异常"""
        # 使用错误处理器处理未知异常
        context = {
            "request_url": str(request.url),
            "request_method": request.method,
            "user_agent": request.headers.get("user-agent", ""),
            "type": "uncaught_exception",
        }

        error_result = error_handler.handle_error(exc, context)

        logger.error(f"未处理的异常: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "内部服务器错误",
                "type": exc.__class__.__name__,
                "timestamp": datetime.now().isoformat(),
                "message": "系统遇到了未预期的错误，请稍后重试",
            },
        )


def setup_static_files(app: FastAPI):
    """配置静态文件"""
    # 检查静态文件目录是否存在
    static_dir = "static"
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 创建应用实例
app = create_app()


# 根路径
@app.get("/")
async def root():
    """API根端点"""
    return {
        "name": "TestAgent API",
        "version": "1.0.0",
        "description": "TestAgent智能测试代理系统API",
        "docs_url": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    from ..core.monitoring import get_health_checker

    try:
        health_checker = get_health_checker()

        # 运行健康检查
        check_results = health_checker.run_health_checks()

        # 确定整体状态
        overall_status = "healthy"
        if any(result.get("status") == "error" for result in check_results.values()):
            overall_status = "error"
        elif any(
            result.get("status") == "unhealthy" for result in check_results.values()
        ):
            overall_status = "unhealthy"
        elif any(
            result.get("status") == "warning" for result in check_results.values()
        ):
            overall_status = "warning"

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "checks": check_results,
            "overall_healthy": health_checker.is_healthy(),
        }

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "error": str(e),
            "overall_healthy": False,
        }


def start_server(
    host: str = "0.0.0.0", port: int = 8000, reload: bool = False, workers: int = 1
):
    """启动API服务器"""
    logger.info(f"启动TestAgent API服务器: {host}:{port}")

    uvicorn.run(
        "src.server.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level="info",
    )


if __name__ == "__main__":
    # 从环境变量获取配置
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    reload = os.environ.get("API_RELOAD", "false").lower() == "true"
    workers = int(os.environ.get("API_WORKERS", "1"))

    start_server(host, port, reload, workers)
