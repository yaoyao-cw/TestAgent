#!/usr/bin/env python3
"""
自然语言反馈处理器
将自然语言反馈转换为结构化的计划修改
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..llm.service import get_llm_service
from ..config.logging_config import get_logger
from ..exceptions import TestAgentException

logger = get_logger("feedback_processor")


class FeedbackProcessor:
    """反馈处理器"""
    
    def __init__(self):
        self.llm_service = get_llm_service()
        self.feedback_patterns = self._init_feedback_patterns()
        
        logger.info("Feedback processor initialized")
    
    def _init_feedback_patterns(self) -> Dict[str, str]:
        """初始化反馈模式"""
        return {
            "add_step": r"添加|增加|新增.*步骤|阶段",
            "remove_step": r"删除|移除|去掉.*步骤|阶段",
            "modify_step": r"修改|更改|调整.*步骤|阶段",
            "change_order": r"调整.*顺序|重新排序|先.*后",
            "change_duration": r"时间|持续时间|耗时|duration",
            "change_description": r"描述|说明|解释",
            "change_tools": r"工具|tool",
            "change_agent": r"代理|智能体|agent"
        }
    
    async def process_natural_language_feedback(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """处理自然语言反馈
        
        Args:
            feedback_text: 自然语言反馈
            current_plan: 当前计划
            context: 上下文信息
            
        Returns:
            结构化的修改建议
        """
        try:
            logger.info(f"处理自然语言反馈: {feedback_text[:100]}...")
            
            # 1. 预处理反馈文本
            processed_feedback = self._preprocess_feedback(feedback_text)
            
            # 2. 识别反馈意图
            intent = await self._identify_feedback_intent(processed_feedback, current_plan)
            
            # 3. 提取具体修改
            modifications = await self._extract_modifications(
                processed_feedback, 
                current_plan, 
                intent,
                context
            )
            
            # 4. 验证修改的合理性
            validated_modifications = self._validate_modifications(modifications, current_plan)
            
            result = {
                "original_feedback": feedback_text,
                "processed_feedback": processed_feedback,
                "intent": intent,
                "modifications": validated_modifications,
                "confidence": self._calculate_confidence(intent, validated_modifications),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"反馈处理完成，意图: {intent['primary']}, 置信度: {result['confidence']}")
            return result
            
        except Exception as e:
            logger.error(f"处理自然语言反馈失败: {e}")
            raise TestAgentException(f"处理自然语言反馈失败: {e}")
    
    def _preprocess_feedback(self, feedback_text: str) -> str:
        """预处理反馈文本"""
        # 清理文本
        text = feedback_text.strip()
        
        # 标准化标点符号
        text = re.sub(r'[，。！？；：]', ',', text)
        
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    async def _identify_feedback_intent(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """识别反馈意图"""
        try:
            # 使用规则匹配进行初步识别
            rule_based_intent = self._rule_based_intent_detection(feedback_text)
            
            # 使用LLM进行深度意图识别
            llm_intent = await self._llm_based_intent_detection(feedback_text, current_plan)
            
            # 合并结果
            combined_intent = self._combine_intents(rule_based_intent, llm_intent)
            
            return combined_intent
            
        except Exception as e:
            logger.error(f"识别反馈意图失败: {e}")
            # 返回默认意图
            return {
                "primary": "modify_step",
                "secondary": [],
                "confidence": 0.3,
                "method": "fallback"
            }
    
    def _rule_based_intent_detection(self, feedback_text: str) -> Dict[str, Any]:
        """基于规则的意图检测"""
        detected_intents = []
        
        for intent, pattern in self.feedback_patterns.items():
            if re.search(pattern, feedback_text, re.IGNORECASE):
                detected_intents.append(intent)
        
        if not detected_intents:
            detected_intents = ["modify_step"]  # 默认意图
        
        return {
            "primary": detected_intents[0],
            "secondary": detected_intents[1:],
            "confidence": 0.7 if len(detected_intents) == 1 else 0.5,
            "method": "rule_based"
        }
    
    async def _llm_based_intent_detection(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """基于LLM的意图检测"""
        try:
            prompt = f"""
分析以下用户反馈，识别用户想要对执行计划进行的操作类型。

当前计划摘要：
- 总步骤数: {len(current_plan.get('steps', []))}
- 计划描述: {current_plan.get('description', '')[:200]}

用户反馈: "{feedback_text}"

请从以下操作类型中选择最匹配的（可以多选）：
1. add_step - 添加新步骤
2. remove_step - 删除步骤
3. modify_step - 修改现有步骤
4. change_order - 调整步骤顺序
5. change_duration - 修改时间估算
6. change_description - 修改描述
7. change_tools - 修改使用的工具
8. change_agent - 修改执行代理

