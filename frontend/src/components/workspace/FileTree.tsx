import React, { useState } from 'react'
import { 
  ChevronRight, 
  ChevronDown, 
  File, 
  Folder, 
  FolderOpen,
  Edit3,
  Eye,
  Download,
  Clock
} from 'lucide-react'
import { cn, formatFileSize, formatRelativeTime, getFileTypeIcon } from '@/lib/utils'
import type { WorkspaceFile } from '@/types'

interface FileTreeProps {
  files: WorkspaceFile[]
  onFileSelect?: (file: WorkspaceFile) => void
  onFileEdit?: (file: WorkspaceFile) => void
  selectedFile?: string
  className?: string
}

interface FileTreeNodeProps {
  file: WorkspaceFile
  level: number
  onFileSelect?: (file: WorkspaceFile) => void
  onFileEdit?: (file: WorkspaceFile) => void
  selectedFile?: string
  children?: WorkspaceFile[]
}

function FileTreeNode({ 
  file, 
  level, 
  onFileSelect, 
  onFileEdit, 
  selectedFile,
  children = []
}: FileTreeNodeProps) {
  const [isExpanded, setIsExpanded] = useState(level < 2) // 默认展开前两层
  const isDirectory = file.type === 'directory'
  const isSelected = selectedFile === file.path
  const hasChildren = children.length > 0

  const handleToggle = () => {
    if (isDirectory && hasChildren) {
      setIsExpanded(!isExpanded)
    }
  }

  const handleSelect = () => {
    if (!isDirectory) {
      onFileSelect?.(file)
    }
  }

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!isDirectory && !file.is_binary) {
      onFileEdit?.(file)
    }
  }

  return (
    <div>
      <div
        className={cn(
          "flex items-center py-1 px-2 hover:bg-gray-50 cursor-pointer group",
          isSelected && "bg-primary-50 border-r-2 border-primary-500",
          "transition-colors duration-150"
        )}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={isDirectory ? handleToggle : handleSelect}
      >
        {/* 展开/收起图标 */}
        <div className="w-4 h-4 mr-1 flex items-center justify-center">
          {isDirectory && hasChildren && (
            isExpanded ? (
              <ChevronDown className="w-3 h-3 text-gray-500" />
            ) : (
              <ChevronRight className="w-3 h-3 text-gray-500" />
            )
          )}
        </div>

        {/* 文件/文件夹图标 */}
        <div className="w-4 h-4 mr-2 flex items-center justify-center">
          {isDirectory ? (
            isExpanded ? (
              <FolderOpen className="w-4 h-4 text-blue-500" />
            ) : (
              <Folder className="w-4 h-4 text-blue-500" />
            )
          ) : (
            <span className="text-sm">{getFileTypeIcon(file.name)}</span>
          )}
        </div>

        {/* 文件名 */}
        <span className={cn(
          "flex-1 text-sm truncate",
          isSelected ? "font-medium text-primary-700" : "text-gray-700"
        )}>
          {file.name}
        </span>

        {/* 文件信息 */}
        {!isDirectory && (
          <div className="flex items-center space-x-2 text-xs text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity">
            {file.size && (
              <span>{formatFileSize(file.size)}</span>
            )}
            <span title={file.modified_at}>
              <Clock className="w-3 h-3 inline mr-1" />
              {formatRelativeTime(file.modified_at)}
            </span>
          </div>
        )}

        {/* 操作按钮 */}
        {!isDirectory && (
          <div className="flex items-center space-x-1 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleSelect}
              className="p-1 hover:bg-gray-200 rounded"
              title="查看文件"
            >
              <Eye className="w-3 h-3 text-gray-600" />
            </button>
            {!file.is_binary && (
              <button
                onClick={handleEdit}
                className="p-1 hover:bg-gray-200 rounded"
                title="编辑文件"
              >
                <Edit3 className="w-3 h-3 text-gray-600" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* 子文件/文件夹 */}
      {isDirectory && isExpanded && hasChildren && (
        <div>
          {children.map((child) => (
            <FileTreeNode
              key={child.path}
              file={child}
              level={level + 1}
              onFileSelect={onFileSelect}
              onFileEdit={onFileEdit}
              selectedFile={selectedFile}
              children={[]} // 这里需要根据实际数据结构来处理子文件
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function FileTree({ 
  files, 
  onFileSelect, 
  onFileEdit, 
  selectedFile, 
  className 
}: FileTreeProps) {
  // 构建文件树结构
  const buildFileTree = (files: WorkspaceFile[]) => {
    const tree: { [key: string]: WorkspaceFile & { children: WorkspaceFile[] } } = {}
    const roots: (WorkspaceFile & { children: WorkspaceFile[] })[] = []

    // 首先创建所有节点
    files.forEach(file => {
      tree[file.path] = { ...file, children: [] }
    })

    // 然后建立父子关系
    files.forEach(file => {
      const pathParts = file.path.split('/')
      if (pathParts.length > 1) {
        const parentPath = pathParts.slice(0, -1).join('/')
        const parent = tree[parentPath]
        if (parent) {
          parent.children.push(tree[file.path])
        } else {
          roots.push(tree[file.path])
        }
      } else {
        roots.push(tree[file.path])
      }
    })

    return roots
  }

  const fileTree = buildFileTree(files)

  if (files.length === 0) {
    return (
      <div className={cn("p-4 text-center text-gray-500", className)}>
        <Folder className="w-8 h-8 mx-auto mb-2 text-gray-400" />
        <p>工作空间为空</p>
      </div>
    )
  }

  return (
    <div className={cn("bg-white border border-gray-200 rounded-lg", className)}>
      <div className="border-b border-gray-200 px-4 py-3">
        <h3 className="text-sm font-medium text-gray-900">文件结构</h3>
        <p className="text-xs text-gray-500 mt-1">
          共 {files.length} 个文件
        </p>
      </div>
      
      <div className="max-h-96 overflow-y-auto">
        {fileTree.map((file) => (
          <FileTreeNode
            key={file.path}
            file={file}
            level={0}
            onFileSelect={onFileSelect}
            onFileEdit={onFileEdit}
            selectedFile={selectedFile}
            children={file.children}
          />
        ))}
      </div>
    </div>
  )
}