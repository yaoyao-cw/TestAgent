"""基础智能体测试

测试智能体的基本创建和配置功能，避免复杂的LLM依赖。
"""

import pytest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.workspace import GlobalState
from src.models.types import AgentType, TaskType
from src.core.base_agent import AgentInput


class TestBasicAgents:
    """基础智能体测试类"""

    @pytest.fixture
    def global_state(self):
        """创建测试用的全局状态"""
        return GlobalState()

    def test_global_state_creation(self, global_state):
        """测试全局状态创建"""
        assert global_state is not None
        assert global_state.workspace_state is not None
        assert global_state.task_metadata is None

    def test_agent_input_creation(self):
        """测试智能体输入创建"""
        input_data = AgentInput(
            data={"user_request": "测试请求", "task_type": "test_case_generation"}
        )

        assert input_data is not None
        assert input_data.data["user_request"] == "测试请求"
        assert input_data.context is None
        assert input_data.metadata is None

    def test_agent_types(self):
        """测试智能体类型枚举"""
        assert AgentType.COORDINATOR.value == "coordinator"
        assert AgentType.PLANNER.value == "planner"
        assert AgentType.RESEARCHER.value == "researcher"
        assert AgentType.CODER.value == "coder"
        assert AgentType.REPORTER.value == "reporter"
        assert AgentType.REVIEWER.value == "reviewer"

    def test_task_types(self):
        """测试任务类型枚举"""
        assert TaskType.TEST_CASE_GENERATION.value == "test_case_generation"
        assert TaskType.TEST_SCRIPT_GENERATION.value == "test_script_generation"
        assert TaskType.REQUIREMENT_EXTRACTION.value == "requirement_extraction"
        assert TaskType.TEST_SCRIPT_EXECUTION.value == "test_script_execution"

    def test_global_state_methods(self, global_state):
        """测试全局状态方法"""
        # 测试任务ID设置
        assert global_state.get_current_task_id() is None

        # 测试步骤管理
        assert global_state.get_current_step() == 0
        global_state.update_step(1)
        assert global_state.get_current_step() == 1

        # 测试活跃智能体设置
        global_state.set_active_agent(AgentType.COORDINATOR)
        assert global_state.workspace_state.active_agent == "coordinator"

        # 测试错误添加
        initial_error_count = global_state.workspace_state.error_count
        global_state.add_error("测试错误")
        assert global_state.workspace_state.error_count == initial_error_count + 1

        # 测试任务活跃状态
        assert not global_state.is_task_active()  # 没有任务元数据时应该返回False

    def test_workspace_state_methods(self, global_state):
        """测试工作空间状态方法"""
        ws_state = global_state.workspace_state

        # 测试任务更新
        ws_state.update_current_task("test_task_123", 0)
        assert ws_state.current_task_id == "test_task_123"
        assert ws_state.current_step == 0
        assert ws_state.error_count == 0

        # 测试步骤增加
        ws_state.increment_step()
        assert ws_state.current_step == 1

        # 测试缓存键管理
        assert len(ws_state.cache_keys) == 0
        ws_state.add_cache_key("test_key")
        assert "test_key" in ws_state.cache_keys
        assert len(ws_state.cache_keys) == 1

        ws_state.clear_cache_keys()
        assert len(ws_state.cache_keys) == 0

        # 测试输出文件设置
        ws_state.set_last_output("/path/to/output.md")
        assert ws_state.last_file_output_path == "/path/to/output.md"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
