"""Planner智能体实现

实现Planner智能体，集成CoT和ToT技术进行任务分解。
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..config.logging_config import get_logger
from ..core.base_agent import AgentInput, AgentOutput, SimpleAgent
from ..core.workspace import workspace_manager
from ..llm.service import get_llm_service
from ..models.types import AgentType, TaskType
from ..models.workspace import FileType, GlobalState

logger = get_logger("planner_agent")


class PlannerAgent(SimpleAgent):
    """Planner智能体

    负责任务分解和计划制定，集成CoT和ToT技术。
    """

    def __init__(self, global_state: GlobalState):
        super().__init__(AgentType.PLANNER, global_state)
        self.llm_service = get_llm_service()

        # Planner智能体可用的工具
        self.available_tools = [
            "file_read",
            "file_write",
            "knowledge_search",
            "task_decompose",
            "plan_generate",
        ]

    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：加载任务信息和背景调查结果"""
        logger.info("Planner智能体开始加载阶段")

        # 获取全局上下文
        context = self.get_context_from_global_state()

        # 加载任务相关文件
        task_id = context.get("current_task_id")
        task_files = {}
        background_info = ""

        if task_id:
            # 读取todo.md文件
            todo_content = self._read_todo_file(task_id)
            task_files["todo"] = todo_content

            # 读取背景调查结果
            files = workspace_manager.get_task_files(task_id)
            for file_ref in files:
                if (
                    "background" in file_ref.path.lower()
                    or "investigation" in file_ref.path.lower()
                ):
                    content = self._read_file_content(task_id, file_ref.path)
                    task_files[file_ref.path] = content
                    background_info += content + "\n\n"

        # 获取任务元数据
        task_metadata = None
        if task_id:
            task_metadata = workspace_manager.load_task_metadata(task_id)

        # 构建状态
        state = {
            "input_data": input_data.data,
            "context": context,
            "task_files": task_files,
            "background_info": background_info,
            "task_metadata": task_metadata,
            "prompt_template": self.get_prompt_template(),
            "available_tools": self.available_tools,
            "metadata": input_data.metadata or {},
            "current_step": context.get("current_step", 0),
            "task_id": task_id,
            "plan_generated": False,
            "cot_reasoning": [],
            "tot_alternatives": [],
        }

        logger.info(f"Planner智能体加载完成，任务ID: {task_id}")
        return state

    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM阶段：使用CoT和ToT技术进行任务分解"""
        logger.info("Planner智能体进入LLM阶段")

        task_metadata = state.get("task_metadata")
        background_info = state.get("background_info", "")

        if not task_metadata:
            state["llm_output"] = {
                "plan": {},
                "cot_reasoning": [],
                "tot_alternatives": [],
                "error": "缺少任务元数据",
                "plan_generated": False,
            }
            return state

        # 第一步：Chain of Thought (CoT) 推理
        cot_reasoning = self._perform_cot_reasoning(task_metadata, background_info)

        # 第二步：Tree of Thoughts (ToT) 生成多个方案
        tot_alternatives = self._generate_tot_alternatives(
            task_metadata, background_info, cot_reasoning
        )

        # 第三步：选择最佳方案并生成详细计划
        final_plan = self._generate_final_plan(
            task_metadata, background_info, cot_reasoning, tot_alternatives
        )

        state["llm_output"] = {
            "plan": final_plan,
            "cot_reasoning": cot_reasoning,
            "tot_alternatives": tot_alternatives,
            "plan_generated": True,
        }

        # 更新状态
        state["plan_generated"] = True
        state["cot_reasoning"] = cot_reasoning
        state["tot_alternatives"] = tot_alternatives

        logger.info("计划生成完成")
        return state

    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：保存计划并决定下一步"""
        logger.info("Planner智能体进入路由阶段")

        llm_output = state.get("llm_output", {})
        plan_generated = llm_output.get("plan_generated", False)
        final_plan = llm_output.get("plan", {})

        # 保存生成的文件
        task_id = state.get("task_id")
        current_step = state.get("current_step", 0)

        output_files = []

        # 保存计划文档
        if plan_generated and final_plan:
            plan_content = self._format_plan_document(
                final_plan,
                state.get("cot_reasoning", []),
                state.get("tot_alternatives", []),
            )

            filename = workspace_manager.create_agent_file(
                task_id,
                current_step + 1,
                self.agent_type,
                "Plan",
                plan_content,
                FileType.MARKDOWN,
            )
            if filename:
                output_files.append(filename)

        # 更新todo.md
        if plan_generated:
            self._update_todo_with_plan(task_id, final_plan)

        # 决定下一个智能体
        next_agent = None
        if plan_generated:
            # 计划生成成功，转到TestTeam路由器
            next_agent = "test_team"

        # 更新全局状态
        self.update_global_state(
            {
                "step": current_step + 1,
                "last_output": output_files[-1] if output_files else None,
            }
        )

        return AgentOutput(
            data={
                "plan": final_plan,
                "cot_reasoning": state.get("cot_reasoning", []),
                "tot_alternatives": state.get("tot_alternatives", []),
                "output_files": output_files,
                "plan_generated": plan_generated,
            },
            next_agent=next_agent,
            metadata={
                "agent": self.name,
                "phase_completed": True,
                "files_created": len(output_files),
            },
        )

    def get_prompt_template(self) -> str:
        """获取Planner智能体的提示词模板"""
        return """你是一个专业的任务规划智能体(Planner)，专门负责任务分解和计划制定。

## 你的核心能力
1. 复杂任务分解和结构化
2. Chain of Thought (CoT) 推理
3. Tree of Thoughts (ToT) 多方案生成
4. 最优执行路径规划

## 规划方法论
### Chain of Thought (CoT)
- 逐步分析任务需求
- 识别关键依赖关系
- 推理最佳执行顺序
- 预测潜在风险和挑战

### Tree of Thoughts (ToT)
- 生成多个可行方案
- 评估每个方案的优缺点
- 考虑不同的执行路径
- 选择最优的综合方案

## 规划要素
1. 任务分解：将复杂任务拆分为可执行的子任务
2. 依赖分析：识别任务间的依赖关系
3. 资源规划：确定所需的工具和资源
4. 时间估算：预估每个阶段的执行时间
5. 风险评估：识别潜在问题和应对策略

## 输出要求
- 详细的执行计划文档
- 清晰的推理过程记录
- 多方案对比分析
- 可操作的任务清单

请使用CoT和ToT技术生成高质量的执行计划。
"""

    def _perform_cot_reasoning(
        self, task_metadata, background_info: str
    ) -> List[Dict[str, Any]]:
        """执行Chain of Thought推理"""
        logger.info("开始CoT推理")

        cot_prompt = f"""
使用Chain of Thought方法分析以下任务：

## 任务信息
标题: {task_metadata.title}
描述: {task_metadata.description}
类型: {task_metadata.task_type.value}

## 背景信息
{background_info if background_info else '无额外背景信息'}

## CoT推理要求
请逐步分析：
1. 任务的核心目标是什么？
2. 需要哪些关键步骤来完成任务？
3. 每个步骤的输入和输出是什么？
4. 步骤之间有什么依赖关系？
5. 可能遇到什么挑战和风险？
6. 如何确保任务质量和成功率？

请提供详细的逐步推理过程：
"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是专业的任务分析专家，擅长使用Chain of Thought方法进行深度推理。",
                },
                {"role": "user", "content": cot_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            reasoning_text = response.content.strip()

            # 解析推理步骤
            reasoning_steps = self._parse_reasoning_steps(reasoning_text)

            logger.info(f"CoT推理完成，生成 {len(reasoning_steps)} 个推理步骤")
            return reasoning_steps

        except Exception as e:
            logger.error(f"CoT推理失败: {e}")
            return [{"step": 1, "content": f"推理失败: {str(e)}", "type": "error"}]

    def _generate_tot_alternatives(
        self, task_metadata, background_info: str, cot_reasoning: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """生成Tree of Thoughts多个方案"""
        logger.info("开始ToT方案生成")

        # 总结CoT推理结果
        cot_summary = "\n".join(
            [f"{step['step']}. {step['content']}" for step in cot_reasoning]
        )

        tot_prompt = f"""
