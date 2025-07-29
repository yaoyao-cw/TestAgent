// 系统相关类型
export interface SystemStatus {
  system: {
    status: string
    version: string
    uptime: number
    timestamp: string
  }
  components: ComponentStatus[]
  resources: SystemResources
  execution_stats: ExecutionStats
}

export interface ComponentStatus {
  name: string
  status: string
  healthy: boolean
  details?: any
  last_check: string
}

export interface SystemResources {
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  network_io: {
    bytes_sent: number
    bytes_recv: number
  }
  process_count: number
}

export interface ExecutionStats {
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  pending_tasks: number
  running_tasks: number
  average_execution_time: number
}

// 任务相关类型
export interface Task {
  task_id: string
  status: string
  task_type?: string
  task_topic?: string
  progress?: number
  current_step?: string
  result?: any
  error?: string
  created_at: string
  updated_at: string
  execution_time?: number
  logs?: string[]
}

export interface TaskSubmissionRequest {
  task_type: string
  task_topic: string
  context?: string
  code_snippets?: string[]
  requirements?: string[]
  locale?: string
  timeout?: number
  config?: any
}

export interface TaskListResponse {
  tasks: Task[]
  total: number
  page: number
  page_size: number
}

// 文档相关类型
export interface Document {
  document_id: string
  filename: string
  file_type: string
  file_size: number
  upload_time: string
  status: string
  chunk_count?: number
  metadata?: any
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
  page: number
  page_size: number
}

export interface DocumentSearchResult {
  document_id: string
  filename: string
  content: string
  score: number
  metadata: any
}

export interface DocumentSearchResponse {
  query: string
  results: DocumentSearchResult[]
  total_results: number
}

// 协作相关类型
export interface Review {
  review_id: string
  plan_id: string
  status: string
  submitted_at: string
  reviewed_at?: string
  reviewer_comment?: string
  plan_data: any
  metadata?: any
}

export interface Feedback {
  feedback_id: string
  target_id: string
  target_type: string
  feedback: string
  feedback_type: string
  priority: string
  status: string
  created_at: string
  processed_at?: string
  result?: any
}

export interface AutoAcceptStatus {
  mode: string
  conditions: any
  statistics: any
}

// 聊天相关类型
export interface ChatMessage {
  id: string
  type: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  metadata?: any
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  created_at: Date
  updated_at: Date
}

// 配置相关类型
export interface LLMConfig {
  provider: string
  model: string
  temperature: number
  max_tokens: number
  timeout: number
  api_key?: string
}

export interface MCPServerConfig {
  name: string
  connection_type: 'stdio' | 'sse'
  command?: string
  args?: string[]
  url?: string
  headers?: Record<string, string>
  env?: Record<string, string>
  disabled: boolean
}

export interface MCPConfig {
  servers: Record<string, MCPServerConfig>
}

export interface AppConfig {
  llm: LLMConfig
  mcp: MCPConfig
  collaboration: {
    auto_accept_mode: string
    review_timeout: number
    confidence_threshold: number
  }
}

// WebSocket相关类型
export interface WebSocketMessage {
  type: string
  data?: any
  timestamp?: string
  [key: string]: any
}

// 工作空间相关类型
export interface WorkspaceFile {
  path: string
  name: string
  type: 'file' | 'directory'
  size?: number
  modified_at: string
  created_by?: string
  content?: string
  is_binary?: boolean
}

export interface WorkspaceStructure {
  task_id: string
  root_path: string
  files: WorkspaceFile[]
  total_files: number
  total_size: number
}

export interface TimelineEvent {
  id: string
  timestamp: string
  event_type: 'agent_start' | 'agent_complete' | 'file_created' | 'file_updated' | 'error' | 'status_change'
  agent_name?: string
  description: string
  details?: any
  file_path?: string
  status?: string
  duration?: number
}

export interface TaskTimeline {
  task_id: string
  events: TimelineEvent[]
  total_events: number
  start_time: string
  end_time?: string
  total_duration?: number
}

// 监控相关类型
export interface PerformanceMetrics {
  kv_cache_hit_rate: number
  average_response_time: number
  total_requests: number
  error_rate: number
  active_connections: number
  memory_usage: number
  cpu_usage: number
}

export interface AgentMetrics {
  agent_name: string
  total_executions: number
  success_rate: number
  average_execution_time: number
  current_status: string
  last_execution: string
}

export interface SystemMetrics {
  performance: PerformanceMetrics
  agents: AgentMetrics[]
  timestamp: string
}

// 通用类型
export interface ApiResponse<T = any> {
  data: T
  message?: string
  success: boolean
}

export interface PaginationParams {
  page: number
  page_size: number
}

export interface FilterParams {
  status?: string
  search?: string
  start_date?: string
  end_date?: string
}

// 表单相关类型
export interface FormField {
  name: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'number' | 'boolean' | 'file'
  required?: boolean
  placeholder?: string
  options?: { label: string; value: any }[]
  validation?: any
}

// 状态管理相关类型
export interface AppState {
  user: any
  config: AppConfig
  currentSession: ChatSession | null
  isConnected: boolean
  systemStatus: SystemStatus | null
}

// 错误类型
export interface ApiError {
  message: string
  code?: string
  details?: any
}

// 导出网络错误处理相关类型
export * from './error'