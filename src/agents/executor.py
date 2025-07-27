"""Executor智能体实现

集成E2B Sandbox，实现强隔离代码执行，
创建执行结果标准化处理和错误日志生成，
建立资源限制和超时控制机制。
"""

import asyncio
import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..config.logging_config import get_logger
from ..core.base_agent import AgentInput, AgentOutput, BaseAgent
from ..core.workspace import workspace_manager
from ..llm.service import get_llm_service
from ..models.types import AgentType, TaskType
from ..models.workspace import FileType, GlobalState
from ..tools.python_repl_final import PythonREPLTool
from ..tools.unified_sandbox import SandboxExecutionResult, UnifiedSandboxExecutor

logger = get_logger("executor_agent")


class EnhancedSandboxExecutor:
    """增强沙盒执行器

    基于统一沙盒接口，提供强隔离的代码执行环境和完整的资源控制。
    """

    def __init__(
        self, timeout: int = 60, memory_limit: str = "512m", prefer_e2b: bool = True
    ):
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.prefer_e2b = prefer_e2b
        self.sandbox = None
        self.python_repl = PythonREPLTool(timeout=timeout)  # 保留作为备用

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start_sandbox()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop_sandbox()

    async def start_sandbox(self):
        """启动沙盒环境"""
        logger.info("启动增强沙盒执行器")

        try:
            self.sandbox = UnifiedSandboxExecutor(
                timeout=self.timeout,
                memory_limit=self.memory_limit,
                prefer_e2b=self.prefer_e2b,
            )
            await self.sandbox.start_sandbox()

            # 获取沙盒信息
            system_info = await self.sandbox.get_system_info()
            sandbox_type = self.sandbox.get_sandbox_type()

            logger.info(f"沙盒启动成功，类型: {sandbox_type}")
            if sandbox_type == "e2b":
                logger.info("使用E2B强隔离沙盒环境")
            else:
                logger.info("使用回退沙盒环境")

        except Exception as e:
            logger.error(f"沙盒启动失败: {e}")
            raise

    async def stop_sandbox(self):
        """停止沙盒环境"""
        if self.sandbox:
            try:
                await self.sandbox.stop_sandbox()
                self.sandbox = None
                logger.info("沙盒环境已停止")
            except Exception as e:
                logger.error(f"停止沙盒失败: {e}")

    async def execute_python_script(
        self, script_content: str, script_name: str = "test_script.py"
    ) -> Dict[str, Any]:
        """执行Python脚本"""
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在沙盒中执行Python脚本: {script_name}")

        try:
            result = await self.sandbox.execute_python_script(
                script_content=script_content, script_name=script_name
            )

            logger.info(
                f"脚本执行完成: {script_name}, 成功: {result.get('success', False)}"
            )
            return result

        except Exception as e:
            logger.error(f"脚本执行异常: {script_name}, 错误: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "script_name": script_name,
                "execution_time": 0,
                "memory_usage": None,
                "error": str(e),
                "sandbox_type": (
                    self.sandbox.get_sandbox_type() if self.sandbox else "unknown"
                ),
            }

    async def execute_python_code(self, code: str) -> Dict[str, Any]:
        """执行Python代码片段"""
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info("在沙盒中执行Python代码片段")

        try:
            result = await self.sandbox.execute_python_code(code)

            # 添加额外信息以保持兼容性
            result["script_name"] = "code_snippet"
            if "result_value" not in result:
                result["result_value"] = None

            logger.info(f"代码执行完成, 成功: {result.get('success', False)}")
            return result

        except Exception as e:
            logger.error(f"代码执行异常: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": 1,
                "script_name": "code_snippet",
                "execution_time": 0,
                "memory_usage": None,
                "error": str(e),
                "result_value": None,
                "sandbox_type": (
                    self.sandbox.get_sandbox_type() if self.sandbox else "unknown"
                ),
            }

    async def execute_pytest_script(
        self,
        script_content: str,
        script_name: str = "test_script.py",
        test_args: List[str] = None,
    ) -> Dict[str, Any]:
        """执行pytest测试脚本"""
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在沙盒中执行pytest测试: {script_name}")

        try:
            result = await self.sandbox.execute_pytest_script(
                script_content=script_content,
                script_name=script_name,
                test_args=test_args,
            )

            logger.info(
                f"pytest执行完成: {script_name}, 成功: {result.get('success', False)}"
            )
            return result

        except Exception as e:
            logger.error(f"pytest执行异常: {script_name}, 错误: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "script_name": script_name,
                "execution_time": 0,
                "memory_usage": None,
                "error": str(e),
                "test_results": {"passed": 0, "failed": 0, "error": 0, "skipped": 0},
                "sandbox_type": (
                    self.sandbox.get_sandbox_type() if self.sandbox else "unknown"
                ),
            }

    async def install_packages(self, packages: List[str]) -> Dict[str, Any]:
        """在沙盒中安装Python包"""
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在沙盒中安装包: {packages}")

        try:
            result = await self.sandbox.install_packages(packages)
            logger.info(f"包安装完成，成功: {result.get('success', False)}")
            return result

        except Exception as e:
            logger.error(f"包安装异常: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "packages": packages,
                "error": str(e),
                "sandbox_type": (
                    self.sandbox.get_sandbox_type() if self.sandbox else "unknown"
                ),
            }

    async def get_system_info(self) -> Dict[str, Any]:
        """获取沙盒系统信息"""
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        try:
            return await self.sandbox.get_system_info()
        except Exception as e:
            logger.error(f"获取系统信息失败: {e}")
            return {"error": str(e)}

    def get_sandbox_type(self) -> str:
        """获取沙盒类型"""
        if self.sandbox:
            return self.sandbox.get_sandbox_type()
        return "unknown"


