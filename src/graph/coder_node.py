#!/usr/bin/env python3
"""
编码员节点实现
负责生成测试脚本、自动化代码和代码质量检查
"""

import re
import ast
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.messages import HumanMessage, AIMessage

from ..models.state import TestAgentState
from ..models.execution import ExecutionStep, StepType
from ..llm.service import LLMService
from ..tools.tool_manager import get_tool_manager
from ..exceptions import TestAgentException

logger = logging.getLogger(__name__)


class CoderNode:
    """编码员节点 - 负责生成测试脚本、自动化代码和代码质量检查"""
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service or self._get_llm_service()
        self.code_cache = {}  # 代码生成缓存
        self.supported_frameworks = ["pytest", "unittest", "selenium", "requests"]
        self.code_templates = self._load_code_templates()
    
    def _get_llm_service(self):
        """获取LLM服务"""
        try:
            return LLMService()
        except Exception as e:
            logger.warning(f"无法初始化LLM服务: {e}")
            return None
    
    def _load_code_templates(self) -> Dict[str, str]:
        """加载代码模板"""
        return {
            "pytest_basic": "import pytest\n\nclass TestExample:\n    def test_method(self):\n        assert True",
            "unittest_basic": "import unittest\n\nclass TestExample(unittest.TestCase):\n    def test_method(self):\n        self.assertTrue(True)"
        }
    
    async def process(self, state: TestAgentState) -> Dict[str, Any]:
        """
        处理编码任务
        
        Args:
            state: 包含执行计划和当前步骤的系统状态
            
        Returns:
            Dict: 更新后的状态信息
        """
        try:
            logger.info("编码员开始处理任务")
            
            # 获取当前执行计划和步骤
            current_plan = state.get("current_plan") if isinstance(state, dict) else state.current_plan
            current_step_index = state.get("current_step", 0) if isinstance(state, dict) else getattr(state, 'current_step', 0)
            observations = state.get("observations", []) if isinstance(state, dict) else state.observations
            
            if not current_plan or not current_plan.steps:
                raise TestAgentException("没有找到执行计划或步骤")
            
            if current_step_index >= len(current_plan.steps):
                logger.info("所有编码步骤已完成")
                return {
                    "current_step": current_step_index,
                    "next_node": "reporter"
                }
            
            current_step = current_plan.steps[current_step_index]
            logger.info(f"执行步骤: {current_step.title} ({current_step.step_type})")
            
            # 根据步骤类型执行相应的编码任务
            if current_step.step_type == StepType.CODING.value:
                result = await self._execute_coding_step(current_step, state, observations)
            else:
                # 非编码类型的步骤，移交给其他节点
                logger.info(f"步骤类型 {current_step.step_type} 不属于编码员处理范围")
                return {
                    "current_step": current_step_index,
                    "next_node": "reporter"
                }
            
            # 更新观察结果
            observations.append({
                "step_index": current_step_index,
                "step_title": current_step.title,
                "step_type": current_step.step_type,
                "result": result,
                "timestamp": "2024-01-01T00:00:00Z"
            })
            
            # 检查是否还有更多编码步骤
            next_step_index = current_step_index + 1
            has_more_coding_steps = False
            
            for i in range(next_step_index, len(current_plan.steps)):
                step = current_plan.steps[i]
                if step.step_type == StepType.CODING.value:
                    has_more_coding_steps = True
                    break
            
            if has_more_coding_steps:
                # 继续处理下一个编码步骤
                return {
                    "current_step": next_step_index,
                    "observations": observations,
                    "next_node": "coder"
                }
            else:
                # 所有编码步骤完成，移交给报告员
                return {
                    "current_step": next_step_index,
                    "observations": observations,
                    "next_node": "reporter"
                }
                
        except Exception as e:
            logger.error(f"编码员处理失败: {e}")
            # 记录错误并继续流程
            error_result = {
                "type": "coding_error",
                "error": str(e),
                "step_title": current_step.title if 'current_step' in locals() else "未知步骤"
            }
            
            observations = state.get("observations", []) if isinstance(state, dict) else state.observations
            observations.append({
                "step_index": current_step_index,
                "step_title": current_step.title if 'current_step' in locals() else "未知步骤",
                "step_type": "coding",
                "result": error_result,
                "error": True
            })
            
            return {
                "current_step": current_step_index + 1,
                "observations": observations,
                "next_node": "reporter"
            }
    
    async def _execute_coding_step(self, step: ExecutionStep, state: TestAgentState, observations: List[Dict]) -> Dict[str, Any]:
        """
        执行编码步骤
        
        Args:
            step: 执行步骤
            state: 系统状态
            observations: 观察结果列表
            
        Returns:
            Dict: 编码结果
        """
        try:
            # 获取任务信息
            task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
            task_type = state.get("task_type") if isinstance(state, dict) else state.task_type
            locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
            
            # 从观察结果中获取上下文信息
            context_info = self._extract_context_from_observations(observations)
            
            # 根据步骤描述判断编码类型
            coding_type = self._determine_coding_type(step.description)
            
            logger.info(f"编码类型: {coding_type}")
            
            # 执行相应的编码任务
            if coding_type == "test_script":
                return await self._generate_test_script(step, task_topic, context_info, locale)
            elif coding_type == "api_test":
                return await self._generate_api_test_code(step, task_topic, context_info, locale)
            else:
                return await self._generate_generic_test_code(step, task_topic, context_info, locale)
                
        except Exception as e:
            logger.error(f"执行编码步骤失败: {e}")
            return {
                "type": "coding_error",
                "error": str(e),
                "step_title": step.title,
                "step_description": step.description
            }
    
    def _extract_context_from_observations(self, observations: List[Dict]) -> str:
        """
        从观察结果中提取上下文信息
        
        Args:
            observations: 观察结果列表
            
        Returns:
            str: 上下文信息
        """
        context_parts = []
        
        for obs in observations:
            if obs.get("result") and isinstance(obs["result"], dict):
                result = obs["result"]
                
                # 提取需求分析结果
                if result.get("type") == "requirement_analysis":
                    context_parts.append(f"需求分析: {result.get('analysis_result', '')}")
                
                # 提取测试用例信息
                elif result.get("type") == "test_case_generation":
                    context_parts.append(f"测试用例: {result.get('test_cases', '')}")
        
        return "\n\n".join(context_parts) if context_parts else "无相关上下文信息"
    
    def _determine_coding_type(self, description: str) -> str:
        """
        根据步骤描述确定编码类型
        
        Args:
            description: 步骤描述
            
        Returns:
            str: 编码类型
        """
        description_lower = description.lower()
        
        # API测试
        if any(keyword in description_lower for keyword in ["api", "接口", "rest", "http", "请求"]):
            return "api_test"
        
        # UI测试
        elif any(keyword in description_lower for keyword in ["ui", "界面", "页面", "selenium", "web", "浏览器"]):
            return "ui_test"
        
        # 性能测试
        elif any(keyword in description_lower for keyword in ["性能", "performance", "load", "stress", "压力"]):
            return "performance_test"
        
        # 自动化脚本
        elif any(keyword in description_lower for keyword in ["自动化", "automation", "脚本", "script"]):
            return "automation_script"
        
        # 默认为测试脚本
        else:
            return "test_script"  
  
    async def _generate_test_script(self, step: ExecutionStep, task_topic: str, context_info: str, locale: str) -> Dict[str, Any]:
        """
        生成测试脚本
        
        Args:
            step: 执行步骤
            task_topic: 任务主题
            context_info: 上下文信息
            locale: 语言设置
            
        Returns:
            Dict: 测试脚本生成结果
        """
        try:
            if not self.llm_service:
                return self._generate_default_test_script(step, task_topic)
            
            # 构建提示词
            if locale == "zh-CN":
                prompt = f"""
                请根据以下信息生成Python测试脚本：
                
                任务主题: {task_topic}
                步骤标题: {step.title}
                步骤描述: {step.description}
                
                上下文信息:
                {context_info}
                
                请生成一个完整的Python测试脚本，要求：
                1. 使用pytest框架
                2. 包含完整的测试类和测试方法
                3. 添加详细的注释和文档字符串
                4. 包含必要的导入语句
                5. 实现具体的测试逻辑和断言
                
                请只返回Python代码，不要包含其他解释文字。
                """
            else:
                prompt = f"""
                Please generate a Python test script based on the following information:
                
                Task Topic: {task_topic}
                Step Title: {step.title}
                Step Description: {step.description}
                
                Context Information:
                {context_info}
                
                Please generate a complete Python test script with the following requirements:
                1. Use pytest framework
                2. Include complete test classes and test methods
                3. Add detailed comments and docstrings
                4. Include necessary import statements
                5. Implement specific test logic and assertions
                
                Please return only Python code without other explanatory text.
                """
            
            # 生成代码
            generated_code = await self.llm_service.generate_response(
                prompt,
                model_type="coding",
                temperature=0.2
            )
            
            # 清理和验证代码
            cleaned_code = self._clean_generated_code(generated_code)
            validation_result = self._validate_python_code(cleaned_code)
            
            return {
                "type": "test_script_generation",
                "task_topic": task_topic,
                "step_title": step.title,
                "generated_code": cleaned_code,
                "framework": "pytest",
                "is_valid": validation_result["is_valid"],
                "validation_error": validation_result.get("error"),
                "test_methods": self._extract_test_methods(cleaned_code)
            }
            
        except Exception as e:
            logger.error(f"生成测试脚本失败: {e}")
            return self._generate_default_test_script(step, task_topic)
    
    async def _generate_api_test_code(self, step: ExecutionStep, task_topic: str, context_info: str, locale: str) -> Dict[str, Any]:
        """
        生成API测试代码
        
        Args:
            step: 执行步骤
            task_topic: 任务主题
            context_info: 上下文信息
            locale: 语言设置
            
        Returns:
            Dict: API测试代码生成结果
        """
        try:
            if not self.llm_service:
                return self._generate_default_api_test(step, task_topic)
            
            # 构建提示词
            if locale == "zh-CN":
                prompt = f"""
                请根据以下信息生成API测试代码：
                
                任务主题: {task_topic}
                步骤标题: {step.title}
                步骤描述: {step.description}
                
                上下文信息:
                {context_info}
                
                请生成一个完整的API测试脚本，要求：
                1. 使用requests库进行HTTP请求
                2. 使用pytest框架组织测试
                3. 包含GET、POST等常见HTTP方法的测试
                4. 添加请求头、参数、JSON数据的处理
                5. 包含状态码、响应数据的验证
                
                请只返回Python代码。
                """
            else:
                prompt = f"""
                Please generate API test code based on the following information:
                
                Task Topic: {task_topic}
                Step Title: {step.title}
                Step Description: {step.description}
                
                Context Information:
                {context_info}
                
                Please generate a complete API test script with the following requirements:
                1. Use requests library for HTTP requests
                2. Use pytest framework to organize tests
                3. Include tests for common HTTP methods like GET, POST
                4. Add handling for request headers, parameters, JSON data
                5. Include validation of status codes and response data
                
                Please return only Python code.
                """
            
            # 生成代码
            generated_code = await self.llm_service.generate_response(
                prompt,
                model_type="coding",
                temperature=0.2
            )
            
            # 清理和验证代码
            cleaned_code = self._clean_generated_code(generated_code)
            validation_result = self._validate_python_code(cleaned_code)
            
            return {
                "type": "api_test_generation",
                "task_topic": task_topic,
                "step_title": step.title,
                "generated_code": cleaned_code,
                "framework": "pytest + requests",
                "is_valid": validation_result["is_valid"],
                "validation_error": validation_result.get("error"),
                "api_methods": self._extract_api_methods(cleaned_code),
                "test_methods": self._extract_test_methods(cleaned_code)
            }
            
        except Exception as e:
            logger.error(f"生成API测试代码失败: {e}")
            return self._generate_default_api_test(step, task_topic)
    
    async def _generate_generic_test_code(self, step: ExecutionStep, task_topic: str, context_info: str, locale: str) -> Dict[str, Any]:
        """
        生成通用测试代码
        
        Args:
            step: 执行步骤
            task_topic: 任务主题
            context_info: 上下文信息
            locale: 语言设置
            
        Returns:
            Dict: 通用测试代码生成结果
        """
        try:
            if not self.llm_service:
                return self._generate_default_generic_test(step, task_topic)
            
            # 构建提示词
            if locale == "zh-CN":
                prompt = f"""
                请根据以下信息生成测试代码：
                
                任务主题: {task_topic}
                步骤标题: {step.title}
                步骤描述: {step.description}
                
                上下文信息:
                {context_info}
                
                请生成一个完整的测试代码，要求：
                1. 使用适合的测试框架（pytest或unittest）
                2. 包含完整的测试逻辑
                3. 添加详细的注释和文档
                4. 包含测试数据和断言
                5. 添加异常处理
                
                请只返回Python代码。
                """
            else:
                prompt = f"""
                Please generate test code based on the following information:
                
                Task Topic: {task_topic}
                Step Title: {step.title}
                Step Description: {step.description}
                
                Context Information:
                {context_info}
                
                Please generate complete test code with the following requirements:
                1. Use appropriate test framework (pytest or unittest)
                2. Include complete test logic
                3. Add detailed comments and documentation
                4. Include test data and assertions
                5. Add exception handling
                
                Please return only Python code.
                """
            
            # 生成代码
            generated_code = await self.llm_service.generate_response(
                prompt,
                model_type="coding",
                temperature=0.3
            )
            
            # 清理和验证代码
            cleaned_code = self._clean_generated_code(generated_code)
            validation_result = self._validate_python_code(cleaned_code)
            
            return {
                "type": "generic_test_generation",
                "task_topic": task_topic,
                "step_title": step.title,
                "generated_code": cleaned_code,
                "framework": "pytest/unittest",
                "is_valid": validation_result["is_valid"],
                "validation_error": validation_result.get("error"),
                "test_methods": self._extract_test_methods(cleaned_code)
            }
            
        except Exception as e:
            logger.error(f"生成通用测试代码失败: {e}")
            return self._generate_default_generic_test(step, task_topic)    

    def _clean_generated_code(self, code: str) -> str:
        """
        清理生成的代码
        
        Args:
            code: 原始生成的代码
            
        Returns:
            str: 清理后的代码
        """
        # 移除markdown代码块标记
        code = re.sub(r'```python\s*\n?', '', code)
        code = re.sub(r'```\s*$', '', code)
        
        # 移除多余的空行
        lines = code.split('\n')
        cleaned_lines = []
        prev_empty = False
        
        for line in lines:
            if line.strip() == '':
                if not prev_empty:
                    cleaned_lines.append(line)
                prev_empty = True
            else:
                cleaned_lines.append(line)
                prev_empty = False
        
        # 确保代码以换行符结尾
        cleaned_code = '\n'.join(cleaned_lines)
        if not cleaned_code.endswith('\n'):
            cleaned_code += '\n'
        
        return cleaned_code
    
    def _validate_python_code(self, code: str) -> Dict[str, Any]:
        """
        验证Python代码语法
        
        Args:
            code: Python代码
            
        Returns:
            Dict: 验证结果
        """
        try:
            ast.parse(code)
            return {"is_valid": True}
        except SyntaxError as e:
            return {
                "is_valid": False,
                "error": f"语法错误: {e.msg} (行 {e.lineno})",
                "line_number": e.lineno,
                "error_type": "SyntaxError"
            }
        except Exception as e:
            return {
                "is_valid": False,
                "error": f"代码验证失败: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def _extract_test_methods(self, code: str) -> List[str]:
        """
        提取测试方法名称
        
        Args:
            code: Python代码
            
        Returns:
            List[str]: 测试方法名称列表
        """
        try:
            tree = ast.parse(code)
            test_methods = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    test_methods.append(node.name)
            
            return test_methods
            
        except Exception as e:
            logger.warning(f"提取测试方法失败: {e}")
            return []
    
    def _extract_api_methods(self, code: str) -> List[str]:
        """
        提取API方法调用
        
        Args:
            code: Python代码
            
        Returns:
            List[str]: API方法列表
        """
        try:
            api_methods = []
            
            # 查找requests方法调用
            patterns = [
                r'requests\.(get|post|put|delete|patch|head|options)\s*\(',
                r'session\.(get|post|put|delete|patch|head|options)\s*\(',
                r'client\.(get|post|put|delete|patch|head|options)\s*\('
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, code, re.IGNORECASE)
                api_methods.extend([match.upper() for match in matches])
            
            return list(set(api_methods))
            
        except Exception as e:
            logger.warning(f"提取API方法失败: {e}")
            return []
    
    # 默认代码生成方法
    def _generate_default_test_script(self, step: ExecutionStep, task_topic: str) -> Dict[str, Any]:
        """生成默认测试脚本"""
        default_code = f'''import pytest
from typing import Any, Dict, List

class Test{self._sanitize_class_name(task_topic)}:
    """
    测试类: {task_topic}
    步骤: {step.title}
    """
    
    def setup_method(self):
        """测试前置设置"""
        self.test_data = {{}}
        self.expected_results = {{}}
    
    def teardown_method(self):
        """测试后置清理"""
        pass
    
    def test_{self._sanitize_method_name(step.title)}(self):
        """
        测试用例: {step.title}
        描述: {step.description}
        """
        # TODO: 实现具体的测试逻辑
        assert True, "测试用例需要具体实现"
    
    def test_edge_cases(self):
        """测试边界情况"""
        # TODO: 实现边界条件测试
        assert True, "边界条件测试需要具体实现"

if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        return {
            "type": "test_script_generation",
            "task_topic": task_topic,
            "step_title": step.title,
            "generated_code": default_code,
            "framework": "pytest",
            "is_valid": True,
            "is_default": True
        }
    
    def _generate_default_api_test(self, step: ExecutionStep, task_topic: str) -> Dict[str, Any]:
        """生成默认API测试"""
        default_code = f'''import pytest
import requests
import json
from typing import Dict, Any

class TestAPI{self._sanitize_class_name(task_topic)}:
    """
    API测试类: {task_topic}
    步骤: {step.title}
    """
    
    def setup_method(self):
        """测试前置设置"""
        self.base_url = "http://localhost:8000"  # TODO: 配置实际的API地址
        self.headers = {{"Content-Type": "application/json"}}
        self.session = requests.Session()
    
    def teardown_method(self):
        """测试后置清理"""
        self.session.close()
    
    def test_get_request(self):
        """测试GET请求"""
        url = f"{{self.base_url}}/api/test"
        response = self.session.get(url, headers=self.headers)
        
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json"
    
    def test_post_request(self):
        """测试POST请求"""
        url = f"{{self.base_url}}/api/test"
        data = {{"key": "value"}}
        
        response = self.session.post(url, json=data, headers=self.headers)
        
        assert response.status_code in [200, 201]
        response_data = response.json()
        assert isinstance(response_data, dict)

if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        return {
            "type": "api_test_generation",
            "task_topic": task_topic,
            "step_title": step.title,
            "generated_code": default_code,
            "framework": "pytest + requests",
            "is_valid": True,
            "is_default": True
        }
    
    def _generate_default_generic_test(self, step: ExecutionStep, task_topic: str) -> Dict[str, Any]:
        """生成默认通用测试"""
        default_code = f'''import pytest
from typing import Any, Dict, List, Optional

class Test{self._sanitize_class_name(task_topic)}:
    """
    通用测试类: {task_topic}
    步骤: {step.title}
    描述: {step.description}
    """
    
    def setup_method(self):
        """方法级别的设置"""
        self.test_data = {{
            "input": "test_input",
            "expected": "expected_output"
        }}
    
    def teardown_method(self):
        """方法级别的清理"""
        pass
    
    def test_{self._sanitize_method_name(step.title)}(self):
        """
        测试用例: {step.title}
        
        测试步骤:
        1. 准备测试数据
        2. 执行测试操作
        3. 验证测试结果
        """
        # 步骤1: 准备测试数据
        input_data = self.test_data["input"]
        expected_result = self.test_data["expected"]
        
        # 步骤2: 执行测试操作
        # TODO: 实现具体的测试逻辑
        actual_result = self._execute_test_logic(input_data)
        
        # 步骤3: 验证测试结果
        assert actual_result is not None, "测试结果不能为空"
    
    def _execute_test_logic(self, input_data: Any) -> Any:
        """
        执行测试逻辑的辅助方法
        
        Args:
            input_data: 输入数据
            
        Returns:
            Any: 测试结果
        """
        # TODO: 实现具体的测试逻辑
        if input_data is None or input_data == "":
            raise ValueError("输入数据无效")
        
        # 模拟处理逻辑
        return f"processed_{{input_data}}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        
        return {
            "type": "generic_test_generation",
            "task_topic": task_topic,
            "step_title": step.title,
            "generated_code": default_code,
            "framework": "pytest",
            "is_valid": True,
            "is_default": True
        }
    
    def _sanitize_class_name(self, name: str) -> str:
        """清理类名，确保符合Python命名规范"""
        # 移除特殊字符，只保留字母数字和下划线
        sanitized = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '', name)
        # 确保以字母开头
        if sanitized and not sanitized[0].isalpha():
            sanitized = 'Test' + sanitized
        return sanitized or 'TestClass'
    
    def _sanitize_method_name(self, name: str) -> str:
        """清理方法名，确保符合Python命名规范"""
        # 移除特殊字符，替换为下划线
        sanitized = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', name)
        # 转换为小写
        sanitized = sanitized.lower()
        # 移除连续的下划线
        sanitized = re.sub(r'_+', '_', sanitized)
        # 移除开头和结尾的下划线
        sanitized = sanitized.strip('_')
        return sanitized or 'test_method'