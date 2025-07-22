#!/usr/bin/env python3
"""
WebSocket API路由
"""

import asyncio
import json
from typing import Dict, Set
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.websockets import WebSocketState

from ...graph.workflow_manager import get_workflow_manager
from ...config.logging_config import get_logger

logger = get_logger("websocket_api")

router = APIRouter()


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 存储活跃连接
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # 存储任务订阅
        self.task_subscriptions: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """连接WebSocket"""
        await websocket.accept()
        
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        
        self.active_connections[client_id].add(websocket)
        logger.info(f"WebSocket连接建立: {client_id}")
    
    def disconnect(self, websocket: WebSocket, client_id: str):
        """断开WebSocket连接"""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
        
        # 清理任务订阅
        for task_id, subscribers in self.task_subscriptions.items():
            subscribers.discard(websocket)
        
        # 清理空的订阅
        empty_subscriptions = [task_id for task_id, subscribers in self.task_subscriptions.items() if not subscribers]
        for task_id in empty_subscriptions:
            del self.task_subscriptions[task_id]
        
        logger.info(f"WebSocket连接断开: {client_id}")
    
    async def send_personal_message(self, message: str, client_id: str):
        """发送个人消息"""
        if client_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[client_id]:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(message)
                    else:
                        disconnected.add(websocket)
                except Exception as e:
                    logger.error(f"发送消息失败: {e}")
                    disconnected.add(websocket)
            
            # 清理断开的连接
            for websocket in disconnected:
                self.active_connections[client_id].discard(websocket)
    
    async def broadcast_message(self, message: str):
        """广播消息"""
        disconnected = []
        
        for client_id, connections in self.active_connections.items():
            for websocket in connections:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(message)
                    else:
                        disconnected.append((client_id, websocket))
                except Exception as e:
                    logger.error(f"广播消息失败: {e}")
                    disconnected.append((client_id, websocket))
        
        # 清理断开的连接
        for client_id, websocket in disconnected:
            if client_id in self.active_connections:
                self.active_connections[client_id].discard(websocket)
    
    def subscribe_to_task(self, websocket: WebSocket, task_id: str):
        """订阅任务更新"""
        if task_id not in self.task_subscriptions:
            self.task_subscriptions[task_id] = set()
        
        self.task_subscriptions[task_id].add(websocket)
        logger.info(f"订阅任务更新: {task_id}")
    
    def unsubscribe_from_task(self, websocket: WebSocket, task_id: str):
        """取消订阅任务更新"""
        if task_id in self.task_subscriptions:
            self.task_subscriptions[task_id].discard(websocket)
            
            if not self.task_subscriptions[task_id]:
                del self.task_subscriptions[task_id]
        
        logger.info(f"取消订阅任务更新: {task_id}")
    
    async def notify_task_update(self, task_id: str, update_data: dict):
        """通知任务更新"""
        if task_id in self.task_subscriptions:
            message = json.dumps({
                "type": "task_update",
                "task_id": task_id,
                "data": update_data,
                "timestamp": datetime.now().isoformat()
            })
            
            disconnected = set()
            for websocket in self.task_subscriptions[task_id]:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(message)
                    else:
                        disconnected.add(websocket)
                except Exception as e:
                    logger.error(f"发送任务更新失败: {e}")
                    disconnected.add(websocket)
            
            # 清理断开的连接
            for websocket in disconnected:
                self.task_subscriptions[task_id].discard(websocket)


# 全局连接管理器
manager = ConnectionManager()


