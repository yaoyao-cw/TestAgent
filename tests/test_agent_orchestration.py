"""智能体编排基础测试"""

import pytest
from unittest.mock import Mock

from src.core.base_agent import BaseAgent, SimpleAgent, ReActAgent, AgentInput, AgentOutput
from src.core.agent_router import AgentRouter, RoutingRule, Message
from src.models.types import AgentType
from src.models.workspace import GlobalState, WorkspaceState


class TestBaseAgent:
    """BaseAgent测试"""
    
    @pytest.fixture
    def global_state(self):
        """全局状态实例"""
        return GlobalState()
    
    @pytest.fixture
    def simple_agent(self, global_state):
        """简单智能体实例"""
        return SimpleAgent(
            agent_type=AgentType.COORDINATOR,
            global_state=global_state,
            prompt_template="测试提示词模板",
            tools=["tool1", "tool2"]
        )
    
    def test_agent_initialization(self, simple_agent, global_state):
        """测试智能体初始化"""
        assert simple_agent.agent_type == AgentType.COORDINATOR
        assert simple_agent.global_state == global_state
        assert simple_agent.name == "coordinator"
    
    def test_agent_execute_flow(self, simple_agent):
        """测试智能体执行流程"""
        input_data = AgentInput(
            data={"test_key": "test_value"},
            metadata={"step": 1}
        )
        
        output = simple_agent.execute(input_data)
        
        assert isinstance(output, AgentOutput)
        assert output.error is None
        assert "content" in output.data
        assert output.metadata is not None
    
    def test_prompt_template(self, simple_agent):
        """测试提示词模板"""
        template = simple_agent.get_prompt_template()
        assert "测试提示词模板" in template
    
    def test_available_tools(self, simple_agent):
        """测试可用工具"""
        tools = simple_agent.get_available_tools()
        assert "tool1" in tools
        assert "tool2" in tools


class MockReActAgent(ReActAgent):
    """Mock ReAct智能体用于测试"""
    
    def load(self, input_data: AgentInput):
        return {
            'input_data': input_data.data,
            'context': self.get_context_from_global_state()
        }
    
    def reason(self, state, history):
        return f"推理步骤 {len(history) + 1}"
    
    def act(self, state, reasoning):
        return {
            'action': 'test_action',
            'reasoning': reasoning,
            'result': 'success'
        }
    
    def observe(self, state, action_result):
        return f"观察到: {action_result['result']}"
    
    def router(self, state):
        return AgentOutput(
            data=state.get('llm_output', {}),
            next_agent=None
        )


class TestReActAgent:
    """ReAct智能体测试"""
    
    @pytest.fixture
    def global_state(self):
        return GlobalState()
    
    @pytest.fixture
    def react_agent(self, global_state):
        return MockReActAgent(
            agent_type=AgentType.RESEARCHER,
            global_state=global_state,
            max_iterations=3
        )
    
    def test_react_agent_initialization(self, react_agent):
        """测试ReAct智能体初始化"""
        assert react_agent.agent_type == AgentType.RESEARCHER
        assert react_agent.max_iterations == 3
    
    def test_react_loop_execution(self, react_agent):
        """测试ReAct循环执行"""
        input_data = AgentInput(data={"task": "test_task"})
        output = react_agent.execute(input_data)
        
        assert output.error is None
        assert 'react_history' in output.data
        
        react_history = output.data['react_history']
        assert len(react_history) > 0
        
        # 检查每个ReAct步骤的结构
        for step in react_history:
            assert 'iteration' in step
            assert 'reasoning' in step
            assert 'action' in step
            assert 'observation' in step


