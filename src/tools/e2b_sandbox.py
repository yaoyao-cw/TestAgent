"""E2B Sandbox集成模块

提供强隔离的代码执行环境，支持Python脚本和pytest测试的安全执行。
实现资源限制、超时控制和详细的执行结果处理。
"""

import asyncio
import json
import time
import tempfile
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path

try:
    from e2b import Sandbox

    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False
    Sandbox = None

from ..config.logging_config import get_logger
from ..config.settings import get_settings

logger = get_logger("e2b_sandbox")


class E2BSandboxExecutor:
    """E2B沙盒执行器

    提供强隔离的代码执行环境，支持多种执行模式和完整的资源控制。
    """

    def __init__(
        self,
        template_id: str = "python3",
        timeout: int = 60,
        memory_limit: int = 512,
        cpu_limit: float = 1.0,
    ):
        """初始化E2B沙盒执行器

        Args:
            template_id: E2B模板ID，默认使用Python3模板
            timeout: 执行超时时间（秒）
            memory_limit: 内存限制（MB）
            cpu_limit: CPU限制（核心数）
        """
        if not E2B_AVAILABLE:
            raise ImportError("E2B库未安装，请运行: pip install e2b")

        self.template_id = template_id
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.sandbox = None

        # 从配置获取E2B API密钥
        settings = get_settings()
        self.api_key = getattr(settings, "E2B_API_KEY", None)

        if not self.api_key:
            logger.warning("E2B_API_KEY未配置，将使用环境变量或默认配置")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start_sandbox()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop_sandbox()

    async def start_sandbox(self):
        """启动沙盒环境"""
        try:
            logger.info(f"启动E2B沙盒环境，模板: {self.template_id}")

            # 创建沙盒实例
            if self.api_key:
                self.sandbox = Sandbox(
                    template=self.template_id,
                    api_key=self.api_key,
                    timeout=self.timeout,
                )
            else:
                self.sandbox = Sandbox(template=self.template_id, timeout=self.timeout)

            # 等待沙盒就绪
            await asyncio.sleep(1)

            logger.info("E2B沙盒环境启动成功")

        except Exception as e:
            logger.error(f"启动E2B沙盒失败: {e}")
            raise

    async def stop_sandbox(self):
        """停止沙盒环境"""
        if self.sandbox:
            try:
                logger.info("停止E2B沙盒环境")
                await self.sandbox.close()
                self.sandbox = None
                logger.info("E2B沙盒环境已停止")
            except Exception as e:
                logger.error(f"停止E2B沙盒失败: {e}")

    async def execute_python_code(
        self, code: str, working_dir: str = "/tmp", env_vars: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """在E2B沙盒中执行Python代码

        Args:
            code: 要执行的Python代码
            working_dir: 工作目录
            env_vars: 环境变量

        Returns:
            执行结果字典
        """
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info("在E2B沙盒中执行Python代码")

        start_time = time.time()

        try:
            # 设置环境变量
            if env_vars:
                for key, value in env_vars.items():
                    await self.sandbox.filesystem.write(f"/tmp/{key}", value)

            # 执行代码
            execution = await self.sandbox.run_code(
                code=code, language="python", timeout=self.timeout
            )

            execution_time = time.time() - start_time

            # 处理执行结果
            result = {
                "success": execution.exit_code == 0,
                "stdout": execution.stdout,
                "stderr": execution.stderr,
                "return_code": execution.exit_code,
                "execution_time": execution_time,
                "memory_usage": None,  # E2B可能提供内存使用信息
                "error": execution.stderr if execution.exit_code != 0 else None,
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"代码执行完成，成功: {result['success']}, 耗时: {execution_time:.2f}秒"
            )
            return result

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"代码执行超时: {self.timeout}秒")

            return {
                "success": False,
                "stdout": "",
                "stderr": f"执行超时 ({self.timeout}秒)",
                "return_code": -1,
                "execution_time": execution_time,
                "memory_usage": None,
                "error": f"执行超时 ({self.timeout}秒)",
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"代码执行异常: {e}")

            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "execution_time": execution_time,
                "memory_usage": None,
                "error": str(e),
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

    async def execute_python_script(
        self,
        script_content: str,
        script_name: str = "script.py",
        working_dir: str = "/tmp",
        env_vars: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """在E2B沙盒中执行Python脚本文件

        Args:
            script_content: 脚本内容
            script_name: 脚本文件名
            working_dir: 工作目录
            env_vars: 环境变量

        Returns:
            执行结果字典
        """
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在E2B沙盒中执行Python脚本: {script_name}")

        start_time = time.time()

        try:
            # 将脚本写入沙盒文件系统
            script_path = f"{working_dir}/{script_name}"
            await self.sandbox.filesystem.write(script_path, script_content)

            # 设置环境变量
            if env_vars:
                for key, value in env_vars.items():
                    await self.sandbox.filesystem.write(f"/tmp/{key}", value)

            # 执行脚本
            execution = await self.sandbox.run_command(
                command=f"cd {working_dir} && python {script_name}",
                timeout=self.timeout,
            )

            execution_time = time.time() - start_time

            # 处理执行结果
            result = {
                "success": execution.exit_code == 0,
                "stdout": execution.stdout,
                "stderr": execution.stderr,
                "return_code": execution.exit_code,
                "script_name": script_name,
                "execution_time": execution_time,
                "memory_usage": None,
                "error": execution.stderr if execution.exit_code != 0 else None,
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"脚本执行完成: {script_name}, 成功: {result['success']}, 耗时: {execution_time:.2f}秒"
            )
            return result

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"脚本执行超时: {script_name}")

            return {
                "success": False,
                "stdout": "",
                "stderr": f"脚本执行超时 ({self.timeout}秒)",
                "return_code": -1,
                "script_name": script_name,
                "execution_time": execution_time,
                "memory_usage": None,
                "error": f"脚本执行超时 ({self.timeout}秒)",
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"脚本执行异常: {script_name}, 错误: {e}")

            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "script_name": script_name,
                "execution_time": execution_time,
                "memory_usage": None,
                "error": str(e),
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

    async def execute_pytest_script(
        self,
        script_content: str,
        script_name: str = "test_script.py",
        test_args: List[str] = None,
        working_dir: str = "/tmp",
        env_vars: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """在E2B沙盒中执行pytest测试脚本

        Args:
            script_content: 测试脚本内容
            script_name: 测试脚本文件名
            test_args: pytest参数
            working_dir: 工作目录
            env_vars: 环境变量

        Returns:
            执行结果字典
        """
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        if test_args is None:
            test_args = [
                "-v",
                "--tb=short",
                "--json-report",
                "--json-report-file=test_results.json",
            ]

        logger.info(f"在E2B沙盒中执行pytest测试: {script_name}")

        start_time = time.time()

        try:
            # 将测试脚本写入沙盒文件系统
            script_path = f"{working_dir}/{script_name}"
            await self.sandbox.filesystem.write(script_path, script_content)

            # 设置环境变量
            if env_vars:
                for key, value in env_vars.items():
                    await self.sandbox.filesystem.write(f"/tmp/{key}", value)

            # 安装pytest（如果需要）
            await self.sandbox.run_command(
                "pip install pytest pytest-json-report", timeout=30
            )

            # 构建pytest命令
            pytest_cmd = f"cd {working_dir} && python -m pytest {' '.join(test_args)} {script_name}"

            # 执行pytest
            execution = await self.sandbox.run_command(
                command=pytest_cmd, timeout=self.timeout
            )

            execution_time = time.time() - start_time

            # 尝试读取JSON测试结果
            test_results = await self._parse_pytest_json_results(working_dir)

            # 处理执行结果
            result = {
                "success": execution.exit_code == 0,
                "stdout": execution.stdout,
                "stderr": execution.stderr,
                "return_code": execution.exit_code,
                "script_name": script_name,
                "execution_time": execution_time,
                "memory_usage": None,
                "error": execution.stderr if execution.exit_code != 0 else None,
                "test_results": test_results
                or self._parse_pytest_output(execution.stdout),
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"pytest执行完成: {script_name}, 成功: {result['success']}, 耗时: {execution_time:.2f}秒"
            )
            return result

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"pytest执行超时: {script_name}")

            return {
                "success": False,
                "stdout": "",
                "stderr": f"pytest执行超时 ({self.timeout}秒)",
                "return_code": -1,
                "script_name": script_name,
                "execution_time": execution_time,
                "memory_usage": None,
                "error": f"pytest执行超时 ({self.timeout}秒)",
                "test_results": {"passed": 0, "failed": 0, "error": 0, "skipped": 0},
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"pytest执行异常: {script_name}, 错误: {e}")

            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "script_name": script_name,
                "execution_time": execution_time,
                "memory_usage": None,
                "error": str(e),
                "test_results": {"passed": 0, "failed": 0, "error": 0, "skipped": 0},
                "sandbox_id": self.sandbox.id if hasattr(self.sandbox, "id") else None,
                "timestamp": datetime.now().isoformat(),
            }

    async def _parse_pytest_json_results(
        self, working_dir: str
    ) -> Optional[Dict[str, Any]]:
        """解析pytest JSON结果文件"""
        try:
            json_path = f"{working_dir}/test_results.json"

            # 检查文件是否存在
            try:
                content = await self.sandbox.filesystem.read(json_path)
                if content:
                    results = json.loads(content)

                    # 提取关键统计信息
                    summary = results.get("summary", {})
                    return {
                        "passed": summary.get("passed", 0),
                        "failed": summary.get("failed", 0),
                        "error": summary.get("error", 0),
                        "skipped": summary.get("skipped", 0),
                        "total": summary.get("total", 0),
                        "duration": results.get("duration", 0),
                        "tests": results.get("tests", []),
                    }
            except:
                pass

        except Exception as e:
            logger.warning(f"解析pytest JSON结果失败: {e}")

        return None

    def _parse_pytest_output(self, output: str) -> Dict[str, int]:
        """解析pytest文本输出结果"""
        results = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}

        try:
            lines = output.split("\n")
            for line in lines:
                if (
                    "passed" in line
                    or "failed" in line
                    or "error" in line
                    or "skipped" in line
                ):
                    # 查找类似 "2 passed, 1 failed" 的行
                    import re

                    pattern = r"(\d+)\s+(\w+)"
                    matches = re.findall(pattern, line)
                    for count, status in matches:
                        if status in results:
                            results[status] = int(count)
                        elif status == "errors":
                            results["error"] = int(count)
        except Exception as e:
            logger.warning(f"解析pytest输出失败: {e}")

        return results

    async def install_packages(self, packages: List[str]) -> Dict[str, Any]:
        """在沙盒中安装Python包

        Args:
            packages: 要安装的包列表

        Returns:
            安装结果
        """
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在E2B沙盒中安装包: {packages}")

        try:
            # 构建pip安装命令
            cmd = f"pip install {' '.join(packages)}"

            execution = await self.sandbox.run_command(
                command=cmd, timeout=min(self.timeout, 120)  # 安装包可能需要更长时间
            )

            result = {
                "success": execution.exit_code == 0,
                "stdout": execution.stdout,
                "stderr": execution.stderr,
                "return_code": execution.exit_code,
                "packages": packages,
                "error": execution.stderr if execution.exit_code != 0 else None,
            }

            logger.info(f"包安装完成，成功: {result['success']}")
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
            }

    async def get_system_info(self) -> Dict[str, Any]:
        """获取沙盒系统信息"""
        if not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        try:
            # 获取系统信息
            info_commands = {
                "python_version": "python --version",
                "pip_version": "pip --version",
                "os_info": "uname -a",
                "memory_info": "free -h",
                "disk_info": "df -h",
                "cpu_info": "nproc",
            }

            system_info = {}

            for key, cmd in info_commands.items():
                try:
                    execution = await self.sandbox.run_command(cmd, timeout=10)
                    if execution.exit_code == 0:
                        system_info[key] = execution.stdout.strip()
                    else:
                        system_info[key] = f"Error: {execution.stderr}"
                except:
                    system_info[key] = "N/A"

            return system_info

        except Exception as e:
            logger.error(f"获取系统信息失败: {e}")
            return {"error": str(e)}


