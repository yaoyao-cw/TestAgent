#!/usr/bin/env python3
"""
报告员节点实现
负责生成测试报告、汇总观察结果和格式化输出
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models.state import TestAgentState
from ..models.execution import ExecutionStep, StepType
from ..models.types import TaskType
from ..llm.service import LLMService
from ..exceptions import TestAgentException

logger = logging.getLogger(__name__)


class ReporterNode:
    """报告员节点 - 负责生成测试报告、汇总观察结果和格式化输出"""
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service or self._get_llm_service()
        self.report_templates = self._load_report_templates()
        self.supported_formats = ["markdown", "html", "json"]
    
    def _get_llm_service(self):
        """获取LLM服务"""
        try:
            return LLMService()
        except Exception as e:
            logger.warning(f"无法初始化LLM服务: {e}")
            return None
    
    def _load_report_templates(self) -> Dict[str, str]:
        """加载报告模板"""
        return {
            "test_case_generation": """# 测试用例生成报告

## 任务概述
- **任务主题**: {task_topic}
- **任务类型**: {task_type}
- **执行时间**: {execution_time}
- **语言**: {locale}

## 执行结果
{execution_results}

## 生成的测试用例
{test_cases}

## 总结
{summary}
""",
            "requirement_analysis": """# 需求分析报告

## 任务概述
- **任务主题**: {task_topic}
- **任务类型**: {task_type}
- **执行时间**: {execution_time}
- **语言**: {locale}

## 分析结果
{analysis_results}

## 提取的需求
{requirements}

## 总结
{summary}
""",
            "code_generation": """# 代码生成报告

## 任务概述
- **任务主题**: {task_topic}
- **任务类型**: {task_type}
- **执行时间**: {execution_time}
- **语言**: {locale}

## 生成的代码
{generated_code}

## 代码质量分析
{code_analysis}

## 总结
{summary}
""",
            "generic": """# 测试任务执行报告

## 任务概述
- **任务主题**: {task_topic}
- **任务类型**: {task_type}
- **执行时间**: {execution_time}
- **语言**: {locale}

## 执行步骤
{execution_steps}

## 主要结果
{main_results}