class ExecutorAgent(BaseAgent):
    """Executor智能体

    负责在强隔离环境中执行测试脚本，处理执行结果和错误日志。
    """

    def __init__(self, global_state: GlobalState):
        super().__init__(AgentType.EXECUTOR, global_state)
        self.llm_service = get_llm_service()
        self.sandbox = None  # 将在需要时异步初始化

        # Executor智能体可用的工具
        self.available_tools = [
            "file_read",
            "file_write",
            "python_execute",
            "pytest_run",
            "sandbox_execute",
            "package_install",
            "system_info",
        ]

    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：加载测试脚本和执行配置"""
        logger.info("Executor智能体开始加载阶段")

        # 获取全局上下文
        context = self.get_context_from_global_state()

        # 加载任务相关文件
        task_id = context.get("current_task_id")
        task_files = {}
        test_scripts = []

        if task_id:
            # 读取todo.md文件
            todo_content = self._read_todo_file(task_id)
            task_files["todo"] = todo_content

            # 读取测试脚本文件
            files = workspace_manager.get_task_files(task_id)
            for file_ref in files:
                if file_ref.path.endswith(".py") and "script" in file_ref.path.lower():
                    content = self._read_file_content(task_id, file_ref.path)
                    task_files[file_ref.path] = content

                    # 解析脚本信息
                    if file_ref.created_by == "coder":
                        script_info = {
                            "name": file_ref.path,
                            "content": content,
                            "file_ref": file_ref,
                        }
                        test_scripts.append(script_info)

        # 构建状态
        state = {
            "input_data": input_data.data,
            "context": context,
            "task_files": task_files,
            "test_scripts": test_scripts,
            "prompt_template": self.get_prompt_template(),
            "available_tools": self.available_tools,
            "metadata": input_data.metadata or {},
            "current_step": context.get("current_step", 0),
            "task_id": task_id,
            "execution_results": [],
            "error_logs": [],
            "todo_updates": [],
        }

        logger.info(
            f"Executor智能体加载完成，任务ID: {task_id}, 脚本数: {len(test_scripts)}"
        )
        return state

    async def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM阶段：分析脚本并制定执行计划"""
        logger.info("Executor智能体进入LLM阶段")

        test_scripts = state.get("test_scripts", [])

        if not test_scripts:
            state["llm_output"] = {
                "execution_plan": [],
                "error": "没有可执行的测试脚本",
                "completed": False,
            }
            return state

        # 初始化沙盒环境
        if not self.sandbox:
            try:
                self.sandbox = EnhancedSandboxExecutor(
                    timeout=60, memory_limit="512m", prefer_e2b=True
                )
                await self.sandbox.start_sandbox()

                # 获取沙盒信息
                system_info = await self.sandbox.get_system_info()
                sandbox_type = self.sandbox.get_sandbox_type()

                logger.info(f"沙盒环境已启动，类型: {sandbox_type}")

            except Exception as e:
                logger.error(f"沙盒初始化失败: {e}")
                state["llm_output"] = {
                    "execution_plan": [],
                    "error": f"沙盒初始化失败: {str(e)}",
                    "completed": False,
                }
                return state

        # 构建执行分析提示
        sandbox_info = await self.sandbox.get_system_info()
        analysis_prompt = f"""
作为Executor智能体，你需要分析测试脚本并制定执行计划。

## 可用测试脚本
{self._format_scripts_for_analysis(test_scripts)}

## 执行环境信息
- 沙盒类型: {self.sandbox.get_sandbox_type()}
- 沙盒信息: {json.dumps(sandbox_info, indent=2, ensure_ascii=False)}
- 执行超时: 60秒
- 内存限制: 512MB
- 强隔离环境: {'是' if self.sandbox.get_sandbox_type() == 'e2b' else '否'}

## 任务要求
1. 分析每个脚本的执行需求和依赖
2. 确定执行顺序和安全策略
3. 制定错误处理和恢复机制
4. 预测可能的执行问题和解决方案

请制定详细的执行计划：
"""

        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": analysis_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            analysis_result = response.content.strip()

            # 执行所有脚本
            execution_results = []
            for script in test_scripts:
                result = await self._execute_script(script, state)
                execution_results.append(result)

            state["llm_output"] = {
                "analysis": analysis_result,
                "execution_plan": [script["name"] for script in test_scripts],
                "execution_results": execution_results,
                "completed": True,
                "sandbox_type": self.sandbox.get_sandbox_type(),
                "system_info": sandbox_info,
            }

            # 更新状态中的执行结果
            state["execution_results"] = execution_results

            logger.info(f"LLM阶段完成，执行了 {len(execution_results)} 个脚本")

        except Exception as e:
            logger.error(f"LLM阶段出错: {e}")
            state["llm_output"] = {
                "analysis": f"分析失败: {str(e)}",
                "execution_plan": [],
                "execution_results": [],
                "error": str(e),
                "completed": False,
                "sandbox_type": (
                    self.sandbox.get_sandbox_type() if self.sandbox else "unknown"
                ),
            }
        finally:
            # 清理沙盒资源
            if self.sandbox:
                try:
                    await self.sandbox.stop_sandbox()
                    self.sandbox = None
                except Exception as e:
                    logger.error(f"清理沙盒资源失败: {e}")

        return state

    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：根据执行结果决定下一步"""
        logger.info("Executor智能体进入路由阶段")

        llm_output = state.get("llm_output", {})
        execution_results = llm_output.get("execution_results", [])
        completed = llm_output.get("completed", False)

        # 保存执行结果文件
        task_id = state.get("task_id")
        current_step = state.get("current_step", 0)

        output_files = []

        # 保存执行结果报告
        if execution_results:
            results_content = self._format_execution_results(execution_results)
            filename = workspace_manager.create_agent_file(
                task_id,
                current_step + 1,
                self.agent_type,
                "ExecutionResults",
                results_content,
                FileType.MARKDOWN,
            )
            if filename:
                output_files.append(filename)

        # 保存错误日志
        error_logs = self._collect_error_logs(execution_results)
        if error_logs:
            error_content = self._format_error_logs(error_logs)
            filename = workspace_manager.create_agent_file(
                task_id,
                current_step + 1,
                self.agent_type,
                "ErrorLogs",
                error_content,
                FileType.LOG,
            )
            if filename:
                output_files.append(filename)

            # 同时追加到全局错误日志
            for error_log in error_logs:
                workspace_manager.append_error_log(task_id, error_log)

        # 更新todo.md
        if state.get("todo_updates"):
            self._update_todo_with_progress(task_id, state["todo_updates"])

        # 生成todo更新
        todo_update = self._generate_todo_update(execution_results)
        if todo_update:
            self._update_todo_with_progress(task_id, [todo_update])

        # 决定下一个智能体
        next_agent = None
        if completed:
            # 检查执行结果
            success_count = sum(
                1 for result in execution_results if result.get("success", False)
            )
            total_count = len(execution_results)

            if success_count == total_count:
                # 全部成功，转到Reporter生成报告
                next_agent = "reporter"
            else:
                # 有失败的测试，转到Reviewer进行分析
                next_agent = "reviewer"

        # 更新全局状态
        self.update_global_state(
            {
                "step": current_step + 1,
                "last_output": output_files[-1] if output_files else None,
            }
        )

        # 计算执行统计
        success_count = sum(
            1 for result in execution_results if result.get("success", False)
        )
        total_count = len(execution_results)

        return AgentOutput(
            data={
                "execution_results": execution_results,
                "analysis": llm_output.get("analysis", ""),
                "output_files": output_files,
                "completed": completed,
                "success_count": success_count,
                "total_count": total_count,
                "success_rate": success_count / max(total_count, 1),
            },
            next_agent=next_agent,
            metadata={
                "agent": self.name,
                "phase_completed": True,
                "files_created": len(output_files),
                "scripts_executed": total_count,
                "success_rate": success_count / max(total_count, 1),
            },
        )

    def get_prompt_template(self) -> str:
        """获取Executor智能体的提示词模板"""
        return """你是一个专业的测试执行智能体(Executor)，专门负责在强隔离沙盒环境中安全执行测试脚本。