class E2BSandboxManager:
    """E2B沙盒管理器

    管理多个沙盒实例，提供资源池和负载均衡功能。
    """

    def __init__(self, max_sandboxes: int = 3):
        self.max_sandboxes = max_sandboxes
        self.active_sandboxes: List[E2BSandboxExecutor] = []
        self.sandbox_pool: List[E2BSandboxExecutor] = []

    async def get_sandbox(self) -> E2BSandboxExecutor:
        """获取可用的沙盒实例"""
        # 从池中获取空闲沙盒
        if self.sandbox_pool:
            sandbox = self.sandbox_pool.pop()
            self.active_sandboxes.append(sandbox)
            return sandbox

        # 如果没有空闲沙盒且未达到最大数量，创建新沙盒
        if len(self.active_sandboxes) < self.max_sandboxes:
            sandbox = E2BSandboxExecutor()
            await sandbox.start_sandbox()
            self.active_sandboxes.append(sandbox)
            return sandbox

        # 等待沙盒可用
        raise RuntimeError("所有沙盒都在使用中，请稍后重试")

    async def return_sandbox(self, sandbox: E2BSandboxExecutor):
        """归还沙盒到池中"""
        if sandbox in self.active_sandboxes:
            self.active_sandboxes.remove(sandbox)
            self.sandbox_pool.append(sandbox)

    async def cleanup_all(self):
        """清理所有沙盒"""
        all_sandboxes = self.active_sandboxes + self.sandbox_pool

        for sandbox in all_sandboxes:
            try:
                await sandbox.stop_sandbox()
            except Exception as e:
                logger.error(f"清理沙盒失败: {e}")

        self.active_sandboxes.clear()
        self.sandbox_pool.clear()


# 全局沙盒管理器实例
sandbox_manager = E2BSandboxManager()


async def execute_code_in_e2b(
    code: str,
    execution_type: str = "python",
    timeout: int = 60,
    env_vars: Dict[str, str] = None,
) -> Dict[str, Any]:
    """在E2B沙盒中执行代码的便捷函数

    Args:
        code: 要执行的代码
        execution_type: 执行类型 ('python', 'script', 'pytest')
        timeout: 超时时间
        env_vars: 环境变量

    Returns:
        执行结果
    """
    try:
        sandbox = await sandbox_manager.get_sandbox()

        try:
            if execution_type == "python":
                result = await sandbox.execute_python_code(code, env_vars=env_vars)
            elif execution_type == "script":
                result = await sandbox.execute_python_script(code, env_vars=env_vars)
            elif execution_type == "pytest":
                result = await sandbox.execute_pytest_script(code, env_vars=env_vars)
            else:
                raise ValueError(f"不支持的执行类型: {execution_type}")

            return result

        finally:
            await sandbox_manager.return_sandbox(sandbox)

    except Exception as e:
        logger.error(f"E2B代码执行失败: {e}")
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "return_code": -1,
            "execution_time": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
