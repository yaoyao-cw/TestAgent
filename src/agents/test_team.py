"""TestTeam路由器实现

创建TestTeam路由器，根据todo.md状态进行智能路由。
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from ..core.base_agent import SimpleAgent, AgentInput, AgentOutput
from ..models.types import AgentType, TaskType
from ..models.workspace import GlobalState
from ..core.workspace import workspace_manager
from ..llm.service import get_llm_service
from ..config.logging_config import get_logger

logger = get_logger("test_team_agent")


class TestTeamRouter(SimpleAgent):
    """TestTeam路由器

    负责根据todo.md状态和任务进度进行智能路由，
    决定下一步应该由哪个智能体执行。
    """

    def __init__(self, global_state: GlobalState):
        super().__init__(AgentType.TESTER, global_state)  # 使用TESTER类型作为路由器
        self.llm_service = get_llm_service()

        # 智能体路由映射
        self.agent_routing_map = {
            "tester": "tester",
            "coder": "coder",
            "executor": "executor",
            "reviewer": "reviewer",
            "reporter": "reporter",
        }

        # TestTeam路由器可用的工具
        self.available_tools = [
            "file_read",
            "task_analyze",
            "progress_check",
            "route_decide",
        ]

    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：加载计划和todo.md状态"""
        logger.info("TestTeam路由器开始加载阶段")

        # 获取全局上下文
        context = self.get_context_from_global_state()

        # 加载任务相关文件
        task_id = context.get("current_task_id")
        task_files = {}
        plan_info = {}

        if task_id:
            # 读取todo.md文件
            todo_content = self._read_todo_file(task_id)
            task_files["todo"] = todo_content

            # 读取计划文件
            files = workspace_manager.get_task_files(task_id)
            for file_ref in files:
                if "plan" in file_ref.path.lower():
                    content = self._read_file_content(task_id, file_ref.path)
                    task_files[file_ref.path] = content
                    plan_info = self._parse_plan_content(content)
                    break

        # 获取任务元数据
        task_metadata = None
        if task_id:
            task_metadata = workspace_manager.load_task_metadata(task_id)

        # 构建状态
        state = {
            "input_data": input_data.data,
            "context": context,
            "task_files": task_files,
            "plan_info": plan_info,
            "task_metadata": task_metadata,
            "prompt_template": self.get_prompt_template(),
            "available_tools": self.available_tools,
            "metadata": input_data.metadata or {},
            "current_step": context.get("current_step", 0),
            "task_id": task_id,
            "routing_decision": None,
            "analysis_result": {},
        }

        logger.info(f"TestTeam路由器加载完成，任务ID: {task_id}")
        return state

    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM阶段：分析当前状态并决定路由"""
        logger.info("TestTeam路由器进入LLM阶段")

        task_metadata = state.get("task_metadata")
        todo_content = state.get("task_files", {}).get("todo", "")
        plan_info = state.get("plan_info", {})

        if not task_metadata:
            state["llm_output"] = {
                "routing_decision": None,
                "analysis": "缺少任务元数据",
                "error": "无法进行路由决策",
                "next_agent": None,
            }
            return state

        # 分析当前任务状态
        status_analysis = self._analyze_task_status(
            task_metadata, todo_content, plan_info
        )

        # 构建路由决策提示
        routing_prompt = f"""
作为TestTeam路由器，你需要分析当前任务状态并决定下一步应该由哪个智能体执行。

## 任务信息
标题: {task_metadata.title}
类型: {task_metadata.task_type.value}
当前步骤: {task_metadata.current_step}
状态: {task_metadata.status.value}

## 状态分析
{status_analysis}

## 可用智能体
1. **Tester**: 负责测试用例生成和思维导图创建
2. **Coder**: 负责测试脚本生成和代码质量检查
3. **Executor**: 负责在沙盒环境中执行测试脚本
4. **Reviewer**: 负责代码质量评审和错误日志分析
5. **Reporter**: 负责测试报告生成和信息汇总

## 路由决策要求
基于当前状态分析，请决定：
1. 下一步应该执行什么任务？
2. 哪个智能体最适合执行这个任务？
3. 为什么选择这个智能体？
4. 有什么特殊的注意事项？