## 你的核心能力
1. **E2B强隔离沙盒执行**: 优先使用E2B Sandbox提供的云端强隔离环境
2. **多层安全防护**: 资源限制、超时控制、恶意代码检测
3. **智能执行策略**: 自动识别脚本类型，选择最佳执行方式
4. **完整结果分析**: 标准化处理执行结果，生成详细报告
5. **错误恢复机制**: 智能错误分类和处理策略

## 执行环境特性
- **E2B Sandbox**: 云端强隔离容器环境（优先选择）
- **回退沙盒**: 本地临时目录隔离（E2B不可用时）
- **Python 3.11+**: 完整的Python运行时环境
- **pytest框架**: 专业的测试执行和报告生成
- **资源控制**: 内存限制512MB，执行超时60秒
- **实时监控**: 执行时间、内存使用、系统资源监控

## 安全保障措施
1. **强隔离执行**: 完全隔离的容器环境，防止系统污染
2. **资源限制**: 严格的CPU、内存、磁盘使用限制
3. **超时保护**: 自动终止长时间运行的恶意或错误代码
4. **输入验证**: 代码执行前的安全性检查和过滤
5. **错误捕获**: 完整的异常处理和错误日志记录

## 工作流程
1. **环境初始化**: 启动最佳可用的沙盒环境
2. **脚本分析**: 识别脚本类型、依赖和执行需求
3. **安全执行**: 在隔离环境中安全执行测试脚本
4. **结果收集**: 收集stdout、stderr、执行时间、资源使用等信息
5. **报告生成**: 生成标准化的执行报告和错误日志

