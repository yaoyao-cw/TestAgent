#!/usr/bin/env python3
"""
工具状态机测试
"""

import asyncio
from datetime import datetime

import pytest

from src.tools.constraint_decoder import (
    ConstraintDecoder,
    apply_tool_constraints,
    get_constraint_decoder,
)
from src.tools.enhanced_tool_manager import (
    EnhancedToolManager,
    ToolExecutionContext,
    get_enhanced_tool_manager,
)
from src.tools.state_machine import (
    AgentState,
    ToolCallMode,
    ToolDefinition,
    ToolStateMachine,
    get_available_tools_for_agent,
    get_tool_state_machine,
    set_agent_state,
)


class TestToolStateMachine:
    """工具状态机测试类"""

    def test_tool_state_machine_initialization(self):
        """测试工具状态机初始化"""
        state_machine = ToolStateMachine()

        # 检查基本属性
        assert state_machine.current_state == AgentState.INITIALIZING
        assert state_machine.call_mode == ToolCallMode.AUTO
        assert len(state_machine.tool_definitions) > 0
        assert len(state_machine.all_tools) > 0

        # 检查工具分类
        assert "file_" in state_machine.TOOL_CATEGORIES
        assert "knowledge_" in state_machine.TOOL_CATEGORIES
        assert "sandbox_" in state_machine.TOOL_CATEGORIES

        print(f"初始化了 {len(state_machine.tool_definitions)} 个工具定义")

    def test_agent_state_transitions(self):
        """测试智能体状态转换"""
        state_machine = ToolStateMachine()

        # 测试状态设置
        state_machine.set_agent_state("Tester", AgentState.GENERATING_MINDMAP)
        assert state_machine.current_state == AgentState.GENERATING_MINDMAP
        assert state_machine.current_agent == "Tester"

        # 测试调用模式设置
        state_machine.set_call_mode(ToolCallMode.SPECIFIED)
        assert state_machine.call_mode == ToolCallMode.SPECIFIED

    def test_tool_availability_by_mode(self):
        """测试不同模式下的工具可用性"""
        state_machine = ToolStateMachine()

        # AUTO模式：所有工具可用
        auto_tools = state_machine.get_available_tools(
            AgentState.INITIALIZING, ToolCallMode.AUTO
        )
        assert len(auto_tools) > 0

        # SPECIFIED模式：只有指定工具可用
        specified_tools = state_machine.get_available_tools(
            AgentState.GENERATING_MINDMAP, ToolCallMode.SPECIFIED
        )
        assert len(specified_tools) > 0
        assert len(specified_tools) <= len(auto_tools)

        # REQUIRED模式：必需工具
        required_tools = state_machine.get_available_tools(
            AgentState.EXECUTING, ToolCallMode.REQUIRED
        )
        assert "sandbox_execute" in required_tools

        print(f"AUTO模式: {len(auto_tools)} 个工具")
        print(f"SPECIFIED模式: {len(specified_tools)} 个工具")
        print(f"REQUIRED模式: {len(required_tools)} 个工具")

    def test_tool_categories(self):
        """测试工具分类"""
        state_machine = ToolStateMachine()

        # 测试按类别获取工具
        file_tools = state_machine.get_tools_by_category("file")
        knowledge_tools = state_machine.get_tools_by_category("knowledge")
        sandbox_tools = state_machine.get_tools_by_category("sandbox")

        assert len(file_tools) > 0
        assert len(knowledge_tools) > 0
        assert len(sandbox_tools) > 0

        # 检查工具名称前缀
        for tool in file_tools:
            assert tool.startswith("file_")

        print(f"文件工具: {file_tools}")
        print(f"知识库工具: {knowledge_tools}")
        print(f"沙盒工具: {sandbox_tools}")

    def test_constraint_config_generation(self):
        """测试约束配置生成"""
        state_machine = ToolStateMachine()

        # 测试不同状态和模式的约束配置
        config = state_machine.get_constraint_config(
            AgentState.GENERATING_TESTCASES, ToolCallMode.SPECIFIED
        )

        assert "mode" in config
        assert "state" in config
        assert "available_tools" in config
        assert "tool_schemas" in config

        assert config["mode"] == "specified"
        assert config["state"] == "generating_testcases"
        assert len(config["available_tools"]) > 0
        assert len(config["tool_schemas"]) > 0

        print(
            f"约束配置: {config['mode']} 模式，{len(config['available_tools'])} 个可用工具"
        )