请以JSON格式回复：
{{
    "primary": "主要意图",
    "secondary": ["次要意图列表"],
    "confidence": 0.8,
    "reasoning": "判断理由"
}}
"""
            
            response = await self.llm_service.generate_response(
                prompt,
                model_name="gpt-3.5-turbo",
                temperature=0.1
            )
            
            # 解析LLM响应
            import json
            try:
                llm_result = json.loads(response)
                llm_result["method"] = "llm_based"
                return llm_result
            except json.JSONDecodeError:
                logger.warning("LLM响应格式错误，使用默认意图")
                return {
                    "primary": "modify_step",
                    "secondary": [],
                    "confidence": 0.4,
                    "method": "llm_fallback"
                }
                
        except Exception as e:
            logger.error(f"LLM意图检测失败: {e}")
            return {
                "primary": "modify_step",
                "secondary": [],
                "confidence": 0.3,
                "method": "llm_error"
            }
    
    def _combine_intents(
        self,
        rule_intent: Dict[str, Any],
        llm_intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合并意图检测结果"""
        # 如果两种方法检测到相同的主要意图，提高置信度
        if rule_intent["primary"] == llm_intent["primary"]:
            return {
                "primary": rule_intent["primary"],
                "secondary": list(set(rule_intent["secondary"] + llm_intent["secondary"])),
                "confidence": min(0.9, (rule_intent["confidence"] + llm_intent["confidence"]) / 2 + 0.2),
                "method": "combined",
                "rule_result": rule_intent,
                "llm_result": llm_intent
            }
        
        # 选择置信度更高的结果
        if rule_intent["confidence"] >= llm_intent["confidence"]:
            primary_result = rule_intent
            secondary_result = llm_intent
        else:
            primary_result = llm_intent
            secondary_result = rule_intent
        
        return {
            "primary": primary_result["primary"],
            "secondary": primary_result["secondary"] + [secondary_result["primary"]],
            "confidence": primary_result["confidence"],
            "method": "combined",
            "rule_result": rule_intent,
            "llm_result": llm_intent
        }
    
    async def _extract_modifications(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any],
        intent: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """提取具体修改"""
        try:
            modifications = {}
            
            # 根据意图类型提取不同的修改
            primary_intent = intent["primary"]
            
            if primary_intent == "add_step":
                modifications.update(await self._extract_add_step_modifications(
                    feedback_text, current_plan, context
                ))
            
            elif primary_intent == "remove_step":
                modifications.update(self._extract_remove_step_modifications(
                    feedback_text, current_plan
                ))
            
            elif primary_intent == "modify_step":
                modifications.update(await self._extract_modify_step_modifications(
                    feedback_text, current_plan, context
                ))
            
            elif primary_intent == "change_order":
                modifications.update(self._extract_order_modifications(
                    feedback_text, current_plan
                ))
            
            elif primary_intent == "change_duration":
                modifications.update(self._extract_duration_modifications(
                    feedback_text, current_plan
                ))
            
            elif primary_intent == "change_description":
                modifications.update(await self._extract_description_modifications(
                    feedback_text, current_plan
                ))
            
            return modifications
            
        except Exception as e:
            logger.error(f"提取修改失败: {e}")
            return {}
    
    async def _extract_add_step_modifications(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """提取添加步骤的修改"""
        try:
            prompt = f"""
用户想要在执行计划中添加新步骤。

当前计划步骤：
{self._format_plan_steps(current_plan)}

用户反馈: "{feedback_text}"

请分析用户想要添加什么步骤，并以JSON格式回复：
{{
    "new_steps": [
        {{
            "description": "步骤描述",
            "step_type": "步骤类型",
            "agent": "执行代理",
            "tools": ["使用的工具"],
            "insert_position": "插入位置（数字或'end'）",
            "expected_output": "预期输出"
        }}
    ]
}}
"""
            
            response = await self.llm_service.generate_response(
                prompt,
                model_name="gpt-3.5-turbo",
                temperature=0.2
            )
            
            import json
            result = json.loads(response)
            return {"add_steps": result.get("new_steps", [])}
            
        except Exception as e:
            logger.error(f"提取添加步骤修改失败: {e}")
            return {}
    
    def _extract_remove_step_modifications(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取删除步骤的修改"""
        # 简单的关键词匹配来识别要删除的步骤
        steps_to_remove = []
        
        for i, step in enumerate(current_plan.get("steps", [])):
            step_desc = step.get("description", "").lower()
            if any(keyword in feedback_text.lower() for keyword in step_desc.split()[:3]):
                steps_to_remove.append(i)
        
        return {"remove_steps": steps_to_remove}
    
    async def _extract_modify_step_modifications(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """提取修改步骤的修改"""
        try:
            prompt = f"""
用户想要修改执行计划中的某些步骤。

当前计划步骤：
{self._format_plan_steps(current_plan)}

用户反馈: "{feedback_text}"

请分析用户想要修改哪些步骤的哪些内容，并以JSON格式回复：
{{
    "step_modifications": {{
        "步骤索引": {{
            "description": "新描述（如果要修改）",
            "tools": ["新工具列表（如果要修改）"],
            "agent": "新代理（如果要修改）",
            "expected_output": "新预期输出（如果要修改）"
        }}
    }}
}}
"""
            
            response = await self.llm_service.generate_response(
                prompt,
                model_name="gpt-3.5-turbo",
                temperature=0.2
            )
            
            import json
            result = json.loads(response)
            return {"steps": result.get("step_modifications", {})}
            
        except Exception as e:
            logger.error(f"提取修改步骤修改失败: {e}")
            return {}
    
    def _extract_order_modifications(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取顺序修改"""
        # 简化实现：检测是否包含顺序相关的关键词
        if re.search(r'先.*后|首先.*然后|第一.*第二', feedback_text):
            return {"reorder_steps": True, "new_order": "auto"}
        return {}
    
    def _extract_duration_modifications(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取时间修改"""
        # 查找时间相关的数字
        time_matches = re.findall(r'(\d+)\s*(分钟|小时|天|秒)', feedback_text)
        if time_matches:
            duration = int(time_matches[0][0])
            unit = time_matches[0][1]
            
            # 转换为分钟
            if unit == "小时":
                duration *= 60
            elif unit == "天":
                duration *= 1440
            elif unit == "秒":
                duration /= 60
            
            return {"estimated_duration": duration}
        return {}
    
    async def _extract_description_modifications(
        self,
        feedback_text: str,
        current_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取描述修改"""
        try:
            prompt = f"""
用户想要修改执行计划的描述。

当前描述: "{current_plan.get('description', '')}"

用户反馈: "{feedback_text}"

请生成新的计划描述，保持简洁明了：
"""
            
            response = await self.llm_service.generate_response(
                prompt,
                model_name="gpt-3.5-turbo",
                temperature=0.3
            )
            
            return {"description": response.strip()}
            
        except Exception as e:
            logger.error(f"提取描述修改失败: {e}")
            return {}
    
    def _format_plan_steps(self, plan: Dict[str, Any]) -> str:
        """格式化计划步骤"""
        steps = plan.get("steps", [])
        formatted_steps = []
        
        for i, step in enumerate(steps):
            formatted_steps.append(
                f"{i+1}. {step.get('description', '')} "
                f"(代理: {step.get('agent', '')}, "
                f"工具: {', '.join(step.get('tools', []))})"
            )
        
        return "\n".join(formatted_steps)
    
    def _validate_modifications(
        self,
        modifications: Dict[str, Any],
        current_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证修改的合理性"""
        validated = {}
        
        # 验证添加步骤
        if "add_steps" in modifications:
            valid_steps = []
            for step in modifications["add_steps"]:
                if step.get("description") and step.get("step_type"):
                    valid_steps.append(step)
            if valid_steps:
                validated["add_steps"] = valid_steps
        
        # 验证删除步骤
        if "remove_steps" in modifications:
            valid_indices = [
                i for i in modifications["remove_steps"]
                if 0 <= i < len(current_plan.get("steps", []))
            ]
            if valid_indices:
                validated["remove_steps"] = valid_indices
        
        # 验证步骤修改
        if "steps" in modifications:
            valid_modifications = {}
            for step_id, changes in modifications["steps"].items():
                if changes:  # 只保留非空的修改
                    valid_modifications[step_id] = changes
            if valid_modifications:
                validated["steps"] = valid_modifications
        
        # 验证其他修改
        for key in ["description", "estimated_duration", "reorder_steps"]:
            if key in modifications and modifications[key]:
                validated[key] = modifications[key]
        
        return validated
    
    def _calculate_confidence(
        self,
        intent: Dict[str, Any],
        modifications: Dict[str, Any]
    ) -> float:
        """计算处理结果的置信度"""
        base_confidence = intent.get("confidence", 0.5)
        
        # 如果成功提取了修改，提高置信度
        if modifications:
            modification_bonus = min(0.3, len(modifications) * 0.1)
            base_confidence += modification_bonus
        
        # 如果意图检测方法是组合的，提高置信度
        if intent.get("method") == "combined":
            base_confidence += 0.1
        
        return min(0.95, base_confidence)