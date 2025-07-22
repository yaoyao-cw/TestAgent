import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { 
  MessageSquare, 
  ListTodo, 
  FileText, 
  Settings, 
  Monitor,
  Menu,
  X,
  Bot,
  Activity
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSystemStatus } from '@/hooks/useSystemStatus'

interface LayoutProps {
  children: React.ReactNode
}

const navigation = [
  { name: '对话', href: '/chat', icon: MessageSquare },
  { name: '任务', href: '/tasks', icon: ListTodo },
  { name: '文档', href: '/documents', icon: FileText },
  { name: '设置', href: '/settings', icon: Settings },
  { name: '系统', href: '/system', icon: Monitor },
]

export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const { data: systemStatus } = useSystemStatus()

  const isActive = (href: string) => {
    if (href === '/chat' && location.pathname === '/') return true
    return location.pathname === href
  }

  const getStatusColor = () => {
    if (!systemStatus) return 'bg-gray-400'
    
    switch (systemStatus.system.status) {
      case 'healthy':
        return 'bg-success-500'
      case 'degraded':
        return 'bg-warning-500'
      case 'unhealthy':
        return 'bg-error-500'
      default:
        return 'bg-gray-400'
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 移动端侧边栏遮罩 */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <div className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex flex-col h-full">
          {/* Logo区域 */}
          <div className="flex items-center justify-between h-16 px-6 border-b border-gray-200">
            <div className="flex items-center space-x-3">
              <div className="flex items-center justify-center w-8 h-8 bg-primary-600 rounded-lg">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-gray-900">TestAgent</h1>
                <div className="flex items-center space-x-2">
                  <div className={cn("w-2 h-2 rounded-full", getStatusColor())} />
                  <span className="text-xs text-gray-500">
                    {systemStatus?.system.status || '未知'}
                  </span>
                </div>
              </div>
            </div>
            <button
              className="lg:hidden p-1 rounded-md hover:bg-gray-100"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 导航菜单 */}
          <nav className="flex-1 px-4 py-6 space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    "flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors",
                    isActive(item.href)
                      ? "bg-primary-50 text-primary-700 border-r-2 border-primary-600"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  )}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon className="w-5 h-5 mr-3" />
                  {item.name}
                </Link>
              )
            })}
          </nav>

          {/* 底部状态信息 */}
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>版本 1.0.0</span>
              <div className="flex items-center space-x-1">
                <Activity className="w-3 h-3" />
                <span>运行中</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 顶部导航栏 */}
        <header className="bg-white border-b border-gray-200 lg:hidden">
          <div className="flex items-center justify-between h-16 px-4">
            <button
              className="p-2 rounded-md hover:bg-gray-100"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-semibold text-gray-900">TestAgent</h1>
            <div className="w-9" /> {/* 占位符保持居中 */}
          </div>
        </header>

        {/* 页面内容 */}
        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}