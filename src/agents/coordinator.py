"""Coordinator智能体实现

开发Coordinator智能体，支持任务创建和工作空间初始化。
"""

import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from ..core.base_agent import SimpleAgent, AgentInput, AgentOutput
from ..models.types import AgentType, TaskType
from ..models.workspace import GlobalState, TaskStatus
from ..core.workspace import workspace_manager
from ..llm.service import get_llm_service
from ..config.logging_config import get_logger

logger = get_logger("coordinator_agent")


class CoordinatorAgent(SimpleAgent):
    """Coordinator智能体
    
    负责任务创建、工作空间初始化和任务协调。
    """
    
    def __init__(self, global_state: GlobalState):
        super().__init__(AgentType.COORDINATOR, global_state)
        self.llm_service = get_llm_service()
        
        # Coordinator智能体可用的工具
        self.available_tools = [
            "file_write",
            "workspace_create",
            "task_initialize",
            "knowledge_search"
        ]
    
    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：加载用户请求和系统配置"""
        logger.info("Coordinator智能体开始加载阶段")
        
        # 获取全局上下文
        context = self.get_context_from_global_state()
        
        # 解析用户请求
        user_request = input_data.data.get('user_request', '')
        task_type_str = input_data.data.get('task_type', 'test_case_generation')
        
        # 转换任务类型
        try:
            task_type = TaskType.from_string(task_type_str)
        except ValueError:
            task_type = TaskType.TEST_CASE_GENERATION
        
        # 构建状态
        state = {
            'input_data': input_data.data,
            'context': context,
            'user_request': user_request,
            'task_type': task_type,
            'prompt_template': self.get_prompt_template(),
            'available_tools': self.available_tools,
            'metadata': input_data.metadata or {},
            'task_created': False,
            'workspace_initialized': False,
            'task_id': None,
            'task_metadata': None
        }
        
        logger.info(f"Coordinator智能体加载完成，用户请求: {user_request[:100]}...")
        return state
    
    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM阶段：分析请求，创建任务目录"""
        logger.info("Coordinator智能体进入LLM阶段")
        
        user_request = state.get('user_request', '')
        task_type = state.get('task_type', TaskType.TEST_CASE_GENERATION)
        
        # 构建任务分析提示
        analysis_prompt = f"""
作为Coordinator智能体，你需要分析用户请求并创建相应的任务。

## 用户请求
{user_request}

## 任务类型
{task_type.value}

## 分析要求
1. 理解用户的具体需求
2. 提取关键信息和约束条件
3. 生成合适的任务标题和描述
4. 确定任务的优先级和复杂度
5. 识别可能需要的资源和工具

请分析用户请求并提供以下信息：
- 任务标题（简洁明确）
- 任务描述（详细说明）
- 关键需求点
- 预期交付物
- 建议的执行步骤

分析结果：
"""
        
        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": analysis_prompt}
            ]
            
            response = self.llm_service.invoke_sync(messages, agent_type=self.agent_type)
            analysis_result = response.content.strip()
            
            # 解析分析结果，提取任务信息
            task_info = self._parse_analysis_result(analysis_result, user_request)
            
            # 创建任务工作空间
            task_metadata = workspace_manager.create_task_workspace(
                title=task_info['title'],
                description=task_info['description'],
                task_type=task_type
            )
            
            # 初始化全局状态
            self.global_state.initialize_task(task_metadata)
            
            state['llm_output'] = {
                'analysis': analysis_result,
                'task_info': task_info,
                'task_metadata': task_metadata,
                'task_created': True,
                'workspace_initialized': True
            }
            
            # 更新状态
            state['task_created'] = True
            state['workspace_initialized'] = True
            state['task_id'] = task_metadata.task_id
            state['task_metadata'] = task_metadata
            
            logger.info(f"任务创建成功，任务ID: {task_metadata.task_id}")
            
        except Exception as e:
            logger.error(f"LLM阶段出错: {e}")
            state['llm_output'] = {
                'analysis': f'分析失败: {str(e)}',
                'task_info': {},
                'task_metadata': None,
                'task_created': False,
                'workspace_initialized': False,
                'error': str(e)
            }
        
        return state
    
    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：根据任务创建结果决定下一步"""
        logger.info("Coordinator智能体进入路由阶段")
        
        llm_output = state.get('llm_output', {})
        task_created = llm_output.get('task_created', False)
        task_metadata = llm_output.get('task_metadata')
        
        # 决定下一个智能体
        next_agent = None
        if task_created and task_metadata:
            # 任务创建成功，检查是否需要背景调查
            user_request = state.get('user_request', '')
            if self._needs_background_investigation(user_request):
                next_agent = "background_investigator"
            else:
                next_agent = "planner"
        
        # 更新全局状态
        if task_metadata:
            self.update_global_state({
                'step': 1,
                'last_output': f"任务已创建: {task_metadata.task_id}"
            })
        
        return AgentOutput(
            data={
                'analysis': llm_output.get('analysis', ''),
                'task_info': llm_output.get('task_info', {}),
                'task_metadata': task_metadata.dict() if task_metadata else None,
                'task_created': task_created,
                'workspace_initialized': llm_output.get('workspace_initialized', False)
            },
            next_agent=next_agent,
            metadata={
                'agent': self.name,
                'phase_completed': True,
                'task_id': task_metadata.task_id if task_metadata else None
            }
        )
    
    def get_prompt_template(self) -> str:
        """获取Coordinator智能体的提示词模板"""
        return """你是一个专业的任务协调智能体(Coordinator)，负责任务创建和工作空间初始化。

