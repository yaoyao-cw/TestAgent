import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Folder, 
  FileText, 
  Clock, 
  RefreshCw, 
  Maximize2, 
  Minimize2,
  Grid,
  List,
  Search
} from 'lucide-react'
import { FileTree } from './FileTree'
import { FileViewer } from './FileViewer'
import { Timeline } from './Timeline'
import { apiClient } from '@/lib/api'
import { cn, debounce } from '@/lib/utils'
import type { WorkspaceFile, WorkspaceStructure, TaskTimeline } from '@/types'
import toast from 'react-hot-toast'

interface WorkspaceViewerProps {
  taskId: string
  className?: string
}

type ViewMode = 'split' | 'files' | 'timeline'

export function WorkspaceViewer({ taskId, className }: WorkspaceViewerProps) {
  const [selectedFile, setSelectedFile] = useState<WorkspaceFile | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('split')
  const [searchQuery, setSearchQuery] = useState('')
  const [isFullscreen, setIsFullscreen] = useState(false)
  
  const queryClient = useQueryClient()

  // 获取工作空间文件结构
  const { 
    data: workspace, 
    isLoading: isLoadingWorkspace, 
    refetch: refetchWorkspace 
  } = useQuery<WorkspaceStructure>({
    queryKey: ['workspace', taskId],
    queryFn: async () => {
      const response = await apiClient.getTaskWorkspace(taskId)
      return response.data
    },
    enabled: !!taskId,
    refetchInterval: 10000, // 每10秒刷新一次
  })

  // 获取任务时间线
  const { 
    data: timeline, 
    isLoading: isLoadingTimeline,
    refetch: refetchTimeline 
  } = useQuery<TaskTimeline>({
    queryKey: ['timeline', taskId],
    queryFn: async () => {
      const response = await apiClient.getTaskTimeline(taskId)
      return response.data
    },
    enabled: !!taskId,
    refetchInterval: 5000, // 每5秒刷新一次
  })

  // 获取文件内容
  const { data: fileContent, isLoading: isLoadingFile } = useQuery({
    queryKey: ['file', taskId, selectedFile?.path],
    queryFn: async () => {
      if (!selectedFile) return null
      const response = await apiClient.getTaskFile(taskId, selectedFile.path)
      return response.data
    },
    enabled: !!selectedFile && !selectedFile.is_binary,
  })

  // 更新文件内容
  const updateFileMutation = useMutation({
    mutationFn: async ({ file, content }: { file: WorkspaceFile; content: string }) => {
      const response = await apiClient.updateTaskFile(taskId, file.path, content)
      return response.data
    },
    onSuccess: () => {
      toast.success('文件更新成功')
      queryClient.invalidateQueries({ queryKey: ['workspace', taskId] })
      queryClient.invalidateQueries({ queryKey: ['file', taskId, selectedFile?.path] })
    },
    onError: (error: any) => {
      toast.error(`文件更新失败: ${error.message}`)
    },
  })

  // 处理文件选择
  const handleFileSelect = (file: WorkspaceFile) => {
    setSelectedFile(file)
  }

  // 处理文件编辑
  const handleFileEdit = (file: WorkspaceFile) => {
    setSelectedFile(file)
    // 可以在这里添加编辑模式的逻辑
  }

  // 处理文件更新
  const handleFileUpdate = async (file: WorkspaceFile, content: string) => {
    await updateFileMutation.mutateAsync({ file, content })
  }

  // 搜索文件
  const debouncedSearch = debounce((query: string) => {
    setSearchQuery(query)
  }, 300)

  // 过滤文件
  const filteredFiles = workspace?.files.filter(file => 
    file.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    file.path.toLowerCase().includes(searchQuery.toLowerCase())
  ) || []

  // 更新选中文件的内容
  useEffect(() => {
    if (selectedFile && fileContent) {
      setSelectedFile(prev => prev ? { ...prev, content: fileContent.content } : null)
    }
  }, [fileContent])

  const renderContent = () => {
    switch (viewMode) {
      case 'files':
        return (
          <div className="h-full">
            <FileTree
              files={filteredFiles}
              onFileSelect={handleFileSelect}
              onFileEdit={handleFileEdit}
              selectedFile={selectedFile?.path}
              className="h-full"
            />
          </div>
        )
      
      case 'timeline':
        return (
          <div className="h-full overflow-y-auto">
            {timeline ? (
              <Timeline timeline={timeline} />
            ) : (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <Clock className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                  <p className="text-gray-500">加载时间线...</p>
                </div>
              </div>
            )}
          </div>
        )
      
      case 'split':
      default:
        return (
          <div className="h-full flex space-x-4">
            {/* 左侧文件树 */}
            <div className="w-1/3">
              <FileTree
                files={filteredFiles}
                onFileSelect={handleFileSelect}
                onFileEdit={handleFileEdit}
                selectedFile={selectedFile?.path}
                className="h-full"
              />
            </div>
            
            {/* 右侧内容区域 */}
            <div className="flex-1 flex flex-col space-y-4">
              {/* 文件查看器 */}
              <div className="flex-1">
                <FileViewer
                  file={selectedFile}
                  onFileUpdate={handleFileUpdate}
                  className="h-full"
                />
              </div>
              
              {/* 时间线 */}
              {timeline && (
                <div className="h-64">
                  <Timeline timeline={timeline} className="h-full" />
                </div>
              )}
            </div>
          </div>
        )
    }
  }

  if (isLoadingWorkspace) {
    return (
      <div className={cn("flex items-center justify-center h-64", className)}>
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">加载工作空间...</p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn(
      "bg-white border border-gray-200 rounded-lg",
      isFullscreen && "fixed inset-4 z-50",
      className
    )}>
      {/* 工作空间头部 */}
      <div className="border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div>
              <h2 className="text-lg font-medium text-gray-900">任务工作空间</h2>
              <p className="text-sm text-gray-600">
                {workspace ? (
                  <>
                    共 {workspace.total_files} 个文件，
                    总大小 {Math.round(workspace.total_size / 1024)} KB
                  </>
                ) : (
                  '加载中...'
                )}
              </p>
            </div>

            {/* 搜索框 */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="搜索文件..."
                onChange={(e) => debouncedSearch(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {/* 视图模式切换 */}
            <div className="flex items-center space-x-1 bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setViewMode('split')}
                className={cn(
                  "px-3 py-1 text-sm rounded-md transition-colors",
                  viewMode === 'split' 
                    ? "bg-white text-gray-900 shadow-sm" 
                    : "text-gray-600 hover:text-gray-900"
                )}
              >
                <Grid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('files')}
                className={cn(
                  "px-3 py-1 text-sm rounded-md transition-colors",
                  viewMode === 'files' 
                    ? "bg-white text-gray-900 shadow-sm" 
                    : "text-gray-600 hover:text-gray-900"
                )}
              >
                <Folder className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('timeline')}
                className={cn(
                  "px-3 py-1 text-sm rounded-md transition-colors",
                  viewMode === 'timeline' 
                    ? "bg-white text-gray-900 shadow-sm" 
                    : "text-gray-600 hover:text-gray-900"
                )}
              >
                <Clock className="w-4 h-4" />
              </button>
            </div>

            {/* 刷新按钮 */}
            <button
              onClick={() => {
                refetchWorkspace()
                refetchTimeline()
              }}
              className="btn btn-ghost btn-sm"
              disabled={isLoadingWorkspace || isLoadingTimeline}
            >
              <RefreshCw className={cn(
                "w-4 h-4",
                (isLoadingWorkspace || isLoadingTimeline) && "animate-spin"
              )} />
            </button>

            {/* 全屏切换 */}
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="btn btn-ghost btn-sm"
            >
              {isFullscreen ? (
                <Minimize2 className="w-4 h-4" />
              ) : (
                <Maximize2 className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* 工作空间内容 */}
      <div className="p-6 h-96">
        {renderContent()}
      </div>
    </div>
  )
}