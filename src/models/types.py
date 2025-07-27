"""基础类型定义"""

from enum import Enum


class TaskType(Enum):
    """任务类型枚举"""

    TEST_CASE_GENERATION = "test_case_generation"
    """测试用例生成"""

    TEST_SCRIPT_GENERATION = "test_script_generation"
    """测试脚本生成"""

    REQUIREMENT_EXTRACTION = "requirement_extraction"
    """需求内容提取"""

    TEST_SCRIPT_EXECUTION = "test_script_execution"
    """测试脚本运行"""

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "TaskType":
        """从字符串创建TaskType实例"""
        for task_type in cls:
            if task_type.value == value:
                return task_type
        raise ValueError(f"Unknown task type: {value}")


class StepType(Enum):
    """执行步骤类型枚举"""

    RESEARCH = "research"
    """研究步骤"""

    CODING = "coding"
    """编码步骤"""

    ANALYSIS = "analysis"
    """分析步骤"""

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "StepType":
        """从字符串创建StepType实例"""
        for step_type in cls:
            if step_type.value == value:
                return step_type
        raise ValueError(f"Unknown step type: {value}")


class AgentType(Enum):
    """智能体类型枚举"""

    COORDINATOR = "coordinator"
    """协调器"""

    PLANNER = "planner"
    """规划器"""

    RESEARCHER = "researcher"
    """研究员"""

    CODER = "coder"
    """编码员"""

    REPORTER = "reporter"
    """报告员"""

    REVIEWER = "reviewer"
    """评审员"""

    def __str__(self) -> str:
        return self.value


class LLMType(Enum):
    """LLM类型枚举"""

    BASIC = "basic"
    """基础模型"""

    ADVANCED = "advanced"
    """高级模型"""

    REASONING = "reasoning"
    """推理模型"""

    def __str__(self) -> str:
        return self.value
