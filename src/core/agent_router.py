"""智能体路由和消息传递机制

实现智能体间的消息传递和路由机制，支持动态路由决策和状态管理。
"""

from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass
import logging

from ..models.types import AgentType
from ..models.workspace import GlobalState
from .base_agent import BaseAgent, AgentInput, AgentOutput


class RoutingStrategy(Enum):
    """路由策略枚举"""
    SEQUENTIAL = "sequential"  # 顺序路由
    CONDITIONAL = "conditional"  # 条件路由
    PARALLEL = "parallel"  # 并行路由
    DYNAMIC = "dynamic"  # 动态路由


@dataclass
class RoutingRule:
    """路由规则"""
    from_agent: str
    to_agent: str
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    priority: int = 0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Message:
    """智能体间消息"""
    from_agent: str
    to_agent: str
    data: Dict[str, Any]
    message_type: str = "data"
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentRouter:
    """智能体路由器
    
    负责管理智能体间的路由规则和消息传递。
    """
    
    def __init__(self, global_state: GlobalState):
        self.global_state = global_state
        self.agents: Dict[str, BaseAgent] = {}
        self.routing_rules: List[RoutingRule] = []
        self.message_queue: List[Message] = []
        self.routing_history: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)
    
    def register_agent(self, agent: BaseAgent):
        """注册智能体"""
        self.agents[agent.name] = agent
        self.logger.info(f"注册智能体: {agent.name}")
    
    def add_routing_rule(self, rule: RoutingRule):
        """添加路由规则"""
        self.routing_rules.append(rule)
        # 按优先级排序
        self.routing_rules.sort(key=lambda r: r.priority, reverse=True)
        self.logger.info(f"添加路由规则: {rule.from_agent} -> {rule.to_agent}")
    
    def route_message(self, from_agent: str, output: AgentOutput) -> Optional[str]:
        """路由消息到下一个智能体
        
        Args:
            from_agent: 源智能体名称
            output: 智能体输出
            
        Returns:
            下一个智能体名称，如果没有则返回None
        """
        # 1. 检查输出中是否明确指定了下一个智能体
        if output.next_agent:
            if output.next_agent in self.agents:
                self.logger.info(f"明确路由: {from_agent} -> {output.next_agent}")
                return output.next_agent
            else:
                self.logger.warning(f"指定的智能体不存在: {output.next_agent}")
        
        # 2. 根据路由规则进行路由
        for rule in self.routing_rules:
            if rule.from_agent == from_agent:
                # 检查条件
                if rule.condition is None or rule.condition(output.data):
                    if rule.to_agent in self.agents:
                        self.logger.info(f"规则路由: {from_agent} -> {rule.to_agent}")
                        return rule.to_agent
        
        # 3. 默认路由逻辑
        next_agent = self._get_default_next_agent(from_agent, output)
        if next_agent:
            self.logger.info(f"默认路由: {from_agent} -> {next_agent}")
        else:
            self.logger.info(f"路由结束: {from_agent}")
        
        return next_agent
    
    def _get_default_next_agent(self, from_agent: str, output: AgentOutput) -> Optional[str]:
        """获取默认的下一个智能体"""
        # 基于智能体类型的默认路由序列
        default_sequence = [
            "coordinator",
            "planner",
            "researcher", 
            "tester",
            "coder",
            "executor",
            "reviewer",
            "reporter"
        ]
        
        try:
            current_index = default_sequence.index(from_agent)
            if current_index < len(default_sequence) - 1:
                next_agent_name = default_sequence[current_index + 1]
                if next_agent_name in self.agents:
                    return next_agent_name
        except ValueError:
            pass
        
        return None
    
    def send_message(self, message: Message):
        """发送消息"""
        self.message_queue.append(message)
        self.logger.info(f"消息入队: {message.from_agent} -> {message.to_agent}")
    
    def get_messages_for_agent(self, agent_name: str) -> List[Message]:
        """获取指定智能体的消息"""
        messages = [msg for msg in self.message_queue if msg.to_agent == agent_name]
        # 从队列中移除已获取的消息
        self.message_queue = [msg for msg in self.message_queue if msg.to_agent != agent_name]
        return messages
    
    def execute_workflow(self, start_agent: str, initial_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行工作流
        
        Args:
            start_agent: 起始智能体名称
            initial_data: 初始数据
            
        Returns:
            工作流执行结果
        """
        current_agent = start_agent
        current_data = initial_data
        execution_history = []
        
        while current_agent and current_agent in self.agents:
            self.logger.info(f"执行智能体: {current_agent}")
            
            # 获取智能体
            agent = self.agents[current_agent]
            
            # 准备输入
            agent_input = AgentInput(
                data=current_data,
                metadata={'execution_step': len(execution_history)}
            )
            
            # 执行智能体
            output = agent.execute(agent_input)
            
            # 记录执行历史
            execution_step = {
                'agent': current_agent,
                'input': current_data,
                'output': output.data,
                'error': output.error,
                'metadata': output.metadata
            }
            execution_history.append(execution_step)
            self.routing_history.append(execution_step)
            
            # 检查是否有错误
            if output.error:
                self.logger.error(f"智能体执行出错: {current_agent} - {output.error}")
                break
            
            # 路由到下一个智能体
            next_agent = self.route_message(current_agent, output)
            
            # 更新数据和智能体
            current_data = output.data
            current_agent = next_agent
        
        return {
            'execution_history': execution_history,
            'final_data': current_data,
            'completed': current_agent is None,
            'routing_history': self.routing_history
        }
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        """获取路由统计信息"""
        if not self.routing_history:
            return {}
        
        agent_counts = {}
        error_counts = {}
        
        for step in self.routing_history:
            agent = step['agent']
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            
            if step.get('error'):
                error_counts[agent] = error_counts.get(agent, 0) + 1
        
        return {
            'total_steps': len(self.routing_history),
            'agent_execution_counts': agent_counts,
            'agent_error_counts': error_counts,
            'success_rate': 1 - (sum(error_counts.values()) / len(self.routing_history))
        }
    
    def clear_history(self):
        """清空路由历史"""
        self.routing_history.clear()
        self.message_queue.clear()


class ConditionalRouter:
    """条件路由器
    
    基于条件表达式进行智能体路由决策。
    """
    
    def __init__(self):
        self.conditions: Dict[str, Callable[[Dict[str, Any]], str]] = {}
    
    def add_condition(self, name: str, condition_func: Callable[[Dict[str, Any]], str]):
        """添加条件函数
        
        Args:
            name: 条件名称
            condition_func: 条件函数，接收数据返回下一个智能体名称
        """
        self.conditions[name] = condition_func
    
    def evaluate(self, condition_name: str, data: Dict[str, Any]) -> Optional[str]:
        """评估条件
        
        Args:
            condition_name: 条件名称
            data: 评估数据
            
        Returns:
            下一个智能体名称
        """
        if condition_name in self.conditions:
            try:
                return self.conditions[condition_name](data)
            except Exception as e:
                logging.error(f"条件评估失败: {condition_name} - {e}")
        return None


# 预定义的路由条件函数
def task_type_router(data: Dict[str, Any]) -> str:
    """基于任务类型的路由"""
    task_type = data.get('task_type', '')
    
    if 'test_case' in task_type:
        return 'tester'
    elif 'code' in task_type:
        return 'coder'
    elif 'review' in task_type:
        return 'reviewer'
    else:
        return 'planner'


def completion_status_router(data: Dict[str, Any]) -> Optional[str]:
    """基于完成状态的路由"""
    if data.get('completed', False):
        return 'reporter'
    elif data.get('needs_review', False):
        return 'reviewer'
    elif data.get('has_errors', False):
        return 'coordinator'  # 返回协调器处理错误
    else:
        return None  # 继续当前流程


def error_handling_router(data: Dict[str, Any]) -> str:
    """错误处理路由"""
    error_type = data.get('error_type', '')
    
    if error_type == 'llm_error':
        return 'coordinator'  # 协调器处理LLM错误
    elif error_type == 'tool_error':
        return 'reviewer'  # 评审员分析工具错误
    elif error_type == 'validation_error':
        return 'planner'  # 规划器重新规划
    else:
        return 'coordinator'  # 默认返回协调器