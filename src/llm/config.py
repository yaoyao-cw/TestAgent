"""LLM配置管理"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from ..models.types import LLMType, AgentType


class LLMConfig(BaseModel):
    """LLM配置模型"""
    
    provider: str = Field(..., description="LLM提供商")
    model: str = Field(..., description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, description="最大token数")
    api_key: Optional[str] = Field(None, description="API密钥")
    base_url: Optional[str] = Field(None, description="API基础URL")
    timeout: int = Field(30, ge=1, description="请求超时时间(秒)")
    max_retries: int = Field(3, ge=0, description="最大重试次数")
    
    class Config:
        """Pydantic配置"""
        validate_assignment = True


class LLMProviderConfig(BaseModel):
    """LLM提供商配置"""
    
    basic: LLMConfig = Field(..., description="基础模型配置")
    advanced: LLMConfig = Field(..., description="高级模型配置")
    reasoning: LLMConfig = Field(..., description="推理模型配置")
    
    def get_config_by_type(self, llm_type: LLMType) -> LLMConfig:
        """根据LLM类型获取配置"""
        if llm_type == LLMType.BASIC:
            return self.basic
        elif llm_type == LLMType.ADVANCED:
            return self.advanced
        elif llm_type == LLMType.REASONING:
            return self.reasoning
        else:
            return self.basic


class AgentLLMMapping(BaseModel):
    """智能体LLM映射配置"""
    
    coordinator: LLMType = Field(LLMType.BASIC, description="协调器使用的LLM类型")
    planner: LLMType = Field(LLMType.ADVANCED, description="规划器使用的LLM类型")
    researcher: LLMType = Field(LLMType.ADVANCED, description="研究员使用的LLM类型")
    coder: LLMType = Field(LLMType.ADVANCED, description="编码员使用的LLM类型")
    reporter: LLMType = Field(LLMType.ADVANCED, description="报告员使用的LLM类型")
    reviewer: LLMType = Field(LLMType.ADVANCED, description="评审员使用的LLM类型")
    
    def get_llm_type_for_agent(self, agent_type: AgentType) -> LLMType:
        """获取指定智能体的LLM类型"""
        mapping = {
            AgentType.COORDINATOR: self.coordinator,
            AgentType.PLANNER: self.planner,
            AgentType.RESEARCHER: self.researcher,
            AgentType.CODER: self.coder,
            AgentType.REPORTER: self.reporter,
            AgentType.REVIEWER: self.reviewer,
        }
        return mapping.get(agent_type, LLMType.BASIC)