# 依赖注入
async def get_workflow_manager_dep():
    """获取工作流管理器依赖"""
    return get_workflow_manager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    workflow_manager = Depends(get_workflow_manager_dep)
):
    """WebSocket端点"""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await handle_websocket_message(websocket, client_id, message, workflow_manager)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "无效的JSON格式",
                    "timestamp": datetime.now().isoformat()
                }))
            except Exception as e:
                logger.error(f"处理WebSocket消息失败: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }))
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket连接异常: {e}")
        manager.disconnect(websocket, client_id)


async def handle_websocket_message(
    websocket: WebSocket,
    client_id: str,
    message: dict,
    workflow_manager
):
    """处理WebSocket消息"""
    message_type = message.get("type")
    
    if message_type == "ping":
        # 心跳检测
        await websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        }))
    
    elif message_type == "subscribe_task":
        # 订阅任务更新
        task_id = message.get("task_id")
        if task_id:
            manager.subscribe_to_task(websocket, task_id)
            await websocket.send_text(json.dumps({
                "type": "subscription_confirmed",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat()
            }))
    
    elif message_type == "unsubscribe_task":
        # 取消订阅任务更新
        task_id = message.get("task_id")
        if task_id:
            manager.unsubscribe_from_task(websocket, task_id)
            await websocket.send_text(json.dumps({
                "type": "unsubscription_confirmed",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat()
            }))
    
    elif message_type == "get_task_status":
        # 获取任务状态
        task_id = message.get("task_id")
        if task_id:
            try:
                execution_status = workflow_manager.get_execution_status(task_id)
                if execution_status:
                    await websocket.send_text(json.dumps({
                        "type": "task_status",
                        "task_id": task_id,
                        "status": execution_status,
                        "timestamp": datetime.now().isoformat()
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"未找到任务: {task_id}",
                        "timestamp": datetime.now().isoformat()
                    }))
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"获取任务状态失败: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }))
    
    elif message_type == "list_tasks":
        # 列出任务
        try:
            executions = workflow_manager.list_executions()
            await websocket.send_text(json.dumps({
                "type": "task_list",
                "tasks": executions,
                "timestamp": datetime.now().isoformat()
            }))
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"列出任务失败: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }))
    
    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"未知的消息类型: {message_type}",
            "timestamp": datetime.now().isoformat()
        }))


@router.websocket("/ws/tasks/{task_id}")
async def task_websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    workflow_manager = Depends(get_workflow_manager_dep)
):
    """任务专用WebSocket端点"""
    await websocket.accept()
    
    # 自动订阅任务更新
    manager.subscribe_to_task(websocket, task_id)
    
    try:
        # 发送初始状态
        execution_status = workflow_manager.get_execution_status(task_id)
        if execution_status:
            await websocket.send_text(json.dumps({
                "type": "initial_status",
                "task_id": task_id,
                "status": execution_status,
                "timestamp": datetime.now().isoformat()
            }))
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"未找到任务: {task_id}",
                "timestamp": datetime.now().isoformat()
            }))
        
        # 保持连接并监听任务状态变化
        while True:
            # 定期检查任务状态
            await asyncio.sleep(2)
            
            current_status = workflow_manager.get_execution_status(task_id)
            if current_status:
                await manager.notify_task_update(task_id, current_status)
                
                # 如果任务完成，发送完成消息并断开连接
                if current_status.get("status") in ["completed", "failed", "cancelled"]:
                    await websocket.send_text(json.dumps({
                        "type": "task_finished",
                        "task_id": task_id,
                        "final_status": current_status,
                        "timestamp": datetime.now().isoformat()
                    }))
                    break
    
    except WebSocketDisconnect:
        manager.unsubscribe_from_task(websocket, task_id)
    except Exception as e:
        logger.error(f"任务WebSocket连接异常: {e}")
        manager.unsubscribe_from_task(websocket, task_id)


# 提供给其他模块使用的通知函数
async def notify_task_status_change(task_id: str, status_data: dict):
    """通知任务状态变化"""
    await manager.notify_task_update(task_id, status_data)


async def broadcast_system_message(message: str, message_type: str = "system"):
    """广播系统消息"""
    system_message = json.dumps({
        "type": message_type,
        "message": message,
        "timestamp": datetime.now().isoformat()
    })
    
    await manager.broadcast_message(system_message)


# 获取连接管理器的函数
def get_connection_manager():
    """获取连接管理器"""
    return manager