class TestConstraintDecoder:
    """约束解码器测试类"""

    def test_constraint_decoder_initialization(self):
        """测试约束解码器初始化"""
        state_machine = ToolStateMachine()
        decoder = ConstraintDecoder(state_machine)

        assert decoder.state_machine == state_machine
        assert len(decoder._tool_tokens) > 0

        print(f"初始化了 {len(decoder._tool_tokens)} 个工具的token映射")

    def test_token_constraints_calculation(self):
        """测试token约束计算"""
        state_machine = ToolStateMachine()
        decoder = ConstraintDecoder(state_machine)

        # 测试不同模式的约束
        auto_constraint = decoder.get_token_constraints(
            AgentState.INITIALIZING, ToolCallMode.AUTO
        )

        specified_constraint = decoder.get_token_constraints(
            AgentState.GENERATING_MINDMAP, ToolCallMode.SPECIFIED
        )

        required_constraint = decoder.get_token_constraints(
            AgentState.EXECUTING, ToolCallMode.REQUIRED
        )

        # 检查约束结构
        assert hasattr(auto_constraint, "allowed_tokens")
        assert hasattr(auto_constraint, "blocked_tokens")
        assert hasattr(auto_constraint, "boost_tokens")
        assert hasattr(auto_constraint, "penalty_tokens")

        # REQUIRED模式应该有更多的boost tokens
        assert len(required_constraint.boost_tokens) >= len(
            auto_constraint.boost_tokens
        )

        print(
            f"AUTO约束: {len(auto_constraint.allowed_tokens)} 允许, {len(auto_constraint.blocked_tokens)} 阻止"
        )
        print(
            f"SPECIFIED约束: {len(specified_constraint.allowed_tokens)} 允许, {len(specified_constraint.blocked_tokens)} 阻止"
        )
        print(
            f"REQUIRED约束: {len(required_constraint.boost_tokens)} boost, {len(required_constraint.penalty_tokens)} penalty"
        )

    def test_response_prefill_generation(self):
        """测试响应预填充生成"""
        state_machine = ToolStateMachine()
        decoder = ConstraintDecoder(state_machine)

        # 测试不同模式的预填充
        auto_prefill = decoder.get_response_prefill(
            AgentState.INITIALIZING, ToolCallMode.AUTO
        )

        required_prefill = decoder.get_response_prefill(
            AgentState.EXECUTING, ToolCallMode.REQUIRED
        )

        # AUTO模式通常不预填充
        assert auto_prefill is None

        # REQUIRED模式应该有预填充
        if required_prefill:
            assert "tool_calls" in required_prefill
            print(f"REQUIRED模式预填充: {required_prefill}")

    def test_tool_call_validation(self):
        """测试工具调用验证"""
        state_machine = ToolStateMachine()
        decoder = ConstraintDecoder(state_machine)

        # 有效的工具调用
        valid_call = {
            "function": {"name": "file_read", "arguments": '{"input": "test.txt"}'}
        }

        is_valid, error = decoder.validate_tool_call(
            valid_call, AgentState.INITIALIZING, ToolCallMode.AUTO
        )

        assert is_valid
        assert error is None

        # 无效的工具调用（工具不存在）
        invalid_call = {"function": {"name": "nonexistent_tool", "arguments": "{}"}}

        is_valid, error = decoder.validate_tool_call(
            invalid_call, AgentState.GENERATING_MINDMAP, ToolCallMode.SPECIFIED
        )

        assert not is_valid
        assert error is not None
        print(f"无效工具调用错误: {error}")


