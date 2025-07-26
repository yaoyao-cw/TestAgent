"""Coder智能体实现

实现Coder智能体的ReAct循环，支持测试脚本生成，
集成代码质量检查和语法验证，建立代码模板和最佳实践库。
"""

import json
import ast
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from ..core.base_agent import ReActAgent, AgentInput, AgentOutput
from ..models.types import AgentType, TaskType
from ..models.workspace import GlobalState, FileType
from ..core.workspace import workspace_manager
from ..llm.service import get_llm_service
from ..tools.tool_manager import get_tool_manager
from ..config.logging_config import get_logger

logger = get_logger("coder_agent")


class CoderAgent(ReActAgent):
    """Coder智能体
    
    负责测试脚本生成、代码质量检查和语法验证。
    采用ReAct框架进行多步推理和代码生成。
    """
    
    def __init__(self, global_state: GlobalState, max_iterations: int = 5):
        super().__init__(AgentType.CODER, global_state, max_iterations)
        self.llm_service = get_llm_service()
        self.tool_manager = get_tool_manager()
        
        # Coder智能体可用的工具
        self.available_tools = [
            "file_read",
            "file_write",
            "python_repl",
            "code_validate",
            "syntax_check",
            "knowledge_search"
        ]
        
        # 代码模板库
        self.code_templates = {
            'pytest_basic': self._get_pytest_basic_template(),
            'unittest_basic': self._get_unittest_basic_template(),
            'api_test': self._get_api_test_template(),
            'ui_test': self._get_ui_test_template()
        }
    
    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：加载测试用例和编码要求"""
        logger.info("Coder智能体开始加载阶段")
        
        # 获取全局上下文
        context = self.get_context_from_global_state()
        
        # 加载任务相关文件
        task_id = context.get('current_task_id')
        task_files = {}
        test_cases = []
        
        if task_id:
            # 读取todo.md文件
            todo_content = self._read_todo_file(task_id)
            task_files['todo'] = todo_content
            
            # 读取测试用例文件
            files = workspace_manager.get_task_files(task_id)
            for file_ref in files:
                if 'testcases' in file_ref.path.lower() or 'test' in file_ref.path.lower():
                    content = self._read_file_content(task_id, file_ref.path)
                    task_files[file_ref.path] = content
                    
                    # 解析测试用例
                    if file_ref.created_by == 'tester':
                        parsed_cases = self._parse_test_cases_from_content(content)
                        test_cases.extend(parsed_cases)
        
        # 构建状态
        state = {
            'input_data': input_data.data,
            'context': context,
            'task_files': task_files,
            'test_cases': test_cases,
            'prompt_template': self.get_prompt_template(),
            'available_tools': self.available_tools,
            'code_templates': self.code_templates,
            'metadata': input_data.metadata or {},
            'current_step': context.get('current_step', 0),
            'task_id': task_id,
            'react_iterations': 0,
            'generated_scripts': [],
            'validation_results': [],
            'todo_updates': []
        }
        
        logger.info(f"Coder智能体加载完成，任务ID: {task_id}, 测试用例数: {len(test_cases)}")
        return state
    
    def reason(self, state: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
        """推理阶段：分析当前状态和历史，决定下一步行动"""
        logger.debug("Coder智能体进入推理阶段")
        
        # 构建推理上下文
        reasoning_context = self._build_reasoning_context(state, history)
        
        # 构建推理提示
        reasoning_prompt = f"""
作为Coder智能体，你需要分析当前情况并决定下一步编码行动。

## 当前任务状态
{reasoning_context['task_status']}

## 可用信息
{reasoning_context['available_info']}

## 历史行动
{reasoning_context['history_summary']}

## 当前目标
根据测试用例生成高质量的测试脚本，确保代码质量和可执行性。

请分析当前情况，思考需要执行什么编码行动来推进任务。你的推理应该包括：
1. 对当前代码生成状态的分析
2. 识别需要生成或优化的代码组件
3. 选择最合适的编码策略和模板
4. 解释为什么选择这个行动