## 执行策略
- **Python脚本**: 直接在沙盒中执行.py文件
- **pytest测试**: 使用pytest框架执行测试用例
- **代码片段**: 在沙盒中执行Python代码块
- **包管理**: 按需安装测试所需的Python包

## 输出标准
- **执行状态**: 成功/失败状态和返回码
- **输出内容**: 完整的标准输出和错误输出
- **性能指标**: 执行时间、内存使用、资源消耗
- **测试结果**: pytest测试的通过/失败/跳过统计
- **错误分析**: 详细的错误分类和处理建议
- **沙盒信息**: 执行环境类型和系统信息

## 质量保证
- 所有代码执行都在安全隔离的环境中进行
- 提供完整的执行轨迹和可追溯性
- 支持错误恢复和重试机制
- 生成专业的测试执行报告

请基于以上能力和标准，专业地分析和执行测试脚本，确保安全性和可靠性。
"""

    async def _execute_script(
        self, script: Dict[str, Any], state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行单个脚本"""
        script_name = script["name"]
        script_content = script["content"]

        logger.info(f"开始执行脚本: {script_name}")

        if not self.sandbox:
            logger.error("沙盒环境未初始化")
            return {
                "success": False,
                "stdout": "",
                "stderr": "沙盒环境未初始化",
                "return_code": -1,
                "script_name": script_name,
                "script_type": "unknown",
                "execution_time": 0,
                "memory_usage": None,
                "error": "沙盒环境未初始化",
                "sandbox_type": "unknown",
            }

        try:
            # 判断脚本类型并执行
            if "pytest" in script_content.lower() or "test_" in script_name:
                # 执行pytest测试
                result = await self.sandbox.execute_pytest_script(
                    script_content=script_content, script_name=script_name
                )
                script_type = "pytest"
            else:
                # 执行Python脚本
                result = await self.sandbox.execute_python_script(
                    script_content=script_content, script_name=script_name
                )
                script_type = "python"

            # 添加脚本类型信息
            result["script_type"] = script_type

            # 记录执行统计
            success = result.get("success", False)
            execution_time = result.get("execution_time", 0)
            sandbox_type = result.get("sandbox_type", "unknown")

            logger.info(
                f"脚本执行完成: {script_name}, 成功: {success}, 耗时: {execution_time:.2f}秒, 沙盒: {sandbox_type}"
            )
            return result

        except Exception as e:
            logger.error(f"脚本执行异常: {script_name}, 错误: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "script_name": script_name,
                "script_type": "unknown",
                "execution_time": 0,
                "memory_usage": None,
                "error": str(e),
                "sandbox_type": (
                    self.sandbox.get_sandbox_type() if self.sandbox else "unknown"
                ),
            }

    def _format_scripts_for_analysis(self, scripts: List[Dict[str, Any]]) -> str:
        """格式化脚本信息用于分析"""
        formatted = []
        for i, script in enumerate(scripts, 1):
            name = script["name"]
            content = script["content"]
            content_preview = content[:200] + "..." if len(content) > 200 else content

            formatted.append(
                f"""
脚本 {i}: {name}
内容预览:
```python
{content_preview}
```
"""
            )

        return "\n".join(formatted)

    def _format_execution_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化执行结果"""
        content = f"""# 测试执行结果报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
