#!/usr/bin/env python3
"""
TestAgent Web API服务简化版本
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# 简化版应用
app = FastAPI(
    title="TestAgent API",
    description="TestAgent智能测试代理系统API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 根路径
@app.get("/")
async def root():
    """API根端点"""
    return {
        "name": "TestAgent API",
        "version": "1.0.0",
        "description": "TestAgent智能测试代理系统API",
        "docs_url": "/docs",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "message": "TestAgent API is running"
    }

# 简化的任务API
@app.post("/api/v1/tasks/submit")
async def submit_task(request: Dict[str, Any]):
    """提交任务（简化版）"""
    return {
        "task_id": f"task_{int(datetime.now().timestamp())}",
        "status": "submitted",
        "message": "任务已提交（演示模式）",
        "created_at": datetime.now().isoformat()
    }

@app.get("/api/v1/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """获取任务状态（简化版）"""
    return {
        "task_id": task_id,
        "status": "completed",
        "progress": 100.0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "message": "任务已完成（演示模式）"
    }

@app.get("/api/v1/tasks")
async def list_tasks():
    """列出任务（简化版）"""
    return {
        "tasks": [
            {
                "task_id": "demo_task_1",
                "status": "completed",
                "task_type": "test_case_generation",
                "task_topic": "演示任务",
                "created_at": datetime.now().isoformat()
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10
    }

# 简化的系统API
@app.get("/api/v1/system/status")
async def get_system_status():
    """获取系统状态（简化版）"""
    return {
        "system": {
            "status": "healthy",
            "version": "1.0.0",
            "uptime": 3600,
            "timestamp": datetime.now().isoformat()
        },
        "components": [
            {
                "name": "api_server",
                "status": "healthy",
                "healthy": True,
                "last_check": datetime.now().isoformat()
            }
        ],
        "resources": {
            "cpu_usage": 25.0,
            "memory_usage": 45.0,
            "disk_usage": 60.0,
            "network_io": {
                "bytes_sent": 1024000,
                "bytes_recv": 2048000
            },
            "process_count": 50
        },
        "execution_stats": {
            "total_tasks": 10,
            "completed_tasks": 8,
            "failed_tasks": 1,
            "pending_tasks": 1,
            "running_tasks": 0,
            "average_execution_time": 120.5
        }
    }

# 异常处理
@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """处理通用异常"""
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "type": exc.__class__.__name__,
            "timestamp": datetime.now().isoformat()
        }
    )

def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
    """启动API服务器"""
    print(f"🚀 启动TestAgent API服务器: http://{host}:{port}")
    print(f"📚 API文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "src.server.main_simple:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    start_server()