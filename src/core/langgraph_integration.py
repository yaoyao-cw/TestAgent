"""LangGraph集成模块

将BaseAgent和AgentRouter与LangGraph框架集成，提供统一的工作流编排能力。
"""

from typing import Any, Callable, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from ..models.state import TestAgentState
from ..models.workspace import GlobalState
from .agent_router import AgentRouter, RoutingRule
from .base_agent import AgentInput, AgentOutput, BaseAgent


class LangGraphAgentNode:
    """LangGraph智能体节点包装器

    将BaseAgent包装为LangGraph节点，实现与LangGraph的无缝集成。
    """

    def __init__(self, agent: BaseAgent):
        self.agent = agent

    def __call__(self, state: TestAgentState) -> TestAgentState:
        """LangGraph节点调用接口"""
        try:
            # 从LangGraph状态提取数据
            input_data = AgentInput(
                data={
                    "messages": state.get("messages", []),
                    "task_topic": state.get("task_topic", ""),
                    "task_type": state.get("task_type"),
                    "current_plan": state.get("current_plan"),
                    "observations": state.get("observations", []),
                    "resources": state.get("resources", []),
                },
                metadata={
                    "plan_iterations": state.get("plan_iterations", 0),
                    "enable_rag_search": state.get("enable_rag_search", True),
                },
            )

            # 执行智能体
            output = self.agent.execute(input_data)

            # 更新LangGraph状态
            if not output.error:
                # 添加消息到状态
                if "content" in output.data:
                    state["messages"] = add_messages(
                        state.get("messages", []),
                        [{"role": "assistant", "content": output.data["content"]}],
                    )

                # 更新其他状态字段
                if "observations" in output.data:
                    state["observations"] = output.data["observations"]

                if "resources" in output.data:
                    state["resources"] = output.data["resources"]

                if "plan" in output.data:
                    state["current_plan"] = output.data["plan"]

                # 更新元数据
                if output.metadata:
                    for key, value in output.metadata.items():
                        if key in state:
                            state[key] = value
            else:
                # 处理错误
                state["messages"] = add_messages(
                    state.get("messages", []),
                    [{"role": "system", "content": f"错误: {output.error}"}],
                )

            return state

        except Exception as e:
            # 异常处理
            state["messages"] = add_messages(
                state.get("messages", []),
                [{"role": "system", "content": f"节点执行异常: {str(e)}"}],
            )
            return state


