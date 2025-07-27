#!/usr/bin/env python3
"""
AI辅助的内容优化功能
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..config.logging_config import get_logger
from ..exceptions import TestAgentException
from ..llm.service import get_llm_service

logger = get_logger("content_optimizer")


class OptimizationSuggestion:
    """优化建议"""

    def __init__(
        self,
        suggestion_type: str,
        target: str,
        original_content: str,
        optimized_content: str,
        reason: str,
        confidence: float,
        metadata: Dict[str, Any] = None,
    ):
        self.suggestion_type = suggestion_type
        self.target = target
        self.original_content = original_content
        self.optimized_content = optimized_content
        self.reason = reason
        self.confidence = confidence
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
        self.id = f"opt_{int(self.timestamp.timestamp())}"
        self.applied = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "suggestion_type": self.suggestion_type,
            "target": self.target,
            "original_content": self.original_content,
            "optimized_content": self.optimized_content,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "applied": self.applied,
        }


class ContentOptimizer:
    """内容优化器"""

    def __init__(self):
        self.llm_service = get_llm_service()
        self.optimization_rules = self._init_optimization_rules()
        self.suggestion_history: Dict[str, List[OptimizationSuggestion]] = {}

        logger.info("Content optimizer initialized")

    def _init_optimization_rules(self) -> Dict[str, Dict[str, Any]]:
        """初始化优化规则"""
        return {
            "clarity": {
                "description": "提高内容清晰度",
                "patterns": [
                    r"这个|那个|它",  # 模糊指代
                    r"可能|也许|大概",  # 不确定表达
                    r"等等|之类的",  # 不完整列举
                ],
                "weight": 0.8,
            },
            "conciseness": {
                "description": "提高内容简洁性",
                "patterns": [
                    r"非常|十分|极其",  # 冗余修饰
                    r"的话|来说|而言",  # 冗余表达
                    r"进行|实施|执行.*操作",  # 冗余动词
                ],
                "weight": 0.7,
            },
            "professionalism": {
                "description": "提高专业性",
                "patterns": [
                    r"感觉|觉得|认为",  # 主观表达
                    r"应该|可以|能够",  # 不确定建议
                    r"比较|相对|还算",  # 模糊比较
                ],
                "weight": 0.9,
            },
            "structure": {
                "description": "改善结构组织",
                "patterns": [
                    r"另外|此外|还有",  # 结构连接词
                    r"首先|其次|最后",  # 逻辑顺序
                    r"总之|综上|因此",  # 总结词汇
                ],
                "weight": 0.8,
            },
        }

    async def analyze_content(
        self,
        content: str,
        content_type: str = "report",
        optimization_goals: List[str] = None,
    ) -> Dict[str, Any]:
        """分析内容并生成优化建议

        Args:
            content: 待分析的内容
            content_type: 内容类型 (report, plan, summary)
            optimization_goals: 优化目标列表

        Returns:
            分析结果和优化建议
        """
        try:
            logger.info(f"开始分析内容，类型: {content_type}, 长度: {len(content)}")

            # 1. 基础分析
            basic_analysis = self._analyze_basic_metrics(content)

            # 2. 规则基础分析
            rule_based_issues = self._analyze_with_rules(content, optimization_goals)

            # 3. AI辅助分析
            ai_suggestions = await self._analyze_with_ai(
                content, content_type, optimization_goals
            )

            # 4. 合并和排序建议
            all_suggestions = rule_based_issues + ai_suggestions
            prioritized_suggestions = self._prioritize_suggestions(all_suggestions)

            # 5. 生成分析报告
            analysis_result = {
                "content_id": f"content_{int(datetime.now().timestamp())}",
                "content_type": content_type,
                "basic_metrics": basic_analysis,
                "total_suggestions": len(prioritized_suggestions),
                "high_priority_suggestions": len(
                    [s for s in prioritized_suggestions if s.confidence > 0.8]
                ),
                "suggestions": [s.to_dict() for s in prioritized_suggestions],
                "optimization_score": self._calculate_optimization_score(
                    basic_analysis, prioritized_suggestions
                ),
                "analysis_timestamp": datetime.now().isoformat(),
            }

            logger.info(f"内容分析完成，生成 {len(prioritized_suggestions)} 个优化建议")
            return analysis_result

        except Exception as e:
            logger.error(f"分析内容失败: {e}")
            raise TestAgentException(f"分析内容失败: {e}")

    def _analyze_basic_metrics(self, content: str) -> Dict[str, Any]:
        """分析基础指标"""
        lines = content.split("\n")
        words = content.split()
        sentences = re.split(r"[.!?。！？]", content)

        # 计算可读性指标
        avg_sentence_length = len(words) / max(len(sentences), 1)
        avg_word_length = sum(len(word) for word in words) / max(len(words), 1)

        # 统计标题和列表
        headers = len(re.findall(r"^#+\s", content, re.MULTILINE))
        bullet_points = len(re.findall(r"^\s*[-*+]\s", content, re.MULTILINE))
        numbered_lists = len(re.findall(r"^\s*\d+\.\s", content, re.MULTILINE))

        return {
            "total_characters": len(content),
            "total_words": len(words),
            "total_lines": len(lines),
            "total_sentences": len([s for s in sentences if s.strip()]),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "avg_word_length": round(avg_word_length, 2),
            "headers_count": headers,
            "bullet_points": bullet_points,
            "numbered_lists": numbered_lists,
            "readability_score": self._calculate_readability_score(
                avg_sentence_length, avg_word_length
            ),
        }

    def _calculate_readability_score(
        self, avg_sentence_length: float, avg_word_length: float
    ) -> float:
        """计算可读性分数（简化版）"""
        # 基于句子长度和词汇长度的简化可读性评分
        sentence_score = max(0, 100 - (avg_sentence_length - 15) * 2)
        word_score = max(0, 100 - (avg_word_length - 4) * 10)
        return round((sentence_score + word_score) / 2, 2)

    def _analyze_with_rules(
        self, content: str, optimization_goals: List[str] = None
    ) -> List[OptimizationSuggestion]:
        """基于规则的分析"""
        suggestions = []

        # 选择要应用的规则
        rules_to_apply = optimization_goals or list(self.optimization_rules.keys())

        for rule_name in rules_to_apply:
            if rule_name not in self.optimization_rules:
                continue

            rule = self.optimization_rules[rule_name]
            patterns = rule["patterns"]
            weight = rule["weight"]

            for pattern in patterns:
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                for match in matches:
                    # 获取匹配的上下文
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    context = content[start:end]

                    suggestion = OptimizationSuggestion(
                        suggestion_type=rule_name,
                        target="text_fragment",
                        original_content=match.group(),
                        optimized_content="",  # 将由AI填充
                        reason=f"检测到{rule['description']}问题: {pattern}",
                        confidence=weight * 0.7,  # 规则基础建议置信度较低
                        metadata={
                            "pattern": pattern,
                            "context": context,
                            "position": match.start(),
                        },
                    )
                    suggestions.append(suggestion)

        return suggestions

    async def _analyze_with_ai(
        self, content: str, content_type: str, optimization_goals: List[str] = None
    ) -> List[OptimizationSuggestion]:
        """AI辅助分析"""
        try:
            goals_text = (
                ", ".join(optimization_goals) if optimization_goals else "整体优化"
            )

            prompt = f"""