## 总结
{summary}
"""
        }
    
    async def process(self, state: TestAgentState) -> Dict[str, Any]:
        """
        处理报告生成任务
        
        Args:
            state: 包含观察结果和任务信息的系统状态
            
        Returns:
            Dict: 生成的报告和更新后的状态信息
        """
        try:
            logger.info("报告员开始生成报告")
            
            # 获取任务信息
            task_topic = state.get("task_topic") if isinstance(state, dict) else state.task_topic
            task_type = state.get("task_type") if isinstance(state, dict) else state.task_type
            locale = state.get("locale", "zh-CN") if isinstance(state, dict) else getattr(state, 'locale', "zh-CN")
            observations = state.get("observations", []) if isinstance(state, dict) else state.observations
            
            # 生成报告
            report = await self._generate_report(
                task_topic=task_topic,
                task_type=task_type,
                observations=observations,
                locale=locale
            )
            
            # 返回结果
            return {
                "report": report,
                "task_completed": True,
                "next_node": "reviewer",  # 可选：移交给评审员
                "observations": observations
            }
            
        except Exception as e:
            logger.error(f"报告员处理失败: {e}")
            return {
                "report": self._generate_error_report(str(e), task_topic, task_type, locale),
                "task_completed": True,
                "error": True,
                "observations": observations
            }
    
    async def _generate_report(self, task_topic: str, task_type: str, observations: List[Dict], locale: str) -> Dict[str, Any]:
        """
        生成报告
        
        Args:
            task_topic: 任务主题
            task_type: 任务类型
            observations: 观察结果列表
            locale: 语言设置
            
        Returns:
            Dict: 生成的报告
        """
        try:
            # 分析观察结果
            analysis = self._analyze_observations(observations)
            
            # 选择报告模板
            template_type = self._determine_report_template(task_type, observations)
            
            # 生成报告内容
            if self.llm_service:
                report_content = await self._generate_report_with_llm(
                    task_topic, task_type, observations, analysis, locale
                )
            else:
                report_content = self._generate_default_report(
                    task_topic, task_type, observations, analysis, template_type, locale
                )
            
            return {
                "type": "final_report",
                "task_topic": task_topic,
                "task_type": task_type,
                "template_type": template_type,
                "content": report_content,
                "format": "markdown",
                "analysis": analysis,
                "generation_time": datetime.now().isoformat(),
                "locale": locale
            }
            
        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return self._generate_error_report(str(e), task_topic, task_type, locale)  
  
    def _analyze_observations(self, observations: List[Dict]) -> Dict[str, Any]:
        """
        分析观察结果
        
        Args:
            observations: 观察结果列表
            
        Returns:
            Dict: 分析结果
        """
        analysis = {
            "total_steps": len(observations),
            "successful_steps": 0,
            "failed_steps": 0,
            "step_types": {},
            "main_results": [],
            "errors": [],
            "generated_content": []
        }
        
        for obs in observations:
            # 统计成功和失败的步骤
            if obs.get("error"):
                analysis["failed_steps"] += 1
                analysis["errors"].append({
                    "step": obs.get("step_title", "未知步骤"),
                    "error": obs.get("result", {}).get("error", "未知错误")
                })
            else:
                analysis["successful_steps"] += 1
            
            # 统计步骤类型
            step_type = obs.get("step_type", "unknown")
            analysis["step_types"][step_type] = analysis["step_types"].get(step_type, 0) + 1
            
            # 提取主要结果
            result = obs.get("result", {})
            if isinstance(result, dict):
                result_type = result.get("type", "")
                
                # 提取不同类型的结果
                if result_type == "requirement_analysis":
                    analysis["main_results"].append({
                        "type": "需求分析",
                        "content": result.get("analysis_result", "")
                    })
                elif result_type == "test_case_generation":
                    analysis["main_results"].append({
                        "type": "测试用例生成",
                        "content": result.get("test_cases", "")
                    })
                elif result_type in ["test_script_generation", "api_test_generation", "generic_test_generation"]:
                    analysis["generated_content"].append({
                        "type": "代码生成",
                        "framework": result.get("framework", ""),
                        "code": result.get("generated_code", ""),
                        "is_valid": result.get("is_valid", False)
                    })
                elif result_type == "mindmap_generation":
                    analysis["main_results"].append({
                        "type": "思维导图",
                        "content": result.get("mindmap", "")
                    })
        
        return analysis
    
    def _determine_report_template(self, task_type: str, observations: List[Dict]) -> str:
        """
        确定报告模板类型
        
        Args:
            task_type: 任务类型
            observations: 观察结果列表
            
        Returns:
            str: 模板类型
        """
        # 根据任务类型选择模板
        if task_type == TaskType.TEST_CASE_GENERATION.value:
            return "test_case_generation"
        elif task_type == TaskType.REQUIREMENT_EXTRACTION.value:
            return "requirement_analysis"
        elif task_type == TaskType.TEST_SCRIPT_GENERATION.value:
            return "code_generation"
        
        # 根据观察结果中的主要内容类型选择模板
        has_code_generation = any(
            obs.get("result", {}).get("type", "") in ["test_script_generation", "api_test_generation", "generic_test_generation"]
            for obs in observations
        )
        
        if has_code_generation:
            return "code_generation"
        
        has_test_cases = any(
            obs.get("result", {}).get("type") == "test_case_generation"
            for obs in observations
        )
        
        if has_test_cases:
            return "test_case_generation"
        
        has_requirements = any(
            obs.get("result", {}).get("type") == "requirement_analysis"
            for obs in observations
        )
        
        if has_requirements:
            return "requirement_analysis"
        
        # 默认使用通用模板
        return "generic"
    
    async def _generate_report_with_llm(self, task_topic: str, task_type: str, 
                                      observations: List[Dict], analysis: Dict[str, Any], 
                                      locale: str) -> str:
        """
        使用LLM生成报告
        
        Args:
            task_topic: 任务主题
            task_type: 任务类型
            observations: 观察结果列表
            analysis: 分析结果
            locale: 语言设置
            
        Returns:
            str: 生成的报告内容
        """
        try:
            # 构建提示词
            if locale == "zh-CN":
                prompt = f"""
                请根据以下信息生成一份详细的测试任务执行报告：
                
                任务主题: {task_topic}
                任务类型: {task_type}
                
                执行统计:
                - 总步骤数: {analysis['total_steps']}
                - 成功步骤: {analysis['successful_steps']}
                - 失败步骤: {analysis['failed_steps']}
                
                主要结果:
                {self._format_main_results(analysis['main_results'])}
                
                生成的内容:
                {self._format_generated_content(analysis['generated_content'])}
                
                错误信息:
                {self._format_errors(analysis['errors'])}
                
                请生成一份结构化的Markdown格式报告，包含：
                1. 任务概述
                2. 执行结果统计
                3. 主要成果展示
                4. 问题和建议
                5. 总结
                
                报告应该专业、详细且易于理解。
                """
            else:
                prompt = f"""
                Please generate a detailed test task execution report based on the following information:
                
                Task Topic: {task_topic}
                Task Type: {task_type}
                
                Execution Statistics:
                - Total Steps: {analysis['total_steps']}
                - Successful Steps: {analysis['successful_steps']}
                - Failed Steps: {analysis['failed_steps']}
                
                Main Results:
                {self._format_main_results(analysis['main_results'])}
                
                Generated Content:
                {self._format_generated_content(analysis['generated_content'])}
                
                Error Information:
                {self._format_errors(analysis['errors'])}
                
                Please generate a structured Markdown format report including:
                1. Task Overview
                2. Execution Results Statistics
                3. Main Achievements Display
                4. Issues and Recommendations
                5. Summary
                
                The report should be professional, detailed, and easy to understand.
                """
            
            # 生成报告
            report_content = await self.llm_service.generate_response(
                prompt,
                model_type="reporting",
                temperature=0.3
            )
            
            return report_content
            
        except Exception as e:
            logger.error(f"使用LLM生成报告失败: {e}")
            # 回退到默认报告生成
            template_type = self._determine_report_template(task_type, observations)
            return self._generate_default_report(task_topic, task_type, observations, analysis, template_type, locale)
    
    def _generate_default_report(self, task_topic: str, task_type: str, observations: List[Dict], 
                               analysis: Dict[str, Any], template_type: str, locale: str) -> str:
        """
        生成默认报告
        
        Args:
            task_topic: 任务主题
            task_type: 任务类型
            observations: 观察结果列表
            analysis: 分析结果
            template_type: 模板类型
            locale: 语言设置
            
        Returns:
            str: 生成的报告内容
        """
        try:
            template = self.report_templates.get(template_type, self.report_templates["generic"])
            
            # 准备模板变量
            template_vars = {
                "task_topic": task_topic,
                "task_type": self._get_task_type_display_name(task_type, locale),
                "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "locale": locale
            }
            
            # 根据模板类型填充特定内容
            if template_type == "test_case_generation":
                template_vars.update({
                    "execution_results": self._format_execution_results(analysis, locale),
                    "test_cases": self._format_test_cases(analysis, locale),
                    "summary": self._generate_summary(analysis, locale)
                })
            elif template_type == "requirement_analysis":
                template_vars.update({
                    "analysis_results": self._format_analysis_results(analysis, locale),
                    "requirements": self._format_requirements(analysis, locale),
                    "summary": self._generate_summary(analysis, locale)
                })
            elif template_type == "code_generation":
                template_vars.update({
                    "generated_code": self._format_generated_code(analysis, locale),
                    "code_analysis": self._format_code_analysis(analysis, locale),
                    "summary": self._generate_summary(analysis, locale)
                })
            else:  # generic
                template_vars.update({
                    "execution_steps": self._format_execution_steps(observations, locale),
                    "main_results": self._format_main_results_section(analysis, locale),
                    "summary": self._generate_summary(analysis, locale)
                })
            
            # 格式化模板
            return template.format(**template_vars)
            
        except Exception as e:
            logger.error(f"生成默认报告失败: {e}")
            return self._generate_error_report(str(e), task_topic, task_type, locale)
    
    def _generate_error_report(self, error_message: str, task_topic: str, task_type: str, locale: str) -> Dict[str, Any]:
        """
        生成错误报告
        
        Args:
            error_message: 错误信息
            task_topic: 任务主题
            task_type: 任务类型
            locale: 语言设置
            
        Returns:
            Dict: 错误报告
        """
        if locale == "zh-CN":
            content = f"""# 报告生成错误

