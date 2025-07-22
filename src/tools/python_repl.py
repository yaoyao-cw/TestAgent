"""Python REPL工具模块 - 基于deer-flow的简洁设计改进"""

import sys
import io
import traceback
import ast
import time
import tempfile
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Tuple, Annotated
import logging
from functools import wraps

# 简化的日志配置
logger = logging.getLogger(__name__)

def log_io(func):
    """简化的输入输出日志装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        params = ", ".join([str(arg)[:100] for arg in args] + [f"{k}={str(v)[:100]}" for k, v in kwargs.items()])
        logger.info(f"Tool {func_name} called with parameters: {params}")
        
        result = func(*args, **kwargs)
        logger.info(f"Tool {func_name} returned: {str(result)[:200]}")
        return result
    return wrapper


class PythonREPL:
    """Python REPL工具，用于安全执行Python代码"""
    
    def __init__(self, timeout: int = 30, max_output_length: int = 10000):
        """初始化Python REPL
        
        Args:
            timeout: 代码执行超时时间（秒）
            max_output_length: 最大输出长度
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # 创建隔离的执行环境
        self.globals_dict = {
            '__builtins__': {
                # 安全的内置函数
                'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
                'chr': chr, 'dict': dict, 'dir': dir, 'divmod': divmod,
                'enumerate': enumerate, 'filter': filter, 'float': float,
                'format': format, 'frozenset': frozenset, 'getattr': getattr,
                'hasattr': hasattr, 'hash': hash, 'hex': hex, 'id': id,
                'int': int, 'isinstance': isinstance, 'issubclass': issubclass,
                'iter': iter, 'len': len, 'list': list, 'map': map,
                'max': max, 'min': min, 'next': next, 'oct': oct,
                'ord': ord, 'pow': pow, 'print': print, 'range': range,
                'repr': repr, 'reversed': reversed, 'round': round,
                'set': set, 'slice': slice, 'sorted': sorted, 'str': str,
                'sum': sum, 'tuple': tuple, 'type': type, 'zip': zip,
                # 数学函数
                'divmod': divmod, 'pow': pow, 'round': round,
                # 异常类
                'Exception': Exception, 'ValueError': ValueError,
                'TypeError': TypeError, 'IndexError': IndexError,
                'KeyError': KeyError, 'AttributeError': AttributeError,
                # 移除不安全的导入函数
            }
        }
        
        # 添加常用模块
        self._setup_safe_modules()
        
        logger.info("Python REPL initialized")
    
    def _setup_safe_modules(self):
        """设置安全的模块"""
        try:
            # 数学模块
            import math
            self.globals_dict['math'] = math
            
            # 随机模块
            import random
            self.globals_dict['random'] = random
            
            # 日期时间模块
            import datetime
            self.globals_dict['datetime'] = datetime
            
            # JSON模块
            import json
            self.globals_dict['json'] = json
            
            # 正则表达式模块
            import re
            self.globals_dict['re'] = re
            
            # 集合模块
            import collections
            self.globals_dict['collections'] = collections
            
            # itertools模块
            import itertools
            self.globals_dict['itertools'] = itertools
            
            logger.info("Safe modules loaded")
            
        except Exception as e:
            logger.warning(f"Failed to load some safe modules: {e}")
    
    def _is_safe_code(self, code: str) -> Tuple[bool, str]:
        """检查代码是否安全
        
        Args:
            code: 要检查的代码
            
        Returns:
            (是否安全, 错误信息)
        """
        try:
            # 解析AST
            tree = ast.parse(code)
            
            # 危险的节点类型
            dangerous_nodes = {
                ast.FunctionDef: "不允许定义函数",
                ast.AsyncFunctionDef: "不允许定义异步函数",
                ast.ClassDef: "不允许定义类",
                ast.Global: "不允许使用global",
                ast.Nonlocal: "不允许使用nonlocal",
            }
            
            # 允许的安全模块
            safe_modules = {
                'math', 'random', 'datetime', 'json', 're', 
                'collections', 'itertools', 'string', 'time'
            }
            
            # 危险的函数调用
            dangerous_calls = {
                'exec', 'eval', 'compile',
                'open', 'file', 'input', 'raw_input',
                'reload', 'vars', 'locals', 'globals',
                'dir', 'help', 'exit', 'quit'
            }
            
            # 遍历AST节点
            for node in ast.walk(tree):
                # 检查危险节点类型
                for dangerous_type, message in dangerous_nodes.items():
                    if isinstance(node, dangerous_type):
                        return False, message
                
                # 检查导入语句
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in safe_modules:
                            return False, f"不允许导入模块: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module not in safe_modules:
                        return False, f"不允许导入模块: {node.module}"
                
                # 检查函数调用
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in dangerous_calls:
                            return False, f"不允许调用函数: {node.func.id}"
                    elif isinstance(node.func, ast.Attribute):
                        # 检查属性访问
                        if node.func.attr.startswith('_'):
                            return False, f"不允许访问私有属性: {node.func.attr}"
                
                # 检查属性访问
                if isinstance(node, ast.Attribute):
                    if node.attr.startswith('_'):
                        return False, f"不允许访问私有属性: {node.attr}"
            
            return True, ""
            
        except SyntaxError as e:
            return False, f"语法错误: {e}"
        except Exception as e:
            return False, f"代码检查失败: {e}"
    
    @log_io
    def execute_code(
        self, 
        code: str, 
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行Python代码
        
        Args:
            code: 要执行的Python代码
            variables: 预设变量
            
        Returns:
            执行结果
        """
        try:
            logger.info(f"Executing Python code: {code[:100]}...")
            
            # 安全检查
            is_safe, error_msg = self._is_safe_code(code)
            if not is_safe:
                return {
                    "success": False,
                    "error": f"代码安全检查失败: {error_msg}",
                    "output": "",
                    "result": None,
                    "execution_time": 0
                }
            
            # 准备执行环境
            exec_globals = self.globals_dict.copy()
            if variables:
                exec_globals.update(variables)
            
            # 直接同步执行代码
            result = self._execute_code_sync(code, exec_globals)
            
            return result
            
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return {
                "success": False,
                "error": f"执行失败: {str(e)}",
                "output": "",
                "result": None,
                "execution_time": 0
            }
    
    def _execute_code_sync(self, code: str, exec_globals: Dict[str, Any]) -> Dict[str, Any]:
        """同步执行代码"""
        import time
        start_time = time.time()
        
        # 捕获输出
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            # 重定向输出
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # 执行代码
            result = None
            try:
                # 尝试作为表达式执行
                compiled = compile(code, '<string>', 'eval')
                result = eval(compiled, exec_globals)
            except SyntaxError:
                # 作为语句执行
                exec(code, exec_globals)
                result = None
            
            # 获取输出
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            # 合并输出
            output = ""
            if stdout_output:
                output += stdout_output
            if stderr_output:
                if output:
                    output += "\n"
                output += f"错误输出: {stderr_output}"
            
            # 限制输出长度
            if len(output) > self.max_output_length:
                output = output[:self.max_output_length] + "\n... (输出被截断)"
            
            execution_time = time.time() - start_time
            
            return {
                "success": True,
                "error": None,
                "output": output,
                "result": result,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_output = stderr_capture.getvalue()
            
            return {
                "success": False,
                "error": str(e),
                "output": error_output,
                "result": None,
                "execution_time": execution_time,
                "traceback": traceback.format_exc()
            }
            
        finally:
            # 恢复输出
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def execute_script(self, script_path: str) -> Dict[str, Any]:
        """执行Python脚本文件
        
        Args:
            script_path: 脚本文件路径
            
        Returns:
            执行结果
        """
        try:
            if not os.path.exists(script_path):
                return {
                    "success": False,
                    "error": f"脚本文件不存在: {script_path}",
                    "output": "",
                    "return_code": -1
                }
            
            # 读取脚本内容
            with open(script_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 安全检查
            is_safe, error_msg = self._is_safe_code(code)
            if not is_safe:
                return {
                    "success": False,
                    "error": f"脚本安全检查失败: {error_msg}",
                    "output": "",
                    "return_code": -1
                }
            
            # 执行脚本
            result = self.execute_code(code)
            
            return {
                "success": result["success"],
                "error": result.get("error"),
                "output": result.get("output", ""),
                "return_code": 0 if result["success"] else 1,
                "execution_time": result.get("execution_time", 0)
            }
            
        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            return {
                "success": False,
                "error": f"脚本执行失败: {str(e)}",
                "output": "",
                "return_code": -1
            }
    
    def run_tests(self, test_code: str, test_framework: str = "pytest") -> Dict[str, Any]:
        """运行测试代码
        
        Args:
            test_code: 测试代码
            test_framework: 测试框架 (pytest, unittest)
            
        Returns:
            测试结果
        """
        try:
            logger.info(f"Running tests with {test_framework}")
            
            # 创建临时测试文件
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.py', 
                delete=False, 
                encoding='utf-8'
            ) as f:
                f.write(test_code)
                temp_file = f.name
            
            try:
                if test_framework.lower() == "pytest":
                    result = self._run_pytest_sync(temp_file)
                elif test_framework.lower() == "unittest":
                    result = self._run_unittest_sync(temp_file)
                else:
                    result = {
                        "success": False,
                        "error": f"不支持的测试框架: {test_framework}",
                        "output": "",
                        "tests_run": 0,
                        "failures": 0,
                        "errors": 0
                    }
                
                return result
                
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {
                "success": False,
                "error": f"测试执行失败: {str(e)}",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 0
            }
    
    def _run_pytest_sync(self, test_file: str) -> Dict[str, Any]:
        """同步运行pytest测试"""
        try:
            import subprocess
            
            # 运行pytest命令
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', test_file, '-v'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            output = result.stdout
            error_output = result.stderr
            
            if error_output:
                output += f"\n错误输出:\n{error_output}"
            
            # 解析pytest输出
            success = result.returncode == 0
            tests_run = output.count('PASSED') + output.count('FAILED')
            failures = output.count('FAILED')
            errors = output.count('ERROR')
            
            return {
                "success": success,
                "error": None if success else "测试失败",
                "output": output,
                "tests_run": tests_run,
                "failures": failures,
                "errors": errors,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"测试执行超时 ({self.timeout}秒)",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 1
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"pytest执行失败: {str(e)}",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 1
            }
    
    def _run_unittest_sync(self, test_file: str) -> Dict[str, Any]:
        """同步运行unittest测试"""
        try:
            import subprocess
            
            # 运行unittest命令
            result = subprocess.run(
                [sys.executable, '-m', 'unittest', test_file, '-v'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            output = result.stdout
            error_output = result.stderr
            
            if error_output:
                output += f"\n错误输出:\n{error_output}"
            
            # 解析unittest输出
            success = result.returncode == 0
            
            # 简单的输出解析
            import re
            ran_match = re.search(r'Ran (\d+) test', output)
            tests_run = int(ran_match.group(1)) if ran_match else 0
            
            failures = output.count('FAIL')
            errors = output.count('ERROR')
            
            return {
                "success": success,
                "error": None if success else "测试失败",
                "output": output,
                "tests_run": tests_run,
                "failures": failures,
                "errors": errors,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"测试执行超时 ({self.timeout}秒)",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 1
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"unittest执行失败: {str(e)}",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 1
            }

    async def _run_pytest(self, test_file: str) -> Dict[str, Any]:
        """运行pytest测试"""
        try:
            # 运行pytest命令
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-m', 'pytest', test_file, '-v',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=self.timeout
            )
            
            output = stdout.decode('utf-8', errors='ignore')
            error_output = stderr.decode('utf-8', errors='ignore')
            
            if error_output:
                output += f"\n错误输出:\n{error_output}"
            
            # 解析pytest输出
            success = process.returncode == 0
            tests_run = output.count('PASSED') + output.count('FAILED')
            failures = output.count('FAILED')
            errors = output.count('ERROR')
            
            return {
                "success": success,
                "error": None if success else "测试失败",
                "output": output,
                "tests_run": tests_run,
                "failures": failures,
                "errors": errors,
                "return_code": process.returncode
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"测试执行超时 ({self.timeout}秒)",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 1
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"pytest执行失败: {str(e)}",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 1
            }
    
    async def _run_unittest(self, test_file: str) -> Dict[str, Any]:
        """运行unittest测试"""
        try:
            # 运行unittest命令
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-m', 'unittest', test_file, '-v',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=self.timeout
            )
            
            output = stdout.decode('utf-8', errors='ignore')
            error_output = stderr.decode('utf-8', errors='ignore')
            
            if error_output:
                output += f"\n错误输出:\n{error_output}"
            
            # 解析unittest输出
            success = process.returncode == 0
            
            # 简单的输出解析
            import re
            ran_match = re.search(r'Ran (\d+) test', output)
            tests_run = int(ran_match.group(1)) if ran_match else 0
            
            failures = output.count('FAIL')
            errors = output.count('ERROR')
            
            return {
                "success": success,
                "error": None if success else "测试失败",
                "output": output,
                "tests_run": tests_run,
                "failures": failures,
                "errors": errors,
                "return_code": process.returncode
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"测试执行超时 ({self.timeout}秒)",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 1
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"unittest执行失败: {str(e)}",
                "output": "",
                "tests_run": 0,
                "failures": 0,
                "errors": 1
            }
    
    def add_variable(self, name: str, value: Any):
        """添加变量到执行环境"""
        self.globals_dict[name] = value
        logger.info(f"Added variable: {name}")
    
    def remove_variable(self, name: str):
        """从执行环境移除变量"""
        if name in self.globals_dict:
            del self.globals_dict[name]
            logger.info(f"Removed variable: {name}")
    
    def list_variables(self) -> Dict[str, str]:
        """列出当前环境中的变量"""
        variables = {}
        for name, value in self.globals_dict.items():
            if not name.startswith('_') and name != '__builtins__':
                try:
                    variables[name] = str(type(value).__name__)
                except:
                    variables[name] = "unknown"
        return variables
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": "PythonREPL",
            "description": "安全的Python代码执行环境",
            "timeout": self.timeout,
            "max_output_length": self.max_output_length,
            "available_modules": list(self.globals_dict.keys()),
            "capabilities": [
                "execute_code",
                "execute_script", 
                "run_tests",
                "variable_management"
            ]
        }
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)