执行脚本数: {len(results)}

## 执行摘要

"""

        success_count = sum(1 for r in results if r.get("success", False))
        total_count = len(results)
        success_rate = success_count / max(total_count, 1) * 100

        content += f"""
- 总脚本数: {total_count}
- 成功执行: {success_count}
- 失败执行: {total_count - success_count}
- 成功率: {success_rate:.1f}%

## 详细结果

"""

        for i, result in enumerate(results, 1):
            script_name = result.get("script_name", f"脚本{i}")
            success = result.get("success", False)
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            execution_time = result.get("execution_time", 0)

            status_icon = "✅" if success else "❌"

            content += f"""
### {status_icon} {script_name}

**执行状态**: {'成功' if success else '失败'}
**返回码**: {result.get('return_code', 'N/A')}
**执行时间**: {execution_time if execution_time else 'N/A'}秒

**标准输出**:
```
{stdout if stdout else '无输出'}
```

**错误输出**:
```
{stderr if stderr else '无错误'}
```

---

"""

        return content

    def _collect_error_logs(self, results: List[Dict[str, Any]]) -> List[str]:
        """收集错误日志"""
        error_logs = []

        for result in results:
            if not result.get("success", False):
                script_name = result.get("script_name", "unknown")
                error = result.get("error", result.get("stderr", "未知错误"))
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                error_log = f"[{timestamp}] {script_name}: {error}"
                error_logs.append(error_log)

        return error_logs

    def _format_error_logs(self, error_logs: List[str]) -> str:
        """格式化错误日志"""
        content = f"""# 执行错误日志

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
错误数量: {len(error_logs)}

## 错误详情

"""

        for error_log in error_logs:
            content += f"{error_log}\n"

        return content

    def _generate_todo_update(self, results: List[Dict[str, Any]]) -> str:
        """生成todo更新内容"""
        success_count = sum(1 for r in results if r.get("success", False))
        total_count = len(results)

        return f"""
## Executor智能体执行报告 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

### 执行统计
- 总脚本数: {total_count}
- 成功执行: {success_count}
- 失败执行: {total_count - success_count}
- 成功率: {success_count / max(total_count, 1) * 100:.1f}%

### 执行结果
{self._format_results_summary(results)}

### 下一步计划
- [ ] 分析执行结果和错误日志
- [ ] 优化失败的测试脚本
- [ ] 生成最终测试报告

### 注意事项
- 所有脚本已在安全沙盒环境中执行
- 详细的执行日志已保存
- 错误信息已记录到错误日志
"""

    def _format_results_summary(self, results: List[Dict[str, Any]]) -> str:
        """格式化结果摘要"""
        if not results:
            return "无执行结果"

        summary_lines = []
        for result in results:
            name = result.get("script_name", "未知脚本")
            success = result.get("success", False)
            status = "✅" if success else "❌"

            summary_lines.append(f"- {status} {name}")

        return "\n".join(summary_lines)

    def _read_todo_file(self, task_id: str) -> str:
        """读取todo.md文件内容"""
        try:
            task_metadata = workspace_manager.load_task_metadata(task_id)
            if not task_metadata:
                return ""

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


def create_executor_agent(global_state: GlobalState) -> ExecutorAgent:
    """创建Executor智能体实例"""
    return ExecutorAgent(global_state)