## 任务信息
- **任务主题**: {task_topic}
- **任务类型**: {task_type}
- **生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 错误信息
```
{error_message}
```

## 说明
报告生成过程中发生错误，请检查系统配置和输入数据。
"""
        else:
            content = f"""# Report Generation Error

## Task Information
- **Task Topic**: {task_topic}
- **Task Type**: {task_type}
- **Generation Time**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Error Information
```
{error_message}
```

## Description
An error occurred during report generation. Please check system configuration and input data.
"""
        
        return {
            "type": "error_report",
            "task_topic": task_topic,
            "task_type": task_type,
            "content": content,
            "format": "markdown",
            "error": True,
            "generation_time": datetime.now().isoformat(),
            "locale": locale
        }    

    # 格式化辅助方法
    def _format_main_results(self, main_results: List[Dict]) -> str:
        """格式化主要结果"""
        if not main_results:
            return "无主要结果"
        
        formatted = []
        for result in main_results:
            formatted.append(f"- **{result['type']}**: {result['content'][:200]}...")
        
        return "\n".join(formatted)
    
    def _format_generated_content(self, generated_content: List[Dict]) -> str:
        """格式化生成的内容"""
        if not generated_content:
            return "无生成内容"
        
        formatted = []
        for content in generated_content:
            status = "✅ 有效" if content.get("is_valid") else "❌ 无效"
            formatted.append(f"- **{content['type']}** ({content.get('framework', 'N/A')}): {status}")
        
        return "\n".join(formatted)
    
    def _format_errors(self, errors: List[Dict]) -> str:
        """格式化错误信息"""
        if not errors:
            return "无错误"
        
        formatted = []
        for error in errors:
            formatted.append(f"- **{error['step']}**: {error['error']}")
        
        return "\n".join(formatted)
    
    def _format_execution_results(self, analysis: Dict[str, Any], locale: str) -> str:
        """格式化执行结果"""
        if locale == "zh-CN":
            return f"""
