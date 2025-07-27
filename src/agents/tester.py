"""Tester智能体实现

实现Tester智能体的load->llm->router流程，在llm阶段内部集成ReAct(Reason-Act-Observe)循环，
创建测试用例生成和思维导图生成功能，建立todo.md动态更新机制引导模型注意力。
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..config.logging_config import get_logger
from ..core.base_agent import AgentInput, AgentOutput, ReActAgent
from ..core.workspace import workspace_manager
from ..llm.service import get_llm_service
from ..models.types import AgentType, TaskType
from ..models.workspace import FileType, GlobalState
from ..tools.tool_manager import get_tool_manager

logger = get_logger("tester_agent")


class TesterAgent(ReActAgent):
    """Tester智能体

    负责测试用例生成、思维导图创建和测试分析。
    采用ReAct框架进行多步推理和工具调用。
    """

    def __init__(self, global_state: GlobalState, max_iterations: int = 5):
        super().__init__(AgentType.TESTER, global_state, max_iterations)
        self.llm_service = get_llm_service()
        self.tool_manager = get_tool_manager()

        # Tester智能体可用的工具
        self.available_tools = [
            "file_read",
            "file_write",
            "knowledge_search",
            "knowledge_retrieve",
            "document_parse",
            "mindmap_generate",
        ]

    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：加载测试任务和相关文档"""
        logger.info("Tester智能体开始加载阶段")

        # 获取全局上下文
        context = self.get_context_from_global_state()

        # 加载任务相关文件
        task_id = context.get("current_task_id")
        task_files = {}

        if task_id:
            # 读取todo.md文件
            todo_content = self._read_todo_file(task_id)
            task_files["todo"] = todo_content

            # 读取相关的需求文档或计划文档
            files = workspace_manager.get_task_files(task_id)
            for file_ref in files:
                if (
                    "plan" in file_ref.path.lower()
                    or "requirement" in file_ref.path.lower()
                ):
                    content = self._read_file_content(task_id, file_ref.path)
                    task_files[file_ref.path] = content

        # 构建状态
        state = {
            "input_data": input_data.data,
            "context": context,
            "task_files": task_files,
            "prompt_template": self.get_prompt_template(),
            "available_tools": self.available_tools,
            "metadata": input_data.metadata or {},
            "current_step": context.get("current_step", 0),
            "task_id": task_id,
            "react_iterations": 0,
            "test_cases": [],
            "mindmap_data": {},
            "todo_updates": [],
        }

        logger.info(f"Tester智能体加载完成，任务ID: {task_id}")
        return state

    def reason(self, state: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
        """推理阶段：分析当前状态和历史，决定下一步行动"""
        logger.debug("Tester智能体进入推理阶段")

        # 构建推理上下文
        reasoning_context = self._build_reasoning_context(state, history)

        # 构建推理提示
        reasoning_prompt = f"""
作为Tester智能体，你需要分析当前情况并决定下一步行动。

## 当前任务状态
{reasoning_context['task_status']}

## 可用信息
{reasoning_context['available_info']}

## 历史行动
{reasoning_context['history_summary']}

## 当前目标
根据任务需求生成高质量的测试用例和思维导图。

请分析当前情况，思考需要执行什么行动来推进任务。你的推理应该包括：
1. 对当前状态的分析
2. 识别需要解决的问题或完成的任务
3. 选择最合适的下一步行动
4. 解释为什么选择这个行动

推理结果：
"""

        # 调用LLM进行推理
        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": reasoning_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            reasoning = response.content.strip()

            logger.debug(f"推理结果: {reasoning[:200]}...")
            return reasoning

        except Exception as e:
            logger.error(f"推理阶段出错: {e}")
            return f"推理出错，将执行默认分析行动: {str(e)}"

    def act(self, state: Dict[str, Any], reasoning: str) -> Dict[str, Any]:
        """行动阶段：根据推理结果执行具体行动"""
        logger.debug("Tester智能体进入行动阶段")

        # 分析推理结果，确定行动类型
        action_type = self._determine_action_type(reasoning, state)

        action_result = {
            "action_type": action_type,
            "reasoning": reasoning,
            "success": False,
            "output": "",
            "error": None,
        }

        try:
            if action_type == "read_requirements":
                action_result = self._action_read_requirements(state)
            elif action_type == "generate_test_cases":
                action_result = self._action_generate_test_cases(state)
            elif action_type == "create_mindmap":
                action_result = self._action_create_mindmap(state)
            elif action_type == "update_todo":
                action_result = self._action_update_todo(state)
            elif action_type == "analyze_coverage":
                action_result = self._action_analyze_coverage(state)
            else:
                action_result = self._action_default_analysis(state)

            action_result["action_type"] = action_type
            action_result["reasoning"] = reasoning

        except Exception as e:
            logger.error(f"行动执行出错: {e}")
            action_result["error"] = str(e)
            action_result["output"] = f"行动执行失败: {str(e)}"

        return action_result

    def observe(self, state: Dict[str, Any], action_result: Dict[str, Any]) -> str:
        """观察阶段：分析行动结果，为下一轮推理提供信息"""
        logger.debug("Tester智能体进入观察阶段")

        action_type = action_result.get("action_type", "unknown")
        success = action_result.get("success", False)
        output = action_result.get("output", "")
        error = action_result.get("error")

        # 构建观察结果
        observation_parts = [
            f"行动类型: {action_type}",
            f"执行状态: {'成功' if success else '失败'}",
        ]

        if success:
            observation_parts.append(f"输出结果: {output}")

            # 更新状态中的相关信息
            if action_type == "generate_test_cases" and "test_cases" in output:
                state["test_cases"].extend(output.get("test_cases", []))
            elif action_type == "create_mindmap" and "mindmap" in output:
                state["mindmap_data"] = output.get("mindmap", {})
        else:
            observation_parts.append(f"错误信息: {error or '未知错误'}")

        # 检查是否完成任务
        if self._check_task_completion(state):
            observation_parts.append("任务已完成，可以结束ReAct循环")
            state["task_completed"] = True

        observation = "\n".join(observation_parts)
        logger.debug(f"观察结果: {observation}")

        return observation

    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：根据LLM输出和全局状态决定下一步控制权移交"""
        logger.info("Tester智能体进入路由阶段")

        llm_output = state.get("llm_output", {})
        react_history = llm_output.get("react_history", [])
        completed = llm_output.get("completed", False)

        # 保存生成的文件
        task_id = state.get("task_id")
        current_step = state.get("current_step", 0)

        output_files = []

        # 保存测试用例
        if state.get("test_cases"):
            test_cases_content = self._format_test_cases(state["test_cases"])
            filename = workspace_manager.create_agent_file(
                task_id,
                current_step + 1,
                self.agent_type,
                "TestCases",
                test_cases_content,
                FileType.MARKDOWN,
            )
            if filename:
                output_files.append(filename)

        # 保存思维导图
        if state.get("mindmap_data"):
            mindmap_content = json.dumps(
                state["mindmap_data"], ensure_ascii=False, indent=2
            )
            filename = workspace_manager.create_agent_file(
                task_id,
                current_step + 1,
                self.agent_type,
                "Mindmap",
                mindmap_content,
                FileType.JSON,
            )
            if filename:
                output_files.append(filename)

        # 更新todo.md
        if state.get("todo_updates"):
            self._update_todo_with_progress(task_id, state["todo_updates"])

        # 决定下一个智能体
        next_agent = None
        if completed and state.get("test_cases"):
            # 如果测试用例生成完成，转到Coder智能体
            next_agent = "coder"
        elif not completed:
            # 如果未完成，可能需要更多信息或人工干预
            next_agent = "reviewer"

        # 更新全局状态
        self.update_global_state(
            {
                "step": current_step + 1,
                "last_output": output_files[-1] if output_files else None,
            }
        )

        return AgentOutput(
            data={
                "react_history": react_history,
                "test_cases": state.get("test_cases", []),
                "mindmap_data": state.get("mindmap_data", {}),
                "output_files": output_files,
                "completed": completed,
                "iterations_used": llm_output.get("iterations_used", 0),
            },
            next_agent=next_agent,
            metadata={
                "agent": self.name,
                "phase_completed": True,
                "files_created": len(output_files),
            },
        )

    def get_prompt_template(self) -> str:
        """获取Tester智能体的提示词模板"""
        return """你是一个专业的测试工程师智能体(Tester)，专门负责测试用例生成、测试分析和质量保证。

## 你的核心能力
1. 需求分析和测试用例设计
2. 测试覆盖度分析
3. 思维导图生成
4. 测试策略制定

## 工作流程
你将使用ReAct框架进行工作：
- Reason: 分析当前任务状态，思考需要执行的测试活动
- Act: 执行具体的测试分析或用例生成行动
- Observe: 观察行动结果，评估质量和完整性

## 可用工具
- file_read: 读取文件内容
- file_write: 写入文件内容
- knowledge_search: 搜索知识库
- knowledge_retrieve: 检索相关文档
- document_parse: 解析文档结构
- mindmap_generate: 生成思维导图

## 输出要求
1. 测试用例应该包含：测试场景、前置条件、测试步骤、预期结果
2. 思维导图应该清晰展示测试覆盖范围和测试策略
3. 持续更新todo.md文件，引导注意力聚焦任务目标

## 质量标准
- 测试用例覆盖率要达到90%以上
- 包含正常场景、异常场景和边界条件测试
- 测试步骤清晰可执行
- 预期结果明确可验证

请根据当前任务上下文，专业地执行测试分析和用例生成工作。
"""

    def _build_reasoning_context(
        self, state: Dict[str, Any], history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """构建推理上下文"""
        task_files = state.get("task_files", {})

        # 任务状态摘要
        task_status = f"""
任务ID: {state.get('task_id', 'N/A')}
当前步骤: {state.get('current_step', 0)}
已生成测试用例数: {len(state.get('test_cases', []))}
思维导图状态: {'已生成' if state.get('mindmap_data') else '未生成'}
"""

        # 可用信息摘要
        available_info = []
        for filename, content in task_files.items():
            available_info.append(f"- {filename}: {len(content)} 字符")

        # 历史行动摘要
        history_summary = []
        for i, step in enumerate(history[-3:], 1):  # 只显示最近3步
            action_type = step.get("action", {}).get("action_type", "unknown")
            success = step.get("action", {}).get("success", False)
            history_summary.append(
                f"{i}. {action_type} ({'成功' if success else '失败'})"
            )

        return {
            "task_status": task_status.strip(),
            "available_info": (
                "\n".join(available_info) if available_info else "无可用文件"
            ),
            "history_summary": (
                "\n".join(history_summary) if history_summary else "无历史行动"
            ),
        }

    def _determine_action_type(self, reasoning: str, state: Dict[str, Any]) -> str:
        """根据推理结果确定行动类型"""
        reasoning_lower = reasoning.lower()

        # 检查是否需要读取需求
        if (
            "需求" in reasoning
            or "要求" in reasoning
            or "requirement" in reasoning_lower
        ) and not state.get("task_files"):
            return "read_requirements"

        # 检查是否需要生成测试用例
        if (
            "测试用例" in reasoning
            or "用例" in reasoning
            or "test case" in reasoning_lower
        ) and not state.get("test_cases"):
            return "generate_test_cases"

        # 检查是否需要创建思维导图
        if (
            "思维导图" in reasoning
            or "导图" in reasoning
            or "mindmap" in reasoning_lower
        ) and not state.get("mindmap_data"):
            return "create_mindmap"

        # 检查是否需要更新todo
        if "todo" in reasoning_lower or "待办" in reasoning or "更新" in reasoning:
            return "update_todo"

        # 检查是否需要分析覆盖度
        if "覆盖" in reasoning or "coverage" in reasoning_lower:
            return "analyze_coverage"

        # 默认分析行动
        return "default_analysis"

    def _action_read_requirements(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """读取需求文档的行动"""
        task_id = state.get("task_id")
        if not task_id:
            return {
                "success": False,
                "output": "无法获取任务ID",
                "error": "Missing task ID",
            }

        # 读取相关文档
        files = workspace_manager.get_task_files(task_id)
        requirements_content = []

        for file_ref in files:
            if any(
                keyword in file_ref.path.lower()
                for keyword in ["plan", "requirement", "spec"]
            ):
                content = self._read_file_content(task_id, file_ref.path)
                requirements_content.append(f"## {file_ref.path}\n{content}")

        if not requirements_content:
            return {
                "success": False,
                "output": "未找到需求相关文档",
                "error": "No requirements documents found",
            }

        combined_content = "\n\n".join(requirements_content)
        state["requirements_content"] = combined_content

        return {
            "success": True,
            "output": f"成功读取 {len(requirements_content)} 个需求文档，总长度: {len(combined_content)} 字符",
            "requirements": combined_content,
        }

    def _action_generate_test_cases(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成测试用例的行动"""
        requirements = state.get("requirements_content") or state.get(
            "task_files", {}
        ).get("todo", "")

        if not requirements:
            return {
                "success": False,
                "output": "缺少需求信息，无法生成测试用例",
                "error": "Missing requirements",
            }

        # 构建测试用例生成提示
        test_case_prompt = f"""
基于以下需求信息，生成全面的测试用例：

## 需求信息
{requirements}

## 测试用例生成要求
1. 覆盖正常场景、异常场景和边界条件
2. 每个测试用例包含：测试场景、前置条件、测试步骤、预期结果
3. 使用结构化格式输出
4. 确保测试用例可执行和可验证

请生成详细的测试用例列表：
"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是专业的测试用例设计专家，能够生成高质量、全面的测试用例。",
                },
                {"role": "user", "content": test_case_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            test_cases_text = response.content.strip()

            # 解析测试用例
            test_cases = self._parse_test_cases(test_cases_text)

            return {
                "success": True,
                "output": f"成功生成 {len(test_cases)} 个测试用例",
                "test_cases": test_cases,
                "raw_content": test_cases_text,
            }

        except Exception as e:
            return {
                "success": False,
                "output": f"测试用例生成失败: {str(e)}",
                "error": str(e),
            }

    def _action_create_mindmap(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """创建思维导图的行动"""
        test_cases = state.get("test_cases", [])
        requirements = state.get("requirements_content", "")

        if not test_cases and not requirements:
            return {
                "success": False,
                "output": "缺少测试用例或需求信息，无法生成思维导图",
                "error": "Missing test cases or requirements",
            }

        # 构建思维导图生成提示
        mindmap_prompt = f"""
基于以下信息生成测试思维导图：

## 需求信息
{requirements[:1000]}...

## 测试用例概览
测试用例数量: {len(test_cases)}
{'测试场景: ' + ', '.join([tc.get('scenario', '') for tc in test_cases[:5]]) if test_cases else ''}

## 思维导图要求
1. 以JSON格式输出思维导图结构
2. 包含测试策略、测试分类、覆盖范围
3. 展示测试用例之间的关系和层次
4. 突出重点测试场景和风险点

请生成思维导图JSON结构：
"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是思维导图设计专家，能够将复杂的测试信息组织成清晰的思维导图结构。",
                },
                {"role": "user", "content": mindmap_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            mindmap_text = response.content.strip()

            # 尝试解析JSON
            try:
                mindmap_data = json.loads(mindmap_text)
            except json.JSONDecodeError:
                # 如果不是有效JSON，创建基础结构
                mindmap_data = {
                    "title": "测试思维导图",
                    "children": [
                        {
                            "title": "测试策略",
                            "children": ["功能测试", "性能测试", "安全测试"],
                        },
                        {
                            "title": "测试覆盖",
                            "children": [f"测试用例数: {len(test_cases)}"],
                        },
                    ],
                    "raw_content": mindmap_text,
                }

            return {
                "success": True,
                "output": "成功生成测试思维导图",
                "mindmap": mindmap_data,
            }

        except Exception as e:
            return {
                "success": False,
                "output": f"思维导图生成失败: {str(e)}",
                "error": str(e),
            }

    def _action_update_todo(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """更新todo.md的行动"""
        task_id = state.get("task_id")
        if not task_id:
            return {
                "success": False,
                "output": "无法获取任务ID",
                "error": "Missing task ID",
            }

        # 构建todo更新内容
        test_cases_count = len(state.get("test_cases", []))
        mindmap_status = "已生成" if state.get("mindmap_data") else "未生成"

        todo_update = f"""
## Tester智能体进度更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

### 已完成任务
- [x] 需求分析和理解
- [{'x' if test_cases_count > 0 else ' '}] 测试用例生成 ({test_cases_count} 个)
- [{'x' if state.get('mindmap_data') else ' '}] 测试思维导图创建 ({mindmap_status})

### 下一步计划
- [ ] 测试用例评审和优化
- [ ] 测试脚本开发准备
- [ ] 与Coder智能体协作

### 注意事项
- 当前测试用例覆盖度: {min(100, test_cases_count * 10)}%
- 需要关注边界条件和异常场景测试
"""

        state["todo_updates"].append(todo_update)

        return {
            "success": True,
            "output": "todo.md更新内容已准备",
            "update_content": todo_update,
        }

    def _action_analyze_coverage(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """分析测试覆盖度的行动"""
        test_cases = state.get("test_cases", [])

        if not test_cases:
            return {
                "success": False,
                "output": "没有测试用例可供分析",
                "error": "No test cases available",
            }

        # 分析测试覆盖度
        coverage_analysis = {
            "total_cases": len(test_cases),
            "normal_scenarios": 0,
            "exception_scenarios": 0,
            "boundary_scenarios": 0,
            "coverage_percentage": 0,
        }

        for test_case in test_cases:
            scenario = test_case.get("scenario", "").lower()
            if "正常" in scenario or "normal" in scenario:
                coverage_analysis["normal_scenarios"] += 1
            elif "异常" in scenario or "exception" in scenario or "错误" in scenario:
                coverage_analysis["exception_scenarios"] += 1
            elif "边界" in scenario or "boundary" in scenario or "极限" in scenario:
                coverage_analysis["boundary_scenarios"] += 1

        # 计算覆盖度百分比
        total_scenarios = (
            coverage_analysis["normal_scenarios"]
            + coverage_analysis["exception_scenarios"]
            + coverage_analysis["boundary_scenarios"]
        )
        coverage_analysis["coverage_percentage"] = min(
            100, (total_scenarios / max(len(test_cases), 1)) * 100
        )

        return {
            "success": True,
            "output": f'测试覆盖度分析完成: {coverage_analysis["coverage_percentage"]:.1f}%',
            "coverage_analysis": coverage_analysis,
        }

    def _action_default_analysis(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """默认分析行动"""
        task_files = state.get("task_files", {})

        analysis_result = {
            "available_files": list(task_files.keys()),
            "test_cases_count": len(state.get("test_cases", [])),
            "mindmap_status": (
                "generated" if state.get("mindmap_data") else "not_generated"
            ),
            "recommendations": [],
        }

        # 生成建议
        if not state.get("test_cases"):
            analysis_result["recommendations"].append("需要生成测试用例")
        if not state.get("mindmap_data"):
            analysis_result["recommendations"].append("需要创建测试思维导图")
        if not task_files:
            analysis_result["recommendations"].append("需要读取需求文档")

        return {
            "success": True,
            "output": f'完成默认分析，发现 {len(analysis_result["recommendations"])} 个建议',
            "analysis": analysis_result,
        }

    def _parse_test_cases(self, test_cases_text: str) -> List[Dict[str, Any]]:
        """解析测试用例文本"""
        test_cases = []

        # 简单的测试用例解析逻辑
        lines = test_cases_text.split("\n")
        current_case = {}

        for line in lines:
            line = line.strip()
            if not line:
                if current_case:
                    test_cases.append(current_case)
                    current_case = {}
                continue

            if line.startswith("##") or line.startswith("测试用例"):
                if current_case:
                    test_cases.append(current_case)
                current_case = {"scenario": line.replace("#", "").strip()}
            elif "前置条件" in line or "precondition" in line.lower():
                current_case["precondition"] = line.split(":", 1)[-1].strip()
            elif "测试步骤" in line or "steps" in line.lower():
                current_case["steps"] = line.split(":", 1)[-1].strip()
            elif "预期结果" in line or "expected" in line.lower():
                current_case["expected"] = line.split(":", 1)[-1].strip()

        if current_case:
            test_cases.append(current_case)

        return test_cases

    def _format_test_cases(self, test_cases: List[Dict[str, Any]]) -> str:
        """格式化测试用例为Markdown"""
        content = f"""# 测试用例文档

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
测试用例总数: {len(test_cases)}

"""

        for i, test_case in enumerate(test_cases, 1):
            content += f"""## 测试用例 {i}: {test_case.get('scenario', '未命名场景')}

**前置条件**: {test_case.get('precondition', '无')}

**测试步骤**: 
{test_case.get('steps', '未定义')}

**预期结果**: 
{test_case.get('expected', '未定义')}

---

"""

        return content

    def _check_task_completion(self, state: Dict[str, Any]) -> bool:
        """检查任务是否完成"""
        # 检查是否有测试用例和思维导图
        has_test_cases = len(state.get("test_cases", [])) > 0
        has_mindmap = bool(state.get("mindmap_data"))

        return has_test_cases and has_mindmap

    def _read_todo_file(self, task_id: str) -> str:
        """读取todo.md文件内容"""
        try:
            task_metadata = workspace_manager.load_task_metadata(task_id)
            if not task_metadata:
                return ""

            from pathlib import Path

            todo_path = Path(task_metadata.workspace_path) / "todo.md"
            if todo_path.exists():
                return todo_path.read_text(encoding="utf-8")
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
                return file_path.read_text(encoding="utf-8")
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


def create_tester_agent(global_state: GlobalState) -> TesterAgent:
    """创建Tester智能体实例"""
    return TesterAgent(global_state)
