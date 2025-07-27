"""智能体工厂

提供统一的智能体创建和管理接口。
"""

from typing import Dict, Any, Optional, Type, Union, List
from ..models.types import AgentType
from ..models.workspace import GlobalState
from ..core.base_agent import BaseAgent

from .coordinator import CoordinatorAgent, create_coordinator_agent
from .planner import PlannerAgent, create_planner_agent
from .test_team import TestTeamRouter, create_test_team_router
from .tester import TesterAgent, create_tester_agent
from .coder import CoderAgent, create_coder_agent
from .executor import ExecutorAgent, create_executor_agent
from .reviewer import ReviewerAgent, create_reviewer_agent
from .reporter import ReporterAgent, create_reporter_agent
from .human import HumanAgent, create_human_agent

from ..config.logging_config import get_logger

logger = get_logger("agent_factory")


class AgentFactory:
    """智能体工厂类

    负责创建和管理所有智能体实例。
    """

    def __init__(self):
        # 智能体类型映射
        self.agent_classes = {
            AgentType.COORDINATOR: CoordinatorAgent,
            AgentType.PLANNER: PlannerAgent,
            AgentType.REVIEWER: ReviewerAgent,
            AgentType.REPORTER: ReporterAgent,
            "test_team": TestTeamRouter,  # 特殊的路由器
            "tester": TesterAgent,
            "coder": CoderAgent,
            "executor": ExecutorAgent,
            "human": HumanAgent,
        }

        # 智能体创建函数映射
        self.agent_creators = {
            AgentType.COORDINATOR: create_coordinator_agent,
            AgentType.PLANNER: create_planner_agent,
            AgentType.REVIEWER: create_reviewer_agent,
            AgentType.REPORTER: create_reporter_agent,
            "test_team": create_test_team_router,
            "tester": create_tester_agent,
            "coder": create_coder_agent,
            "executor": create_executor_agent,
            "human": create_human_agent,
        }

        # 智能体实例缓存
        self.agent_cache: Dict[str, BaseAgent] = {}

    def create_agent(
        self, agent_type: Union[AgentType, str], global_state: GlobalState
    ) -> Optional[BaseAgent]:
        """创建智能体实例

        Args:
            agent_type: 智能体类型
            global_state: 全局状态

        Returns:
            智能体实例，如果创建失败返回None
        """
        try:
            # 标准化智能体类型
            if isinstance(agent_type, str):
                agent_key = agent_type.lower()
            else:
                agent_key = agent_type

            # 检查缓存
            cache_key = f"{agent_key}_{id(global_state)}"
            if cache_key in self.agent_cache:
                logger.debug(f"从缓存返回智能体: {agent_key}")
                return self.agent_cache[cache_key]

            # 创建新实例
            if agent_key in self.agent_creators:
                creator_func = self.agent_creators[agent_key]
                agent = creator_func(global_state)

                # 缓存实例
                self.agent_cache[cache_key] = agent

                logger.info(f"成功创建智能体: {agent_key}")
                return agent
            else:
                logger.error(f"未知的智能体类型: {agent_key}")
                return None

        except Exception as e:
            logger.error(f"创建智能体失败: {agent_type}, 错误: {e}")
            return None

    def get_agent_info(self, agent_type: Union[AgentType, str]) -> Dict[str, Any]:
        """获取智能体信息

        Args:
            agent_type: 智能体类型

        Returns:
            智能体信息字典
        """
        # 标准化智能体类型
        if isinstance(agent_type, str):
            agent_key = agent_type.lower()
        else:
            agent_key = agent_type

        if agent_key in self.agent_classes:
            agent_class = self.agent_classes[agent_key]
            return {
                "name": agent_class.__name__,
                "type": str(agent_key),
                "description": agent_class.__doc__ or "无描述",
                "available": True,
            }
        else:
            return {
                "name": "Unknown",
                "type": str(agent_key),
                "description": "未知智能体类型",
                "available": False,
            }

    def list_available_agents(self) -> List[Dict[str, Any]]:
        """列出所有可用的智能体

        Returns:
            智能体信息列表
        """
        agents = []
        for agent_key in self.agent_classes.keys():
            agent_info = self.get_agent_info(agent_key)
            agents.append(agent_info)

        return agents

    def clear_cache(self):
        """清空智能体缓存"""
        self.agent_cache.clear()
        logger.info("智能体缓存已清空")

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息

        Returns:
            缓存统计信息
        """
        return {
            "cached_agents": len(self.agent_cache),
            "cache_keys": list(self.agent_cache.keys()),
            "available_types": list(self.agent_classes.keys()),
        }


# 全局智能体工厂实例
_agent_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """获取智能体工厂单例

    Returns:
        智能体工厂实例
    """
    global _agent_factory
    if _agent_factory is None:
        _agent_factory = AgentFactory()
    return _agent_factory


def create_agent(
    agent_type: Union[AgentType, str], global_state: GlobalState
) -> Optional[BaseAgent]:
    """便捷的智能体创建函数

    Args:
        agent_type: 智能体类型
        global_state: 全局状态

    Returns:
        智能体实例
    """
    factory = get_agent_factory()
    return factory.create_agent(agent_type, global_state)


def list_agents() -> List[Dict[str, Any]]:
    """列出所有可用智能体的便捷函数

    Returns:
        智能体信息列表
    """
    factory = get_agent_factory()
    return factory.list_available_agents()


# 智能体执行流程管理
class AgentWorkflow:
    """智能体工作流程管理器

    管理智能体之间的执行流程和状态转换。
    """

    def __init__(self, global_state: GlobalState):
        self.global_state = global_state
        self.factory = get_agent_factory()
        self.execution_history: List[Dict[str, Any]] = []

    def execute_agent(
        self, agent_type: Union[AgentType, str], input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行指定智能体

        Args:
            agent_type: 智能体类型
            input_data: 输入数据

        Returns:
            执行结果
        """
        from ..core.base_agent import AgentInput

        try:
            # 创建智能体
            agent = self.factory.create_agent(agent_type, self.global_state)
            if not agent:
                return {
                    "success": False,
                    "error": f"无法创建智能体: {agent_type}",
                    "data": {},
                    "next_agent": None,
                }

            # 准备输入
            agent_input = AgentInput(data=input_data)

            # 执行智能体
            logger.info(f"开始执行智能体: {agent_type}")
            result = agent.execute(agent_input)

            # 记录执行历史
            execution_record = {
                "agent_type": str(agent_type),
                "timestamp": datetime.now().isoformat(),
                "success": result.error is None,
                "error": result.error,
                "next_agent": result.next_agent,
                "metadata": result.metadata,
            }
            self.execution_history.append(execution_record)

            logger.info(f"智能体执行完成: {agent_type}, 下一个: {result.next_agent}")

            return {
                "success": result.error is None,
                "error": result.error,
                "data": result.data,
                "next_agent": result.next_agent,
                "metadata": result.metadata,
            }

        except Exception as e:
            logger.error(f"智能体执行异常: {agent_type}, 错误: {e}")

            # 记录错误
            execution_record = {
                "agent_type": str(agent_type),
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "error": str(e),
                "next_agent": None,
                "metadata": {},
            }
            self.execution_history.append(execution_record)

            return {
                "success": False,
                "error": str(e),
                "data": {},
                "next_agent": None,
                "metadata": {},
            }

    def execute_workflow(
        self,
        start_agent: Union[AgentType, str],
        input_data: Dict[str, Any],
        max_steps: int = 10,
    ) -> List[Dict[str, Any]]:
        """执行完整的智能体工作流程

        Args:
            start_agent: 起始智能体
            input_data: 初始输入数据
            max_steps: 最大执行步数

        Returns:
            执行结果列表
        """
        results = []
        current_agent = start_agent
        current_data = input_data
        step = 0

        while current_agent and step < max_steps:
            logger.info(f"工作流程步骤 {step + 1}: 执行 {current_agent}")

            # 执行当前智能体
            result = self.execute_agent(current_agent, current_data)
            results.append(result)

            # 检查是否成功
            if not result["success"]:
                logger.error(f"工作流程中断: {result['error']}")
                break

            # 准备下一步
            next_agent = result["next_agent"]
            if next_agent:
                current_agent = next_agent
                current_data = result["data"]
            else:
                logger.info("工作流程完成，没有下一个智能体")
                break

            step += 1

        if step >= max_steps:
            logger.warning(f"工作流程达到最大步数限制: {max_steps}")

        return results

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """获取执行历史

        Returns:
            执行历史记录
        """
        return self.execution_history.copy()

    def clear_history(self):
        """清空执行历史"""
        self.execution_history.clear()
        logger.info("执行历史已清空")


def create_workflow(global_state: GlobalState) -> AgentWorkflow:
    """创建智能体工作流程管理器

    Args:
        global_state: 全局状态

    Returns:
        工作流程管理器实例
    """
    return AgentWorkflow(global_state)