### 执行统计
- 总步骤数: {analysis['total_steps']}
- 成功步骤: {analysis['successful_steps']}
- 失败步骤: {analysis['failed_steps']}
- 成功率: {(analysis['successful_steps'] / analysis['total_steps'] * 100):.1f}%

### 步骤类型分布
{self._format_step_types(analysis['step_types'])}
"""
        else:
            return f"""
### Execution Statistics
- Total Steps: {analysis['total_steps']}
- Successful Steps: {analysis['successful_steps']}
- Failed Steps: {analysis['failed_steps']}
- Success Rate: {(analysis['successful_steps'] / analysis['total_steps'] * 100):.1f}%

### Step Type Distribution
{self._format_step_types(analysis['step_types'])}
"""
    
    def _format_step_types(self, step_types: Dict[str, int]) -> str:
        """格式化步骤类型分布"""
        if not step_types:
            return "- 无数据"
        
        formatted = []
        for step_type, count in step_types.items():
            formatted.append(f"- {step_type}: {count}")
        
        return "\n".join(formatted)
    
    def _format_test_cases(self, analysis: Dict[str, Any], locale: str) -> str:
        """格式化测试用例"""
        test_case_results = [r for r in analysis['main_results'] if r['type'] == '测试用例生成']
        
        if not test_case_results:
            return "无测试用例生成" if locale == "zh-CN" else "No test cases generated"
        
        formatted = []
        for i, result in enumerate(test_case_results, 1):
            formatted.append(f"### 测试用例组 {i}\n```\n{result['content']}\n```")
        
        return "\n\n".join(formatted)
    
    def _format_analysis_results(self, analysis: Dict[str, Any], locale: str) -> str:
        """格式化分析结果"""
        analysis_results = [r for r in analysis['main_results'] if r['type'] == '需求分析']
        
        if not analysis_results:
            return "无分析结果" if locale == "zh-CN" else "No analysis results"
        
        formatted = []
        for i, result in enumerate(analysis_results, 1):
            formatted.append(f"### 分析结果 {i}\n{result['content']}")
        
        return "\n\n".join(formatted)
    
    def _format_requirements(self, analysis: Dict[str, Any], locale: str) -> str:
        """格式化需求"""
        # 从主要结果中提取需求相关内容
        requirements = []
        for result in analysis['main_results']:
            if '需求' in result['type'] or 'requirement' in result['type'].lower():
                requirements.append(result['content'])
        
        if not requirements:
            return "无提取的需求" if locale == "zh-CN" else "No extracted requirements"
        
        formatted = []
        for i, req in enumerate(requirements, 1):
            formatted.append(f"{i}. {req}")
        
        return "\n".join(formatted)
    
    def _format_generated_code(self, analysis: Dict[str, Any], locale: str) -> str:
        """格式化生成的代码"""
        if not analysis['generated_content']:
            return "无生成代码" if locale == "zh-CN" else "No generated code"
        
        formatted = []
        for i, content in enumerate(analysis['generated_content'], 1):
            status = "✅ 有效" if content.get("is_valid") else "❌ 无效"
            formatted.append(f"""### 代码片段 {i} - {content.get('framework', 'Unknown')} ({status})

