import { useEffect, useRef, useState, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'
import type { WebSocketMessage } from '@/types'

interface UseWebSocketOptions {
  url?: string
  autoConnect?: boolean
  onMessage?: (message: WebSocketMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: any) => void
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    url = '/ws',
    autoConnect = true,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const socketRef = useRef<Socket | null>(null)

  const connect = useCallback(() => {
    if (socketRef.current?.connected) {
      return
    }

    try {
      const socket = io(url, {
        transports: ['websocket'],
        upgrade: false,
      })

      socket.on('connect', () => {
        setIsConnected(true)
        setConnectionError(null)
        onConnect?.()
      })

      socket.on('disconnect', () => {
        setIsConnected(false)
        onDisconnect?.()
      })

      socket.on('error', (error) => {
        setConnectionError(error.message || '连接错误')
        onError?.(error)
      })

      socket.on('message', (message: WebSocketMessage) => {
        onMessage?.(message)
      })

      socketRef.current = socket
    } catch (error: any) {
      setConnectionError(error.message || '连接失败')
      onError?.(error)
    }
  }, [url, onConnect, onDisconnect, onError, onMessage])

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect()
      socketRef.current = null
      setIsConnected(false)
    }
  }, [])

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('message', message)
    } else {
      console.warn('WebSocket未连接，无法发送消息')
    }
  }, [])

  const subscribeToTask = useCallback((taskId: string) => {
    sendMessage({
      type: 'subscribe_task',
      task_id: taskId,
    })
  }, [sendMessage])

  const unsubscribeFromTask = useCallback((taskId: string) => {
    sendMessage({
      type: 'unsubscribe_task',
      task_id: taskId,
    })
  }, [sendMessage])

  useEffect(() => {
    if (autoConnect) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [autoConnect, connect, disconnect])

  return {
    isConnected,
    connectionError,
    connect,
    disconnect,
    sendMessage,
    subscribeToTask,
    unsubscribeFromTask,
  }
}

// 专门用于任务状态更新的WebSocket Hook
export function useTaskWebSocket(taskId: string | null) {
  const [taskStatus, setTaskStatus] = useState<any>(null)
  const [isListening, setIsListening] = useState(false)

  const { isConnected, sendMessage, subscribeToTask, unsubscribeFromTask } = useWebSocket({
    onMessage: (message) => {
      if (message.type === 'task_update' && message.task_id === taskId) {
        setTaskStatus(message.data)
      }
    },
    onConnect: () => {
      if (taskId) {
        subscribeToTask(taskId)
        setIsListening(true)
      }
    },
  })

  useEffect(() => {
    if (isConnected && taskId && !isListening) {
      subscribeToTask(taskId)
      setIsListening(true)
    }

    return () => {
      if (taskId && isListening) {
        unsubscribeFromTask(taskId)
        setIsListening(false)
      }
    }
  }, [taskId, isConnected, isListening, subscribeToTask, unsubscribeFromTask])

  return {
    taskStatus,
    isConnected,
    isListening,
  }
}