请分析以下{content_type}内容，并提供优化建议。

优化目标: {goals_text}

内容:
```
{content[:2000]}  # 限制长度避免token超限
```

请从以下方面分析并提供具体的优化建议：
1. 内容清晰度 - 是否表达清楚，避免歧义
2. 逻辑结构 - 是否组织合理，层次分明
3. 专业性 - 是否用词准确，表达专业
4. 简洁性 - 是否简洁明了，避免冗余
5. 完整性 - 是否信息完整，覆盖全面

请以JSON格式回复，包含具体的优化建议：
{{
    "suggestions": [
        {{
            "type": "clarity|structure|professionalism|conciseness|completeness",
            "target": "具体位置或段落",
            "issue": "发现的问题",
            "original": "原始内容片段",
            "optimized": "优化后的内容",
            "reason": "优化理由",
            "confidence": 0.8
        }}
    ],
    "overall_assessment": "整体评估",
    "priority_areas": ["需要优先改进的方面"]
}}
"""

            response = await self.llm_service.generate_response(
                prompt, model_name="gpt-3.5-turbo", temperature=0.2
            )

            # 解析AI响应
            import json

            try:
                ai_result = json.loads(response)
                suggestions = []

                for suggestion_data in ai_result.get("suggestions", []):
                    suggestion = OptimizationSuggestion(
                        suggestion_type=suggestion_data.get("type", "general"),
                        target=suggestion_data.get("target", "content"),
                        original_content=suggestion_data.get("original", ""),
                        optimized_content=suggestion_data.get("optimized", ""),
                        reason=suggestion_data.get("reason", ""),
                        confidence=suggestion_data.get("confidence", 0.7),
                        metadata={
                            "source": "ai_analysis",
                            "issue": suggestion_data.get("issue", ""),
                            "overall_assessment": ai_result.get(
                                "overall_assessment", ""
                            ),
                            "priority_areas": ai_result.get("priority_areas", []),
                        },
                    )
                    suggestions.append(suggestion)

                return suggestions

            except json.JSONDecodeError:
                logger.warning("AI响应格式错误，返回空建议列表")
                return []

        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return []

    def _prioritize_suggestions(
        self, suggestions: List[OptimizationSuggestion]
    ) -> List[OptimizationSuggestion]:
        """优先级排序建议"""

        # 按置信度和重要性排序
        def priority_score(suggestion: OptimizationSuggestion) -> float:
            base_score = suggestion.confidence

            # 根据建议类型调整权重
            type_weights = {
                "clarity": 1.0,
                "professionalism": 0.9,
                "structure": 0.8,
                "conciseness": 0.7,
                "completeness": 0.8,
            }

            type_weight = type_weights.get(suggestion.suggestion_type, 0.6)

            # AI建议权重更高
            if suggestion.metadata.get("source") == "ai_analysis":
                base_score *= 1.2

            return base_score * type_weight

        return sorted(suggestions, key=priority_score, reverse=True)

    def _calculate_optimization_score(
        self, basic_metrics: Dict[str, Any], suggestions: List[OptimizationSuggestion]
    ) -> float:
        """计算优化分数"""
        # 基础分数来自可读性
        base_score = basic_metrics.get("readability_score", 50)

        # 根据建议数量调整分数
        suggestion_penalty = min(30, len(suggestions) * 2)

        # 根据高优先级建议调整
        high_priority_count = len([s for s in suggestions if s.confidence > 0.8])
        high_priority_penalty = min(20, high_priority_count * 5)

        final_score = max(0, base_score - suggestion_penalty - high_priority_penalty)
        return round(final_score, 2)

    async def optimize_content(
        self, content: str, selected_suggestions: List[str], content_id: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """应用优化建议

        Args:
            content: 原始内容
            selected_suggestions: 选中的建议ID列表
            content_id: 内容ID

        Returns:
            (优化后的内容, 应用结果)
        """
        try:
            if content_id and content_id in self.suggestion_history:
                available_suggestions = self.suggestion_history[content_id]
            else:
                # 如果没有历史建议，先分析内容
                analysis_result = await self.analyze_content(content)
                available_suggestions = [
                    OptimizationSuggestion(
                        suggestion_type=s["suggestion_type"],
                        target=s["target"],
                        original_content=s["original_content"],
                        optimized_content=s["optimized_content"],
                        reason=s["reason"],
                        confidence=s["confidence"],
                        metadata=s["metadata"],
                    )
                    for s in analysis_result["suggestions"]
                ]

            # 筛选要应用的建议
            suggestions_to_apply = [
                s for s in available_suggestions if s.id in selected_suggestions
            ]

            if not suggestions_to_apply:
                return content, {"applied_count": 0, "message": "没有选择要应用的建议"}

            # 应用建议
            optimized_content = content
            applied_suggestions = []

            for suggestion in suggestions_to_apply:
                try:
                    if suggestion.original_content and suggestion.optimized_content:
                        # 替换内容
                        optimized_content = optimized_content.replace(
                            suggestion.original_content, suggestion.optimized_content
                        )
                        suggestion.applied = True
                        applied_suggestions.append(suggestion.id)

                except Exception as e:
                    logger.error(f"应用建议失败 {suggestion.id}: {e}")
                    continue

            # 记录应用结果
            application_result = {
                "applied_count": len(applied_suggestions),
                "total_selected": len(selected_suggestions),
                "applied_suggestions": applied_suggestions,
                "optimization_timestamp": datetime.now().isoformat(),
                "content_length_change": len(optimized_content) - len(content),
            }

            logger.info(f"内容优化完成，应用了 {len(applied_suggestions)} 个建议")
            return optimized_content, application_result

        except Exception as e:
            logger.error(f"优化内容失败: {e}")
            raise TestAgentException(f"优化内容失败: {e}")

    async def batch_optimize(
        self, content_sections: Dict[str, str], optimization_goals: List[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """批量优化多个内容段落

        Args:
            content_sections: 内容段落字典 {section_name: content}
            optimization_goals: 优化目标

        Returns:
            优化结果字典
        """
        try:
            results = {}

            for section_name, content in content_sections.items():
                logger.info(f"优化段落: {section_name}")

                # 分析内容
                analysis_result = await self.analyze_content(
                    content,
                    content_type="section",
                    optimization_goals=optimization_goals,
                )

                # 自动应用高置信度建议
                high_confidence_suggestions = [
                    s["id"]
                    for s in analysis_result["suggestions"]
                    if s["confidence"] > 0.8
                ]

                if high_confidence_suggestions:
                    optimized_content, application_result = await self.optimize_content(
                        content, high_confidence_suggestions
                    )
                else:
                    optimized_content = content
                    application_result = {"applied_count": 0}

                results[section_name] = {
                    "original_content": content,
                    "optimized_content": optimized_content,
                    "analysis": analysis_result,
                    "application": application_result,
                }

            logger.info(f"批量优化完成，处理了 {len(content_sections)} 个段落")
            return results

        except Exception as e:
            logger.error(f"批量优化失败: {e}")
            raise TestAgentException(f"批量优化失败: {e}")

    def get_optimization_templates(self) -> Dict[str, str]:
        """获取优化模板"""
        return {
            "executive_summary": """
优化目标：简洁明了，突出重点
- 使用主动语态
- 避免技术术语过多
- 突出关键发现和建议
- 控制在200字以内
""",
            "technical_details": """
优化目标：准确专业，逻辑清晰
- 使用准确的技术术语
- 提供具体的数据和证据
- 保持逻辑结构清晰
- 添加必要的解释说明
""",
            "recommendations": """
优化目标：可操作性强，优先级明确
- 使用动作导向的语言
- 提供具体的实施步骤
- 标明优先级和时间框架
- 考虑实施的可行性
""",
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        total_suggestions = sum(
            len(suggestions) for suggestions in self.suggestion_history.values()
        )
        applied_suggestions = sum(
            len([s for s in suggestions if s.applied])
            for suggestions in self.suggestion_history.values()
        )

        return {
            "total_content_analyzed": len(self.suggestion_history),
            "total_suggestions_generated": total_suggestions,
            "total_suggestions_applied": applied_suggestions,
            "application_rate": applied_suggestions / max(total_suggestions, 1),
            "optimization_rules_count": len(self.optimization_rules),
            "avg_suggestions_per_content": total_suggestions
            / max(len(self.suggestion_history), 1),
        }