```python
{content.get('code', '')[:500]}...
```
""")
        
        return "\n\n".join(formatted)
    
    def _format_code_analysis(self, analysis: Dict[str, Any], locale: str) -> str:
        """格式化代码分析"""
        if not analysis['generated_content']:
            return "无代码分析" if locale == "zh-CN" else "No code analysis"
        
        valid_count = sum(1 for c in analysis['generated_content'] if c.get('is_valid'))
        total_count = len(analysis['generated_content'])
        
        if locale == "zh-CN":
            return f"""
### 代码质量统计
- 生成代码片段数: {total_count}
- 有效代码片段: {valid_count}
- 代码有效率: {(valid_count / total_count * 100):.1f}%

### 使用的框架
{self._format_frameworks(analysis['generated_content'])}
"""
        else:
            return f"""
### Code Quality Statistics
- Generated Code Snippets: {total_count}
- Valid Code Snippets: {valid_count}
- Code Validity Rate: {(valid_count / total_count * 100):.1f}%

### Used Frameworks
{self._format_frameworks(analysis['generated_content'])}
"""
    
    def _format_frameworks(self, generated_content: List[Dict]) -> str:
        """格式化使用的框架"""
        frameworks = {}
        for content in generated_content:
            framework = content.get('framework', 'Unknown')
            frameworks[framework] = frameworks.get(framework, 0) + 1
        
        formatted = []
        for framework, count in frameworks.items():
            formatted.append(f"- {framework}: {count}")
        
        return "\n".join(formatted) if formatted else "- 无框架信息"
    
    def _format_execution_steps(self, observations: List[Dict], locale: str) -> str:
        """格式化执行步骤"""
        if not observations:
            return "无执行步骤" if locale == "zh-CN" else "No execution steps"
        
        formatted = []
        for i, obs in enumerate(observations, 1):
            status = "❌ 失败" if obs.get("error") else "✅ 成功"
            step_title = obs.get("step_title", f"步骤 {i}")
            step_type = obs.get("step_type", "unknown")
            
            formatted.append(f"{i}. **{step_title}** ({step_type}) - {status}")
        
        return "\n".join(formatted)
    
    def _format_main_results_section(self, analysis: Dict[str, Any], locale: str) -> str:
        """格式化主要结果部分"""
        if not analysis['main_results']:
            return "无主要结果" if locale == "zh-CN" else "No main results"
        
        formatted = []
        for result in analysis['main_results']:
            formatted.append(f"""### {result['type']}
{result['content']}
""")
        
        return "\n".join(formatted)
    
    def _generate_summary(self, analysis: Dict[str, Any], locale: str) -> str:
        """生成总结"""
        total_steps = analysis['total_steps']
        successful_steps = analysis['successful_steps']
        failed_steps = analysis['failed_steps']
        
        if locale == "zh-CN":
            summary = f"""本次任务共执行了 {total_steps} 个步骤，其中 {successful_steps} 个步骤成功完成，{failed_steps} 个步骤执行失败。"""
            
            if successful_steps == total_steps:
                summary += "所有步骤都成功完成，任务执行非常顺利。"
            elif successful_steps > failed_steps:
                summary += "大部分步骤成功完成，任务基本达到预期目标。"
            else:
                summary += "存在较多执行失败的步骤，建议检查配置和输入数据。"
            
            if analysis['generated_content']:
                valid_code = sum(1 for c in analysis['generated_content'] if c.get('is_valid'))
                total_code = len(analysis['generated_content'])
                summary += f" 生成了 {total_code} 个代码片段，其中 {valid_code} 个通过了语法验证。"
        
        else:
            summary = f"""This task executed {total_steps} steps in total, with {successful_steps} steps completed successfully and {failed_steps} steps failed."""
            
            if successful_steps == total_steps:
                summary += " All steps completed successfully, task execution was very smooth."
            elif successful_steps > failed_steps:
                summary += " Most steps completed successfully, task basically achieved expected goals."
            else:
                summary += " There are many failed execution steps, recommend checking configuration and input data."
            
            if analysis['generated_content']:
                valid_code = sum(1 for c in analysis['generated_content'] if c.get('is_valid'))
                total_code = len(analysis['generated_content'])
                summary += f" Generated {total_code} code snippets, with {valid_code} passing syntax validation."
        
        return summary
    
    def _get_task_type_display_name(self, task_type: str, locale: str) -> str:
        """获取任务类型显示名称"""
        if locale == "zh-CN":
            type_names = {
                TaskType.TEST_CASE_GENERATION.value: "测试用例生成",
                TaskType.REQUIREMENT_EXTRACTION.value: "需求提取",
                TaskType.TEST_SCRIPT_GENERATION.value: "测试脚本生成",
                TaskType.TEST_SCRIPT_EXECUTION.value: "测试脚本执行"
            }
        else:
            type_names = {
                TaskType.TEST_CASE_GENERATION.value: "Test Case Generation",
                TaskType.REQUIREMENT_EXTRACTION.value: "Requirement Extraction", 
                TaskType.TEST_SCRIPT_GENERATION.value: "Test Script Generation",
                TaskType.TEST_SCRIPT_EXECUTION.value: "Test Script Execution"
            }
        
        return type_names.get(task_type, task_type)
    
    def format_as_html(self, report_content: str) -> str:
        """将Markdown报告转换为HTML格式"""
        try:
            # 简单的Markdown到HTML转换
            html_content = report_content
            
            # 转换标题
            html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
            html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
            html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
            
            # 转换代码块
            html_content = re.sub(r'```(\w+)?\n(.*?)\n```', r'<pre><code>\2</code></pre>', html_content, flags=re.DOTALL)
            
            # 转换粗体
            html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
            
            # 转换列表
            html_content = re.sub(r'^- (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
            
            # 转换段落
            html_content = re.sub(r'\n\n', '</p><p>', html_content)
            html_content = f'<p>{html_content}</p>'
            
            return html_content
            
        except Exception as e:
            logger.error(f"转换HTML格式失败: {e}")
            return report_content
    
    def format_as_json(self, report_data: Dict[str, Any]) -> str:
        """将报告数据转换为JSON格式"""
        try:
            return json.dumps(report_data, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"转换JSON格式失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)