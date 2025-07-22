#!/usr/bin/env python3
"""
TestAgent 图节点实现
包含协调器、规划器、研究团队、报告员和评审员等核心节点
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage

from ..models.state import TestAgentState, TaskType
from ..models.execution import ExecutionPlan, ExecutionStep, StepType
from ..llm.service import LLMService
from ..tools.tool_manager import get_tool_manager
from ..exceptions import TestAgentException, PlanningException

logger = logging.getLogger(__name__)


class CoordinatorNode:
    """协调器节点 - 系统入口点，识别用户意图并路由到相应的处理流程"""
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service or self._get_llm_service()
        self.conversation_context = []  # 对话上下文记忆
        self.user_preferences = {}  # 用户偏好设置
    
    def _get_llm_service(self):
        """获取LLM服务，如果失败则返回None"""
        try:
            return LLMService()
        except Exception as e:
            logger.warning(f"无法初始化LLM服务: {e}")
            return None
        
    async def process(self, state: TestAgentState) -> Dict[str, Any]:
        """
        处理用户输入，识别测试相关任务
        
        Args:
            state: 包含用户消息的系统状态
            
        Returns:
            Dict: 更新后的状态信息
        """
        try:
            logger.info("协调器开始处理用户输入")
            
            # 获取最新的用户消息
            if not state.get("messages"):
                raise TestAgentException("没有找到用户消息")
            
            user_message = state["messages"][-1]
            if not isinstance(user_message, HumanMessage):
                raise TestAgentException("最后一条消息不是用户消息")
            
            user_input = user_message.content
            logger.info(f"用户输入: {user_input[:100]}...")
            
            # 更新对话上下文
            self._update_conversation_context(user_input)
            
            # 检测语言并设置locale
            locale = self._detect_language_with_context(user_input)
            logger.info(f"检测到语言: {locale}")
            
            # 学习用户偏好
            self._learn_user_preferences(user_input, locale)
            
            # 判断是否与测试相关
            is_test_related = await self._is_test_related_enhanced(user_input)
            logger.info(f"是否测试相关: {is_test_related}")
            
            if not is_test_related:
                # 非测试相关内容，给出简单回复
                response = self._generate_simple_response(user_input, locale)
                messages = state["messages"] + [AIMessage(content=response)]
                logger.info("非测试相关内容，已生成简单回复")
                return {"messages": messages, "final_report": response}
            
            # 提取任务信息
            task_info = await self._extract_task_info_enhanced(user_input, locale)
            logger.info(f"提取的任务信息: {task_info}")
            
            # 使用工作流工具进行移交
            logger.info("协调器处理完成，准备移交给规划器")
            
            try:
                # 获取工具管理器
                tool_manager = get_tool_manager()
                
                if tool_manager and tool_manager._initialized:
                    # 使用工作流工具进行移交
                    handoff_result = await tool_manager.execute_tool(
                        "workflow", 
                        "handoff_to_planner",
                        task_type=task_info.get("task_type"),
                        task_topic=task_info.get("topic", ""),
                        locale=locale,
                        additional_context=self._get_context_summary()
                    )
                    
                    if handoff_result.get("success"):
                        # 添加移交消息到对话历史
                        messages = state["messages"] + [AIMessage(content=handoff_result.get("message", ""))]
                        
                        return {
                            "locale": locale,
                            "task_topic": task_info.get("topic", ""),
                            "task_type": task_info.get("task_type"),
                            "messages": messages,
                            "next_node": "planner"
                        }
                    else:
                        logger.warning(f"工作流工具移交失败: {handoff_result.get('error')}")
                        
            except Exception as e:
                logger.warning(f"使用工作流工具移交失败: {e}，使用默认移交方式")
            
            # 默认移交方式（如果工作流工具不可用）
            return {
                "locale": locale,
                "task_topic": task_info.get("topic", ""),
                "task_type": task_info.get("task_type"),
                "messages": state["messages"],
                "next_node": "planner"
            }
            
        except Exception as e:
            logger.error(f"协调器处理失败: {e}")
            locale = state.get("locale", "zh-CN")
            error_response = self._generate_error_response(str(e), locale)
            messages = state.get("messages", []) + [AIMessage(content=error_response)]
            return {"messages": messages, "final_report": error_response}
    
    def _detect_language(self, text: str) -> str:
        """
        检测文本语言
        
        Args:
            text: 输入文本
            
        Returns:
            str: 语言代码 (zh-CN 或 en-US)
        """
        # 简单的语言检测：统计中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.sub(r'\s', '', text))
        
        if total_chars == 0:
            return "en-US"
        
        chinese_ratio = chinese_chars / total_chars
        
        # 如果中文字符超过30%，认为是中文
        return "zh-CN" if chinese_ratio > 0.3 else "en-US"
    
    async def _is_test_related(self, user_input: str) -> bool:
        """
        判断输入是否与测试相关
        
        Args:
            user_input: 用户输入
            
        Returns:
            bool: 是否与测试相关
        """
        # 测试相关关键词
        test_keywords = [
            # 中文关键词
            "测试", "测试用例", "测试脚本", "单元测试", "集成测试", "功能测试",
            "自动化测试", "测试计划", "测试报告", "bug", "缺陷", "验证", "校验",
            "需求分析", "需求提取", "测试覆盖", "测试数据", "测试环境",
            # 英文关键词
            "test", "testing", "test case", "test script", "unit test", 
            "integration test", "functional test", "automated test", 
            "test plan", "test report", "bug", "defect", "verify", 
            "validation", "requirement", "coverage", "qa", "quality"
        ]
        
        user_input_lower = user_input.lower()
        
        # 检查是否包含测试相关关键词
        for keyword in test_keywords:
            if keyword.lower() in user_input_lower:
                return True
        
        # 使用LLM进行更智能的判断
        if self.llm_service:
            try:
                prompt = f"""
                请判断以下用户输入是否与软件测试相关。
                
                用户输入: {user_input}
                
                如果输入涉及以下任何内容，请回答"是"：
                - 测试用例生成或设计
                - 测试脚本编写或执行
                - 需求分析或提取
                - 软件质量保证
                - Bug发现或验证
                - 自动化测试
                - 测试计划或策略
                
                如果输入是日常对话、问候、或与测试无关的技术问题，请回答"否"。
                
                请只回答"是"或"否"。
                """
                
                response = await self.llm_service.generate_response(
                    prompt, 
                    model_type="basic",
                    temperature=0.1
                )
                
                return "是" in response or "yes" in response.lower()
                
            except Exception as e:
                logger.warning(f"LLM判断测试相关性失败，使用关键词判断结果: {e}")
        
        return False
    
    async def _extract_task_info(self, user_input: str, locale: str) -> Dict[str, Any]:
        """
        提取任务信息和类型
        
        Args:
            user_input: 用户输入
            locale: 语言设置
            
        Returns:
            Dict: 包含任务主题和类型的信息
        """
        # 首先尝试基于关键词的简单分析
        task_type = self._analyze_task_type_by_keywords(user_input)
        topic = user_input[:50] + "..." if len(user_input) > 50 else user_input
        
        # 如果有LLM服务，使用更智能的分析
        if self.llm_service:
            try:
                if locale == "zh-CN":
                    prompt = f"""
                    请分析以下用户输入，提取任务信息：
                    
                    用户输入: {user_input}
                    
                    请识别任务类型并提取任务主题。任务类型包括：
                    1. test_case_generation - 测试用例生成
                    2. test_script_generation - 测试脚本生成  
                    3. requirement_extraction - 需求内容提取
                    4. test_script_execution - 测试脚本运行
                    
                    请以JSON格式返回结果：
                    {{
                        "topic": "任务主题的简短描述",
                        "task_type": "任务类型代码"
                    }}
                    """
                else:
                    prompt = f"""
                    Please analyze the following user input and extract task information:
                    
                    User input: {user_input}
                    
                    Please identify the task type and extract the task topic. Task types include:
                    1. test_case_generation - Generate test cases
                    2. test_script_generation - Generate test scripts
                    3. requirement_extraction - Extract requirements
                    4. test_script_execution - Execute test scripts
                    
                    Please return the result in JSON format:
                    {{
                        "topic": "Brief description of the task topic",
                        "task_type": "task type code"
                    }}
                    """
                
                response = await self.llm_service.generate_response(
                    prompt,
                    model_type="basic",
                    temperature=0.1
                )
                
                # 解析JSON响应
                try:
                    # 提取JSON部分
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        json_str = json_match.group()
                        task_info = json.loads(json_str)
                        
                        # 验证任务类型
                        if task_info.get("task_type") in [t.value for t in TaskType]:
                            task_info["task_type"] = TaskType(task_info["task_type"])
                            return task_info
                        
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"解析任务信息失败: {e}")
                    
            except Exception as e:
                logger.warning(f"LLM提取任务信息失败: {e}")
        
        # 返回基于关键词分析的结果
        return {
            "topic": topic,
            "task_type": task_type
        }
    
    def _analyze_task_type_by_keywords(self, user_input: str) -> TaskType:
        """
        基于关键词分析任务类型
        
        Args:
            user_input: 用户输入
            
        Returns:
            TaskType: 任务类型
        """
        user_input_lower = user_input.lower()
        
        # 测试脚本生成关键词
        script_keywords = ["脚本", "script", "代码", "code", "自动化", "automation", "编写", "write"]
        if any(keyword in user_input_lower for keyword in script_keywords):
            if any(keyword in user_input_lower for keyword in ["生成", "generate", "创建", "create"]):
                return TaskType.TEST_SCRIPT_GENERATION
            elif any(keyword in user_input_lower for keyword in ["运行", "执行", "run", "execute"]):
                return TaskType.TEST_SCRIPT_EXECUTION
        
        # 需求提取关键词
        requirement_keywords = ["需求", "requirement", "文档", "document", "提取", "extract", "分析", "analyze"]
        if any(keyword in user_input_lower for keyword in requirement_keywords):
            return TaskType.REQUIREMENT_EXTRACTION
        
        # 默认为测试用例生成
        return TaskType.TEST_CASE_GENERATION
    
    def _generate_simple_response(self, user_input: str, locale: str) -> str:
        """
        为非测试相关内容生成简单回复
        
        Args:
            user_input: 用户输入
            locale: 语言设置
            
        Returns:
            str: 简单回复内容
        """
        if locale == "zh-CN":
            if any(greeting in user_input.lower() for greeting in ["你好", "hello", "hi", "嗨"]):
                return """你好！我是TestAgent，一个专门用于测试相关任务的智能助手。

