import React, { useState } from 'react'
import { Save, RefreshCw, Plus, Trash2, Settings, Bot, Plug, Shield } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { cn } from '@/lib/utils'

// 配置验证模式
const llmConfigSchema = z.object({
  provider: z.string().min(1, '请选择LLM提供商'),
  model: z.string().min(1, '请输入模型名称'),
  temperature: z.number().min(0).max(2),
  max_tokens: z.number().min(1).max(32000),
  timeout: z.number().min(1).max(300),
  api_key: z.string().optional(),
})

const mcpServerSchema = z.object({
  name: z.string().min(1, '请输入服务器名称'),
  connection_type: z.enum(['stdio', 'sse']),
  command: z.string().optional(),
  args: z.array(z.string()).optional(),
  url: z.string().optional(),
  headers: z.record(z.string()).optional(),
  env: z.record(z.string()).optional(),
  disabled: z.boolean(),
})

type LLMConfigForm = z.infer<typeof llmConfigSchema>
type MCPServerForm = z.infer<typeof mcpServerSchema>

const LLM_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: '通义千问 (Qwen)' },
  { value: 'kimi', label: 'Kimi (月之暗面)' },
  { value: 'doubao', label: '豆包 (字节跳动)' },
  { value: 'zhipu', label: '智谱AI (GLM)' },
  { value: 'baichuan', label: '百川智能' },
  { value: 'local', label: '本地模型' },
]

const OPENAI_MODELS = [
  'gpt-4',
  'gpt-4-turbo',
  'gpt-3.5-turbo',
  'gpt-3.5-turbo-16k',
]

const ANTHROPIC_MODELS = [
  'claude-3-opus-20240229',
  'claude-3-sonnet-20240229',
  'claude-3-haiku-20240307',
]

const DEEPSEEK_MODELS = [
  'deepseek-chat',
  'deepseek-coder',
  'deepseek-v2.5',
  'deepseek-v3',
]

const QWEN_MODELS = [
  'qwen-turbo',
  'qwen-plus',
  'qwen-max',
  'qwen-max-longcontext',
  'qwen2.5-72b-instruct',
  'qwen2.5-32b-instruct',
  'qwen2.5-14b-instruct',
  'qwen2.5-7b-instruct',
]

const KIMI_MODELS = [
  'moonshot-v1-8k',
  'moonshot-v1-32k',
  'moonshot-v1-128k',
]

const DOUBAO_MODELS = [
  'doubao-lite-4k',
  'doubao-lite-32k',
  'doubao-lite-128k',
  'doubao-pro-4k',
  'doubao-pro-32k',
  'doubao-pro-128k',
]

const ZHIPU_MODELS = [
  'glm-4',
  'glm-4-air',
  'glm-4-airx',
  'glm-4-flash',
  'glm-3-turbo',
]

