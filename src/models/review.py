"""评审数据模型"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class ReviewScore(BaseModel):
    """评审分数模型"""

    overall_score: float = Field(..., ge=0, le=100, description="总体分数 (0-100)")
    completeness: float = Field(..., ge=0, le=100, description="完整性分数")
    accuracy: float = Field(..., ge=0, le=100, description="准确性分数")
    maintainability: float = Field(..., ge=0, le=100, description="可维护性分数")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    details: Optional[Dict[str, Any]] = Field(None, description="详细评审信息")

    @validator("overall_score", "completeness", "accuracy", "maintainability")
    def validate_score_range(cls, v):
        """验证分数范围"""
        if not 0 <= v <= 100:
            raise ValueError("Score must be between 0 and 100")
        return v

    def get_grade(self) -> str:
        """获取等级评价"""
        if self.overall_score >= 90:
            return "优秀"
        elif self.overall_score >= 80:
            return "良好"
        elif self.overall_score >= 70:
            return "中等"
        elif self.overall_score >= 60:
            return "及格"
        else:
            return "不及格"

    def is_passing(self, threshold: float = 60.0) -> bool:
        """检查是否通过评审

        Args:
            threshold: 通过阈值

        Returns:
            是否通过
        """
        return self.overall_score >= threshold

    def add_suggestion(self, suggestion: str):
        """添加改进建议"""
        if suggestion and suggestion not in self.suggestions:
            self.suggestions.append(suggestion)


class TestCaseReview(ReviewScore):
    """测试用例评审模型"""

    coverage_score: float = Field(..., ge=0, le=100, description="覆盖度分数")
    clarity_score: float = Field(..., ge=0, le=100, description="清晰度分数")
    executability_score: float = Field(..., ge=0, le=100, description="可执行性分数")

    @validator("coverage_score", "clarity_score", "executability_score")
    def validate_additional_scores(cls, v):
        """验证额外分数范围"""
        if not 0 <= v <= 100:
            raise ValueError("Score must be between 0 and 100")
        return v


class TestScriptReview(ReviewScore):
    """测试脚本评审模型"""

    syntax_score: float = Field(..., ge=0, le=100, description="语法正确性分数")
    logic_score: float = Field(..., ge=0, le=100, description="逻辑合理性分数")
    performance_score: float = Field(..., ge=0, le=100, description="性能分数")

    @validator("syntax_score", "logic_score", "performance_score")
    def validate_script_scores(cls, v):
        """验证脚本相关分数范围"""
        if not 0 <= v <= 100:
            raise ValueError("Score must be between 0 and 100")
        return v


class RequirementReview(ReviewScore):
    """需求提取评审模型"""

    extraction_score: float = Field(..., ge=0, le=100, description="提取完整性分数")
    relevance_score: float = Field(..., ge=0, le=100, description="相关性分数")
    structure_score: float = Field(..., ge=0, le=100, description="结构化程度分数")

    @validator("extraction_score", "relevance_score", "structure_score")
    def validate_requirement_scores(cls, v):
        """验证需求相关分数范围"""
        if not 0 <= v <= 100:
            raise ValueError("Score must be between 0 and 100")
        return v
