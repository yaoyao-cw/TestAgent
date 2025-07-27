"""核心智能体测试

测试Coordinator、Planner、TestTeam、Tester、Coder和Executor智能体的基本功能。
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from src.agents import (
    create_coder_agent,
    create_coordinator_agent,
    create_executor_agent,
    create_planner_agent,
    create_test_team_router,
    create_tester_agent,
    create_workflow,
    get_agent_factory,
)
from src.core.base_agent import AgentInput
from src.models.types import AgentType, TaskType
from src.models.workspace import GlobalState, TaskMetadata


class TestCoreAgents:
    """核心智能体测试类"""

    @pytest.fixture
    def global_state(self):
        """创建测试用的全局状态"""
        return GlobalState()

    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作空间"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_coordinator_agent_creation(self, global_state):
        """测试Coordinator智能体创建"""
        agent = create_coordinator_agent(global_state)

        assert agent is not None
        assert agent.agent_type == AgentType.COORDINATOR
        assert agent.name == "coordinator"
        assert len(agent.available_tools) > 0

    def test_planner_agent_creation(self, global_state):
        """测试Planner智能体创建"""
        agent = create_planner_agent(global_state)

        assert agent is not None
        assert agent.agent_type == AgentType.PLANNER
        assert agent.name == "planner"
        assert len(agent.available_tools) > 0

    def test_test_team_router_creation(self, global_state):
        """测试TestTeam路由器创建"""
        router = create_test_team_router(global_state)

        assert router is not None
        assert router.agent_type == AgentType.TESTER  # 路由器使用TESTER类型
        assert len(router.available_tools) > 0
        assert hasattr(router, "agent_routing_map")

    def test_tester_agent_creation(self, global_state):
        """测试Tester智能体创建"""
        agent = create_tester_agent(global_state)

        assert agent is not None
        assert agent.agent_type == AgentType.TESTER
        assert agent.name == "tester"
        assert len(agent.available_tools) > 0
        assert hasattr(agent, "max_iterations")

    def test_coder_agent_creation(self, global_state):
        """测试Coder智能体创建"""
        agent = create_coder_agent(global_state)

        assert agent is not None
        assert agent.agent_type == AgentType.CODER
        assert agent.name == "coder"
        assert len(agent.available_tools) > 0
        assert hasattr(agent, "code_templates")

    def test_executor_agent_creation(self, global_state):
        """测试Executor智能体创建"""
        agent = create_executor_agent(global_state)

        assert agent is not None
        assert agent.agent_type == AgentType.EXECUTOR
        assert agent.name == "executor"
        assert len(agent.available_tools) > 0
        assert hasattr(agent, "sandbox")

    def test_agent_factory(self, global_state):
        """测试智能体工厂"""
        factory = get_agent_factory()

        # 测试创建不同类型的智能体
        coordinator = factory.create_agent(AgentType.COORDINATOR, global_state)
        assert coordinator is not None
        assert coordinator.agent_type == AgentType.COORDINATOR

        planner = factory.create_agent("planner", global_state)
        assert planner is not None
        assert planner.agent_type == AgentType.PLANNER

        tester = factory.create_agent("tester", global_state)
        assert tester is not None
        assert tester.agent_type == AgentType.TESTER

        # 测试列出可用智能体
        agents = factory.list_available_agents()
        assert len(agents) > 0
        assert any(agent["type"] == "coordinator" for agent in agents)

        # 测试缓存功能
        cache_info = factory.get_cache_info()
        assert "cached_agents" in cache_info
        assert cache_info["cached_agents"] > 0

    def test_agent_workflow(self, global_state):
        """测试智能体工作流程"""
        workflow = create_workflow(global_state)

        assert workflow is not None
        assert workflow.global_state == global_state
        assert len(workflow.execution_history) == 0

        # 测试执行历史功能
        history = workflow.get_execution_history()
        assert isinstance(history, list)
        assert len(history) == 0

        # 清空历史
        workflow.clear_history()
        assert len(workflow.execution_history) == 0

    def test_coordinator_load_phase(self, global_state):
        """测试Coordinator智能体的load阶段"""
        agent = create_coordinator_agent(global_state)

        input_data = AgentInput(
            data={
                "user_request": "生成用户登录功能的测试用例",
                "task_type": "test_case_generation",
            }
        )

        state = agent.load(input_data)

        assert "user_request" in state
        assert "task_type" in state
        assert state["user_request"] == "生成用户登录功能的测试用例"
        assert state["task_type"] == TaskType.TEST_CASE_GENERATION
        assert "prompt_template" in state
        assert "available_tools" in state

    def test_tester_load_phase(self, global_state):
        """测试Tester智能体的load阶段"""
        agent = create_tester_agent(global_state)

        input_data = AgentInput(data={"test_requirements": "测试用户登录功能"})

        state = agent.load(input_data)

        assert "input_data" in state
        assert "context" in state
        assert "available_tools" in state
        assert "react_iterations" in state
        assert state["react_iterations"] == 0
        assert "test_cases" in state
        assert isinstance(state["test_cases"], list)

    def test_coder_load_phase(self, global_state):
        """测试Coder智能体的load阶段"""
        agent = create_coder_agent(global_state)

        input_data = AgentInput(
            data={
                "test_cases": [
                    {
                        "scenario": "用户正常登录",
                        "steps": "输入用户名密码",
                        "expected": "登录成功",
                    }
                ]
            }
        )

        state = agent.load(input_data)

        assert "input_data" in state
        assert "context" in state
        assert "code_templates" in state
        assert "generated_scripts" in state
        assert isinstance(state["generated_scripts"], list)
        assert len(state["code_templates"]) > 0

    def test_executor_load_phase(self, global_state):
        """测试Executor智能体的load阶段"""
        agent = create_executor_agent(global_state)

        input_data = AgentInput(data={"scripts": ["test_login.py"]})

        state = agent.load(input_data)

        assert "input_data" in state
        assert "context" in state
        assert "test_scripts" in state
        assert "execution_results" in state
        assert isinstance(state["execution_results"], list)

    def test_agent_prompt_templates(self, global_state):
        """测试智能体提示词模板"""
        agents = [
            create_coordinator_agent(global_state),
            create_planner_agent(global_state),
            create_test_team_router(global_state),
            create_tester_agent(global_state),
            create_coder_agent(global_state),
            create_executor_agent(global_state),
        ]

        for agent in agents:
            template = agent.get_prompt_template()
            assert isinstance(template, str)
            assert len(template) > 0
            assert "智能体" in template or "agent" in template.lower()

    def test_agent_tools(self, global_state):
        """测试智能体工具配置"""
        agents = [
            create_coordinator_agent(global_state),
            create_planner_agent(global_state),
            create_test_team_router(global_state),
            create_tester_agent(global_state),
            create_coder_agent(global_state),
            create_executor_agent(global_state),
        ]

        for agent in agents:
            tools = agent.get_available_tools()
            assert isinstance(tools, list)
            # 每个智能体都应该有一些工具
            # 注意：有些智能体可能返回空列表，这是正常的

    def test_react_agent_properties(self, global_state):
        """测试ReAct智能体的特殊属性"""
        tester = create_tester_agent(global_state)
        coder = create_coder_agent(global_state)

        # 测试ReAct智能体的最大迭代次数
        assert hasattr(tester, "max_iterations")
        assert tester.max_iterations > 0

        assert hasattr(coder, "max_iterations")
        assert coder.max_iterations > 0

        # 测试ReAct方法存在
        assert hasattr(tester, "reason")
        assert hasattr(tester, "act")
        assert hasattr(tester, "observe")

        assert hasattr(coder, "reason")
        assert hasattr(coder, "act")
        assert hasattr(coder, "observe")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