const BAICHUAN_MODELS = [
  'baichuan2-turbo',
  'baichuan2-turbo-192k',
  'baichuan3-turbo',
  'baichuan3-turbo-128k',
]

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState('llm')
  const [mcpServers, setMcpServers] = useState<MCPServerForm[]>([])
  const [showAddServer, setShowAddServer] = useState(false)

  // LLM配置表单
  const llmForm = useForm<LLMConfigForm>({
    resolver: zodResolver(llmConfigSchema),
    defaultValues: {
      provider: 'openai',
      model: 'gpt-3.5-turbo',
      temperature: 0.7,
      max_tokens: 2000,
      timeout: 60,
    },
  })

  // MCP服务器表单
  const mcpForm = useForm<MCPServerForm>({
    resolver: zodResolver(mcpServerSchema),
    defaultValues: {
      name: '',
      connection_type: 'stdio',
      disabled: false,
    },
  })

  const selectedProvider = llmForm.watch('provider')

  const getModelOptions = () => {
    switch (selectedProvider) {
      case 'openai':
        return OPENAI_MODELS
      case 'anthropic':
        return ANTHROPIC_MODELS
      case 'deepseek':
        return DEEPSEEK_MODELS
      case 'qwen':
        return QWEN_MODELS
      case 'kimi':
        return KIMI_MODELS
      case 'doubao':
        return DOUBAO_MODELS
      case 'zhipu':
        return ZHIPU_MODELS
      case 'baichuan':
        return BAICHUAN_MODELS
      default:
        return []
    }
  }

  const handleSaveLLMConfig = async (data: LLMConfigForm) => {
    try {
      // 这里应该调用API保存配置
      console.log('保存LLM配置:', data)
      toast.success('LLM配置已保存')
    } catch (error) {
      toast.error('保存配置失败')
    }
  }

  const handleAddMCPServer = (data: MCPServerForm) => {
    setMcpServers(prev => [...prev, { ...data }])
    mcpForm.reset()
    setShowAddServer(false)
    toast.success('MCP服务器已添加')
  }

  const handleRemoveMCPServer = (index: number) => {
    setMcpServers(prev => prev.filter((_, i) => i !== index))
    toast.success('MCP服务器已删除')
  }

  const handleToggleServer = (index: number) => {
    setMcpServers(prev => prev.map((server, i) => 
      i === index ? { ...server, disabled: !server.disabled } : server
    ))
  }

  const tabs = [
    { id: 'llm', label: 'LLM配置', icon: Bot },
    { id: 'mcp', label: 'MCP工具', icon: Plug },
    { id: 'collaboration', label: '协作设置', icon: Settings },
    { id: 'security', label: '安全设置', icon: Shield },
  ]

  return (
    <div className="flex h-full bg-gray-50">
      {/* 侧边栏 */}
      <div className="w-64 bg-white border-r border-gray-200">
        <div className="p-6">
          <h1 className="text-xl font-bold text-gray-900">系统设置</h1>
          <p className="text-sm text-gray-600 mt-1">
            配置TestAgent的各项参数
          </p>
        </div>
        
        <nav className="px-4 space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "w-full flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors",
                  activeTab === tab.id
                    ? "bg-primary-50 text-primary-700 border-r-2 border-primary-600"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                )}
              >
                <Icon className="w-5 h-5 mr-3" />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'llm' && (
          <div className="p-8">
            <div className="max-w-2xl">
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">LLM配置</h2>
                <p className="text-gray-600">
                  配置大语言模型的提供商和参数设置
                </p>
              </div>

              <form onSubmit={llmForm.handleSubmit(handleSaveLLMConfig)} className="space-y-6">
                {/* 提供商选择 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    LLM提供商
                  </label>
                  <select
                    {...llmForm.register('provider')}
                    className="input"
                  >
                    {LLM_PROVIDERS.map(provider => (
                      <option key={provider.value} value={provider.value}>
                        {provider.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* 模型选择 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    模型
                  </label>
                  <select
                    {...llmForm.register('model')}
                    className="input"
                  >
                    {getModelOptions().map(model => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>

                {/* API密钥 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    API密钥
                  </label>
                  <input
                    type="password"
                    {...llmForm.register('api_key')}
                    placeholder="输入API密钥"
                    className="input"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    API密钥将被安全存储，不会在界面中显示
                  </p>
                </div>

                {/* 温度参数 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    温度参数: {llmForm.watch('temperature')}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    {...llmForm.register('temperature', { valueAsNumber: true })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>保守 (0)</span>
                    <span>创造性 (2)</span>
                  </div>
                </div>

                {/* 最大令牌数 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    最大令牌数
                  </label>
                  <input
                    type="number"
                    {...llmForm.register('max_tokens', { valueAsNumber: true })}
                    className="input"
                    min="1"
                    max="32000"
                  />
                </div>

                {/* 超时时间 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    超时时间 (秒)
                  </label>
                  <input
                    type="number"
                    {...llmForm.register('timeout', { valueAsNumber: true })}
                    className="input"
                    min="1"
                    max="300"
                  />
                </div>

                <div className="flex items-center space-x-3 pt-6">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={llmForm.formState.isSubmitting}
                  >
                    {llmForm.formState.isSubmitting ? (
                      <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Save className="w-4 h-4 mr-2" />
                    )}
                    保存配置
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                  >
                    测试连接
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {activeTab === 'mcp' && (
          <div className="p-8">
            <div className="max-w-4xl">
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">MCP工具配置</h2>
                  <p className="text-gray-600">
                    管理Model Context Protocol工具服务器
                  </p>
                </div>
                <button
                  onClick={() => setShowAddServer(true)}
                  className="btn btn-primary"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  添加服务器
                </button>
              </div>

              {/* MCP服务器列表 */}
              <div className="space-y-4">
                {mcpServers.map((server, index) => (
                  <div
                    key={index}
                    className="bg-white rounded-lg border border-gray-200 p-6"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <h3 className="text-lg font-medium text-gray-900">
                            {server.name}
                          </h3>
                          <span className={cn(
                            "px-2 py-1 text-xs font-medium rounded-full",
                            server.disabled 
                              ? "bg-gray-100 text-gray-600"
                              : "bg-success-100 text-success-700"
                          )}>
                            {server.disabled ? '已禁用' : '已启用'}
                          </span>
                          <span className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded-full">
                            {server.connection_type.toUpperCase()}
                          </span>
                        </div>
                        
                        <div className="text-sm text-gray-600 space-y-1">
                          {server.connection_type === 'stdio' && server.command && (
                            <div>命令: {server.command} {server.args?.join(' ')}</div>
                          )}
                          {server.connection_type === 'sse' && server.url && (
                            <div>URL: {server.url}</div>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleToggleServer(index)}
                          className={cn(
                            "btn btn-sm",
                            server.disabled ? "btn-ghost" : "btn-outline"
                          )}
                        >
                          {server.disabled ? '启用' : '禁用'}
                        </button>
                        <button
                          onClick={() => handleRemoveMCPServer(index)}
                          className="btn btn-ghost btn-sm text-error-600 hover:text-error-700"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}

                {mcpServers.length === 0 && (
                  <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
                    <Plug className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 mb-2">
                      暂无MCP服务器
                    </h3>
                    <p className="text-gray-500 mb-6">
                      添加MCP服务器以扩展TestAgent的工具能力
                    </p>
                    <button
                      onClick={() => setShowAddServer(true)}
                      className="btn btn-primary"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      添加服务器
                    </button>
                  </div>
                )}
              </div>

              {/* 添加服务器表单 */}
              {showAddServer && (
                <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
                  <div className="bg-white rounded-lg p-6 w-full max-w-md">
                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                      添加MCP服务器
                    </h3>
                    
                    <form onSubmit={mcpForm.handleSubmit(handleAddMCPServer)} className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          服务器名称
                        </label>
                        <input
                          {...mcpForm.register('name')}
                          className="input"
                          placeholder="例如: file-operations"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          连接类型
                        </label>
                        <select
                          {...mcpForm.register('connection_type')}
                          className="input"
                        >
                          <option value="stdio">STDIO</option>
                          <option value="sse">SSE</option>
                        </select>
                      </div>

                      {mcpForm.watch('connection_type') === 'stdio' && (
                        <>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              命令
                            </label>
                            <input
                              {...mcpForm.register('command')}
                              className="input"
                              placeholder="例如: uvx"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              参数 (每行一个)
                            </label>
                            <textarea
                              className="textarea"
                              rows={3}
                              placeholder="例如: mcp-server-package"
                            />
                          </div>
                        </>
                      )}

                      {mcpForm.watch('connection_type') === 'sse' && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            URL
                          </label>
                          <input
                            {...mcpForm.register('url')}
                            className="input"
                            placeholder="https://api.example.com/mcp/sse"
                          />
                        </div>
                      )}

                      <div className="flex items-center space-x-3 pt-4">
                        <button
                          type="submit"
                          className="btn btn-primary"
                        >
                          添加
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowAddServer(false)}
                          className="btn btn-ghost"
                        >
                          取消
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'collaboration' && (
          <div className="p-8">
            <div className="max-w-2xl">
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">协作设置</h2>
                <p className="text-gray-600">
                  配置人机协作和自动接受策略
                </p>
              </div>

              <div className="space-y-6">
                <div className="bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">
                    自动接受设置
                  </h3>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        自动接受模式
                      </label>
                      <select className="input">
                        <option value="never">从不自动接受</option>
                        <option value="conditional">条件自动接受</option>
                        <option value="always">总是自动接受</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        置信度阈值: 0.8
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        defaultValue="0.8"
                        className="w-full"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>低 (0)</span>
                        <span>高 (1)</span>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        审查超时时间 (分钟)
                      </label>
                      <input
                        type="number"
                        defaultValue="60"
                        className="input"
                        min="1"
                        max="1440"
                      />
                    </div>
                  </div>
                </div>

                <button className="btn btn-primary">
                  <Save className="w-4 h-4 mr-2" />
                  保存设置
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'security' && (
          <div className="p-8">
            <div className="max-w-2xl">
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">安全设置</h2>
                <p className="text-gray-600">
                  配置系统安全和访问控制
                </p>
              </div>

              <div className="space-y-6">
                <div className="bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">
                    API访问控制
                  </h3>
                  
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">启用API密钥验证</div>
                        <div className="text-sm text-gray-500">要求客户端提供有效的API密钥</div>
                      </div>
                      <input type="checkbox" className="toggle" />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">启用速率限制</div>
                        <div className="text-sm text-gray-500">限制API请求频率</div>
                      </div>
                      <input type="checkbox" className="toggle" defaultChecked />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        每分钟最大请求数
                      </label>
                      <input
                        type="number"
                        defaultValue="60"
                        className="input"
                        min="1"
                        max="1000"
                      />
                    </div>
                  </div>
                </div>

                <button className="btn btn-primary">
                  <Save className="w-4 h-4 mr-2" />
                  保存设置
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}