我可以帮助您：
- 生成测试用例
- 编写测试脚本
- 提取需求文档中的关键信息
- 运行和分析测试脚本

请告诉我您需要什么测试相关的帮助！"""
            else:
                return """抱歉，我是TestAgent，专门处理测试相关的任务。

我可以帮助您：
- 📝 生成测试用例
- 🔧 编写测试脚本  
- 📋 提取需求信息
- ▶️ 运行测试脚本

如果您有测试相关的需求，请重新描述您的问题。"""
        else:
            if any(greeting in user_input.lower() for greeting in ["hello", "hi", "hey"]):
                return """Hello! I'm TestAgent, an intelligent assistant specialized in testing-related tasks.

I can help you with:
- Generating test cases
- Writing test scripts
- Extracting requirements from documents
- Running and analyzing test scripts

Please let me know what testing help you need!"""
            else:
                return """Sorry, I'm TestAgent, specialized in testing-related tasks.

I can help you with:
- 📝 Generate test cases
- 🔧 Write test scripts
- 📋 Extract requirements
- ▶️ Run test scripts

If you have testing-related needs, please describe your requirements."""
    
    def _generate_error_response(self, error: str, locale: str) -> str:
        """
        生成错误响应
        
        Args:
            error: 错误信息
            locale: 语言设置
            
        Returns:
            str: 错误响应
        """
        if locale == "zh-CN":
            return f"""抱歉，处理您的请求时遇到了问题：

错误信息：{error}

请稍后重试，或者重新描述您的需求。如果问题持续存在，请联系技术支持。"""
        else:
            return f"""Sorry, I encountered an issue while processing your request:

Error: {error}

