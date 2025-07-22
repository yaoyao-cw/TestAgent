import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Loader2, Plus, Settings, FileText } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useSubmitTask } from '@/hooks/useTasks'
import { useWebSocket } from '@/hooks/useWebSocket'
import { cn, formatDate } from '@/lib/utils'
import type { ChatMessage, TaskSubmissionRequest } from '@/types'
import { CodeBlock } from '@/components/CodeBlock'
import { TaskCard } from '@/components/TaskCard'

const TASK_TYPES = [
  { value: 'test_case_generation', label: '测试用例生成' },
  { value: 'test_analysis', label: '测试分析' },
  { value: 'code_review', label: '代码审查' },
  { value: 'bug_analysis', label: 'Bug分析' },
]

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'system',
      content: '欢迎使用TestAgent！我是您的智能测试助手，可以帮您生成测试用例、分析代码质量、审查测试策略等。请告诉我您需要什么帮助？',
      timestamp: new Date(),
    }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedTaskType, setSelectedTaskType] = useState('test_case_generation')
  const [showTaskForm, setShowTaskForm] = useState(false)
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  
  const submitTaskMutation = useSubmitTask()
  
  const { isConnected, sendMessage } = useWebSocket({
    onMessage: (message) => {
      if (message.type === 'task_update') {
        // 处理任务状态更新
        addMessage({
          type: 'system',
          content: `任务 ${message.task_id} 状态更新: ${message.data?.status}`,
        })
      }
    },
  })

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const addMessage = (message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: Date.now().toString(),
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, newMessage])
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage = inputValue.trim()
    setInputValue('')
    setIsLoading(true)

    // 添加用户消息
    addMessage({
      type: 'user',
      content: userMessage,
    })

    try {
      // 分析用户输入，决定是否需要创建任务
      if (shouldCreateTask(userMessage)) {
        setShowTaskForm(true)
        addMessage({
          type: 'assistant',
          content: '我理解您需要创建一个测试任务。请选择任务类型并提供更多详细信息：',
        })
      } else {
        // 模拟AI回复
        setTimeout(() => {
          addMessage({
            type: 'assistant',
            content: generateResponse(userMessage),
          })
          setIsLoading(false)
        }, 1000)
      }
    } catch (error) {
      addMessage({
        type: 'system',
        content: '抱歉，处理您的请求时出现了错误。请稍后重试。',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreateTask = async (taskData: Partial<TaskSubmissionRequest>) => {
    try {
      const result = await submitTaskMutation.mutateAsync({
        task_type: selectedTaskType,
        task_topic: taskData.task_topic || '用户请求的任务',
        context: taskData.context || inputValue,
        code_snippets: taskData.code_snippets,
        requirements: taskData.requirements,
        locale: 'zh-CN',
        ...taskData,
      })

      addMessage({
        type: 'assistant',
        content: `任务已创建成功！任务ID: ${result.task_id}`,
        metadata: { taskId: result.task_id, taskType: selectedTaskType },
      })

      setShowTaskForm(false)
    } catch (error: any) {
      addMessage({
        type: 'system',
        content: `创建任务失败: ${error.message}`,
      })
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const shouldCreateTask = (message: string): boolean => {
    const taskKeywords = ['生成测试', '测试用例', '代码审查', '分析代码', '测试计划', 'bug分析']
    return taskKeywords.some(keyword => message.includes(keyword))
  }

  const generateResponse = (message: string): string => {
    // 简单的响应生成逻辑
    if (message.includes('测试')) {
      return '我可以帮您生成各种类型的测试用例，包括单元测试、集成测试和端到端测试。您可以提供代码片段或需求描述，我会为您创建相应的测试策略。'
    } else if (message.includes('代码')) {
      return '我可以分析您的代码质量，检查潜在的问题，并提供改进建议。请分享您的代码，我会进行详细的审查。'
    } else {
      return '我是TestAgent，专门帮助您处理测试相关的任务。我可以生成测试用例、分析代码质量、审查测试策略等。请告诉我您具体需要什么帮助？'
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* 聊天头部 */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex items-center justify-center w-10 h-10 bg-primary-600 rounded-full">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-gray-900">TestAgent</h1>
              <div className="flex items-center space-x-2 text-sm text-gray-500">
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  isConnected ? "bg-success-500" : "bg-gray-400"
                )} />
                <span>{isConnected ? '已连接' : '未连接'}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button className="btn btn-ghost btn-sm">
              <FileText className="w-4 h-4" />
              导出对话
            </button>
            <button className="btn btn-ghost btn-sm">
              <Settings className="w-4 h-4" />
              设置
            </button>
          </div>
        </div>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 custom-scrollbar">
        <AnimatePresence>
          {messages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className={cn(
                "flex",
                message.type === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              <div className={cn(
                "flex items-start space-x-3 max-w-[80%]",
                message.type === 'user' ? 'flex-row-reverse space-x-reverse' : ''
              )}>
                {/* 头像 */}
                <div className={cn(
                  "flex items-center justify-center w-8 h-8 rounded-full flex-shrink-0",
                  message.type === 'user' 
                    ? "bg-primary-600" 
                    : message.type === 'assistant'
                    ? "bg-gray-600"
                    : "bg-warning-500"
                )}>
                  {message.type === 'user' ? (
                    <User className="w-4 h-4 text-white" />
                  ) : message.type === 'assistant' ? (
                    <Bot className="w-4 h-4 text-white" />
                  ) : (
                    <Settings className="w-4 h-4 text-white" />
                  )}
                </div>

                {/* 消息内容 */}
                <div className={cn(
                  "rounded-lg px-4 py-2 shadow-sm",
                  message.type === 'user'
                    ? "bg-primary-600 text-white"
                    : message.type === 'assistant'
                    ? "bg-white text-gray-900 border border-gray-200"
                    : "bg-warning-50 text-warning-800 border border-warning-200"
                )}>
                  <div className="text-sm whitespace-pre-wrap">
                    {message.content}
                  </div>
                  
                  {/* 任务卡片 */}
                  {message.metadata?.taskId && (
                    <div className="mt-3">
                      <TaskCard taskId={message.metadata.taskId} />
                    </div>
                  )}
                  
                  <div className="text-xs opacity-70 mt-2">
                    {formatDate(message.timestamp)}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* 加载指示器 */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex justify-start"
          >
            <div className="flex items-center space-x-3">
              <div className="flex items-center justify-center w-8 h-8 bg-gray-600 rounded-full">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white rounded-lg px-4 py-2 border border-gray-200">
                <div className="flex items-center space-x-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm text-gray-500">正在思考...</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 任务创建表单 */}
      {showTaskForm && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-6 mb-4 p-4 bg-white rounded-lg border border-gray-200 shadow-sm"
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                任务类型
              </label>
              <select
                value={selectedTaskType}
                onChange={(e) => setSelectedTaskType(e.target.value)}
                className="input"
              >
                {TASK_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="flex space-x-2">
              <button
                onClick={() => handleCreateTask({ task_topic: inputValue })}
                className="btn btn-primary btn-sm"
                disabled={submitTaskMutation.isPending}
              >
                {submitTaskMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  '创建任务'
                )}
              </button>
              <button
                onClick={() => setShowTaskForm(false)}
                className="btn btn-secondary btn-sm"
              >
                取消
              </button>
            </div>
          </div>
        </motion.div>
      )}

      {/* 输入区域 */}
      <div className="bg-white border-t border-gray-200 px-6 py-4">
        <div className="flex items-end space-x-3">
          <div className="flex-1">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入您的问题或需求..."
              className="textarea resize-none"
              rows={1}
              style={{
                minHeight: '40px',
                maxHeight: '120px',
                height: 'auto',
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = 'auto'
                target.style.height = target.scrollHeight + 'px'
              }}
            />
          </div>
          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            className="btn btn-primary btn-md"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
        
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
          <span>按 Enter 发送，Shift + Enter 换行</span>
          <span>{inputValue.length}/2000</span>
        </div>
      </div>
    </div>
  )
}