基于以下CoT推理结果，使用Tree of Thoughts方法生成多个执行方案：

## 任务信息
标题: {task_metadata.title}
描述: {task_metadata.description}

## CoT推理摘要
{cot_summary}

## ToT方案生成要求
请生成3个不同的执行方案，每个方案应该：
1. 有不同的执行策略和重点
2. 考虑不同的风险偏好
3. 适应不同的资源约束
4. 提供方案的优缺点分析

方案类型建议：
- 方案A：快速执行方案（注重效率）
- 方案B：稳健执行方案（注重质量）
- 方案C：创新执行方案（注重创新）

请为每个方案提供详细描述：
"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是专业的方案设计专家，擅长使用Tree of Thoughts方法生成多样化的解决方案。",
                },
                {"role": "user", "content": tot_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            alternatives_text = response.content.strip()

            # 解析方案
            alternatives = self._parse_alternatives(alternatives_text)

            logger.info(f"ToT方案生成完成，生成 {len(alternatives)} 个方案")
            return alternatives

        except Exception as e:
            logger.error(f"ToT方案生成失败: {e}")
            return [
                {
                    "name": "默认方案",
                    "description": f"方案生成失败: {str(e)}",
                    "type": "error",
                }
            ]

    def _generate_final_plan(
        self,
        task_metadata,
        background_info: str,
        cot_reasoning: List[Dict[str, Any]],
        tot_alternatives: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """生成最终执行计划"""
        logger.info("开始生成最终计划")

        # 总结前面的分析结果
        cot_summary = "\n".join([f"- {step['content']}" for step in cot_reasoning])
        alternatives_summary = "\n".join(
            [
                f"- {alt['name']}: {alt['description'][:100]}..."
                for alt in tot_alternatives
            ]
        )

        final_plan_prompt = f"""
基于CoT推理和ToT方案分析，生成最终的执行计划：

## 任务信息
标题: {task_metadata.title}
描述: {task_metadata.description}
类型: {task_metadata.task_type.value}

## CoT推理要点
{cot_summary}

## ToT方案选项
{alternatives_summary}

## 最终计划要求
请综合以上分析，生成一个详细的执行计划，包括：

1. **执行概述**：计划的总体策略和目标
2. **详细步骤**：具体的执行步骤和时间安排
3. **资源需求**：所需的工具、数据和人力资源
4. **质量保证**：质量控制和验收标准
5. **风险管理**：潜在风险和应对措施
6. **成功指标**：衡量成功的具体指标

请生成结构化的执行计划：
"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是专业的项目规划专家，能够综合多种分析结果生成高质量的执行计划。",
                },
                {"role": "user", "content": final_plan_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            plan_text = response.content.strip()

            # 解析计划
            final_plan = self._parse_final_plan(plan_text, task_metadata)

            logger.info("最终计划生成完成")
            return final_plan

        except Exception as e:
            logger.error(f"最终计划生成失败: {e}")
            return {
                "overview": f"计划生成失败: {str(e)}",
                "steps": [],
                "resources": [],
                "quality_assurance": [],
                "risk_management": [],
                "success_metrics": [],
                "error": str(e),
            }

    def _parse_reasoning_steps(self, reasoning_text: str) -> List[Dict[str, Any]]:
        """解析推理步骤"""
        steps = []
        lines = reasoning_text.split("\n")

        current_step = 1
        current_content = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是新的步骤
            if line.startswith(f"{current_step}.") or line.startswith(
                f"步骤{current_step}"
            ):
                if current_content:
                    steps.append(
                        {
                            "step": current_step - 1,
                            "content": current_content.strip(),
                            "type": "reasoning",
                        }
                    )
                current_content = line
                current_step += 1
            else:
                current_content += " " + line

        # 添加最后一个步骤
        if current_content:
            steps.append(
                {
                    "step": current_step - 1,
                    "content": current_content.strip(),
                    "type": "reasoning",
                }
            )

        # 如果没有解析到步骤，将整个文本作为一个步骤
        if not steps:
            steps.append({"step": 1, "content": reasoning_text, "type": "reasoning"})

        return steps

    def _parse_alternatives(self, alternatives_text: str) -> List[Dict[str, Any]]:
        """解析ToT方案"""
        alternatives = []
        lines = alternatives_text.split("\n")

        current_alternative = None
        current_content = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是新的方案
            if "方案" in line and (
                "A" in line
                or "B" in line
                or "C" in line
                or "1" in line
                or "2" in line
                or "3" in line
            ):
                if current_alternative:
                    current_alternative["description"] = current_content.strip()
                    alternatives.append(current_alternative)

                # 提取方案名称
                name = (
                    line.split("：")[0]
                    if "：" in line
                    else line.split(":")[0] if ":" in line else line
                )
                current_alternative = {
                    "name": name,
                    "description": "",
                    "type": "alternative",
                }
                current_content = line
            else:
                current_content += " " + line

        # 添加最后一个方案
        if current_alternative:
            current_alternative["description"] = current_content.strip()
            alternatives.append(current_alternative)

        # 如果没有解析到方案，创建默认方案
        if not alternatives:
            alternatives.append(
                {
                    "name": "综合方案",
                    "description": alternatives_text,
                    "type": "alternative",
                }
            )

        return alternatives

    def _parse_final_plan(self, plan_text: str, task_metadata) -> Dict[str, Any]:
        """解析最终计划"""
        plan = {
            "task_id": task_metadata.task_id,
            "task_title": task_metadata.title,
            "overview": "",
            "steps": [],
            "resources": [],
            "quality_assurance": [],
            "risk_management": [],
            "success_metrics": [],
            "created_at": datetime.now().isoformat(),
        }

        lines = plan_text.split("\n")
        current_section = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 识别不同的部分
            if "执行概述" in line or "概述" in line:
                current_section = "overview"
                current_content = []
            elif "详细步骤" in line or "执行步骤" in line or "步骤" in line:
                if current_section == "overview":
                    plan["overview"] = "\n".join(current_content)
                current_section = "steps"
                current_content = []
            elif "资源需求" in line or "资源" in line:
                if current_section == "steps":
                    plan["steps"] = self._parse_steps(current_content)
                current_section = "resources"
                current_content = []
            elif "质量保证" in line or "质量" in line:
                if current_section == "resources":
                    plan["resources"] = self._parse_list_items(current_content)
                current_section = "quality"
                current_content = []
            elif "风险管理" in line or "风险" in line:
                if current_section == "quality":
                    plan["quality_assurance"] = self._parse_list_items(current_content)
                current_section = "risk"
                current_content = []
            elif "成功指标" in line or "指标" in line:
                if current_section == "risk":
                    plan["risk_management"] = self._parse_list_items(current_content)
                current_section = "metrics"
                current_content = []
            else:
                current_content.append(line)

        # 处理最后一个部分
        if current_section == "overview":
            plan["overview"] = "\n".join(current_content)
        elif current_section == "steps":
            plan["steps"] = self._parse_steps(current_content)
        elif current_section == "resources":
            plan["resources"] = self._parse_list_items(current_content)
        elif current_section == "quality":
            plan["quality_assurance"] = self._parse_list_items(current_content)
        elif current_section == "risk":
            plan["risk_management"] = self._parse_list_items(current_content)
        elif current_section == "metrics":
            plan["success_metrics"] = self._parse_list_items(current_content)

        # 如果没有解析到概述，使用整个文本
        if not plan["overview"]:
            plan["overview"] = plan_text

        return plan

    def _parse_steps(self, content_lines: List[str]) -> List[Dict[str, Any]]:
        """解析执行步骤"""
        steps = []
        current_step = None

        for line in content_lines:
            if line.startswith("-") or line.startswith("•") or line.startswith("*"):
                if current_step:
                    steps.append(current_step)

                step_text = line[1:].strip()
                current_step = {
                    "id": len(steps) + 1,
                    "title": step_text,
                    "description": "",
                    "estimated_time": "待定",
                    "dependencies": [],
                    "deliverables": [],
                }
            elif current_step and line:
                current_step["description"] += " " + line

        if current_step:
            steps.append(current_step)

        return steps

    def _parse_list_items(self, content_lines: List[str]) -> List[str]:
        """解析列表项"""
        items = []

        for line in content_lines:
            if line.startswith("-") or line.startswith("•") or line.startswith("*"):
                items.append(line[1:].strip())
            elif line and not items:
                # 如果没有列表格式，将每行作为一个项目
                items.append(line)

        return items

    def _format_plan_document(
        self,
        plan: Dict[str, Any],
        cot_reasoning: List[Dict[str, Any]],
        tot_alternatives: List[Dict[str, Any]],
    ) -> str:
        """格式化计划文档"""
        content = f"""# 任务执行计划

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
任务ID: {plan.get('task_id', 'N/A')}
任务标题: {plan.get('task_title', 'N/A')}

## 执行概述

{plan.get('overview', '无概述信息')}

## 详细执行步骤

"""

        steps = plan.get("steps", [])
        for step in steps:
            content += f"""
### 步骤 {step.get('id', 'N/A')}: {step.get('title', '未命名步骤')}

**描述**: {step.get('description', '无描述')}
**预估时间**: {step.get('estimated_time', '待定')}
**依赖关系**: {', '.join(step.get('dependencies', [])) or '无'}
**交付物**: {', '.join(step.get('deliverables', [])) or '待定'}

"""

        content += f"""
## 资源需求

{chr(10).join(f"- {resource}" for resource in plan.get('resources', [])) or '- 无特殊资源需求'}

## 质量保证

{chr(10).join(f"- {qa}" for qa in plan.get('quality_assurance', [])) or '- 标准质量控制流程'}

## 风险管理

{chr(10).join(f"- {risk}" for risk in plan.get('risk_management', [])) or '- 常规风险监控'}

## 成功指标

{chr(10).join(f"- {metric}" for metric in plan.get('success_metrics', [])) or '- 任务完成度100%'}

---

## 附录：推理过程

### Chain of Thought 推理

"""

        for reasoning in cot_reasoning:
            content += (
                f"{reasoning.get('step', 'N/A')}. {reasoning.get('content', '')}\n\n"
            )

        content += """
### Tree of Thoughts 方案分析

"""

        for alternative in tot_alternatives:
            content += f"""
**{alternative.get('name', '未命名方案')}**

{alternative.get('description', '无描述')}

"""

        return content

    def _update_todo_with_plan(self, task_id: str, plan: Dict[str, Any]):
        """更新todo.md文件"""
        try:
            current_todo = self._read_todo_file(task_id)

            # 生成计划摘要
            plan_summary = f"""
## Planner智能体计划更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

### 执行计划已生成
- [x] 任务分析和理解
- [x] CoT推理完成
- [x] ToT方案生成
- [x] 最终计划制定

### 计划概述
{plan.get('overview', '无概述')[:200]}...

### 执行步骤
{chr(10).join(f"- [ ] {step.get('title', '未命名步骤')}" for step in plan.get('steps', [])[:5])}

### 下一步行动
- [ ] 开始执行第一个步骤
- [ ] 分配任务给相应的智能体
- [ ] 监控执行进度

### 注意事项
- 计划已保存到plan.md文件
- 包含详细的推理过程
- 考虑了多种执行方案
"""

            # 添加更新内容
            updated_content = current_todo + "\n\n" + plan_summary

            workspace_manager.update_todo_file(task_id, updated_content)
            logger.info("已更新todo.md文件，添加了计划信息")

        except Exception as e:
            logger.error(f"更新todo.md失败: {e}")

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


def create_planner_agent(global_state: GlobalState) -> PlannerAgent:
    """创建Planner智能体实例"""
    return PlannerAgent(global_state)