class LangGraphWorkflowBuilder:
    """LangGraph工作流构建器

    使用BaseAgent和AgentRouter构建LangGraph工作流。
    """

    def __init__(self, global_state: GlobalState):
        self.global_state = global_state
        self.router = AgentRouter(global_state)
        self.graph = StateGraph(TestAgentState)
        self.checkpointer = MemorySaver()

    def add_agent_node(self, agent: BaseAgent, node_name: Optional[str] = None):
        """添加智能体节点"""
        node_name = node_name or agent.name

        # 注册到路由器
        self.router.register_agent(agent)

        # 创建LangGraph节点
        node = LangGraphAgentNode(agent)
        self.graph.add_node(node_name, node)

        return node_name

    def add_routing_rule(self, rule: RoutingRule):
        """添加路由规则"""
        self.router.add_routing_rule(rule)

    def add_conditional_edge(
        self,
        from_node: str,
        condition_func: Callable[[TestAgentState], str],
        condition_map: Dict[str, str],
    ):
        """添加条件边"""
        self.graph.add_conditional_edges(from_node, condition_func, condition_map)

    def add_simple_edge(self, from_node: str, to_node: str):
        """添加简单边"""
        self.graph.add_edge(from_node, to_node)

    def set_entry_point(self, node_name: str):
        """设置入口点"""
        self.graph.set_entry_point(node_name)

    def build(self) -> StateGraph:
        """构建工作流"""
        return self.graph.compile(checkpointer=self.checkpointer)

    def create_default_workflow(self, agents: List[BaseAgent]) -> StateGraph:
        """创建默认工作流

        Args:
            agents: 智能体列表

        Returns:
            编译后的工作流图
        """
        # 添加所有智能体节点
        node_names = []
        for agent in agents:
            node_name = self.add_agent_node(agent)
            node_names.append(node_name)

        # 设置入口点
        if node_names:
            self.set_entry_point(node_names[0])

        # 添加顺序边
        for i in range(len(node_names) - 1):
            self.add_simple_edge(node_names[i], node_names[i + 1])

        # 最后一个节点连接到END
        if node_names:
            self.add_simple_edge(node_names[-1], END)

        return self.build()

    def create_conditional_workflow(self, agents: List[BaseAgent]) -> StateGraph:
        """创建条件工作流

        Args:
            agents: 智能体列表

        Returns:
            编译后的工作流图
        """
        # 添加所有智能体节点
        agent_nodes = {}
        for agent in agents:
            node_name = self.add_agent_node(agent)
            agent_nodes[agent.name] = node_name

        # 设置入口点（通常是coordinator）
        if "coordinator" in agent_nodes:
            self.set_entry_point(agent_nodes["coordinator"])
        elif agent_nodes:
            self.set_entry_point(list(agent_nodes.values())[0])

        # 添加条件路由逻辑
        def route_condition(state: TestAgentState) -> str:
            """路由条件函数"""
            # 获取当前计划状态
            current_plan = state.get("current_plan")
            observations = state.get("observations", [])

            # 基于状态决定下一个节点
            if not current_plan:
                return "planner"
            elif not observations:
                return "researcher"
            elif state.get("task_type") == "test_case_generation":
                return "tester"
            elif state.get("task_type") == "test_script_generation":
                return "coder"
            else:
                return END

        # 为每个节点添加条件边
        for node_name in agent_nodes.values():
            condition_map = {name: name for name in agent_nodes.values()}
            condition_map[END] = END

            self.add_conditional_edge(node_name, route_condition, condition_map)

        return self.build()


def create_agent_workflow(
    agents: List[BaseAgent], global_state: GlobalState, workflow_type: str = "default"
) -> StateGraph:
    """创建智能体工作流的便捷函数

    Args:
        agents: 智能体列表
        global_state: 全局状态
        workflow_type: 工作流类型 ("default" 或 "conditional")

    Returns:
        编译后的工作流图
    """
    builder = LangGraphWorkflowBuilder(global_state)

    if workflow_type == "conditional":
        return builder.create_conditional_workflow(agents)
    else:
        return builder.create_default_workflow(agents)


# 预定义的路由条件函数
def task_completion_router(state: TestAgentState) -> str:
    """基于任务完成状态的路由"""
    if state.get("final_report"):
        return END
    elif state.get("review_score") and state["review_score"].overall_score < 0.7:
        return "reviewer"
    elif not state.get("current_plan"):
        return "planner"
    else:
        return "tester"


def error_recovery_router(state: TestAgentState) -> str:
    """错误恢复路由"""
    messages = state.get("messages", [])

    # 检查最近的消息是否包含错误
    if messages:
        last_message = messages[-1]
        if "error" in last_message.get("content", "").lower():
            return "coordinator"  # 返回协调器处理错误

    # 检查观察结果中的错误
    observations = state.get("observations", [])
    if observations:
        last_observation = observations[-1]
        if "error" in last_observation.lower() or "failed" in last_observation.lower():
            return "reviewer"  # 让评审员分析错误

    return "planner"  # 默认继续正常流程


def plan_iteration_router(state: TestAgentState) -> str:
    """计划迭代路由"""
    plan_iterations = state.get("plan_iterations", 0)
    max_iterations = 3

    if plan_iterations >= max_iterations:
        return "reporter"  # 达到最大迭代次数，生成报告
    elif not state.get("current_plan"):
        return "planner"  # 没有计划，需要规划
    elif state.get("auto_accepted_plan", True):
        return "tester"  # 自动接受计划，开始测试
    else:
        return "reviewer"  # 需要人工审查计划