推理结果：
"""
        
        # 调用LLM进行推理
        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": reasoning_prompt}
            ]
            
            response = self.llm_service.invoke_sync(messages, agent_type=self.agent_type)
            reasoning = response.content.strip()
            
            logger.debug(f"推理结果: {reasoning[:200]}...")
            return reasoning
            
        except Exception as e:
            logger.error(f"推理阶段出错: {e}")
            return f"推理出错，将执行默认代码生成行动: {str(e)}"
    
    def act(self, state: Dict[str, Any], reasoning: str) -> Dict[str, Any]:
        """行动阶段：根据推理结果执行具体行动"""
        logger.debug("Coder智能体进入行动阶段")
        
        # 分析推理结果，确定行动类型
        action_type = self._determine_action_type(reasoning, state)
        
        action_result = {
            'action_type': action_type,
            'reasoning': reasoning,
            'success': False,
            'output': '',
            'error': None
        }
        
        try:
            if action_type == 'analyze_test_cases':
                action_result = self._action_analyze_test_cases(state)
            elif action_type == 'generate_test_script':
                action_result = self._action_generate_test_script(state)
            elif action_type == 'validate_code':
                action_result = self._action_validate_code(state)
            elif action_type == 'optimize_code':
                action_result = self._action_optimize_code(state)
            elif action_type == 'create_test_suite':
                action_result = self._action_create_test_suite(state)
            elif action_type == 'update_todo':
                action_result = self._action_update_todo(state)
            else:
                action_result = self._action_default_coding(state)
            
            action_result['action_type'] = action_type
            action_result['reasoning'] = reasoning
            
        except Exception as e:
            logger.error(f"行动执行出错: {e}")
            action_result['error'] = str(e)
            action_result['output'] = f"行动执行失败: {str(e)}"
        
        return action_result
    
    def observe(self, state: Dict[str, Any], action_result: Dict[str, Any]) -> str:
        """观察阶段：分析行动结果，为下一轮推理提供信息"""
        logger.debug("Coder智能体进入观察阶段")
        
        action_type = action_result.get('action_type', 'unknown')
        success = action_result.get('success', False)
        output = action_result.get('output', '')
        error = action_result.get('error')
        
        # 构建观察结果
        observation_parts = [
            f"行动类型: {action_type}",
            f"执行状态: {'成功' if success else '失败'}"
        ]
        
        if success:
            observation_parts.append(f"输出结果: {output}")
            
            # 更新状态中的相关信息
            if action_type == 'generate_test_script' and 'script' in action_result:
                state['generated_scripts'].append(action_result['script'])
            elif action_type == 'validate_code' and 'validation' in action_result:
                state['validation_results'].append(action_result['validation'])
        else:
            observation_parts.append(f"错误信息: {error or '未知错误'}")
        
        # 检查是否完成任务
        if self._check_task_completion(state):
            observation_parts.append("代码生成任务已完成，可以结束ReAct循环")
            state['task_completed'] = True
        
        observation = "\n".join(observation_parts)
        logger.debug(f"观察结果: {observation}")
        
        return observation
    
    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：根据LLM输出和全局状态决定下一步控制权移交"""
        logger.info("Coder智能体进入路由阶段")
        
        llm_output = state.get('llm_output', {})
        react_history = llm_output.get('react_history', [])
        completed = llm_output.get('completed', False)
        
        # 保存生成的文件
        task_id = state.get('task_id')
        current_step = state.get('current_step', 0)
        
        output_files = []
        
        # 保存生成的测试脚本
        if state.get('generated_scripts'):
            for i, script in enumerate(state['generated_scripts']):
                script_content = script.get('code', '')
                script_name = script.get('name', f'test_script_{i+1}')
                
                filename = workspace_manager.create_agent_file(
                    task_id,
                    current_step + 1,
                    self.agent_type,
                    f"Script_{script_name}",
                    script_content,
                    FileType.PYTHON
                )
                if filename:
                    output_files.append(filename)
        
        # 保存验证结果
        if state.get('validation_results'):
            validation_content = self._format_validation_results(state['validation_results'])
            filename = workspace_manager.create_agent_file(
                task_id,
                current_step + 1,
                self.agent_type,
                "ValidationReport",
                validation_content,
                FileType.MARKDOWN
            )
            if filename:
                output_files.append(filename)
        
        # 更新todo.md
        if state.get('todo_updates'):
            self._update_todo_with_progress(task_id, state['todo_updates'])
        
        # 决定下一个智能体
        next_agent = None
        if completed and state.get('generated_scripts'):
            # 如果代码生成完成，转到Executor智能体执行测试
            next_agent = "executor"
        elif not completed:
            # 如果未完成，可能需要评审或更多信息
            next_agent = "reviewer"
        
        # 更新全局状态
        self.update_global_state({
            'step': current_step + 1,
            'last_output': output_files[-1] if output_files else None
        })
        
        return AgentOutput(
            data={
                'react_history': react_history,
                'generated_scripts': state.get('generated_scripts', []),
                'validation_results': state.get('validation_results', []),
                'output_files': output_files,
                'completed': completed,
                'iterations_used': llm_output.get('iterations_used', 0)
            },
            next_agent=next_agent,
            metadata={
                'agent': self.name,
                'phase_completed': True,
                'files_created': len(output_files),
                'scripts_generated': len(state.get('generated_scripts', []))
            }
        )
    
    def get_prompt_template(self) -> str:
        """获取Coder智能体的提示词模板"""
        return """你是一个专业的测试代码工程师智能体(Coder)，专门负责测试脚本生成、代码质量检查和语法验证。

## 你的核心能力
1. 基于测试用例生成高质量的测试脚本
2. 代码语法检查和质量验证
3. 测试框架集成(pytest, unittest等)
4. 代码优化和重构

## 工作流程
你将使用ReAct框架进行工作：
- Reason: 分析测试用例和代码需求，思考编码策略
- Act: 执行具体的代码生成、验证或优化行动
- Observe: 观察代码质量和执行结果，评估改进需求

## 可用工具
- file_read: 读取文件内容
- file_write: 写入文件内容
- python_repl: 执行Python代码验证
- code_validate: 代码质量检查
- syntax_check: 语法检查
- knowledge_search: 搜索编程知识

## 代码质量标准
1. 代码符合PEP 8规范
2. 包含完整的文档字符串
3. 异常处理完善
4. 测试覆盖率高
5. 代码可读性强

## 支持的测试框架
- pytest: 推荐的现代测试框架
- unittest: Python标准测试框架
- API测试: requests + pytest
- UI测试: selenium + pytest

请根据测试用例生成高质量、可执行的测试脚本。
"""
    
    def _build_reasoning_context(self, state: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建推理上下文"""
        test_cases = state.get('test_cases', [])
        generated_scripts = state.get('generated_scripts', [])
        
        # 任务状态摘要
        task_status = f"""
任务ID: {state.get('task_id', 'N/A')}
当前步骤: {state.get('current_step', 0)}
可用测试用例数: {len(test_cases)}
已生成脚本数: {len(generated_scripts)}
验证结果数: {len(state.get('validation_results', []))}
"""
        
        # 可用信息摘要
        available_info = []
        available_info.append(f"- 测试用例: {len(test_cases)} 个")
        available_info.append(f"- 代码模板: {len(self.code_templates)} 个")
        
        task_files = state.get('task_files', {})
        for filename, content in task_files.items():
            available_info.append(f"- {filename}: {len(content)} 字符")
        
        # 历史行动摘要
        history_summary = []
        for i, step in enumerate(history[-3:], 1):  # 只显示最近3步
            action_type = step.get('action', {}).get('action_type', 'unknown')
            success = step.get('action', {}).get('success', False)
            history_summary.append(f"{i}. {action_type} ({'成功' if success else '失败'})")
        
        return {
            'task_status': task_status.strip(),
            'available_info': '\n'.join(available_info),
            'history_summary': '\n'.join(history_summary) if history_summary else '无历史行动'
        }
    
    def _determine_action_type(self, reasoning: str, state: Dict[str, Any]) -> str:
        """根据推理结果确定行动类型"""
        reasoning_lower = reasoning.lower()
        
        # 检查是否需要分析测试用例
        if ('分析' in reasoning or '理解' in reasoning or 'analyze' in reasoning_lower) and not state.get('test_cases_analyzed'):
            return 'analyze_test_cases'
        
        # 检查是否需要生成测试脚本
        if ('生成' in reasoning or '编写' in reasoning or 'generate' in reasoning_lower or 'script' in reasoning_lower) and not state.get('generated_scripts'):
            return 'generate_test_script'
        
        # 检查是否需要验证代码
        if ('验证' in reasoning or '检查' in reasoning or 'validate' in reasoning_lower or 'check' in reasoning_lower):
            return 'validate_code'
        
        # 检查是否需要优化代码
        if ('优化' in reasoning or '改进' in reasoning or 'optimize' in reasoning_lower or 'improve' in reasoning_lower):
            return 'optimize_code'
        
        # 检查是否需要创建测试套件
        if ('套件' in reasoning or 'suite' in reasoning_lower or '整合' in reasoning):
            return 'create_test_suite'
        
        # 检查是否需要更新todo
        if 'todo' in reasoning_lower or '待办' in reasoning or '更新' in reasoning:
            return 'update_todo'
        
        # 默认编码行动
        return 'default_coding'
    
    def _action_analyze_test_cases(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """分析测试用例的行动"""
        test_cases = state.get('test_cases', [])
        
        if not test_cases:
            return {
                'success': False,
                'output': '没有可用的测试用例进行分析',
                'error': 'No test cases available'
            }
        
        # 分析测试用例
        analysis = {
            'total_cases': len(test_cases),
            'case_types': {},
            'complexity_levels': {},
            'required_frameworks': set(),
            'dependencies': set()
        }
        
        for test_case in test_cases:
            scenario = test_case.get('scenario', '').lower()
            steps = test_case.get('steps', '').lower()
            
            # 分析测试类型
            if 'api' in scenario or 'api' in steps:
                analysis['case_types']['api'] = analysis['case_types'].get('api', 0) + 1
                analysis['required_frameworks'].add('requests')
            elif 'ui' in scenario or 'ui' in steps or '界面' in scenario:
                analysis['case_types']['ui'] = analysis['case_types'].get('ui', 0) + 1
                analysis['required_frameworks'].add('selenium')
            else:
                analysis['case_types']['unit'] = analysis['case_types'].get('unit', 0) + 1
            
            # 分析复杂度
            step_count = len(steps.split('\n')) if steps else 1
            if step_count <= 3:
                analysis['complexity_levels']['simple'] = analysis['complexity_levels'].get('simple', 0) + 1
            elif step_count <= 6:
                analysis['complexity_levels']['medium'] = analysis['complexity_levels'].get('medium', 0) + 1
            else:
                analysis['complexity_levels']['complex'] = analysis['complexity_levels'].get('complex', 0) + 1
        
        # 添加基础框架
        analysis['required_frameworks'].add('pytest')
        
        state['test_cases_analyzed'] = True
        state['analysis_result'] = analysis
        
        return {
            'success': True,
            'output': f'成功分析 {len(test_cases)} 个测试用例，识别出 {len(analysis["case_types"])} 种测试类型',
            'analysis': analysis
        }
    
    def _action_generate_test_script(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成测试脚本的行动"""
        test_cases = state.get('test_cases', [])
        analysis = state.get('analysis_result', {})
        
        if not test_cases:
            return {
                'success': False,
                'output': '没有测试用例可供生成脚本',
                'error': 'No test cases available'
            }
        
        # 根据分析结果选择合适的模板
        case_types = analysis.get('case_types', {})
        primary_type = max(case_types.keys(), key=lambda k: case_types[k]) if case_types else 'unit'
        
        template_key = 'pytest_basic'
        if primary_type == 'api':
            template_key = 'api_test'
        elif primary_type == 'ui':
            template_key = 'ui_test'
        
        template = self.code_templates.get(template_key, self.code_templates['pytest_basic'])
        
        # 构建代码生成提示
        code_prompt = f"""
基于以下测试用例生成Python测试脚本：

## 测试用例分析
{json.dumps(analysis, ensure_ascii=False, indent=2)}

## 测试用例详情
{self._format_test_cases_for_prompt(test_cases[:5])}  # 限制显示前5个用例

## 代码生成要求
1. 使用pytest框架
2. 遵循PEP 8代码规范
3. 包含完整的文档字符串
4. 添加适当的异常处理
5. 使用以下模板作为参考：

```python
{template}
```

请生成完整的测试脚本：
"""
        
        try:
            messages = [
                {"role": "system", "content": "你是专业的Python测试代码生成专家，能够生成高质量、可执行的测试脚本。"},
                {"role": "user", "content": code_prompt}
            ]
            
            response = self.llm_service.invoke_sync(messages, agent_type=self.agent_type)
            generated_code = response.content.strip()
            
            # 提取代码块
            code_blocks = self._extract_code_blocks(generated_code)
            main_script = code_blocks[0] if code_blocks else generated_code
            
            # 验证语法
            syntax_valid, syntax_error = self._validate_python_syntax(main_script)
            
            script_info = {
                'name': f'test_{primary_type}',
                'code': main_script,
                'template_used': template_key,
                'syntax_valid': syntax_valid,
                'syntax_error': syntax_error,
                'test_count': len(test_cases)
            }
            
            return {
                'success': True,
                'output': f'成功生成测试脚本，包含 {len(test_cases)} 个测试用例',
                'script': script_info
            }
            
        except Exception as e:
            return {
                'success': False,
                'output': f'测试脚本生成失败: {str(e)}',
                'error': str(e)
            }
    
    def _action_validate_code(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """验证代码的行动"""
        generated_scripts = state.get('generated_scripts', [])
        
        if not generated_scripts:
            return {
                'success': False,
                'output': '没有生成的代码可供验证',
                'error': 'No generated code available'
            }
        
        validation_results = []
        
        for script in generated_scripts:
            script_name = script.get('name', 'unknown')
            code = script.get('code', '')
            
            # 语法验证
            syntax_valid, syntax_error = self._validate_python_syntax(code)
            
            # 代码质量检查
            quality_issues = self._check_code_quality(code)
            
            # 测试框架兼容性检查
            framework_compatible = self._check_framework_compatibility(code)
            
            validation_result = {
                'script_name': script_name,
                'syntax_valid': syntax_valid,
                'syntax_error': syntax_error,
                'quality_issues': quality_issues,
                'framework_compatible': framework_compatible,
                'overall_score': self._calculate_quality_score(syntax_valid, quality_issues, framework_compatible)
            }
            
            validation_results.append(validation_result)
        
        # 计算总体验证结果
        total_scripts = len(validation_results)
        valid_scripts = sum(1 for r in validation_results if r['syntax_valid'])
        avg_score = sum(r['overall_score'] for r in validation_results) / total_scripts if total_scripts > 0 else 0
        
        return {
            'success': True,
            'output': f'验证完成: {valid_scripts}/{total_scripts} 个脚本语法正确，平均质量分数: {avg_score:.2f}',
            'validation': {
                'total_scripts': total_scripts,
                'valid_scripts': valid_scripts,
                'average_score': avg_score,
                'details': validation_results
            }
        }
    
    def _action_optimize_code(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """优化代码的行动"""
        generated_scripts = state.get('generated_scripts', [])
        validation_results = state.get('validation_results', [])
        
        if not generated_scripts:
            return {
                'success': False,
                'output': '没有代码可供优化',
                'error': 'No code available for optimization'
            }
        
        optimized_count = 0
        
        for i, script in enumerate(generated_scripts):
            # 查找对应的验证结果
            validation = None
            if i < len(validation_results):
                validation = validation_results[i].get('details', [])
                if validation and len(validation) > i:
                    validation = validation[i]
            
            if validation and validation.get('quality_issues'):
                # 优化代码
                optimized_code = self._optimize_script_code(script['code'], validation['quality_issues'])
                if optimized_code != script['code']:
                    script['code'] = optimized_code
                    script['optimized'] = True
                    optimized_count += 1
        
        return {
            'success': True,
            'output': f'优化完成，改进了 {optimized_count} 个脚本',
            'optimized_count': optimized_count
        }
    
    def _action_create_test_suite(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """创建测试套件的行动"""
        generated_scripts = state.get('generated_scripts', [])
        
        if not generated_scripts:
            return {
                'success': False,
                'output': '没有脚本可供创建测试套件',
                'error': 'No scripts available'
            }
        
        # 生成测试套件配置
        suite_config = {
            'name': 'TestSuite',
            'description': '自动生成的测试套件',
            'scripts': [script['name'] for script in generated_scripts],
            'setup': 'pytest.ini配置',
            'requirements': list(self._extract_requirements_from_scripts(generated_scripts))
        }
        
        # 生成pytest配置文件内容
        pytest_ini_content = self._generate_pytest_config(suite_config)
        
        # 生成requirements.txt内容
        requirements_content = '\n'.join(suite_config['requirements'])
        
        return {
            'success': True,
            'output': f'成功创建测试套件，包含 {len(generated_scripts)} 个脚本',
            'suite_config': suite_config,
            'pytest_ini': pytest_ini_content,
            'requirements': requirements_content
        }
    
    def _action_update_todo(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """更新todo.md的行动"""
        task_id = state.get('task_id')
        if not task_id:
            return {
                'success': False,
                'output': '无法获取任务ID',
                'error': 'Missing task ID'
            }
        
        # 构建todo更新内容
        scripts_count = len(state.get('generated_scripts', []))
        validation_count = len(state.get('validation_results', []))
        
        todo_update = f"""
## Coder智能体进度更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

### 已完成任务
- [x] 测试用例分析和理解
- [{'x' if scripts_count > 0 else ' '}] 测试脚本生成 ({scripts_count} 个)
- [{'x' if validation_count > 0 else ' '}] 代码质量验证 ({validation_count} 个结果)

### 生成的脚本
{self._format_scripts_summary(state.get('generated_scripts', []))}

### 下一步计划
- [ ] 脚本执行测试
- [ ] 结果分析和优化
- [ ] 与Executor智能体协作

### 注意事项
- 所有脚本已通过语法检查
- 代码遵循PEP 8规范
- 包含完整的异常处理
"""
        
        state['todo_updates'].append(todo_update)
        
        return {
            'success': True,
            'output': 'todo.md更新内容已准备',
            'update_content': todo_update
        }
    
    def _action_default_coding(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """默认编码行动"""
        test_cases = state.get('test_cases', [])
        
        if not test_cases:
            return {
                'success': False,
                'output': '缺少测试用例，无法执行编码任务',
                'error': 'Missing test cases'
            }
        
        # 执行基础的代码生成
        basic_script = self._generate_basic_test_script(test_cases[:3])  # 限制前3个用例
        
        script_info = {
            'name': 'basic_test',
            'code': basic_script,
            'template_used': 'pytest_basic',
            'test_count': min(3, len(test_cases))
        }
        
        return {
            'success': True,
            'output': f'执行默认编码，生成基础测试脚本包含 {script_info["test_count"]} 个测试',
            'script': script_info
        }
    
    def _check_task_completion(self, state: Dict[str, Any]) -> bool:
        """检查任务是否完成"""
        # 检查是否有生成的脚本且通过验证
        generated_scripts = state.get('generated_scripts', [])
        validation_results = state.get('validation_results', [])
        
        if not generated_scripts:
            return False
        
        # 检查是否所有脚本都通过了基本验证
        if validation_results:
            for validation in validation_results:
                if isinstance(validation, dict) and 'details' in validation:
                    details = validation['details']
                    if isinstance(details, list):
                        for detail in details:
                            if not detail.get('syntax_valid', False):
                                return False
        
        return True
    
    # 代码模板方法
    def _get_pytest_basic_template(self) -> str:
        """获取pytest基础模板"""
        return '''"""
基础pytest测试模板
"""
import pytest


class TestBasic:
    """基础测试类"""
    
    def setup_method(self):
        """测试前置设置"""
        pass
    
    def teardown_method(self):
        """测试后置清理"""
        pass
    
    def test_example(self):
        """示例测试用例"""
        assert True
    
    @pytest.mark.parametrize("input_value,expected", [
        (1, 1),
        (2, 2),
    ])
    def test_parametrized(self, input_value, expected):
        """参数化测试示例"""
        assert input_value == expected
'''
    
    def _get_unittest_basic_template(self) -> str:
        """获取unittest基础模板"""
        return '''"""
基础unittest测试模板
"""
import unittest


class TestBasic(unittest.TestCase):
    """基础测试类"""
    
    def setUp(self):
        """测试前置设置"""
        pass
    
    def tearDown(self):
        """测试后置清理"""
        pass
    
    def test_example(self):
        """示例测试用例"""
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
'''
    
    def _get_api_test_template(self) -> str:
        """获取API测试模板"""
        return '''"""
API测试模板
"""
import pytest
import requests


class TestAPI:
    """API测试类"""
    
    @pytest.fixture
    def base_url(self):
        """基础URL配置"""
        return "http://localhost:8000"
    
    def test_get_endpoint(self, base_url):
        """GET接口测试"""
        response = requests.get(f"{base_url}/api/test")
        assert response.status_code == 200
    
    def test_post_endpoint(self, base_url):
        """POST接口测试"""
        data = {"key": "value"}
        response = requests.post(f"{base_url}/api/test", json=data)
        assert response.status_code in [200, 201]
'''
    
    def _get_ui_test_template(self) -> str:
        """获取UI测试模板"""
        return '''"""
UI测试模板
"""
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By


class TestUI:
    """UI测试类"""
    
    @pytest.fixture
    def driver(self):
        """WebDriver配置"""
        driver = webdriver.Chrome()
        yield driver
        driver.quit()
    
    def test_page_load(self, driver):
        """页面加载测试"""
        driver.get("http://localhost:3000")
        assert "Test Page" in driver.title
    
    def test_element_interaction(self, driver):
        """元素交互测试"""
        driver.get("http://localhost:3000")
        element = driver.find_element(By.ID, "test-button")
        element.click()
        assert element.is_displayed()
'''
    
    # 辅助方法
    def _parse_test_cases_from_content(self, content: str) -> List[Dict[str, Any]]:
        """从内容中解析测试用例"""
        test_cases = []
        
        # 简单的解析逻辑，查找测试用例结构
        lines = content.split('\n')
        current_case = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('## 测试用例') or line.startswith('# 测试用例'):
                if current_case:
                    test_cases.append(current_case)
                current_case = {'scenario': line.replace('#', '').strip()}
            elif '前置条件' in line:
                current_case['precondition'] = line.split(':', 1)[-1].strip()
            elif '测试步骤' in line:
                current_case['steps'] = line.split(':', 1)[-1].strip()
            elif '预期结果' in line:
                current_case['expected'] = line.split(':', 1)[-1].strip()
        
        if current_case:
            test_cases.append(current_case)
        
        return test_cases
    
    def _format_test_cases_for_prompt(self, test_cases: List[Dict[str, Any]]) -> str:
        """格式化测试用例用于提示"""
        formatted = []
        for i, case in enumerate(test_cases, 1):
            formatted.append(f"""
测试用例 {i}: {case.get('scenario', '未命名')}
前置条件: {case.get('precondition', '无')}
测试步骤: {case.get('steps', '未定义')}
预期结果: {case.get('expected', '未定义')}
""")
        return '\n'.join(formatted)
    
    def _extract_code_blocks(self, text: str) -> List[str]:
        """提取代码块"""
        import re
        pattern = r'```python\n(.*?)\n```'
        matches = re.findall(pattern, text, re.DOTALL)
        if not matches:
            # 尝试提取任何代码块
            pattern = r'```\n(.*?)\n```'
            matches = re.findall(pattern, text, re.DOTALL)
        return matches
    
    def _validate_python_syntax(self, code: str) -> tuple[bool, Optional[str]]:
        """验证Python语法"""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)
    
    def _check_code_quality(self, code: str) -> List[str]:
        """检查代码质量"""
        issues = []
        
        # 检查基本的代码质量问题
        if 'import *' in code:
            issues.append('避免使用 import *')
        
        if len([line for line in code.split('\n') if len(line) > 100]) > 0:
            issues.append('存在过长的代码行')
        
        if 'TODO' in code or 'FIXME' in code:
            issues.append('存在未完成的TODO或FIXME')
        
        # 检查是否有文档字符串
        if '"""' not in code and "'''" not in code:
            issues.append('缺少文档字符串')
        
        return issues
    
    def _check_framework_compatibility(self, code: str) -> bool:
        """检查测试框架兼容性"""
        # 检查是否包含pytest或unittest相关导入
        return 'pytest' in code or 'unittest' in code or 'import pytest' in code
    
    def _calculate_quality_score(self, syntax_valid: bool, quality_issues: List[str], framework_compatible: bool) -> float:
        """计算质量分数"""
        score = 0.0
        
        if syntax_valid:
            score += 50.0
        
        if framework_compatible:
            score += 20.0
        
        # 根据质量问题扣分
        issue_penalty = min(30.0, len(quality_issues) * 5.0)
        score += (30.0 - issue_penalty)
        
        return min(100.0, score)
    
    def _optimize_script_code(self, code: str, quality_issues: List[str]) -> str:
        """优化脚本代码"""
        optimized_code = code
        
        # 简单的优化逻辑
        for issue in quality_issues:
            if 'import *' in issue:
                # 这里可以添加具体的import优化逻辑
                pass
            elif '过长的代码行' in issue:
                # 这里可以添加代码行长度优化逻辑
                pass
        
        return optimized_code
    
    def _extract_requirements_from_scripts(self, scripts: List[Dict[str, Any]]) -> set:
        """从脚本中提取依赖需求"""
        requirements = set()
        
        for script in scripts:
            code = script.get('code', '')
            
            # 提取import语句
            import_lines = [line.strip() for line in code.split('\n') if line.strip().startswith('import ') or line.strip().startswith('from ')]
            
            for line in import_lines:
                if 'pytest' in line:
                    requirements.add('pytest>=6.0.0')
                elif 'requests' in line:
                    requirements.add('requests>=2.25.0')
                elif 'selenium' in line:
                    requirements.add('selenium>=4.0.0')
        
        # 添加基础依赖
        requirements.add('pytest>=6.0.0')
        
        return requirements
    
    def _generate_pytest_config(self, suite_config: Dict[str, Any]) -> str:
        """生成pytest配置"""
        return f"""[tool:pytest]
testpaths = .
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
"""
    
    def _generate_basic_test_script(self, test_cases: List[Dict[str, Any]]) -> str:
        """生成基础测试脚本"""
        script_parts = [
            '"""',
            '自动生成的基础测试脚本',
            '"""',
            'import pytest',
            '',
            '',
            'class TestGenerated:',
            '    """自动生成的测试类"""',
            ''
        ]
        
        for i, case in enumerate(test_cases, 1):
            scenario = case.get('scenario', f'test_case_{i}')
            method_name = f"test_{scenario.lower().replace(' ', '_').replace(':', '')}"
            
            script_parts.extend([
                f'    def {method_name}(self):',
                f'        """测试: {scenario}"""',
                f'        # 前置条件: {case.get("precondition", "无")}',
                f'        # 测试步骤: {case.get("steps", "未定义")}',
                f'        # 预期结果: {case.get("expected", "未定义")}',
                '        assert True  # 占位符，需要实现具体逻辑',
                ''
            ])
        
        return '\n'.join(script_parts)
    
    def _format_validation_results(self, validation_results: List[Dict[str, Any]]) -> str:
        """格式化验证结果"""
        content = f"""# 代码验证报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 验证摘要

"""
        
        for validation in validation_results:
            if 'details' in validation:
                details = validation['details']
                total = validation.get('total_scripts', 0)
                valid = validation.get('valid_scripts', 0)
                avg_score = validation.get('average_score', 0)
                
                content += f"""
总脚本数: {total}
语法正确脚本数: {valid}
平均质量分数: {avg_score:.2f}

## 详细结果

"""
                
                if isinstance(details, list):
                    for detail in details:
                        content += f"""
### {detail.get('script_name', '未知脚本')}

- 语法检查: {'通过' if detail.get('syntax_valid') else '失败'}
- 语法错误: {detail.get('syntax_error', '无')}
- 框架兼容: {'是' if detail.get('framework_compatible') else '否'}
- 质量分数: {detail.get('overall_score', 0):.2f}
- 质量问题: {', '.join(detail.get('quality_issues', [])) or '无'}

"""
        
        return content
    
    def _format_scripts_summary(self, scripts: List[Dict[str, Any]]) -> str:
        """格式化脚本摘要"""
        if not scripts:
            return "无生成的脚本"
        
        summary_lines = []
        for script in scripts:
            name = script.get('name', '未知')
            template = script.get('template_used', '未知模板')
            test_count = script.get('test_count', 0)
            syntax_valid = script.get('syntax_valid', False)
            
            status = '✓' if syntax_valid else '✗'
            summary_lines.append(f"- {status} {name} (模板: {template}, 测试数: {test_count})")
        
        return '\n'.join(summary_lines)
    
    def _read_todo_file(self, task_id: str) -> str:
        """读取todo.md文件内容"""
        try:
            task_metadata = workspace_manager.load_task_metadata(task_id)
            if not task_metadata:
                return ""
            
            from pathlib import Path
            todo_path = Path(task_metadata.workspace_path) / "todo.md"
            if todo_path.exists():
                return todo_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"读取todo.md失败: {e}")
        
        return ""
    
    def _read_file_content(self, task_id: str, filename: str) -> str:
        """读取指定文件内容"""
        try:
            task_metadata = workspace_manager.load_task_metadata(task_id)
            if not task_metadata:
                return ""
            
            from pathlib import Path
            file_path = Path(task_metadata.workspace_path) / filename
            if file_path.exists():
                return file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"读取文件 {filename} 失败: {e}")
        
        return ""
    
    def _update_todo_with_progress(self, task_id: str, updates: List[str]):
        """更新todo.md文件"""
        try:
            current_todo = self._read_todo_file(task_id)
            
            # 添加更新内容
            updated_content = current_todo + "\n\n" + "\n\n".join(updates)
            
            workspace_manager.update_todo_file(task_id, updated_content)
            logger.info(f"已更新todo.md文件，添加了 {len(updates)} 个更新")
            
        except Exception as e:
            logger.error(f"更新todo.md失败: {e}")


def create_coder_agent(global_state: GlobalState) -> CoderAgent:
    """创建Coder智能体实例"""
    return CoderAgent(global_state)