"""统一沙盒接口

提供统一的沙盒执行接口，自动选择E2B或回退沙盒。
实现资源限制、超时控制和详细的执行结果处理。
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from .e2b_sandbox import E2BSandboxExecutor, E2B_AVAILABLE
from .fallback_sandbox import FallbackSandboxExecutor
from ..config.logging_config import get_logger
from ..config.settings import get_settings

logger = get_logger("unified_sandbox")


class UnifiedSandboxExecutor:
    """统一沙盒执行器

    自动选择最佳的沙盒执行环境（E2B优先，回退到本地沙盒）。
    提供统一的接口和完整的错误处理。
    """

    def __init__(
        self, timeout: int = 60, memory_limit: str = "512m", prefer_e2b: bool = True
    ):
        """初始化统一沙盒执行器

        Args:
            timeout: 执行超时时间（秒）
            memory_limit: 内存限制
            prefer_e2b: 是否优先使用E2B
        """
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.prefer_e2b = prefer_e2b
        self.sandbox = None
        self.sandbox_type = None
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
        logger.info("启动统一沙盒环境")

        # 尝试使用E2B沙盒
        if self.prefer_e2b and E2B_AVAILABLE:
            try:
                settings = get_settings()
                e2b_api_key = getattr(settings, "E2B_API_KEY", None)

                if e2b_api_key:
                    logger.info("尝试启动E2B沙盒")
                    self.sandbox = E2BSandboxExecutor(
                        timeout=self.timeout,
                        memory_limit=int(self.memory_limit.replace("m", "")),
                    )
                    await self.sandbox.start_sandbox()
                    self.sandbox_type = "e2b"
                    self.is_active = True
                    logger.info("E2B沙盒启动成功")
                    return
                else:
                    logger.warning("E2B_API_KEY未配置，将使用回退沙盒")

            except Exception as e:
                logger.warning(f"E2B沙盒启动失败，将使用回退沙盒: {e}")

        # 使用回退沙盒
        try:
            logger.info("启动回退沙盒")
            self.sandbox = FallbackSandboxExecutor(
                timeout=self.timeout, memory_limit=self.memory_limit
            )
            await self.sandbox.start_sandbox()
            self.sandbox_type = "fallback"
            self.is_active = True
            logger.info("回退沙盒启动成功")

        except Exception as e:
            logger.error(f"沙盒启动失败: {e}")
            raise RuntimeError(f"无法启动任何沙盒环境: {e}")

    async def stop_sandbox(self):
        """停止沙盒环境"""
        if self.sandbox:
            try:
                logger.info(f"停止{self.sandbox_type}沙盒环境")
                await self.sandbox.stop_sandbox()
                self.sandbox = None
                self.sandbox_type = None
                self.is_active = False
                logger.info("沙盒环境已停止")
            except Exception as e:
                logger.error(f"停止沙盒失败: {e}")

    async def execute_python_code(
        self, code: str, working_dir: str = None, env_vars: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """执行Python代码

        Args:
            code: 要执行的Python代码
            working_dir: 工作目录
            env_vars: 环境变量

        Returns:
            执行结果字典
        """
        if not self.is_active or not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在{self.sandbox_type}沙盒中执行Python代码")

        try:
            result = await self.sandbox.execute_python_code(
                code=code, working_dir=working_dir, env_vars=env_vars
            )

            # 添加沙盒类型信息
            result["sandbox_type"] = self.sandbox_type

            return result

        except Exception as e:
            logger.error(f"Python代码执行失败: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "execution_time": 0,
                "memory_usage": None,
                "error": str(e),
                "sandbox_type": self.sandbox_type,
                "timestamp": datetime.now().isoformat(),
            }

    async def execute_python_script(
        self,
        script_content: str,
        script_name: str = "script.py",
        working_dir: str = None,
        env_vars: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """执行Python脚本文件

        Args:
            script_content: 脚本内容
            script_name: 脚本文件名
            working_dir: 工作目录
            env_vars: 环境变量

        Returns:
            执行结果字典
        """
        if not self.is_active or not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在{self.sandbox_type}沙盒中执行Python脚本: {script_name}")

        try:
            result = await self.sandbox.execute_python_script(
                script_content=script_content,
                script_name=script_name,
                working_dir=working_dir,
                env_vars=env_vars,
            )

            # 添加沙盒类型信息
            result["sandbox_type"] = self.sandbox_type

            return result

        except Exception as e:
            logger.error(f"Python脚本执行失败: {script_name}, 错误: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "script_name": script_name,
                "execution_time": 0,
                "memory_usage": None,
                "error": str(e),
                "sandbox_type": self.sandbox_type,
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
        """执行pytest测试脚本

        Args:
            script_content: 测试脚本内容
            script_name: 测试脚本文件名
            test_args: pytest参数
            working_dir: 工作目录
            env_vars: 环境变量

        Returns:
            执行结果字典
        """
        if not self.is_active or not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在{self.sandbox_type}沙盒中执行pytest测试: {script_name}")

        try:
            result = await self.sandbox.execute_pytest_script(
                script_content=script_content,
                script_name=script_name,
                test_args=test_args,
                working_dir=working_dir,
                env_vars=env_vars,
            )

            # 添加沙盒类型信息
            result["sandbox_type"] = self.sandbox_type

            return result

        except Exception as e:
            logger.error(f"pytest执行失败: {script_name}, 错误: {e}")
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
                "sandbox_type": self.sandbox_type,
                "timestamp": datetime.now().isoformat(),
            }

    async def install_packages(self, packages: List[str]) -> Dict[str, Any]:
        """安装Python包

        Args:
            packages: 要安装的包列表

        Returns:
            安装结果
        """
        if not self.is_active or not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        logger.info(f"在{self.sandbox_type}沙盒中安装包: {packages}")

        try:
            result = await self.sandbox.install_packages(packages)
            result["sandbox_type"] = self.sandbox_type
            return result

        except Exception as e:
            logger.error(f"包安装失败: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "packages": packages,
                "error": str(e),
                "sandbox_type": self.sandbox_type,
            }

    async def get_system_info(self) -> Dict[str, Any]:
        """获取沙盒系统信息

        Returns:
            系统信息字典
        """
        if not self.is_active or not self.sandbox:
            raise RuntimeError("沙盒环境未启动")

        try:
            info = await self.sandbox.get_system_info()
            info["sandbox_type"] = self.sandbox_type
            info["e2b_available"] = E2B_AVAILABLE
            return info

        except Exception as e:
            logger.error(f"获取系统信息失败: {e}")
            return {
                "error": str(e),
                "sandbox_type": self.sandbox_type,
                "e2b_available": E2B_AVAILABLE,
            }

    def get_sandbox_type(self) -> str:
        """获取当前沙盒类型"""
        return self.sandbox_type or "unknown"

    def is_e2b_sandbox(self) -> bool:
        """检查是否使用E2B沙盒"""
        return self.sandbox_type == "e2b"

    def is_fallback_sandbox(self) -> bool:
        """检查是否使用回退沙盒"""
        return self.sandbox_type == "fallback"


class SandboxExecutionResult:
    """沙盒执行结果封装类"""

    def __init__(self, result_dict: Dict[str, Any]):
        self.raw_result = result_dict

        # 基本属性
        self.success = result_dict.get("success", False)
        self.stdout = result_dict.get("stdout", "")
        self.stderr = result_dict.get("stderr", "")
        self.return_code = result_dict.get("return_code", -1)
        self.execution_time = result_dict.get("execution_time", 0)
        self.error = result_dict.get("error")
        self.sandbox_type = result_dict.get("sandbox_type", "unknown")
        self.timestamp = result_dict.get("timestamp")

        # 脚本相关属性
        self.script_name = result_dict.get("script_name")

        # 测试相关属性
        self.test_results = result_dict.get("test_results", {})

        # 资源使用属性
        self.memory_usage = result_dict.get("memory_usage")
        self.sandbox_id = result_dict.get("sandbox_id")

    def is_successful(self) -> bool:
        """检查执行是否成功"""
        return self.success

    def has_output(self) -> bool:
        """检查是否有输出"""
        return bool(self.stdout.strip())

    def has_error(self) -> bool:
        """检查是否有错误"""
        return bool(self.stderr.strip() or self.error)

    def get_test_summary(self) -> Dict[str, int]:
        """获取测试结果摘要"""
        if not self.test_results:
            return {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "total": 0}

        summary = self.test_results.copy()
        if "total" not in summary:
            summary["total"] = sum(
                summary.get(k, 0) for k in ["passed", "failed", "error", "skipped"]
            )

        return summary

    def get_formatted_output(self) -> str:
        """获取格式化的输出"""
        output_parts = []

        if self.stdout:
            output_parts.append(f"标准输出:\n{self.stdout}")

        if self.stderr:
            output_parts.append(f"错误输出:\n{self.stderr}")

        if self.test_results:
            summary = self.get_test_summary()
            output_parts.append(f"测试结果: {summary}")

        return "\n\n".join(output_parts) if output_parts else "无输出"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.raw_result.copy()


async def create_sandbox_executor(
    timeout: int = 60, memory_limit: str = "512m", prefer_e2b: bool = True
) -> UnifiedSandboxExecutor:
    """创建沙盒执行器的便捷函数

    Args:
        timeout: 执行超时时间
        memory_limit: 内存限制
        prefer_e2b: 是否优先使用E2B

    Returns:
        配置好的沙盒执行器
    """
    executor = UnifiedSandboxExecutor(
        timeout=timeout, memory_limit=memory_limit, prefer_e2b=prefer_e2b
    )

    await executor.start_sandbox()
    return executor


async def execute_code_safely(
    code: str,
    execution_type: str = "python",
    timeout: int = 60,
    env_vars: Dict[str, str] = None,
    script_name: str = None,
) -> SandboxExecutionResult:
    """安全执行代码的便捷函数

    Args:
        code: 要执行的代码
        execution_type: 执行类型 ('python', 'script', 'pytest')
        timeout: 超时时间
        env_vars: 环境变量
        script_name: 脚本名称（用于script和pytest类型）

    Returns:
        封装的执行结果
    """
    async with UnifiedSandboxExecutor(timeout=timeout) as executor:
        if execution_type == "python":
            result = await executor.execute_python_code(code, env_vars=env_vars)
        elif execution_type == "script":
            result = await executor.execute_python_script(
                code, script_name or "script.py", env_vars=env_vars
            )
        elif execution_type == "pytest":
            result = await executor.execute_pytest_script(
                code, script_name or "test_script.py", env_vars=env_vars
            )
        else:
            raise ValueError(f"不支持的执行类型: {execution_type}")

        return SandboxExecutionResult(result)