class TestAgentRouter:
    """智能体路由器测试"""
    
    @pytest.fixture
    def global_state(self):
        return GlobalState()
    
    @pytest.fixture
    def router(self, global_state):
        return AgentRouter(global_state)
    
    @pytest.fixture
    def mock_agents(self, global_state):
        """创建模拟智能体"""
        coordinator = SimpleAgent(AgentType.COORDINATOR, global_state)
        planner = SimpleAgent(AgentType.PLANNER, global_state)
        tester = SimpleAgent(AgentType.RESEARCHER, global_state)  # 使用RESEARCHER作为测试
        
        return {
            'coordinator': coordinator,
            'planner': planner,
            'researcher': tester
        }
    
    def test_router_initialization(self, router):
        """测试路由器初始化"""
        assert len(router.agents) == 0
        assert len(router.routing_rules) == 0
        assert len(router.message_queue) == 0
    
    def test_register_agent(self, router, mock_agents):
        """测试注册智能体"""
        coordinator = mock_agents['coordinator']
        router.register_agent(coordinator)
        
        assert 'coordinator' in router.agents
        assert router.agents['coordinator'] == coordinator
    
    def test_add_routing_rule(self, router):
        """测试添加路由规则"""
        rule = RoutingRule(
            from_agent='coordinator',
            to_agent='planner',
            priority=1
        )
        
        router.add_routing_rule(rule)
        
        assert len(router.routing_rules) == 1
        assert router.routing_rules[0] == rule
    
    def test_route_message_explicit(self, router, mock_agents):
        """测试明确指定的消息路由"""
        # 注册智能体
        for agent in mock_agents.values():
            router.register_agent(agent)
        
        # 创建输出，明确指定下一个智能体
        output = AgentOutput(
            data={'result': 'test'},
            next_agent='planner'
        )
        
        next_agent = router.route_message('coordinator', output)
        assert next_agent == 'planner'
    
    def test_route_message_by_rule(self, router, mock_agents):
        """测试基于规则的消息路由"""
        # 注册智能体
        for agent in mock_agents.values():
            router.register_agent(agent)
        
        # 添加路由规则
        rule = RoutingRule(
            from_agent='coordinator',
            to_agent='researcher',
            condition=lambda data: data.get('needs_research', False)
        )
        router.add_routing_rule(rule)
        
        # 创建满足条件的输出
        output = AgentOutput(
            data={'needs_research': True}
        )
        
        next_agent = router.route_message('coordinator', output)
        assert next_agent == 'researcher'
    
    def test_default_routing(self, router, mock_agents):
        """测试默认路由"""
        # 注册智能体
        for agent in mock_agents.values():
            router.register_agent(agent)
        
        # 创建没有明确指定的输出
        output = AgentOutput(data={'result': 'test'})
        
        next_agent = router.route_message('coordinator', output)
        assert next_agent == 'planner'  # 根据默认序列
    
    def test_message_queue(self, router):
        """测试消息队列"""
        message = Message(
            from_agent='coordinator',
            to_agent='planner',
            data={'test': 'data'}
        )
        
        router.send_message(message)
        assert len(router.message_queue) == 1
        
        messages = router.get_messages_for_agent('planner')
        assert len(messages) == 1
        assert messages[0] == message
        assert len(router.message_queue) == 0  # 消息已被取出
    
    def test_workflow_execution(self, router, mock_agents):
        """测试工作流执行"""
        # 注册智能体
        for agent in mock_agents.values():
            router.register_agent(agent)
        
        # 执行工作流
        result = router.execute_workflow(
            start_agent='coordinator',
            initial_data={'task': 'test_task'}
        )
        
        assert 'execution_history' in result
        assert 'final_data' in result
        assert len(result['execution_history']) > 0
        
        # 检查执行历史
        first_step = result['execution_history'][0]
        assert first_step['agent'] == 'coordinator'
        assert 'input' in first_step
        assert 'output' in first_step
    
    def test_routing_statistics(self, router, mock_agents):
        """测试路由统计"""
        # 注册智能体并执行工作流
        for agent in mock_agents.values():
            router.register_agent(agent)
        
        router.execute_workflow('coordinator', {'task': 'test'})
        
        stats = router.get_routing_statistics()
        
        assert 'total_steps' in stats
        assert 'agent_execution_counts' in stats
        assert 'success_rate' in stats
        assert stats['total_steps'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])