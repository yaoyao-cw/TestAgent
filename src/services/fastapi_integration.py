"""
FastAPI集成示例

展示如何将外部服务集成到FastAPI应用中。
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .startup import initialize_external_services, shutdown_external_services
from .api_endpoints import router as services_router
from ..config.logging_config import get_logger

logger = get_logger("fastapi_integration")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI生命周期管理"""
    # 启动时初始化外部服务
    logger.info("FastAPI应用启动，初始化外部服务")
    success = await initialize_external_services()

    if success:
        logger.info("外部服务初始化成功")
    else:
        logger.warning("外部服务初始化失败，应用将继续运行但功能可能受限")

    yield

    # 关闭时清理外部服务
    logger.info("FastAPI应用关闭，清理外部服务")
    await shutdown_external_services()


def create_app_with_services() -> FastAPI:
    """创建包含外部服务的FastAPI应用"""
    app = FastAPI(
        title="TestAgent API",
        description="智能测试平台API，集成外部服务支持",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 包含服务管理路由
    app.include_router(services_router)

    # 添加健康检查端点
    @app.get("/health")
    async def health_check():
        """应用健康检查"""
        from .external_service_manager import get_external_service_manager

        try:
            service_manager = get_external_service_manager()
            stats = service_manager.get_service_statistics()

            return {
                "status": "healthy",
                "services": {
                    "total": stats["total_services"],
                    "active": stats["active_services"],
                    "availability": f"{stats['availability_percentage']:.1f}%",
                },
            }
        except Exception as e:
            return {"status": "degraded", "error": str(e)}

    # 添加根端点
    @app.get("/")
    async def root():
        """根端点"""
        return {
            "message": "TestAgent API with External Services",
            "version": "1.0.0",
            "services_endpoint": "/api/services",
        }

    return app


# 创建应用实例
app = create_app_with_services()


if __name__ == "__main__":
    import uvicorn

    # 运行应用
    uvicorn.run(
        "src.services.fastapi_integration:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 生产环境建议关闭
        log_level="info",
    )