## 你的核心能力
1. 用户需求分析和理解
2. 任务创建和工作空间管理
3. 任务优先级和复杂度评估
4. 资源需求识别和规划

## 工作职责
1. 接收和分析用户请求
2. 创建结构化的任务定义
3. 初始化任务工作空间
4. 确定任务执行路径和下一步行动

## 分析维度
- 需求明确性：用户需求是否清晰明确
- 技术复杂度：任务的技术实现难度
- 资源需求：需要的工具、数据和人力资源
- 时间估算：预期的完成时间
- 风险评估：可能遇到的问题和挑战

## 输出要求
- 清晰的任务标题和描述
- 详细的需求分析
- 合理的执行建议
- 完整的工作空间初始化

请专业地分析用户请求并创建高质量的任务定义。
"""
    
    def _parse_analysis_result(self, analysis: str, user_request: str) -> Dict[str, Any]:
        """解析分析结果，提取任务信息"""
        # 简单的解析逻辑，实际可以更复杂
        lines = analysis.split('\n')
        
        task_info = {
            'title': '智能测试任务',
            'description': user_request,
            'key_requirements': [],
            'deliverables': [],
            'suggested_steps': []
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 识别不同的部分
            if '任务标题' in line or '标题' in line:
                current_section = 'title'
                # 提取标题
                if ':' in line:
                    title = line.split(':', 1)[1].strip()
                    if title:
                        task_info['title'] = title
            elif '任务描述' in line or '描述' in line:
                current_section = 'description'
            elif '关键需求' in line or '需求点' in line:
                current_section = 'requirements'
            elif '预期交付' in line or '交付物' in line:
                current_section = 'deliverables'
            elif '执行步骤' in line or '建议步骤' in line:
                current_section = 'steps'
            elif line.startswith('-') or line.startswith('•'):
                # 列表项
                item = line[1:].strip()
                if current_section == 'requirements':
                    task_info['key_requirements'].append(item)
                elif current_section == 'deliverables':
                    task_info['deliverables'].append(item)
                elif current_section == 'steps':
                    task_info['suggested_steps'].append(item)
            elif current_section == 'description' and not any(keyword in line for keyword in ['标题', '需求', '交付', '步骤']):
                # 描述内容
                if task_info['description'] == user_request:
                    task_info['description'] = line
                else:
                    task_info['description'] += ' ' + line
        
        # 确保有基本信息
        if not task_info['key_requirements']:
            task_info['key_requirements'] = ['根据用户需求生成测试用例', '确保测试覆盖率', '提供详细的测试报告']
        
        if not task_info['deliverables']:
            task_info['deliverables'] = ['测试用例文档', '测试脚本', '执行结果报告']
        
        if not task_info['suggested_steps']:
            task_info['suggested_steps'] = ['需求分析', '测试用例设计', '脚本开发', '执行测试', '结果分析']
        
        return task_info
    
    def _needs_background_investigation(self, user_request: str) -> bool:
        """判断是否需要背景调查"""
        # 检查请求中是否包含需要调查的关键词
        investigation_keywords = [
            '研究', '调查', '分析', '了解', '背景', '资料',
            'research', 'investigate', 'analyze', 'background'
        ]
        
        user_request_lower = user_request.lower()
        return any(keyword in user_request_lower for keyword in investigation_keywords)


def create_coordinator_agent(global_state: GlobalState) -> CoordinatorAgent:
    """创建Coordinator智能体实例"""
    return CoordinatorAgent(global_state)