#!/usr/bin/env python3
"""
工具状态机简单测试
不依赖完整的配置系统
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.constraint_decoder import ConstraintDecoder
# 直接导入需要测试的模块
from src.tools.state_machine import (AgentState, ToolCallMode, ToolDefinition,
                                     ToolStateMachine)


def test_tool_state_machine_basic():
    """测试工具状态机基本功能"""
    print("测试工具状态机初始化...")

    # 创建状态机
    state_machine = ToolStateMachine()

    # 检查初始状态
    assert state_machine.current_state == AgentState.INITIALIZING
    assert state_machine.call_mode == ToolCallMode.AUTO

    # 检查工具定义
    assert len(state_machine.tool_definitions) > 0
    assert len(state_machine.all_tools) > 0

    print(f"✓ 初始化了 {len(state_machine.tool_definitions)} 个工具定义")

    # 测试工具分类
    assert "file_" in state_machine.TOOL_CATEGORIES
    assert "knowledge_" in state_machine.TOOL_CATEGORIES
    assert "sandbox_" in state_machine.TOOL_CATEGORIES

    print("✓ 工具分类正确")

    # 测试状态转换
    state_machine.set_agent_state("Tester", AgentState.GENERATING_MINDMAP)
    assert state_machine.current_state == AgentState.GENERATING_MINDMAP
    assert state_machine.current_agent == "Tester"

    print("✓ 状态转换正常")

    # 测试调用模式
    state_machine.set_call_mode(ToolCallMode.SPECIFIED)
    assert state_machine.call_mode == ToolCallMode.SPECIFIED

    print("✓ 调用模式设置正常")


def test_tool_availability():
    """测试工具可用性"""
    print("\n测试工具可用性...")

    state_machine = ToolStateMachine()

    # AUTO模式：所有工具可用
    auto_tools = state_machine.get_available_tools(
        AgentState.INITIALIZING, ToolCallMode.AUTO
    )
    assert len(auto_tools) > 0
    print(f"✓ AUTO模式: {len(auto_tools)} 个工具可用")

    # SPECIFIED模式：指定工具可用
    specified_tools = state_machine.get_available_tools(
        AgentState.GENERATING_MINDMAP, ToolCallMode.SPECIFIED
    )
    assert len(specified_tools) > 0
    print(f"✓ SPECIFIED模式: {len(specified_tools)} 个工具可用")

    # REQUIRED模式：必需工具
    required_tools = state_machine.get_available_tools(
        AgentState.EXECUTING, ToolCallMode.REQUIRED
    )
    assert len(required_tools) > 0
    print(f"✓ REQUIRED模式: {len(required_tools)} 个工具可用")

    # 检查特定工具
    assert "sandbox_execute" in required_tools
    print("✓ 执行状态下包含sandbox_execute工具")


def test_tool_categories():
    """测试工具分类"""
    print("\n测试工具分类...")

    state_machine = ToolStateMachine()

    # 测试按类别获取工具
    file_tools = state_machine.get_tools_by_category("file")
    knowledge_tools = state_machine.get_tools_by_category("knowledge")
    sandbox_tools = state_machine.get_tools_by_category("sandbox")

    assert len(file_tools) > 0
    assert len(knowledge_tools) > 0
    assert len(sandbox_tools) > 0

    print(f"✓ 文件工具: {len(file_tools)} 个")
    print(f"✓ 知识库工具: {len(knowledge_tools)} 个")
    print(f"✓ 沙盒工具: {len(sandbox_tools)} 个")

    # 检查工具名称前缀
    for tool in file_tools:
        assert tool.startswith("file_")

    print("✓ 工具命名前缀正确")


def test_constraint_decoder():
    """测试约束解码器"""
    print("\n测试约束解码器...")

    state_machine = ToolStateMachine()
    decoder = ConstraintDecoder(state_machine)

    # 检查初始化
    assert decoder.state_machine == state_machine
    assert len(decoder._tool_tokens) > 0

    print(f"✓ 初始化了 {len(decoder._tool_tokens)} 个工具的token映射")

    # 测试token约束计算
    constraint = decoder.get_token_constraints(
        AgentState.GENERATING_MINDMAP, ToolCallMode.SPECIFIED
    )

    assert hasattr(constraint, "allowed_tokens")
    assert hasattr(constraint, "blocked_tokens")
    assert hasattr(constraint, "boost_tokens")
    assert hasattr(constraint, "penalty_tokens")

    print(
        f"✓ 约束计算正常: {len(constraint.allowed_tokens)} 允许, {len(constraint.blocked_tokens)} 阻止"
    )

    # 测试工具调用验证
    valid_call = {
        "function": {"name": "file_read", "arguments": '{"input": "test.txt"}'}
    }

    is_valid, error = decoder.validate_tool_call(
        valid_call, AgentState.INITIALIZING, ToolCallMode.AUTO
    )

    assert is_valid
    assert error is None

    print("✓ 工具调用验证正常")


def test_constraint_config():
    """测试约束配置"""
    print("\n测试约束配置...")

    state_machine = ToolStateMachine()

    # 测试约束配置生成
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
        f"✓ 约束配置生成正常: {config['mode']} 模式，{len(config['available_tools'])} 个可用工具"
    )


def test_state_info():
    """测试状态信息"""
    print("\n测试状态信息...")

    state_machine = ToolStateMachine()
    state_machine.set_agent_state("TestAgent", AgentState.CODING)
    state_machine.set_call_mode(ToolCallMode.SPECIFIED)

    info = state_machine.get_state_info()

    assert info["current_state"] == "coding"
    assert info["current_agent"] == "TestAgent"
    assert info["call_mode"] == "specified"
    assert info["total_tools"] > 0
    assert info["enabled_tools"] > 0

    print(
        f"✓ 状态信息正确: {info['current_agent']} - {info['current_state']} - {info['call_mode']}"
    )


def test_tool_enable_disable():
    """测试工具启用/禁用"""
    print("\n测试工具启用/禁用...")

    state_machine = ToolStateMachine()

    # 获取初始可用工具数量
    initial_count = len(state_machine.get_available_tools())

    # 禁用一个工具
    state_machine.disable_tool("file_read")

    # 检查工具是否被禁用
    tool_def = state_machine.get_tool_definition("file_read")
    assert tool_def is not None
    assert not tool_def.enabled

    # 重新启用工具
    state_machine.enable_tool("file_read")

    # 检查工具是否被启用
    tool_def = state_machine.get_tool_definition("file_read")
    assert tool_def.enabled

    print("✓ 工具启用/禁用功能正常")


def main():
    """运行所有测试"""
    print("开始工具状态机简单测试...\n")

    try:
        test_tool_state_machine_basic()
        test_tool_availability()
        test_tool_categories()
        test_constraint_decoder()
        test_constraint_config()
        test_state_info()
        test_tool_enable_disable()

        print("\n🎉 所有测试通过！")
        print("\n工具状态机和约束解码系统实现正确，功能完整。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
