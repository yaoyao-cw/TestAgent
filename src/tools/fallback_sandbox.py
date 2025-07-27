"""回退沙盒执行器

当E2B不可用时，提供本地沙盒执行环境。
使用subprocess和临时目录实现基本的隔离执行。
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.logging_config import get_logger

logger = get_logger("fallback_sandbox")


class FallbackSandboxExecutor:
    """回退沙盒执行器

    在E2B不可用时提供基本的沙盒执行功能。
    使用临时目录和subprocess实现基本隔离。
    """

    def __init__(self, timeout: int = 60, memory_limit: str = "512m"):
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.temp_dir = None
        self.is_active = False

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
            logger.info("启动回退沙盒环境")

            # 创建临时工作目录
            self.temp_dir = tempfile.mkdtemp(prefix="fallback_sandbox_")
            self.is_active = True

            logger.info(f"回退沙盒环境启动成功，工作目录: {self.temp_dir}")

        except Exception as e:
            logger.error(f"启动回退沙盒失败: {e}")
            raise

    async def stop_sandbox(self):
        """停止沙盒环境"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                logger.info("停止回退沙盒环境")
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
                self.is_active = False
                logger.info("回退沙盒环境已停止")
            except Exception as e:
                logger.error(f"停止回退沙盒失败: {e}")

    async def execute_python_code(
        self, code: str, working_dir: str = None, env_vars: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """执行Python代码"""
        if not self.is_active:
            raise RuntimeError("沙盒环境未启动")

        logger.info("在回退沙盒中执行Python代码")

        start_time = time.time()

        try:
            # 创建临时Python文件
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", dir=self.temp_dir, delete=False
            ) as temp_file:
                temp_file.write(code)
                temp_file_path = temp_file.name

            # 设置环境变量
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)

            # 执行代码
            result = await asyncio.create_subprocess_exec(
                "python",
                temp_file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir or self.temp_dir,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(), timeout=self.timeout
                )

                execution_time = time.time() - start_time

                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass

                return {
                    "success": result.returncode == 0,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "return_code": result.returncode,
                    "execution_time": execution_time,
                    "memory_usage": None,
                    "error": (
                        stderr.decode("utf-8", errors="replace")
                        if result.returncode != 0
                        else None
                    ),
                    "sandbox_id": f"fallback_{id(self)}",
                    "timestamp": datetime.now().isoformat(),
                }

            except asyncio.TimeoutError:
                # 终止进程
                result.terminate()
                await result.wait()

                execution_time = time.time() - start_time

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"执行超时 ({self.timeout}秒)",
                    "return_code": -1,
                    "execution_time": execution_time,
                    "memory_usage": None,
                    "error": f"执行超时 ({self.timeout}秒)",
                    "sandbox_id": f"fallback_{id(self)}",
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
                "sandbox_id": f"fallback_{id(self)}",
                "timestamp": datetime.now().isoformat(),
            }

    async def execute_python_script(
        self,
        script_content: str,
        script_name: str = "script.py",
        working_dir: str = None,
        env_vars: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """执行Python脚本文件"""
        if not self.is_active:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在回退沙盒中执行Python脚本: {script_name}")

        start_time = time.time()

        try:
            # 将脚本写入文件
            script_path = os.path.join(self.temp_dir, script_name)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)

            # 设置环境变量
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)

            # 执行脚本
            result = await asyncio.create_subprocess_exec(
                "python",
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir or self.temp_dir,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(), timeout=self.timeout
                )

                execution_time = time.time() - start_time

                return {
                    "success": result.returncode == 0,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "return_code": result.returncode,
                    "script_name": script_name,
                    "execution_time": execution_time,
                    "memory_usage": None,
                    "error": (
                        stderr.decode("utf-8", errors="replace")
                        if result.returncode != 0
                        else None
                    ),
                    "sandbox_id": f"fallback_{id(self)}",
                    "timestamp": datetime.now().isoformat(),
                }

            except asyncio.TimeoutError:
                # 终止进程
                result.terminate()
                await result.wait()

                execution_time = time.time() - start_time

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"脚本执行超时 ({self.timeout}秒)",
                    "return_code": -1,
                    "script_name": script_name,
                    "execution_time": execution_time,
                    "memory_usage": None,
                    "error": f"脚本执行超时 ({self.timeout}秒)",
                    "sandbox_id": f"fallback_{id(self)}",
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
                "sandbox_id": f"fallback_{id(self)}",
                "timestamp": datetime.now().isoformat(),
            }

    async def execute_pytest_script(
        self,
        script_content: str,
        script_name: str = "test_script.py",
        test_args: List[str] = None,
        working_dir: str = None,
        env_vars: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """执行pytest测试脚本"""
        if not self.is_active:
            raise RuntimeError("沙盒环境未启动")

        if test_args is None:
            test_args = ["-v", "--tb=short"]

        logger.info(f"在回退沙盒中执行pytest测试: {script_name}")

        start_time = time.time()

        try:
            # 将测试脚本写入文件
            script_path = os.path.join(self.temp_dir, script_name)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)

            # 设置环境变量
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)

            # 构建pytest命令
            cmd = ["python", "-m", "pytest"] + test_args + [script_path]

            # 执行pytest
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir or self.temp_dir,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(), timeout=self.timeout
                )

                execution_time = time.time() - start_time

                # 解析pytest输出
                test_results = self._parse_pytest_output(
                    stdout.decode("utf-8", errors="replace")
                )

                return {
                    "success": result.returncode == 0,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "return_code": result.returncode,
                    "script_name": script_name,
                    "execution_time": execution_time,
                    "memory_usage": None,
                    "error": (
                        stderr.decode("utf-8", errors="replace")
                        if result.returncode != 0
                        else None
                    ),
                    "test_results": test_results,
                    "sandbox_id": f"fallback_{id(self)}",
                    "timestamp": datetime.now().isoformat(),
                }

            except asyncio.TimeoutError:
                # 终止进程
                result.terminate()
                await result.wait()

                execution_time = time.time() - start_time

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"pytest执行超时 ({self.timeout}秒)",
                    "return_code": -1,
                    "script_name": script_name,
                    "execution_time": execution_time,
                    "memory_usage": None,
                    "error": f"pytest执行超时 ({self.timeout}秒)",
                    "test_results": {
                        "passed": 0,
                        "failed": 0,
                        "error": 0,
                        "skipped": 0,
                    },
                    "sandbox_id": f"fallback_{id(self)}",
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
                "sandbox_id": f"fallback_{id(self)}",
                "timestamp": datetime.now().isoformat(),
            }

    def _parse_pytest_output(self, output: str) -> Dict[str, int]:
        """解析pytest输出结果"""
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
        """安装Python包"""
        if not self.is_active:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在回退沙盒中安装包: {packages}")

        try:
            # 构建pip安装命令
            cmd = ["python", "-m", "pip", "install"] + packages

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.temp_dir,
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(), timeout=min(self.timeout, 120)
            )

            return {
                "success": result.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "return_code": result.returncode,
                "packages": packages,
                "error": (
                    stderr.decode("utf-8", errors="replace")
                    if result.returncode != 0
                    else None
                ),
            }

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
        """获取系统信息"""
        if not self.is_active:
            raise RuntimeError("沙盒环境未启动")

        try:
            import platform
            import sys

            return {
                "python_version": sys.version,
                "platform": platform.platform(),
                "architecture": platform.architecture(),
                "processor": platform.processor(),
                "sandbox_type": "fallback",
                "temp_dir": self.temp_dir,
            }

        except Exception as e:
            logger.error(f"获取系统信息失败: {e}")
            return {"error": str(e)}