Please try again later or rephrase your request. If the problem persists, please contact technical support."""
    
    def _update_conversation_context(self, user_input: str):
        """
        更新对话上下文记忆
        
        Args:
            user_input: 用户输入
        """
        # 保持最近10轮对话的上下文
        max_context_length = 10
        
        # 添加当前输入到上下文
        context_entry = {
            "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
                "coordinator", logging.INFO, "", 0, "", (), None
            )) if logger.handlers else None,
            "user_input": user_input,
            "input_length": len(user_input),
            "contains_keywords": self._extract_keywords(user_input)
        }
        
        self.conversation_context.append(context_entry)
        
        # 保持上下文长度限制
        if len(self.conversation_context) > max_context_length:
            self.conversation_context = self.conversation_context[-max_context_length:]
        
        logger.debug(f"更新对话上下文，当前上下文长度: {len(self.conversation_context)}")
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        从文本中提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 关键词列表
        """
        # 测试相关关键词
        test_keywords = [
            "测试", "测试用例", "测试脚本", "单元测试", "集成测试", "功能测试",
            "自动化测试", "测试计划", "测试报告", "bug", "缺陷", "验证", "校验",
            "需求分析", "需求提取", "测试覆盖", "测试数据", "测试环境",
            "test", "testing", "test case", "test script", "unit test", 
            "integration test", "functional test", "automated test", 
            "test plan", "test report", "bug", "defect", "verify", 
            "validation", "requirement", "coverage", "qa", "quality"
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in test_keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _detect_language_with_context(self, text: str) -> str:
        """
        基于上下文的语言检测
        
        Args:
            text: 输入文本
            
        Returns:
            str: 语言代码
        """
        # 首先使用基础语言检测
        detected_locale = self._detect_language(text)
        
        # 如果有历史上下文，考虑用户的语言偏好
        if self.conversation_context:
            # 统计历史对话中的语言使用情况
            chinese_count = 0
            english_count = 0
            
            for context in self.conversation_context[-5:]:  # 查看最近5轮对话
                context_locale = self._detect_language(context["user_input"])
                if context_locale == "zh-CN":
                    chinese_count += 1
                else:
                    english_count += 1
            
            # 如果历史对话明显偏向某种语言，且当前检测结果不确定时，使用历史偏好
            if chinese_count > english_count * 2:
                self.user_preferences["preferred_language"] = "zh-CN"
            elif english_count > chinese_count * 2:
                self.user_preferences["preferred_language"] = "en-US"
            
            # 如果当前文本很短且检测不准确，使用用户偏好
            if len(text.strip()) < 10 and "preferred_language" in self.user_preferences:
                detected_locale = self.user_preferences["preferred_language"]
        
        return detected_locale
    
    def _learn_user_preferences(self, user_input: str, locale: str):
        """
        学习用户偏好
        
        Args:
            user_input: 用户输入
            locale: 检测到的语言
        """
        # 更新语言偏好
        self.user_preferences["preferred_language"] = locale
        
        # 分析任务类型偏好
        task_type = self._analyze_task_type_by_keywords(user_input)
        if "task_type_history" not in self.user_preferences:
            self.user_preferences["task_type_history"] = []
        
        self.user_preferences["task_type_history"].append(task_type.value)
        
        # 保持最近20个任务类型记录
        if len(self.user_preferences["task_type_history"]) > 20:
            self.user_preferences["task_type_history"] = self.user_preferences["task_type_history"][-20:]
        
        # 分析用户的表达习惯
        if "expression_patterns" not in self.user_preferences:
            self.user_preferences["expression_patterns"] = {
                "avg_input_length": 0,
                "uses_formal_language": False,
                "common_phrases": []
            }
        
        # 更新平均输入长度
        current_avg = self.user_preferences["expression_patterns"]["avg_input_length"]
        input_length = len(user_input)
        
        # 使用简单的累积平均计算
        if current_avg == 0:
            self.user_preferences["expression_patterns"]["avg_input_length"] = input_length
        else:
            # 使用滑动平均，给新输入更多权重
            self.user_preferences["expression_patterns"]["avg_input_length"] = \
                (current_avg * 0.8 + input_length * 0.2)
        
        # 检测是否使用正式语言
        formal_indicators = ["请", "您", "谢谢", "please", "thank you", "could you"]
        if any(indicator in user_input.lower() for indicator in formal_indicators):
            self.user_preferences["expression_patterns"]["uses_formal_language"] = True
        
        logger.debug(f"更新用户偏好: {self.user_preferences}")
    
    async def _is_test_related_enhanced(self, user_input: str) -> bool:
        """
        增强版测试相关性判断，考虑上下文信息
        
        Args:
            user_input: 用户输入
            
        Returns:
            bool: 是否与测试相关
        """
        # 首先使用基础判断
        basic_result = await self._is_test_related(user_input)
        
        # 如果基础判断已经确定是测试相关，直接返回
        if basic_result:
            return True
        
        # 考虑上下文信息进行增强判断
        if self.conversation_context:
            # 检查最近的对话是否都是测试相关的
            recent_test_related = 0
            recent_contexts = self.conversation_context[-3:]  # 最近3轮对话
            
            for context in recent_contexts:
                if context["contains_keywords"]:
                    recent_test_related += 1
            
            # 如果最近的对话都是测试相关的，且当前输入可能是延续
            if recent_test_related >= 2 and len(recent_contexts) >= 2:
                # 检查是否是延续性的表达
                continuation_phrases = [
                    "继续", "还有", "另外", "还需要", "再", "也",
                    "continue", "also", "additionally", "furthermore", "more"
                ]
                
                if any(phrase in user_input.lower() for phrase in continuation_phrases):
                    logger.info("基于上下文判断为测试相关的延续对话")
                    return True
        
        # 检查用户的历史任务类型偏好
        if "task_type_history" in self.user_preferences:
            history = self.user_preferences["task_type_history"]
            if len(history) >= 3:
                # 如果用户最近都在做测试相关任务，倾向于判断为测试相关
                recent_tasks = history[-3:]
                if len(set(recent_tasks)) <= 2:  # 最近任务类型比较集中
                    logger.info("基于用户历史偏好判断可能为测试相关")
                    # 进行更宽松的关键词检查
                    loose_keywords = ["功能", "系统", "应用", "软件", "程序", "代码", 
                                    "function", "system", "application", "software", "program", "code"]
                    if any(keyword in user_input.lower() for keyword in loose_keywords):
                        return True
        
        return False
    
    async def _extract_task_info_enhanced(self, user_input: str, locale: str) -> Dict[str, Any]:
        """
        增强版任务信息提取，考虑用户偏好和上下文
        
        Args:
            user_input: 用户输入
            locale: 语言设置
            
        Returns:
            Dict: 包含任务主题和类型的信息
        """
        # 首先使用基础提取
        basic_info = await self._extract_task_info(user_input, locale)
        
        # 基于用户偏好进行调整
        if "task_type_history" in self.user_preferences:
            history = self.user_preferences["task_type_history"]
            if len(history) >= 3:
                # 统计用户最常用的任务类型
                from collections import Counter
                task_counter = Counter(history[-10:])  # 最近10个任务
                most_common_task = task_counter.most_common(1)[0][0]
                
                # 如果当前任务类型检测不确定，且用户有明显偏好，考虑使用偏好
                if (basic_info["task_type"] == TaskType.TEST_CASE_GENERATION and 
                    task_counter[most_common_task] >= 3):
                    logger.info(f"基于用户偏好调整任务类型: {most_common_task}")
                    basic_info["task_type"] = TaskType(most_common_task)
        
        # 基于上下文丰富任务主题
        if self.conversation_context:
            recent_context = self.conversation_context[-1]
            if recent_context["contains_keywords"]:
                # 如果之前的对话包含更多上下文信息，可以丰富当前任务主题
                context_keywords = recent_context["contains_keywords"]
                if len(context_keywords) > 2:
                    # 将上下文关键词添加到任务主题中
                    enhanced_topic = f"{basic_info['topic']} (相关: {', '.join(context_keywords[:3])})"
                    basic_info["topic"] = enhanced_topic
        
        return basic_info
    
    def _get_context_summary(self) -> str:
        """
        获取上下文摘要，用于工作流移交
        
        Returns:
            str: 上下文摘要
        """
        if not self.conversation_context:
            return ""
        
        # 生成上下文摘要
        recent_contexts = self.conversation_context[-3:]
        
        summary_parts = []
        
        # 用户偏好摘要
        if self.user_preferences:
            preferred_lang = self.user_preferences.get("preferred_language", "zh-CN")
            if preferred_lang == "zh-CN":
                summary_parts.append("用户偏好：中文交流")
            else:
                summary_parts.append("用户偏好：英文交流")
            
            if "task_type_history" in self.user_preferences:
                history = self.user_preferences["task_type_history"]
                if len(history) >= 2:
                    from collections import Counter
                    task_counter = Counter(history[-5:])
                    most_common = task_counter.most_common(1)[0]
                    summary_parts.append(f"常用任务类型：{most_common[0]} ({most_common[1]}次)")
        
        # 最近对话摘要
        if recent_contexts:
            keywords_summary = []
            for context in recent_contexts:
                if context["contains_keywords"]:
                    keywords_summary.extend(context["contains_keywords"])
            
            if keywords_summary:
                unique_keywords = list(set(keywords_summary))[:5]
                summary_parts.append(f"相关关键词：{', '.join(unique_keywords)}")
        
        return " | ".join(summary_parts) if summary_parts else ""


class PlannerNode:
    """规划器节点 - 分析测试任务，创建结构化执行计划"""
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service or self._get_llm_service()
        self.plan_cache = {}  # 计划缓存
        self.max_iterations = 3  # 最大迭代次数
    
    def _get_llm_service(self):
        """获取LLM服务，如果失败则返回None"""
        try:
            return LLMService()
        except Exception as e:
            logger.warning(f"无法初始化LLM服务: {e}")
            return None
    
    async def process(self, state: TestAgentState) -> Dict[str, Any]:
        """
        生成测试任务执行计划
        
        Args:
            state: 包含任务信息的系统状态
            
        Returns:
            Dict: 包含执行计划的更新状态
        """
        try:
            logger.info("规划器开始生成执行计划")
            
            # 检查必要信息
            task_type = state.get("task_type") if isinstance(state, dict) else state.task_type
            task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
            locale = state.get("locale") if isinstance(state, dict) else state.locale
            plan_iterations = state.get("plan_iterations", 0) if isinstance(state, dict) else state.plan_iterations
            
            if not task_type or not task_topic:
                raise PlanningException("缺少任务类型或主题信息")
            
            # 检查是否超过最大迭代次数
            if plan_iterations >= self.max_iterations:
                logger.warning(f"已达到最大迭代次数 {self.max_iterations}，使用默认计划")
                execution_plan = self._create_default_plan(task_type, locale)
            else:
                # 检查缓存
                cache_key = self._generate_cache_key(task_type, task_topic, locale)
                if cache_key in self.plan_cache:
                    logger.info("使用缓存的执行计划")
                    execution_plan = self.plan_cache[cache_key]
                else:
                    # 生成新的执行计划
                    execution_plan = await self._create_execution_plan_enhanced(
                        task_type, 
                        task_topic, 
                        locale,
                        state
                    )
                    
                    # 验证计划
                    if self._validate_execution_plan(execution_plan):
                        # 缓存有效计划
                        self.plan_cache[cache_key] = execution_plan
                        logger.info("执行计划验证通过，已缓存")
                    else:
                        logger.warning("执行计划验证失败，使用默认计划")
                        execution_plan = self._create_default_plan(state.task_type, state.locale)
            
            # 更新状态
            if isinstance(state, dict):
                state["current_plan"] = execution_plan
                state["plan_iterations"] = plan_iterations + 1
            else:
                state.current_plan = execution_plan
                state.plan_iterations += 1
            
            logger.info(f"生成执行计划: {execution_plan.title}")
            logger.info(f"计划步骤数: {len(execution_plan.steps)}")
            
            # 使用工作流工具移交给研究团队
            try:
                tool_manager = get_tool_manager()
                if tool_manager and tool_manager._initialized:
                    handoff_result = await tool_manager.execute_tool(
                        "workflow",
                        "handoff_to_research_team",
                        execution_plan=execution_plan,
                        current_step=0
                    )
                    
                    if handoff_result and handoff_result.get("success"):
                        messages = state.get("messages", []) + [AIMessage(content=handoff_result.get("message", ""))]
                        return {
                            "current_plan": execution_plan,
                            "plan_iterations": plan_iterations + 1,
                            "messages": messages,
                            "next_node": "research_team"
                        }
            except Exception as e:
                logger.warning(f"工作流工具移交失败: {e}")
            
            # 默认返回
            return {
                "current_plan": execution_plan,
                "plan_iterations": plan_iterations + 1,
                "next_node": "research_team"
            }
            
        except Exception as e:
            logger.error(f"规划器处理失败: {e}")
            raise PlanningException(f"生成执行计划失败: {e}")
    
    async def _create_execution_plan(self, task_type: TaskType, task_topic: str, locale: str) -> ExecutionPlan:
        """
        创建执行计划
        
        Args:
            task_type: 任务类型
            task_topic: 任务主题
            locale: 语言设置
            
        Returns:
            ExecutionPlan: 执行计划
        """
        # 根据任务类型创建不同的计划模板
        plan_templates = self._get_plan_templates(locale)
        template = plan_templates.get(task_type.value, plan_templates["default"])
        
        # 使用LLM生成详细计划
        prompt = self._build_planning_prompt(task_type, task_topic, template, locale)
        
        response = await self.llm_service.generate_response(
            prompt,
            model_type="advanced",
            temperature=0.3
        )
        
        # 解析响应并创建执行计划
        return self._parse_execution_plan(response, task_type, locale)
    
    def _get_plan_templates(self, locale: str) -> Dict[str, Dict]:
        """获取计划模板"""
        if locale == "zh-CN":
            return {
                "test_case_generation": {
                    "title": "测试用例生成计划",
                    "steps": [
                        {"title": "需求分析", "type": "research", "desc": "分析需求文档，提取测试要点"},
                        {"title": "测试思维导图", "type": "research", "desc": "生成测试思维导图"},
                        {"title": "测试用例设计", "type": "research", "desc": "基于思维导图设计详细测试用例"}
                    ]
                },
                "test_script_generation": {
                    "title": "测试脚本生成计划", 
                    "steps": [
                        {"title": "测试用例分析", "type": "research", "desc": "分析现有测试用例"},
                        {"title": "脚本框架设计", "type": "coding", "desc": "设计测试脚本框架"},
                        {"title": "脚本实现", "type": "coding", "desc": "实现具体测试脚本"}
                    ]
                },
                "requirement_extraction": {
                    "title": "需求提取计划",
                    "steps": [
                        {"title": "文档检索", "type": "research", "desc": "检索相关需求文档"},
                        {"title": "内容分析", "type": "analysis", "desc": "分析文档内容"},
                        {"title": "需求整理", "type": "research", "desc": "整理和结构化需求信息"}
                    ]
                },
                "test_script_execution": {
                    "title": "测试脚本执行计划",
                    "steps": [
                        {"title": "脚本分析", "type": "coding", "desc": "分析测试脚本结构"},
                        {"title": "环境准备", "type": "coding", "desc": "准备测试执行环境"},
                        {"title": "脚本执行", "type": "coding", "desc": "执行测试脚本并收集结果"}
                    ]
                },
                "default": {
                    "title": "通用测试计划",
                    "steps": [
                        {"title": "需求分析", "type": "research", "desc": "分析用户需求"},
                        {"title": "方案设计", "type": "analysis", "desc": "设计解决方案"}
                    ]
                }
            }
        else:
            return {
                "test_case_generation": {
                    "title": "Test Case Generation Plan",
                    "steps": [
                        {"title": "Requirement Analysis", "type": "research", "desc": "Analyze requirements and extract test points"},
                        {"title": "Test Mind Map", "type": "research", "desc": "Generate test mind map"},
                        {"title": "Test Case Design", "type": "research", "desc": "Design detailed test cases based on mind map"}
                    ]
                },
                "test_script_generation": {
                    "title": "Test Script Generation Plan",
                    "steps": [
                        {"title": "Test Case Analysis", "type": "research", "desc": "Analyze existing test cases"},
                        {"title": "Script Framework Design", "type": "coding", "desc": "Design test script framework"},
                        {"title": "Script Implementation", "type": "coding", "desc": "Implement specific test scripts"}
                    ]
                },
                "requirement_extraction": {
                    "title": "Requirement Extraction Plan",
                    "steps": [
                        {"title": "Document Retrieval", "type": "research", "desc": "Retrieve relevant requirement documents"},
                        {"title": "Content Analysis", "type": "analysis", "desc": "Analyze document content"},
                        {"title": "Requirement Organization", "type": "research", "desc": "Organize and structure requirement information"}
                    ]
                },
                "test_script_execution": {
                    "title": "Test Script Execution Plan",
                    "steps": [
                        {"title": "Script Analysis", "type": "coding", "desc": "Analyze test script structure"},
                        {"title": "Environment Setup", "type": "coding", "desc": "Prepare test execution environment"},
                        {"title": "Script Execution", "type": "coding", "desc": "Execute test scripts and collect results"}
                    ]
                },
                "default": {
                    "title": "General Test Plan",
                    "steps": [
                        {"title": "Requirement Analysis", "type": "research", "desc": "Analyze user requirements"},
                        {"title": "Solution Design", "type": "analysis", "desc": "Design solution approach"}
                    ]
                }
            }
    
    def _build_planning_prompt(self, task_type: TaskType, task_topic: str, template: Dict, locale: str) -> str:
        """构建规划提示词"""
        if locale == "zh-CN":
            return f"""
            请为以下测试任务创建详细的执行计划：
            
            任务类型：{task_type.value}
            任务主题：{task_topic}
            
            基础模板：
            标题：{template['title']}
            步骤：{template['steps']}
            
            请生成一个JSON格式的执行计划，包含：
            1. title: 计划标题
            2. thought: 计划思路和策略
            3. locale: 语言设置 ({locale})
            4. task_type: 任务类型 ({task_type.value})
            5. steps: 执行步骤列表，每个步骤包含：
               - title: 步骤标题
               - description: 详细描述
               - step_type: 步骤类型 (research/coding/analysis)
            6. has_enough_context: 是否有足够上下文信息 (true/false)
            
            请确保计划具体可执行，步骤之间逻辑清晰。
            """
        else:
            return f"""
            Please create a detailed execution plan for the following test task:
            
            Task Type: {task_type.value}
            Task Topic: {task_topic}
            
            Base Template:
            Title: {template['title']}
            Steps: {template['steps']}
            
            Please generate a JSON format execution plan including:
            1. title: Plan title
            2. thought: Planning strategy and approach
            3. locale: Language setting ({locale})
            4. task_type: Task type ({task_type.value})
            5. steps: List of execution steps, each step includes:
               - title: Step title
               - description: Detailed description
               - step_type: Step type (research/coding/analysis)
            6. has_enough_context: Whether there is enough context information (true/false)
            
            Please ensure the plan is specific and executable with clear logic between steps.
            """
    
    def _parse_execution_plan(self, response: str, task_type: TaskType, locale: str) -> ExecutionPlan:
        """解析执行计划响应"""
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("无法找到JSON格式的响应")
            
            json_str = json_match.group()
            plan_data = json.loads(json_str)
            
            # 创建执行步骤
            steps = []
            for step_data in plan_data.get("steps", []):
                step = ExecutionStep(
                    title=step_data.get("title", ""),
                    description=step_data.get("description", ""),
                    step_type=StepType(step_data.get("step_type", "research"))
                )
                steps.append(step)
            
            # 创建执行计划
            execution_plan = ExecutionPlan(
                title=plan_data.get("title", "执行计划"),
                thought=plan_data.get("thought", ""),
                locale=locale,
                task_type=task_type,
                steps=steps,
                has_enough_context=plan_data.get("has_enough_context", False)
            )
            
            return execution_plan
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"解析执行计划失败，使用默认计划: {e}")
            # 返回默认计划
            return self._create_default_plan(task_type, locale)
    
    def _create_default_plan(self, task_type: TaskType, locale: str) -> ExecutionPlan:
        """创建默认执行计划"""
        templates = self._get_plan_templates(locale)
        template = templates.get(task_type.value, templates["default"])
        
        steps = []
        for step_template in template["steps"]:
            step = ExecutionStep(
                title=step_template["title"],
                description=step_template["desc"],
                step_type=StepType(step_template["type"])
            )
            steps.append(step)
        
        return ExecutionPlan(
            title=template["title"],
            thought="基于任务类型生成的标准执行计划",
            locale=locale,
            task_type=task_type,
            steps=steps,
            has_enough_context=False
        )
    
    def _generate_cache_key(self, task_type: TaskType, task_topic: str, locale: str) -> str:
        """生成缓存键"""
        import hashlib
        key_string = f"{task_type.value}_{task_topic}_{locale}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def _create_execution_plan_enhanced(self, task_type: TaskType, task_topic: str, locale: str, state: TestAgentState) -> ExecutionPlan:
        """
        创建增强版执行计划
        
        Args:
            task_type: 任务类型
            task_topic: 任务主题
            locale: 语言设置
            state: 当前状态（包含上下文信息）
            
        Returns:
            ExecutionPlan: 执行计划
        """
        try:
            # 如果没有LLM服务，使用默认计划
            if not self.llm_service:
                logger.warning("LLM服务不可用，使用默认计划")
                return self._create_default_plan(task_type, locale)
            
            # 根据任务类型创建不同的计划模板
            plan_templates = self._get_plan_templates(locale)
            template = plan_templates.get(task_type.value, plan_templates["default"])
            
            # 构建增强版提示词（包含上下文信息）
            prompt = self._build_enhanced_planning_prompt(task_type, task_topic, template, locale, state)
            
            # 使用LLM生成详细计划
            response = await self.llm_service.generate_response(
                prompt,
                model_type="advanced",
                temperature=0.3
            )
            
            # 解析响应并创建执行计划
            execution_plan = self._parse_execution_plan(response, task_type, locale)
            
            # 增强计划（添加上下文相关的步骤）
            enhanced_plan = self._enhance_execution_plan(execution_plan, state)
            
            return enhanced_plan
            
        except Exception as e:
            logger.warning(f"创建增强版执行计划失败: {e}，使用默认计划")
            return self._create_default_plan(task_type, locale)
    
    def _build_enhanced_planning_prompt(self, task_type: TaskType, task_topic: str, template: Dict, locale: str, state: TestAgentState) -> str:
        """构建增强版规划提示词"""
        # 获取上下文信息
        context_info = []
        if hasattr(state, 'messages') and state.messages:
            recent_messages = state.messages[-3:]  # 最近3条消息
            for msg in recent_messages:
                if hasattr(msg, 'content'):
                    context_info.append(msg.content[:100])
        
        context_summary = " | ".join(context_info) if context_info else "无额外上下文"
        
        if locale == "zh-CN":
            return f"""
            请为以下测试任务创建详细的执行计划：
            
            任务类型：{task_type.value}
            任务主题：{task_topic}
            上下文信息：{context_summary}
            
            基础模板：
            标题：{template['title']}
            步骤：{template['steps']}
            
            请生成一个JSON格式的执行计划，包含：
            1. title: 计划标题
            2. thought: 计划思路和策略（考虑上下文信息）
            3. locale: 语言设置 ({locale})
            4. task_type: 任务类型 ({task_type.value})
            5. steps: 执行步骤列表，每个步骤包含：
               - title: 步骤标题
               - description: 详细描述
               - step_type: 步骤类型 (research/coding/analysis)
            6. has_enough_context: 是否有足够上下文信息 (true/false)
            
            请确保计划具体可执行，步骤之间逻辑清晰，并充分考虑上下文信息。
            """
        else:
            return f"""
            Please create a detailed execution plan for the following test task:
            
            Task Type: {task_type.value}
            Task Topic: {task_topic}
            Context Information: {context_summary}
            
            Base Template:
            Title: {template['title']}
            Steps: {template['steps']}
            
            Please generate a JSON format execution plan including:
            1. title: Plan title
            2. thought: Planning strategy and approach (considering context information)
            3. locale: Language setting ({locale})
            4. task_type: Task type ({task_type.value})
            5. steps: List of execution steps, each step includes:
               - title: Step title
               - description: Detailed description
               - step_type: Step type (research/coding/analysis)
            6. has_enough_context: Whether there is enough context information (true/false)
            
            Please ensure the plan is specific and executable with clear logic between steps, 
            and fully consider the context information.
            """
    
    def _enhance_execution_plan(self, plan: ExecutionPlan, state: TestAgentState) -> ExecutionPlan:
        """
        增强执行计划
        
        Args:
            plan: 基础执行计划
            state: 当前状态
            
        Returns:
            ExecutionPlan: 增强后的执行计划
        """
        # 如果计划步骤太少，添加一些通用步骤
        if len(plan.steps) < 2:
            additional_steps = self._get_additional_steps(plan.task_type, plan.locale)
            plan.steps.extend(additional_steps)
        
        # 根据任务类型添加特定的验证步骤
        validation_step = self._get_validation_step(plan.task_type, plan.locale)
        if validation_step:
            plan.steps.append(validation_step)
        
        return plan
    
    def _get_additional_steps(self, task_type: TaskType, locale: str) -> List[ExecutionStep]:
        """获取额外的执行步骤"""
        additional_steps = []
        
        if locale == "zh-CN":
            if task_type == TaskType.TEST_CASE_GENERATION:
                additional_steps.append(ExecutionStep(
                    title="边界条件分析",
                    description="分析边界条件和异常情况",
                    step_type=StepType.ANALYSIS
                ))
            elif task_type == TaskType.TEST_SCRIPT_GENERATION:
                additional_steps.append(ExecutionStep(
                    title="测试数据准备",
                    description="准备测试所需的数据和环境",
                    step_type=StepType.RESEARCH
                ))
        else:
            if task_type == TaskType.TEST_CASE_GENERATION:
                additional_steps.append(ExecutionStep(
                    title="Boundary Condition Analysis",
                    description="Analyze boundary conditions and exception cases",
                    step_type=StepType.ANALYSIS
                ))
            elif task_type == TaskType.TEST_SCRIPT_GENERATION:
                additional_steps.append(ExecutionStep(
                    title="Test Data Preparation",
                    description="Prepare test data and environment",
                    step_type=StepType.RESEARCH
                ))
        
        return additional_steps
    
    def _get_validation_step(self, task_type: TaskType, locale: str) -> Optional[ExecutionStep]:
        """获取验证步骤"""
        if locale == "zh-CN":
            return ExecutionStep(
                title="结果验证",
                description="验证生成结果的完整性和准确性",
                step_type=StepType.ANALYSIS
            )
        else:
            return ExecutionStep(
                title="Result Validation",
                description="Validate the completeness and accuracy of generated results",
                step_type=StepType.ANALYSIS
            )
    
    def _validate_execution_plan(self, plan: ExecutionPlan) -> bool:
        """
        验证执行计划的有效性
        
        Args:
            plan: 执行计划
            
        Returns:
            bool: 是否有效
        """
        try:
            # 基本验证
            if not plan or not plan.title or not plan.steps:
                return False
            
            # 检查步骤数量
            if len(plan.steps) < 1:
                return False
            
            # 检查每个步骤的完整性
            for step in plan.steps:
                if not step.title or not step.description:
                    return False
                
                # 检查步骤类型是否有效
                valid_step_types = [StepType.RESEARCH.value, StepType.CODING.value, StepType.ANALYSIS.value]
                if step.step_type not in valid_step_types:
                    return False
            
            # 检查步骤的逻辑顺序
            if not self._validate_step_sequence(plan.steps):
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"验证执行计划时出错: {e}")
            return False
    
    def _validate_step_sequence(self, steps: List[ExecutionStep]) -> bool:
        """
        验证步骤序列的逻辑性
        
        Args:
            steps: 执行步骤列表
            
        Returns:
            bool: 序列是否合理
        """
        # 简单的序列验证：research步骤通常在前，coding步骤在后
        step_types = [step.step_type for step in steps]
        
        # 如果有coding步骤，前面应该有research或analysis步骤
        coding_indices = [i for i, t in enumerate(step_types) if t == StepType.CODING.value]
        for coding_index in coding_indices:
            if coding_index == 0:
                continue  # 第一个步骤可以是coding
            
            # 检查前面是否有research或analysis步骤
            has_prep_step = any(
                step_types[i] in [StepType.RESEARCH.value, StepType.ANALYSIS.value] 
                for i in range(coding_index)
            )
            if not has_prep_step:
                return False
        
        return True

