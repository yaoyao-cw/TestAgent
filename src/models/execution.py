"""执行计划和步骤相关数据模型"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator

from .types import TaskType, StepType


class ExecutionStep(BaseModel):
    """执行步骤模型"""
    
    title: str = Field(..., description="步骤标题", min_length=1, max_length=200)
    description: str = Field(..., description="步骤描述", min_length=1, max_length=1000)
    step_type: StepType = Field(..., description="步骤类型")
    execution_res: Optional[str] = Field(None, description="执行结果", max_length=10000)
    
    @validator('title')
    def validate_title(cls, v):
        """验证标题"""
        if not v.strip():
            raise ValueError("标题不能为空")
        return v.strip()
    
    @validator('description')
    def validate_description(cls, v):
        """验证描述"""
        if not v.strip():
            raise ValueError("描述不能为空")
        return v.strip()
    
    def is_completed(self) -> bool:
        """检查步骤是否已完成"""
        return self.execution_res is not None and len(self.execution_res.strip()) > 0
    
    def mark_completed(self, result: str) -> None:
        """标记步骤为已完成"""
        self.execution_res = result
    
    class Config:
        """Pydantic配置"""
        use_enum_values = True
        validate_assignment = True


class ExecutionPlan(BaseModel):
    """执行计划模型"""
    
    title: str = Field(..., description="计划标题", min_length=1, max_length=200)
    thought: str = Field(..., description="计划思路", min_length=1, max_length=2000)
    locale: str = Field(default="zh-CN", description="语言设置", pattern=r"^[a-z]{2}-[A-Z]{2}$")
    task_type: TaskType = Field(..., description="任务类型")
    steps: List[ExecutionStep] = Field(default_factory=list, description="执行步骤列表")
    has_enough_context: bool = Field(default=False, description="是否有足够的上下文信息")
    
    @validator('title')
    def validate_title(cls, v):
        """验证标题"""
        if not v.strip():
            raise ValueError("计划标题不能为空")
        return v.strip()
    
    @validator('thought')
    def validate_thought(cls, v):
        """验证思路"""
        if not v.strip():
            raise ValueError("计划思路不能为空")
        return v.strip()
    
    @validator('steps')
    def validate_steps(cls, v):
        """验证步骤列表"""
        if len(v) > 10:
            raise ValueError("执行步骤不能超过10个")
        return v
    
    def add_step(self, step: ExecutionStep) -> None:
        """添加执行步骤"""
        if len(self.steps) >= 10:
            raise ValueError("执行步骤不能超过10个")
        self.steps.append(step)
    
    def get_completed_steps(self) -> List[ExecutionStep]:
        """获取已完成的步骤"""
        return [step for step in self.steps if step.is_completed()]
    
    def get_pending_steps(self) -> List[ExecutionStep]:
        """获取待执行的步骤"""
        return [step for step in self.steps if not step.is_completed()]
    
    def is_completed(self) -> bool:
        """检查计划是否已完成"""
        return len(self.steps) > 0 and all(step.is_completed() for step in self.steps)
    
    def get_progress(self) -> float:
        """获取执行进度（0.0-1.0）"""
        if not self.steps:
            return 0.0
        completed_count = len(self.get_completed_steps())
        return completed_count / len(self.steps)
    
    def get_incomplete_steps(self) -> List[ExecutionStep]:
        """获取未完成的步骤"""
        return [step for step in self.steps if not step.is_completed()]
    
    def get_next_step(self) -> Optional[ExecutionStep]:
        """获取下一个要执行的步骤"""
        incomplete_steps = self.get_incomplete_steps()
        return incomplete_steps[0] if incomplete_steps else None
    
    def complete_step(self, step_title: str, result: str) -> bool:
        """完成指定步骤
        
        Args:
            step_title: 步骤标题
            result: 执行结果
            
        Returns:
            是否成功找到并完成步骤
        """
        for step in self.steps:
            if step.title == step_title:
                step.execution_res = result
                return True
        return False
    
    class Config:
        """Pydantic配置"""
        use_enum_values = True
        validate_assignment = True