请提供路由决策：
"""

        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": routing_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            routing_analysis = response.content.strip()

            # 解析路由决策
            routing_decision = self._parse_routing_decision(routing_analysis)

            state["llm_output"] = {
                "routing_decision": routing_decision,
                "analysis": routing_analysis,
                "status_analysis": status_analysis,
                "next_agent": routing_decision.get("agent", None),
            }

            # 更新状态
            state["routing_decision"] = routing_decision
            state["analysis_result"] = {
                "routing_analysis": routing_analysis,
                "status_analysis": status_analysis,
            }

            logger.info(
                f"路由决策完成，下一个智能体: {routing_decision.get('agent', 'None')}"
            )

        except Exception as e:
            logger.error(f"LLM阶段出错: {e}")
            state["llm_output"] = {
                "routing_decision": None,
                "analysis": f"路由分析失败: {str(e)}",
                "error": str(e),
                "next_agent": None,
            }

        return state

    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：执行路由决策"""
        logger.info("TestTeam路由器进入路由阶段")

        llm_output = state.get("llm_output", {})
        routing_decision = llm_output.get("routing_decision", {})
        next_agent = llm_output.get("next_agent")

        # 更新todo.md文件
        task_id = state.get("task_id")
        if task_id and routing_decision:
            self._update_todo_with_routing(task_id, routing_decision)

        # 更新全局状态
        current_step = state.get("current_step", 0)
        self.update_global_state(
            {
                "step": current_step,  # 路由器不增加步骤
                "last_output": f"路由到: {next_agent}",
            }
        )

        return AgentOutput(
            data={
                "routing_decision": routing_decision,
                "analysis": llm_output.get("analysis", ""),
                "status_analysis": llm_output.get("status_analysis", ""),
                "next_agent": next_agent,
            },
            next_agent=next_agent,
            metadata={
                "agent": "test_team_router",
                "phase_completed": True,
                "routing_target": next_agent,
            },
        )

    def get_prompt_template(self) -> str:
        """获取TestTeam路由器的提示词模板"""
        return """你是一个专业的测试团队路由器(TestTeam Router)，负责智能任务调度和流程控制。

## 你的核心能力
1. 任务状态分析和进度评估
2. 智能体能力匹配和任务分配
3. 工作流程优化和路由决策
4. 任务依赖关系管理

## 路由决策原则
1. **状态驱动**: 基于当前任务状态和完成情况
2. **能力匹配**: 选择最适合当前任务的智能体
3. **依赖优先**: 确保任务依赖关系得到满足
4. **效率优化**: 选择最高效的执行路径

## 智能体能力矩阵
- **Tester**: 需求分析、测试用例设计、思维导图生成
- **Coder**: 代码生成、脚本开发、语法检查
- **Executor**: 代码执行、测试运行、结果收集
- **Reviewer**: 质量评审、错误分析、改进建议
- **Reporter**: 报告生成、结果汇总、文档整理

## 路由策略
1. 新任务 → Tester（需求分析和用例设计）
2. 有测试用例 → Coder（脚本开发）
3. 有测试脚本 → Executor（执行测试）
4. 有执行结果 → Reviewer（质量评审）
5. 需要报告 → Reporter（生成报告）

## 决策输出
- 明确的下一步智能体选择
- 详细的决策理由
- 任务执行建议
- 注意事项和风险提示

请基于任务状态进行专业的路由决策。
"""

    def _analyze_task_status(
        self, task_metadata, todo_content: str, plan_info: Dict[str, Any]
    ) -> str:
        """分析任务状态"""
        analysis_parts = []

        # 基本状态信息
        analysis_parts.append(f"任务状态: {task_metadata.status.value}")
        analysis_parts.append(f"当前步骤: {task_metadata.current_step}")
        analysis_parts.append(f"错误计数: {task_metadata.error_count}")
        analysis_parts.append(f"活跃智能体: {task_metadata.active_agent or '无'}")

        # 文件完成情况
        files = task_metadata.files
        file_types = {}
        for file_ref in files:
            agent = file_ref.created_by
            if agent not in file_types:
                file_types[agent] = []
            file_types[agent].append(file_ref.path)

        analysis_parts.append("\n已完成的工作:")
        for agent, file_list in file_types.items():
            analysis_parts.append(f"- {agent}: {len(file_list)} 个文件")

        # TODO状态分析
        if todo_content:
            completed_tasks = todo_content.count("[x]")
            pending_tasks = todo_content.count("[ ]")
            analysis_parts.append(
                f"\nTODO状态: {completed_tasks} 已完成, {pending_tasks} 待完成"
            )

        # 计划执行情况
        if plan_info:
            steps = plan_info.get("steps", [])
            analysis_parts.append(f"\n计划步骤: 共 {len(steps)} 个步骤")

        return "\n".join(analysis_parts)

    def _parse_plan_content(self, plan_content: str) -> Dict[str, Any]:
        """解析计划内容"""
        plan_info = {
            "steps": [],
            "overview": "",
            "resources": [],
            "success_metrics": [],
        }

        # 简单的解析逻辑
        lines = plan_content.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if "执行概述" in line or "概述" in line:
                current_section = "overview"
            elif "执行步骤" in line or "步骤" in line:
                current_section = "steps"
            elif "资源需求" in line:
                current_section = "resources"
            elif "成功指标" in line:
                current_section = "metrics"
            elif line.startswith("###") and current_section == "steps":
                # 步骤标题
                step_title = line.replace("#", "").strip()
                plan_info["steps"].append({"title": step_title, "description": ""})
            elif line.startswith("-") and current_section in ["resources", "metrics"]:
                item = line[1:].strip()
                if current_section == "resources":
                    plan_info["resources"].append(item)
                elif current_section == "metrics":
                    plan_info["success_metrics"].append(item)

        return plan_info

    def _parse_routing_decision(self, routing_analysis: str) -> Dict[str, Any]:
        """解析路由决策"""
        decision = {"agent": None, "task": "", "reason": "", "notes": []}

        # 查找智能体名称
        agent_names = ["tester", "coder", "executor", "reviewer", "reporter"]
        routing_lower = routing_analysis.lower()

        for agent in agent_names:
            if agent in routing_lower:
                decision["agent"] = agent
                break

        # 如果没有找到明确的智能体，尝试从上下文推断
        if not decision["agent"]:
            if "测试用例" in routing_analysis or "用例" in routing_analysis:
                decision["agent"] = "tester"
            elif "代码" in routing_analysis or "脚本" in routing_analysis:
                decision["agent"] = "coder"
            elif "执行" in routing_analysis or "运行" in routing_analysis:
                decision["agent"] = "executor"
            elif "评审" in routing_analysis or "检查" in routing_analysis:
                decision["agent"] = "reviewer"
            elif "报告" in routing_analysis or "汇总" in routing_analysis:
                decision["agent"] = "reporter"
            else:
                # 默认选择tester
                decision["agent"] = "tester"

        # 提取任务和原因
        lines = routing_analysis.split("\n")
        for line in lines:
            line = line.strip()
            if "任务" in line and ":" in line:
                decision["task"] = line.split(":", 1)[1].strip()
            elif "原因" in line and ":" in line:
                decision["reason"] = line.split(":", 1)[1].strip()
            elif "注意" in line or "建议" in line:
                decision["notes"].append(line)

        # 如果没有提取到具体信息，使用整个分析作为原因
        if not decision["reason"]:
            decision["reason"] = routing_analysis

        return decision

    def _update_todo_with_routing(self, task_id: str, routing_decision: Dict[str, Any]):
        """更新todo.md文件"""
        try:
            current_todo = self._read_todo_file(task_id)

            # 生成路由更新
            routing_update = f"""
## TestTeam路由决策 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

### 路由结果
- **下一个智能体**: {routing_decision.get('agent', '未确定')}
- **执行任务**: {routing_decision.get('task', '待定')}
- **决策原因**: {routing_decision.get('reason', '无')}

### 注意事项
{chr(10).join(f"- {note}" for note in routing_decision.get('notes', [])) or '- 无特殊注意事项'}

### 执行状态
- [ ] 智能体已接收任务
- [ ] 任务执行中
- [ ] 任务完成确认

---
"""

            # 添加更新内容
            updated_content = current_todo + "\n\n" + routing_update

            workspace_manager.update_todo_file(task_id, updated_content)
            logger.info(f"已更新todo.md文件，添加了路由决策信息")

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


def create_test_team_router(global_state: GlobalState) -> TestTeamRouter:
    """创建TestTeam路由器实例"""
    return TestTeamRouter(global_state)
