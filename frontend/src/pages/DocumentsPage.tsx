import React, { useState } from 'react'
import { Upload, Search, FileText, Download, Trash2, RefreshCw } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { cn, formatFileSize, formatDate } from '@/lib/utils'

export function DocumentsPage() {
  const [documents, setDocuments] = useState([])
  const [isUploading, setIsUploading] = useState(false)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: async (acceptedFiles) => {
      setIsUploading(true)
      // 这里处理文件上传
      setTimeout(() => {
        setIsUploading(false)
      }, 2000)
    },
    accept: {
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
  })

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* 页面头部 */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">文档管理</h1>
            <p className="text-gray-600 mt-1">
              上传和管理测试相关文档，支持智能搜索
            </p>
          </div>
          <button className="btn btn-ghost btn-sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </button>
        </div>
      </div>

      <div className="flex-1 p-6">
        {/* 文件上传区域 */}
        <div
          {...getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors mb-6",
            isDragActive 
              ? "border-primary-500 bg-primary-50" 
              : "border-gray-300 hover:border-gray-400"
          )}
        >
          <input {...getInputProps()} />
          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          {isDragActive ? (
            <p className="text-primary-600 font-medium">
              拖放文件到这里...
            </p>
          ) : (
            <div>
              <p className="text-gray-600 font-medium mb-2">
                拖放文件到这里，或点击选择文件
              </p>
              <p className="text-sm text-gray-500">
                支持 PDF, DOC, DOCX, TXT, MD 格式，最大 50MB
              </p>
            </div>
          )}
          {isUploading && (
            <div className="mt-4">
              <div className="inline-flex items-center space-x-2">
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span className="text-sm">上传中...</span>
              </div>
            </div>
          )}
        </div>

        {/* 搜索栏 */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜索文档内容..."
              className="input pl-10"
            />
          </div>
        </div>

        {/* 文档列表 */}
        <div className="bg-white rounded-lg border border-gray-200">
          {documents.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                暂无文档
              </h3>
              <p className="text-gray-500 mb-6">
                上传文档以开始使用智能搜索功能
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {/* 文档列表项 */}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}