class TestEnhancedToolManager:
    """增强工具管理器测试类"""

    @pytest.mark.asyncio
    async def test_enhanced_tool_manager_initialization(self):
        """测试增强工具管理器初始化"""
        manager = EnhancedToolManager()

        # 检查基本属性
        assert manager.state_machine is not None
        assert manager.constraint_decoder is not None
        assert manager.current_context is None

        # 初始化工具
        await manager.initialize_tools()
        assert manager._initialized

        print("增强工具管理器初始化成功")

    @pytest.mark.asyncio
    async def test_execution_context_management(self):
        """测试执行上下文管理"""
        manager = EnhancedToolManager()
        await manager.initialize_tools()

        # 设置执行上下文
        context = ToolExecutionContext(
            agent_name="Tester",
            agent_state=AgentState.GENERATING_TESTCASES,
            call_mode=ToolCallMode.SPECIFIED,
            task_id="test_task_001",
            step_id="step_001",
        )

        manager.set_execution_context(context)

        assert manager.current_context == context
        assert manager.state_machine.current_agent == "Tester"
        assert manager.state_machine.current_state == AgentState.GENERATING_TESTCASES

        # 获取上下文可用工具
        available_tools = manager.get_available_tools_for_context()
        assert len(available_tools) > 0

        print(f"上下文可用工具: {available_tools}")

    @pytest.mark.asyncio
    async def test_constraint_config_for_llm(self):
        """测试LLM约束配置"""
        manager = EnhancedToolManager()
        await manager.initialize_tools()

        # 设置上下文
        context = ToolExecutionContext(
            agent_name="Coder",
            agent_state=AgentState.CODING,
            call_mode=ToolCallMode.SPECIFIED,
        )
        manager.set_execution_context(context)

        # 获取LLM约束配置
        config = manager.get_constraint_config_for_llm()

        assert "mode" in config
        assert "available_tools" in config
        assert "tool_schemas" in config
        assert config["mode"] == "specified"

        print(
            f"LLM约束配置: {len(config['available_tools'])} 个工具，{len(config['tool_schemas'])} 个schema"
        )

    @pytest.mark.asyncio
    async def test_tool_suggestions(self):
        """测试工具建议"""
        manager = EnhancedToolManager()
        await manager.initialize_tools()

        # 设置上下文
        context = ToolExecutionContext(
            agent_name="Researcher",
            agent_state=AgentState.RESEARCHING,
            call_mode=ToolCallMode.SPECIFIED,
        )
        manager.set_execution_context(context)

        # 获取工具建议
        suggestions = manager.get_tool_suggestions()

        assert len(suggestions) > 0

        for suggestion in suggestions[:3]:  # 检查前3个建议
            assert "tool_name" in suggestion
            assert "description" in suggestion
            assert "category" in suggestion
            assert "example_call" in suggestion

            print(f"工具建议: {suggestion['tool_name']} - {suggestion['description']}")


def test_global_functions():
    """测试全局便捷函数"""
    # 测试全局状态机获取
    state_machine = get_tool_state_machine()
    assert isinstance(state_machine, ToolStateMachine)

    # 测试设置智能体状态
    set_agent_state("TestAgent", AgentState.PLANNING)
    assert state_machine.current_agent == "TestAgent"
    assert state_machine.current_state == AgentState.PLANNING

    # 测试获取可用工具
    available_tools = get_available_tools_for_agent(
        "TestAgent", AgentState.CODING, ToolCallMode.SPECIFIED
    )
    assert len(available_tools) > 0

    print(f"全局函数测试通过，可用工具: {len(available_tools)} 个")


if __name__ == "__main__":
    # 运行基本测试
    print("开始工具状态机测试...")

    # 同步测试
    test_state_machine = TestToolStateMachine()
    test_state_machine.test_tool_state_machine_initialization()
    test_state_machine.test_agent_state_transitions()
    test_state_machine.test_tool_availability_by_mode()
    test_state_machine.test_tool_categories()
    test_state_machine.test_constraint_config_generation()

    test_decoder = TestConstraintDecoder()
    test_decoder.test_constraint_decoder_initialization()
    test_decoder.test_token_constraints_calculation()
    test_decoder.test_response_prefill_generation()
    test_decoder.test_tool_call_validation()

    test_global_functions()

    # 异步测试
    async def run_async_tests():
        test_manager = TestEnhancedToolManager()
        await test_manager.test_enhanced_tool_manager_initialization()
        await test_manager.test_execution_context_management()
        await test_manager.test_constraint_config_for_llm()
        await test_manager.test_tool_suggestions()

    asyncio.run(run_async_tests())

    print("所有测试通过！")
