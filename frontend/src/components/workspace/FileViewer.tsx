import React, { useState, useEffect } from 'react'
import { 
  File, 
  Edit3, 
  Save, 
  X, 
  Download, 
  Copy, 
  Eye,
  Code,
  FileText,
  Image as ImageIcon
} from 'lucide-react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { cn, formatFileSize, formatRelativeTime, getFileTypeIcon } from '@/lib/utils'
import type { WorkspaceFile } from '@/types'
import toast from 'react-hot-toast'

interface FileViewerProps {
  file: WorkspaceFile | null
  onFileUpdate?: (file: WorkspaceFile, content: string) => void
  onClose?: () => void
  className?: string
}

export function FileViewer({ file, onFileUpdate, onClose, className }: FileViewerProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (file?.content) {
      setEditContent(file.content)
    }
  }, [file])

  if (!file) {
    return (
      <div className={cn("flex items-center justify-center h-64 bg-gray-50 rounded-lg", className)}>
        <div className="text-center">
          <File className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">选择一个文件来查看内容</p>
        </div>
      </div>
    )
  }

  const getLanguage = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase()
    switch (ext) {
      case 'js':
      case 'jsx':
        return 'javascript'
      case 'ts':
      case 'tsx':
        return 'typescript'
      case 'py':
        return 'python'
      case 'json':
        return 'json'
      case 'md':
        return 'markdown'
      case 'html':
        return 'html'
      case 'css':
        return 'css'
      case 'sql':
        return 'sql'
      case 'yaml':
      case 'yml':
        return 'yaml'
      case 'xml':
        return 'xml'
      case 'sh':
        return 'bash'
      default:
        return 'text'
    }
  }

  const handleSave = async () => {
    if (!onFileUpdate) return
    
    setIsSaving(true)
    try {
      await onFileUpdate(file, editContent)
      setIsEditing(false)
      toast.success('文件保存成功')
    } catch (error: any) {
      toast.error(`保存失败: ${error.message}`)
    } finally {
      setIsSaving(false)
    }
  }

  const handleCopy = () => {
    if (file.content) {
      navigator.clipboard.writeText(file.content)
      toast.success('内容已复制到剪贴板')
    }
  }

  const handleDownload = () => {
    if (file.content) {
      const blob = new Blob([file.content], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('文件下载开始')
    }
  }

  const renderContent = () => {
    if (file.is_binary) {
      const ext = file.name.split('.').pop()?.toLowerCase()
      const isImage = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext || '')
      
      if (isImage) {
        return (
          <div className="flex items-center justify-center h-64 bg-gray-50">
            <div className="text-center">
              <ImageIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">图片文件预览暂不支持</p>
              <button
                onClick={handleDownload}
                className="mt-2 btn btn-sm btn-primary"
              >
                <Download className="w-4 h-4 mr-2" />
                下载查看
              </button>
            </div>
          </div>
        )
      }
      
      return (
        <div className="flex items-center justify-center h-64 bg-gray-50">
          <div className="text-center">
            <File className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">二进制文件无法预览</p>
            <button
              onClick={handleDownload}
              className="mt-2 btn btn-sm btn-primary"
            >
              <Download className="w-4 h-4 mr-2" />
              下载文件
            </button>
          </div>
        </div>
      )
    }

    if (!file.content) {
      return (
        <div className="flex items-center justify-center h-64 bg-gray-50">
          <div className="text-center">
            <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">文件内容为空</p>
          </div>
        </div>
      )
    }

    if (isEditing) {
      return (
        <textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          className="w-full h-96 p-4 font-mono text-sm border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          placeholder="输入文件内容..."
        />
      )
    }

    const language = getLanguage(file.name)
    
    return (
      <div className="relative">
        <SyntaxHighlighter
          language={language}
          style={vscDarkPlus}
          customStyle={{
            margin: 0,
            borderRadius: '0.5rem',
            fontSize: '0.875rem',
            maxHeight: '24rem',
          }}
          showLineNumbers
          wrapLines
        >
          {file.content}
        </SyntaxHighlighter>
      </div>
    )
  }

  return (
    <div className={cn("bg-white border border-gray-200 rounded-lg", className)}>
      {/* 文件头部信息 */}
      <div className="border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-lg">{getFileTypeIcon(file.name)}</span>
            <div>
              <h3 className="text-sm font-medium text-gray-900">{file.name}</h3>
              <div className="flex items-center space-x-4 text-xs text-gray-500 mt-1">
                <span>{file.path}</span>
                {file.size && <span>{formatFileSize(file.size)}</span>}
                <span>修改于 {formatRelativeTime(file.modified_at)}</span>
                {file.created_by && <span>创建者: {file.created_by}</span>}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {!file.is_binary && (
              <>
                <button
                  onClick={handleCopy}
                  className="btn btn-ghost btn-sm"
                  title="复制内容"
                >
                  <Copy className="w-4 h-4" />
                </button>
                
                {isEditing ? (
                  <>
                    <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className="btn btn-primary btn-sm"
                    >
                      <Save className="w-4 h-4 mr-1" />
                      {isSaving ? '保存中...' : '保存'}
                    </button>
                    <button
                      onClick={() => {
                        setIsEditing(false)
                        setEditContent(file.content || '')
                      }}
                      className="btn btn-ghost btn-sm"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="btn btn-ghost btn-sm"
                    title="编辑文件"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                )}
              </>
            )}
            
            <button
              onClick={handleDownload}
              className="btn btn-ghost btn-sm"
              title="下载文件"
            >
              <Download className="w-4 h-4" />
            </button>

            {onClose && (
              <button
                onClick={onClose}
                className="btn btn-ghost btn-sm"
                title="关闭"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 文件内容 */}
      <div className="p-4">
        {renderContent()}
      </div>
    </div>
  )
}