class ResearcherNode:
    """研究员节点 - 负责执行研究和分析任务，包括文档检索、需求分析、测试用例生成等"""
    
    def __init__(self, llm_service=None, rag_service=None):
        self.llm_service = llm_service or self._get_llm_service()
        self.rag_service = rag_service or self._get_rag_service()
        self.research_cache = {}  # 研究结果缓存
        self.max_rag_results = 5  # 最大RAG检索结果数量
    
    def _get_llm_service(self):
        """获取LLM服务"""
        try:
            return LLMService()
        except Exception as e:
            logger.warning(f"无法初始化LLM服务: {e}")
            return None
    
    def _get_rag_service(self):
        """获取RAG服务"""
        try:
            from ..rag.rag_service import RAGService
            return RAGService()
        except Exception as e:
            logger.warning(f"无法初始化RAG服务: {e}")
            return None
    
    async def process(self, state: TestAgentState) -> Dict[str, Any]:
        """
        处理研究任务
        
        Args:
            state: 包含执行计划和当前步骤的系统状态
            
        Returns:
            Dict: 更新后的状态信息
        """
        try:
            logger.info("研究员开始处理任务")
            
            # 获取当前执行计划和步骤
            current_plan = state.get("current_plan") if isinstance(state, dict) else state.current_plan
            current_step_index = state.get("current_step", 0) if isinstance(state, dict) else getattr(state, 'current_step', 0)
            
            if not current_plan or not current_plan.steps:
                raise TestAgentException("没有找到执行计划或步骤")
            
            if current_step_index >= len(current_plan.steps):
                logger.info("所有研究步骤已完成")
                return {
                    "current_step": current_step_index,
                    "next_node": "reporter"
                }
            
            current_step = current_plan.steps[current_step_index]
            logger.info(f"执行步骤: {current_step.title} ({current_step.step_type})")
            
            # 根据步骤类型执行相应的研究任务
            if current_step.step_type == StepType.RESEARCH.value:
                result = await self._execute_research_step(current_step, state)
            elif current_step.step_type == StepType.ANALYSIS.value:
                result = await self._execute_analysis_step(current_step, state)
            else:
                # 非研究类型的步骤，移交给其他节点
                logger.info(f"步骤类型 {current_step.step_type} 不属于研究员处理范围")
                return {
                    "current_step": current_step_index,
                    "next_node": "coder"
                }
            
            # 更新状态
            observations = state.get("observations", []) if isinstance(state, dict) else state.observations
            observations.append({
                "step_index": current_step_index,
                "step_title": current_step.title,
                "step_type": current_step.step_type,
                "result": result,
                "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
                    "researcher", logging.INFO, "", 0, "", (), None
                )) if logger.handlers else None
            })
            
            # 检查是否还有更多研究步骤
            next_step_index = current_step_index + 1
            has_more_research_steps = False
            
            for i in range(next_step_index, len(current_plan.steps)):
                step = current_plan.steps[i]
                if step.step_type in [StepType.RESEARCH.value, StepType.ANALYSIS.value]:
                    has_more_research_steps = True
                    break
            
            if has_more_research_steps:
                # 继续处理下一个研究步骤
                return {
                    "current_step": next_step_index,
                    "observations": observations,
                    "next_node": "researcher"
                }
            else:
                # 所有研究步骤完成，移交给下一个节点
                return {
                    "current_step": next_step_index,
                    "observations": observations,
                    "next_node": "coder"
                }
            
        except Exception as e:
            logger.error(f"研究员处理失败: {e}")
            raise TestAgentException(f"研究任务执行失败: {e}")
    
    async def _execute_research_step(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        执行研究步骤
        
        Args:
            step: 当前执行步骤
            state: 系统状态
            
        Returns:
            Dict: 研究结果
        """
        logger.info(f"执行研究步骤: {step.title}")
        
        # 根据步骤标题和描述确定具体的研究任务
        if "需求" in step.title or "requirement" in step.title.lower():
            return await self._perform_requirement_analysis(step, state)
        elif "思维导图" in step.title or "mind map" in step.title.lower():
            return await self._generate_test_mind_map(step, state)
        elif "测试用例" in step.title or "test case" in step.title.lower():
            return await self._generate_test_cases(step, state)
        elif "文档" in step.title or "document" in step.title.lower():
            return await self._perform_document_research(step, state)
        else:
            # 通用研究任务
            return await self._perform_general_research(step, state)
    
    async def _execute_analysis_step(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        执行分析步骤
        
        Args:
            step: 当前执行步骤
            state: 系统状态
            
        Returns:
            Dict: 分析结果
        """
        logger.info(f"执行分析步骤: {step.title}")
        
        # 根据步骤标题确定具体的分析任务
        if "边界" in step.title or "boundary" in step.title.lower():
            return await self._analyze_boundary_conditions(step, state)
        elif "验证" in step.title or "validation" in step.title.lower():
            return await self._perform_validation_analysis(step, state)
        else:
            # 通用分析任务
            return await self._perform_general_analysis(step, state)
    
    async def _perform_requirement_analysis(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        执行需求分析
        
        Args:
            step: 当前步骤
            state: 系统状态
            
        Returns:
            Dict: 需求分析结果
        """
        logger.info("开始需求分析")
        
        # 获取任务主题
        task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
        locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
        
        # 使用RAG检索相关文档
        rag_results = []
        if self.rag_service:
            try:
                search_query = f"{task_topic} 需求 功能" if locale == "zh-CN" else f"{task_topic} requirements functionality"
                rag_results = await self.rag_service.search_documents(
                    query=search_query,
                    top_k=self.max_rag_results
                )
                logger.info(f"RAG检索到 {len(rag_results)} 个相关文档")
            except Exception as e:
                logger.warning(f"RAG检索失败: {e}")
        
        # 使用LLM进行需求分析
        analysis_result = ""
        if self.llm_service:
            try:
                # 构建分析提示词
                context = ""
                if rag_results:
                    context = "\n".join([f"文档{i+1}: {doc.get('content', '')[:500]}..." 
                                       for i, doc in enumerate(rag_results)])
                
                if locale == "zh-CN":
                    prompt = f"""
                    请对以下任务进行详细的需求分析：
                    
                    任务主题：{task_topic}
                    步骤描述：{step.description}
                    
                    相关文档内容：
                    {context}
                    
                    请从以下角度进行分析：
                    1. 功能需求：明确需要实现的核心功能
                    2. 非功能需求：性能、安全、可用性等要求
                    3. 用户场景：主要的使用场景和用户流程
                    4. 约束条件：技术约束、业务约束等
                    5. 验收标准：如何判断需求是否满足
                    
                    请提供结构化的分析结果。
                    """
                else:
                    prompt = f"""
                    Please perform a detailed requirement analysis for the following task:
                    
                    Task Topic: {task_topic}
                    Step Description: {step.description}
                    
                    Related Document Content:
                    {context}
                    
                    Please analyze from the following perspectives:
                    1. Functional Requirements: Core functionality to be implemented
                    2. Non-functional Requirements: Performance, security, usability requirements
                    3. User Scenarios: Main use cases and user workflows
                    4. Constraints: Technical and business constraints
                    5. Acceptance Criteria: How to determine if requirements are met
                    
                    Please provide structured analysis results.
                    """
                
                analysis_result = await self.llm_service.generate_response(
                    prompt,
                    model_type="advanced",
                    temperature=0.3
                )
                
            except Exception as e:
                logger.warning(f"LLM需求分析失败: {e}")
                analysis_result = f"需求分析失败: {e}"
        
        return {
            "type": "requirement_analysis",
            "task_topic": task_topic,
            "analysis_result": analysis_result,
            "rag_results": rag_results,
            "step_title": step.title,
            "step_description": step.description
        }
    
    async def _generate_test_mind_map(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        生成测试思维导图
        
        Args:
            step: 当前步骤
            state: 系统状态
            
        Returns:
            Dict: 思维导图生成结果
        """
        logger.info("开始生成测试思维导图")
        
        # 获取任务信息和之前的观察结果
        task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
        locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
        observations = state.get("observations", []) if isinstance(state, dict) else state.observations
        
        # 从之前的观察结果中获取需求分析信息
        requirement_info = ""
        for obs in observations:
            if obs.get("result", {}).get("type") == "requirement_analysis":
                requirement_info = obs["result"].get("analysis_result", "")
                break
        
        mind_map_result = ""
        if self.llm_service:
            try:
                if locale == "zh-CN":
                    prompt = f"""
                    请为以下测试任务生成详细的测试思维导图：
                    
                    任务主题：{task_topic}
                    步骤描述：{step.description}
                    
                    需求分析信息：
                    {requirement_info}
                    
                    请按照以下结构生成测试思维导图：
                    
                    # 测试思维导图：{task_topic}
                    
                    ## 1. 功能测试
                    ### 1.1 正常流程测试
                    - 主要功能点1
                    - 主要功能点2
                    
                    ### 1.2 异常流程测试
                    - 异常情况1
                    - 异常情况2
                    
                    ## 2. 边界值测试
                    ### 2.1 输入边界
                    - 最小值测试
                    - 最大值测试
                    
                    ### 2.2 输出边界
                    - 边界条件验证
                    
                    ## 3. 性能测试
                    ### 3.1 响应时间
                    ### 3.2 并发处理
                    
                    ## 4. 安全测试
                    ### 4.1 输入验证
                    ### 4.2 权限控制
                    
                    ## 5. 兼容性测试
                    ### 5.1 浏览器兼容
                    ### 5.2 设备兼容
                    
                    请根据具体的任务主题，详细展开每个测试点。
                    """
                else:
                    prompt = f"""
                    Please generate a detailed test mind map for the following testing task:
                    
                    Task Topic: {task_topic}
                    Step Description: {step.description}
                    
                    Requirement Analysis Information:
                    {requirement_info}
                    
                    Please generate the test mind map following this structure:
                    
                    # Test Mind Map: {task_topic}
                    
                    ## 1. Functional Testing
                    ### 1.1 Normal Flow Testing
                    - Main function point 1
                    - Main function point 2
                    
                    ### 1.2 Exception Flow Testing
                    - Exception case 1
                    - Exception case 2
                    
                    ## 2. Boundary Value Testing
                    ### 2.1 Input Boundaries
                    - Minimum value testing
                    - Maximum value testing
                    
                    ### 2.2 Output Boundaries
                    - Boundary condition verification
                    
                    ## 3. Performance Testing
                    ### 3.1 Response Time
                    ### 3.2 Concurrent Processing
                    
                    ## 4. Security Testing
                    ### 4.1 Input Validation
                    ### 4.2 Access Control
                    
                    ## 5. Compatibility Testing
                    ### 5.1 Browser Compatibility
                    ### 5.2 Device Compatibility
                    
                    Please elaborate on each test point based on the specific task topic.
                    """
                
                mind_map_result = await self.llm_service.generate_response(
                    prompt,
                    model_type="advanced",
                    temperature=0.4
                )
                
            except Exception as e:
                logger.warning(f"LLM思维导图生成失败: {e}")
                mind_map_result = f"思维导图生成失败: {e}"
        
        return {
            "type": "test_mind_map",
            "task_topic": task_topic,
            "mind_map": mind_map_result,
            "step_title": step.title,
            "step_description": step.description
        }
    
    async def _generate_test_cases(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        生成测试用例
        
        Args:
            step: 当前步骤
            state: 系统状态
            
        Returns:
            Dict: 测试用例生成结果
        """
        logger.info("开始生成测试用例")
        
        # 获取任务信息和之前的观察结果
        task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
        locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
        observations = state.get("observations", []) if isinstance(state, dict) else state.observations
        
        # 从之前的观察结果中获取需求分析和思维导图信息
        requirement_info = ""
        mind_map_info = ""
        
        for obs in observations:
            result = obs.get("result", {})
            if result.get("type") == "requirement_analysis":
                requirement_info = result.get("analysis_result", "")
            elif result.get("type") == "test_mind_map":
                mind_map_info = result.get("mind_map", "")
        
        test_cases_result = ""
        if self.llm_service:
            try:
                if locale == "zh-CN":
                    prompt = f"""
                    请基于以下信息生成详细的测试用例：
                    
                    任务主题：{task_topic}
                    步骤描述：{step.description}
                    
                    需求分析信息：
                    {requirement_info}
                    
                    测试思维导图：
                    {mind_map_info}
                    
                    请按照以下格式生成测试用例：
                    
                    # 测试用例：{task_topic}
                    
                    ## 测试用例1：[用例名称]
                    - **测试目标**：描述测试目标
                    - **前置条件**：执行测试前需要满足的条件
                    - **测试步骤**：
                      1. 步骤1
                      2. 步骤2
                      3. 步骤3
                    - **预期结果**：期望的测试结果
                    - **优先级**：高/中/低
                    - **测试类型**：功能测试/性能测试/安全测试等
                    
                    ## 测试用例2：[用例名称]
                    ...
                    
                    请生成至少5个不同类型的测试用例，包括正常流程、异常流程、边界值等。
                    """
                else:
                    prompt = f"""
                    Please generate detailed test cases based on the following information:
                    
                    Task Topic: {task_topic}
                    Step Description: {step.description}
                    
                    Requirement Analysis Information:
                    {requirement_info}
                    
                    Test Mind Map:
                    {mind_map_info}
                    
                    Please generate test cases in the following format:
                    
                    # Test Cases: {task_topic}
                    
                    ## Test Case 1: [Case Name]
                    - **Test Objective**: Describe the test objective
                    - **Preconditions**: Conditions that must be met before executing the test
                    - **Test Steps**:
                      1. Step 1
                      2. Step 2
                      3. Step 3
                    - **Expected Result**: Expected test result
                    - **Priority**: High/Medium/Low
                    - **Test Type**: Functional/Performance/Security testing, etc.
                    
                    ## Test Case 2: [Case Name]
                    ...
                    
                    Please generate at least 5 different types of test cases, including normal flow, exception flow, boundary values, etc.
                    """
                
                test_cases_result = await self.llm_service.generate_response(
                    prompt,
                    model_type="advanced",
                    temperature=0.3
                )
                
            except Exception as e:
                logger.warning(f"LLM测试用例生成失败: {e}")
                test_cases_result = f"测试用例生成失败: {e}"
        
        return {
            "type": "test_cases",
            "task_topic": task_topic,
            "test_cases": test_cases_result,
            "step_title": step.title,
            "step_description": step.description
        }
    
    async def _perform_document_research(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        执行文档研究
        
        Args:
            step: 当前步骤
            state: 系统状态
            
        Returns:
            Dict: 文档研究结果
        """
        logger.info("开始文档研究")
        
        # 获取任务信息
        task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
        locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
        
        # 使用RAG检索相关文档
        rag_results = []
        if self.rag_service:
            try:
                # 构建搜索查询
                search_queries = [
                    task_topic,
                    f"{task_topic} 文档",
                    f"{task_topic} 规范"
                ]
                
                all_results = []
                for query in search_queries:
                    results = await self.rag_service.search_documents(
                        query=query,
                        top_k=3
                    )
                    all_results.extend(results)
                
                # 去重并限制结果数量
                seen_docs = set()
                for result in all_results:
                    doc_id = result.get('id') or result.get('content', '')[:100]
                    if doc_id not in seen_docs:
                        seen_docs.add(doc_id)
                        rag_results.append(result)
                        if len(rag_results) >= self.max_rag_results:
                            break
                
                logger.info(f"文档研究检索到 {len(rag_results)} 个相关文档")
                
            except Exception as e:
                logger.warning(f"文档检索失败: {e}")
        
        # 使用LLM分析文档内容
        analysis_result = ""
        if self.llm_service and rag_results:
            try:
                # 构建文档内容摘要
                doc_summaries = []
                for i, doc in enumerate(rag_results):
                    content = doc.get('content', '')[:1000]  # 限制长度
                    doc_summaries.append(f"文档{i+1}: {content}")
                
                documents_text = "\n\n".join(doc_summaries)
                
                if locale == "zh-CN":
                    prompt = f"""
                    请分析以下文档内容，提取与任务相关的关键信息：
                    
                    任务主题：{task_topic}
                    步骤描述：{step.description}
                    
                    文档内容：
                    {documents_text}
                    
                    请从以下角度进行分析：
                    1. 关键功能点：文档中描述的主要功能
                    2. 技术规范：相关的技术要求和规范
                    3. 业务流程：涉及的业务流程和规则
                    4. 接口信息：API接口、数据格式等
                    5. 注意事项：需要特别关注的点
                    
                    请提供结构化的分析结果。
                    """
                else:
                    prompt = f"""
                    Please analyze the following document content and extract key information related to the task:
                    
                    Task Topic: {task_topic}
                    Step Description: {step.description}
                    
                    Document Content:
                    {documents_text}
                    
                    Please analyze from the following perspectives:
                    1. Key Features: Main functions described in the documents
                    2. Technical Specifications: Related technical requirements and specifications
                    3. Business Processes: Involved business processes and rules
                    4. Interface Information: API interfaces, data formats, etc.
                    5. Important Notes: Points that need special attention
                    
                    Please provide structured analysis results.
                    """
                
                analysis_result = await self.llm_service.generate_response(
                    prompt,
                    model_type="advanced",
                    temperature=0.3
                )
                
            except Exception as e:
                logger.warning(f"LLM文档分析失败: {e}")
                analysis_result = f"文档分析失败: {e}"
        
        return {
            "type": "document_research",
            "task_topic": task_topic,
            "documents_found": len(rag_results),
            "analysis_result": analysis_result,
            "rag_results": rag_results,
            "step_title": step.title,
            "step_description": step.description
        }
    
    async def _perform_general_research(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        执行通用研究任务
        
        Args:
            step: 当前步骤
            state: 系统状态
            
        Returns:
            Dict: 通用研究结果
        """
        logger.info("开始通用研究任务")
        
        # 获取任务信息
        task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
        locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
        
        research_result = ""
        if self.llm_service:
            try:
                if locale == "zh-CN":
                    prompt = f"""
                    请对以下研究任务进行深入分析：
                    
                    任务主题：{task_topic}
                    步骤标题：{step.title}
                    步骤描述：{step.description}
                    
                    请从以下角度进行研究：
                    1. 任务背景：分析任务的背景和目标
                    2. 关键要素：识别任务中的关键要素和组成部分
                    3. 实施方法：建议的实施方法和步骤
                    4. 潜在风险：可能遇到的问题和风险
                    5. 成功标准：如何判断任务是否成功完成
                    
                    请提供详细的研究分析结果。
                    """
                else:
                    prompt = f"""
                    Please conduct an in-depth analysis of the following research task:
                    
                    Task Topic: {task_topic}
                    Step Title: {step.title}
                    Step Description: {step.description}
                    
                    Please research from the following perspectives:
                    1. Task Background: Analyze the background and objectives of the task
                    2. Key Elements: Identify key elements and components in the task
                    3. Implementation Methods: Recommended implementation methods and steps
                    4. Potential Risks: Possible problems and risks that may be encountered
                    5. Success Criteria: How to determine if the task is successfully completed
                    
                    Please provide detailed research analysis results.
                    """
                
                research_result = await self.llm_service.generate_response(
                    prompt,
                    model_type="advanced",
                    temperature=0.4
                )
                
            except Exception as e:
                logger.warning(f"LLM通用研究失败: {e}")
                research_result = f"通用研究失败: {e}"
        
        return {
            "type": "general_research",
            "task_topic": task_topic,
            "research_result": research_result,
            "step_title": step.title,
            "step_description": step.description
        }
    
    async def _analyze_boundary_conditions(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        分析边界条件
        
        Args:
            step: 当前步骤
            state: 系统状态
            
        Returns:
            Dict: 边界条件分析结果
        """
        logger.info("开始边界条件分析")
        
        # 获取任务信息和之前的观察结果
        task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
        locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
        observations = state.get("observations", []) if isinstance(state, dict) else state.observations
        
        # 从之前的观察结果中获取相关信息
        context_info = ""
        for obs in observations:
            result = obs.get("result", {})
            if result.get("type") in ["requirement_analysis", "test_mind_map", "test_cases"]:
                context_info += f"\n{result.get('analysis_result', result.get('mind_map', result.get('test_cases', '')))}"
        
        boundary_analysis_result = ""
        if self.llm_service:
            try:
                if locale == "zh-CN":
                    prompt = f"""
                    请对以下任务进行边界条件分析：
                    
                    任务主题：{task_topic}
                    步骤描述：{step.description}
                    
                    相关上下文信息：
                    {context_info}
                    
                    请从以下角度分析边界条件：
                    
                    ## 1. 输入边界条件
                    - 最小值边界：输入的最小有效值
                    - 最大值边界：输入的最大有效值
                    - 无效输入：超出范围的输入值
                    - 特殊字符：特殊字符和符号的处理
                    
                    ## 2. 输出边界条件
                    - 正常输出范围：期望的输出值范围
                    - 异常输出：错误情况下的输出
                    - 空值处理：空值或null的处理方式
                    
                    ## 3. 系统边界条件
                    - 性能边界：系统能处理的最大负载
                    - 存储边界：数据存储的限制
                    - 时间边界：超时和时间限制
                    
                    ## 4. 业务边界条件
                    - 权限边界：用户权限的边界
                    - 业务规则边界：业务规则的限制条件
                    
                    请提供具体的边界条件测试建议。
                    """
                else:
                    prompt = f"""
                    Please perform boundary condition analysis for the following task:
                    
                    Task Topic: {task_topic}
                    Step Description: {step.description}
                    
                    Related Context Information:
                    {context_info}
                    
                    Please analyze boundary conditions from the following perspectives:
                    
                    ## 1. Input Boundary Conditions
                    - Minimum boundary: Minimum valid input value
                    - Maximum boundary: Maximum valid input value
                    - Invalid input: Input values outside the range
                    - Special characters: Handling of special characters and symbols
                    
                    ## 2. Output Boundary Conditions
                    - Normal output range: Expected output value range
                    - Exception output: Output in error situations
                    - Null handling: Handling of null or empty values
                    
                    ## 3. System Boundary Conditions
                    - Performance boundary: Maximum load the system can handle
                    - Storage boundary: Data storage limitations
                    - Time boundary: Timeout and time limits
                    
                    ## 4. Business Boundary Conditions
                    - Permission boundary: User permission boundaries
                    - Business rule boundary: Business rule constraints
                    
                    Please provide specific boundary condition testing recommendations.
                    """
                
                boundary_analysis_result = await self.llm_service.generate_response(
                    prompt,
                    model_type="advanced",
                    temperature=0.3
                )
                
            except Exception as e:
                logger.warning(f"LLM边界条件分析失败: {e}")
                boundary_analysis_result = f"边界条件分析失败: {e}"
        
        return {
            "type": "boundary_analysis",
            "task_topic": task_topic,
            "boundary_analysis": boundary_analysis_result,
            "step_title": step.title,
            "step_description": step.description
        }
    
    async def _perform_validation_analysis(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        执行验证分析
        
        Args:
            step: 当前步骤
            state: 系统状态
            
        Returns:
            Dict: 验证分析结果
        """
        logger.info("开始验证分析")
        
        # 获取任务信息和之前的观察结果
        task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
        locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
        observations = state.get("observations", []) if isinstance(state, dict) else state.observations
        
        # 收集所有之前的研究结果
        all_results = []
        for obs in observations:
            result = obs.get("result", {})
            if result.get("type") in ["requirement_analysis", "test_mind_map", "test_cases", "boundary_analysis"]:
                all_results.append(result)
        
        validation_result = ""
        if self.llm_service:
            try:
                # 构建验证上下文
                context_summary = ""
                for result in all_results:
                    result_type = result.get("type", "")
                    if result_type == "requirement_analysis":
                        context_summary += f"\n需求分析结果：{result.get('analysis_result', '')[:500]}..."
                    elif result_type == "test_mind_map":
                        context_summary += f"\n测试思维导图：{result.get('mind_map', '')[:500]}..."
                    elif result_type == "test_cases":
                        context_summary += f"\n测试用例：{result.get('test_cases', '')[:500]}..."
                    elif result_type == "boundary_analysis":
                        context_summary += f"\n边界条件分析：{result.get('boundary_analysis', '')[:500]}..."
                
                if locale == "zh-CN":
                    prompt = f"""
                    请对之前的研究和分析结果进行验证分析：
                    
                    任务主题：{task_topic}
                    步骤描述：{step.description}
                    
                    之前的研究结果：
                    {context_summary}
                    
                    请从以下角度进行验证分析：
                    
                    ## 1. 完整性验证
                    - 需求覆盖度：是否覆盖了所有重要需求
                    - 测试覆盖度：测试用例是否充分覆盖功能点
                    - 场景完整性：是否考虑了所有重要场景
                    
                    ## 2. 一致性验证
                    - 需求一致性：各部分需求描述是否一致
                    - 测试一致性：测试用例与需求是否一致
                    - 逻辑一致性：整体逻辑是否合理
                    
                    ## 3. 可行性验证
                    - 技术可行性：技术实现的可行性
                    - 测试可行性：测试执行的可行性
                    - 资源可行性：所需资源是否合理
                    
                    ## 4. 质量验证
                    - 需求质量：需求描述的清晰度和准确性
                    - 测试质量：测试用例的有效性和可执行性
                    - 整体质量：整体方案的质量评估
                    
                    ## 5. 改进建议
                    - 发现的问题：识别出的问题和不足
                    - 改进方向：具体的改进建议
                    - 优化建议：进一步优化的方向
                    
                    请提供详细的验证分析结果和改进建议。
                    """
                else:
                    prompt = f"""
                    Please perform validation analysis on the previous research and analysis results:
                    
                    Task Topic: {task_topic}
                    Step Description: {step.description}
                    
                    Previous Research Results:
                    {context_summary}
                    
                    Please perform validation analysis from the following perspectives:
                    
                    ## 1. Completeness Validation
                    - Requirement coverage: Whether all important requirements are covered
                    - Test coverage: Whether test cases adequately cover functional points
                    - Scenario completeness: Whether all important scenarios are considered
                    
                    ## 2. Consistency Validation
                    - Requirement consistency: Whether requirement descriptions are consistent
                    - Test consistency: Whether test cases are consistent with requirements
                    - Logical consistency: Whether the overall logic is reasonable
                    
                    ## 3. Feasibility Validation
                    - Technical feasibility: Feasibility of technical implementation
                    - Test feasibility: Feasibility of test execution
                    - Resource feasibility: Whether required resources are reasonable
                    
                    ## 4. Quality Validation
                    - Requirement quality: Clarity and accuracy of requirement descriptions
                    - Test quality: Effectiveness and executability of test cases
                    - Overall quality: Quality assessment of the overall solution
                    
                    ## 5. Improvement Suggestions
                    - Identified issues: Problems and deficiencies identified
                    - Improvement directions: Specific improvement suggestions
                    - Optimization suggestions: Directions for further optimization
                    
                    Please provide detailed validation analysis results and improvement suggestions.
                    """
                
                validation_result = await self.llm_service.generate_response(
                    prompt,
                    model_type="advanced",
                    temperature=0.3
                )
                
            except Exception as e:
                logger.warning(f"LLM验证分析失败: {e}")
                validation_result = f"验证分析失败: {e}"
        
        return {
            "type": "validation_analysis",
            "task_topic": task_topic,
            "validation_result": validation_result,
            "analyzed_results_count": len(all_results),
            "step_title": step.title,
            "step_description": step.description
        }
    
    async def _perform_general_analysis(self, step: ExecutionStep, state: TestAgentState) -> Dict[str, Any]:
        """
        执行通用分析任务
        
        Args:
            step: 当前步骤
            state: 系统状态
            
        Returns:
            Dict: 通用分析结果
        """
        logger.info("开始通用分析任务")
        
        # 获取任务信息和之前的观察结果
        task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
        locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
        observations = state.get("observations", []) if isinstance(state, dict) else state.observations
        
        # 收集相关的上下文信息
        context_info = ""
        for obs in observations:
            result = obs.get("result", {})
            if result.get("type"):
                context_info += f"\n{obs['step_title']}: {str(result)[:300]}..."
        
        analysis_result = ""
        if self.llm_service:
            try:
                if locale == "zh-CN":
                    prompt = f"""
                    请对以下分析任务进行深入分析：
                    
                    任务主题：{task_topic}
                    步骤标题：{step.title}
                    步骤描述：{step.description}
                    
                    相关上下文信息：
                    {context_info}
                    
                    请从以下角度进行分析：
                    1. 现状分析：当前的情况和状态
                    2. 问题识别：存在的问题和挑战
                    3. 原因分析：问题产生的根本原因
                    4. 影响评估：问题可能产生的影响
                    5. 解决方案：建议的解决方案和措施
                    6. 风险评估：实施过程中的风险
                    7. 预期效果：预期能达到的效果
                    
                    请提供结构化的分析结果。
                    """
                else:
                    prompt = f"""
                    Please conduct an in-depth analysis of the following analysis task:
                    
                    Task Topic: {task_topic}
                    Step Title: {step.title}
                    Step Description: {step.description}
                    
                    Related Context Information:
                    {context_info}
                    
                    Please analyze from the following perspectives:
                    1. Current Status Analysis: Current situation and status
                    2. Problem Identification: Existing problems and challenges
                    3. Root Cause Analysis: Root causes of the problems
                    4. Impact Assessment: Potential impacts of the problems
                    5. Solutions: Recommended solutions and measures
                    6. Risk Assessment: Risks in the implementation process
                    7. Expected Results: Expected achievable results
                    
                    Please provide structured analysis results.
                    """
                
                analysis_result = await self.llm_service.generate_response(
                    prompt,
                    model_type="advanced",
                    temperature=0.4
                )
                
            except Exception as e:
                logger.warning(f"LLM通用分析失败: {e}")
                analysis_result = f"通用分析失败: {e}"
        
        return {
            "type": "general_analysis",
            "task_topic": task_topic,
            "analysis_result": analysis_result,
            "step_title": step.title,
            "step_description": step.description
        }


# 导入编码员节点
from .coder_node import CoderNode