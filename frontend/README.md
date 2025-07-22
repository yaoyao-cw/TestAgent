# TestAgent Frontend

TestAgent的现代化Web前端界面，基于React + TypeScript + Tailwind CSS构建。

## 功能特性

### 🎯 核心功能
- **智能对话界面** - 与TestAgent进行自然语言交互
- **任务管理** - 创建、监控和管理测试任务
- **文档管理** - 上传和搜索测试相关文档
- **实时监控** - 系统状态和性能监控
- **配置管理** - LLM和MCP工具配置

### 🚀 技术特性
- **响应式设计** - 支持桌面和移动设备
- **实时通信** - WebSocket支持实时状态更新
- **现代UI** - 基于Tailwind CSS的美观界面
- **类型安全** - 完整的TypeScript支持
- **状态管理** - React Query + Zustand
- **组件化** - 可复用的UI组件

## 技术栈

- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **样式**: Tailwind CSS
- **状态管理**: React Query + Zustand
- **路由**: React Router
- **表单**: React Hook Form + Zod
- **图标**: Lucide React
- **动画**: Framer Motion
- **通信**: Axios + Socket.IO

## 快速开始

### 环境要求

- Node.js 16+
- npm 或 yarn

### 安装依赖

```bash
cd TestAgent/frontend
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

构建文件将输出到 `dist` 目录。

## 项目结构

```
frontend/
├── public/                 # 静态资源
├── src/
│   ├── components/         # 可复用组件
│   │   ├── Layout.tsx     # 布局组件
│   │   ├── TaskCard.tsx   # 任务卡片
│   │   └── CodeBlock.tsx  # 代码块
│   ├── pages/             # 页面组件
│   │   ├── ChatPage.tsx   # 对话页面
│   │   ├── TasksPage.tsx  # 任务管理
│   │   ├── DocumentsPage.tsx # 文档管理
│   │   ├── SettingsPage.tsx  # 系统设置
│   │   └── SystemPage.tsx    # 系统监控
│   ├── hooks/             # 自定义Hooks
│   │   ├── useTasks.ts    # 任务相关
│   │   ├── useWebSocket.ts # WebSocket
│   │   └── useSystemStatus.ts # 系统状态
│   ├── lib/               # 工具库
│   │   ├── api.ts         # API客户端
│   │   └── utils.ts       # 工具函数
│   ├── types/             # 类型定义
│   │   └── index.ts       # 全局类型
│   ├── App.tsx            # 主应用组件
│   ├── main.tsx           # 应用入口
│   └── index.css          # 全局样式
├── package.json
├── vite.config.ts         # Vite配置
├── tailwind.config.js     # Tailwind配置
└── tsconfig.json          # TypeScript配置
```

## 页面说明

### 对话页面 (ChatPage)
- 与TestAgent进行自然语言对话
- 支持创建测试任务
- 实时显示任务状态
- 消息历史记录

### 任务管理 (TasksPage)
- 查看所有任务列表
- 过滤和搜索任务
- 监控任务执行状态
- 取消和重试任务

### 文档管理 (DocumentsPage)
- 拖拽上传文档
- 智能文档搜索
- 文档预览和下载
- 支持多种格式

### 系统设置 (SettingsPage)
- **LLM配置**: 配置语言模型提供商和参数
- **MCP工具**: 管理Model Context Protocol工具
- **协作设置**: 配置人机协作策略
- **安全设置**: API访问控制和安全配置

### 系统监控 (SystemPage)
- 实时系统状态
- 资源使用监控
- 组件健康状态
- 执行统计信息

## 组件说明

### Layout组件
- 响应式侧边栏导航
- 系统状态指示器
- 移动端适配

### TaskCard组件
- 任务状态展示
- 进度条显示
- 实时状态更新
- 操作按钮

### CodeBlock组件
- 语法高亮
- 代码复制功能
- 多语言支持
- 行号显示

## API集成

前端通过以下方式与后端通信：

### HTTP API
- 使用Axios进行HTTP请求
- 自动错误处理和重试
- 请求/响应拦截器
- 类型安全的API调用

### WebSocket
- 实时任务状态更新
- 系统事件通知
- 自动重连机制
- 消息类型验证

## 状态管理

### React Query
- 服务器状态管理
- 自动缓存和同步
- 后台更新
- 乐观更新

### Zustand (可选)
- 客户端状态管理
- 简单的状态存储
- 类型安全

## 样式系统

### Tailwind CSS
- 实用优先的CSS框架
- 响应式设计
- 深色模式支持
- 自定义主题

### 组件样式
- 可复用的样式类
- 一致的设计系统
- 动画和过渡效果

## 开发指南

### 添加新页面

1. 在 `src/pages/` 创建页面组件
2. 在 `App.tsx` 中添加路由
3. 在 `Layout.tsx` 中添加导航项

### 添加新组件

1. 在 `src/components/` 创建组件
2. 使用TypeScript定义Props类型
3. 添加适当的样式类

### 添加新API

1. 在 `src/lib/api.ts` 中添加API方法
2. 在 `src/types/` 中定义类型
3. 创建对应的React Hook

### 样式规范

- 使用Tailwind CSS类名
- 遵循响应式设计原则
- 保持一致的间距和颜色
- 使用语义化的组件类

## 部署

### 开发环境
```bash
npm run dev
```

### 生产环境
```bash
# 构建
npm run build

# 预览
npm run preview
```

### Docker部署
```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## 环境变量

创建 `.env` 文件：

```bash
# API基础URL
VITE_API_BASE_URL=http://localhost:8000

# WebSocket URL
VITE_WS_URL=ws://localhost:8000

# 应用配置
VITE_APP_TITLE=TestAgent
VITE_APP_VERSION=1.0.0
```

## 故障排除

### 常见问题

1. **API连接失败**
   - 检查后端服务是否运行
   - 确认API URL配置正确
   - 检查CORS设置

2. **WebSocket连接失败**
   - 检查WebSocket URL
   - 确认防火墙设置
   - 检查代理配置

3. **构建失败**
   - 清理node_modules重新安装
   - 检查TypeScript类型错误
   - 确认依赖版本兼容性

### 调试技巧

- 使用浏览器开发者工具
- 检查Network面板的API请求
- 查看Console面板的错误信息
- 使用React Developer Tools

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

### 代码规范

- 使用ESLint和Prettier
- 遵循TypeScript最佳实践
- 编写有意义的提交信息
- 添加适当的注释

## 许可证

MIT License