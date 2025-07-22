"""
最终版本的Python REPL工具
结合了deer-flow的简洁性和我们的安全性，提供完整的功能
"""

import sys
import io
import ast
import time
import logging
import traceback
from typing import Dict, Any, Optional, Tuple, Annotated, List
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def log_io(func):
    """输入输出日志装饰器 - 基于deer-flow设计"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        
        # 记录输入参数
        if args and len(args) > 0:
            if isinstance(args[0], str):  # 对于函数调用
                code_preview = args[0][:100] + "..." if len(args[0]) > 100 else args[0]
                logger.info(f"Tool {func_name} executing: {code_preview}")
            elif len(args) > 1 and isinstance(args[1], str):  # 对于方法调用
                code_preview = args[1][:100] + "..." if len(args[1]) > 100 else args[1]
                logger.info(f"Tool {func_name} executing: {code_preview}")
        
        # 执行函数
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # 记录输出结果
        if isinstance(result, str):
            if "Successfully executed:" in result:
                logger.info(f"Tool {func_name} completed successfully in {execution_time:.4f}s")
            elif "Error executing code:" in result:
                logger.error(f"Tool {func_name} failed in {execution_time:.4f}s")
        elif isinstance(result, dict):
            success = result.get('success', False)
            logger.info(f"Tool {func_name} {'succeeded' if success else 'failed'} in {execution_time:.4f}s")
        
        return result
    return wrapper


class PythonREPLTool:
    """
    最终版本的Python REPL工具
    结合了deer-flow的简洁性和强大的安全性
    """
    
    def __init__(self, timeout: int = 30, max_output_length: int = 10000):
        """
        初始化Python REPL工具
        
        Args:
            timeout: 代码执行超时时间（秒）
            max_output_length: 最大输出长度
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.safe_globals = self._create_safe_environment()
        self.execution_history: List[Dict[str, Any]] = []
        logger.info("Python REPL Tool initialized")
    
    def _create_safe_environment(self) -> Dict[str, Any]:
        """创建安全的执行环境"""
        # 安全的内置函数
        safe_builtins = {
            # 基本类型和函数
            'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
            'chr': chr, 'dict': dict, 'enumerate': enumerate, 'filter': filter,
            'float': float, 'format': format, 'frozenset': frozenset,
            'getattr': getattr, 'hasattr': hasattr, 'hash': hash, 'hex': hex,
            'id': id, 'int': int, 'isinstance': isinstance, 'issubclass': issubclass,
            'iter': iter, 'len': len, 'list': list, 'map': map,
            'max': max, 'min': min, 'next': next, 'oct': oct, 'ord': ord,
            'pow': pow, 'print': print, 'range': range, 'repr': repr,
            'reversed': reversed, 'round': round, 'set': set, 'slice': slice,
            'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
            'type': type, 'zip': zip,
            # 异常类
            'Exception': Exception, 'ValueError': ValueError,
            'TypeError': TypeError, 'IndexError': IndexError,
            'KeyError': KeyError, 'AttributeError': AttributeError,
            'ZeroDivisionError': ZeroDivisionError, 'NameError': NameError,
            'SyntaxError': SyntaxError, 'RuntimeError': RuntimeError,
        }
        
        # 预加载安全模块
        safe_modules = {}
        module_names = ['math', 'random', 'datetime', 'json', 're', 'collections', 'itertools', 'string']
        
        for module_name in module_names:
            try:
                module = __import__(module_name)
                safe_modules[module_name] = module
            except ImportError:
                logger.warning(f"Failed to import {module_name}")
        
        return {
            '__builtins__': safe_builtins,
            **safe_modules
        }
    
    def _is_safe_code(self, code: str) -> Tuple[bool, str]:
        """
        检查代码安全性
        使用AST分析来检测危险操作
        """
        try:
            tree = ast.parse(code)
            
            # 危险的节点类型
            dangerous_nodes = [
                ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Global, ast.Nonlocal
            ]
            
            # 危险的函数调用
            dangerous_calls = {
                'exec', 'eval', 'compile', '__import__', 'open', 'file',
                'input', 'raw_input', 'vars', 'locals', 'globals', 'dir',
                'help', 'exit', 'quit', 'reload', 'delattr', 'setattr'
            }
            
            # 遍历AST节点
            for node in ast.walk(tree):
                # 检查危险节点类型
                if any(isinstance(node, dangerous_type) for dangerous_type in dangerous_nodes):
                    return False, f"不允许的操作: {type(node).__name__}"
                
                # 检查危险函数调用
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in dangerous_calls:
                        return False, f"不允许调用: {node.func.id}"
                
                # 检查导入语句
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return False, "不允许导入模块"
                
                # 检查私有属性访问
                if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
                    return False, f"不允许访问私有属性: {node.attr}"
                
                # 检查删除操作
                if isinstance(node, ast.Delete):
                    return False, "不允许删除操作"
            
            return True, ""
            
        except SyntaxError as e:
            return False, f"语法错误: {e}"
        except Exception as e:
            return False, f"代码分析失败: {e}"
    
    @contextmanager
    def _capture_output(self):
        """上下文管理器用于捕获输出"""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            yield stdout_capture, stderr_capture
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def run(self, code: str) -> str:
        """
        执行Python代码 - deer-flow兼容接口
        
        Args:
            code: 要执行的Python代码
            
        Returns:
            执行结果字符串
        """
        if not isinstance(code, str):
            return f"Error: code must be a string, got {type(code)}"
        
        # 安全检查
        is_safe, error_msg = self._is_safe_code(code)
        if not is_safe:
            return f"Error: {error_msg}"
        
        # 执行代码
        with self._capture_output() as (stdout_capture, stderr_capture):
            try:
                # 复制安全环境
                exec_globals = self.safe_globals.copy()
                
                # 尝试执行
                result = None
                try:
                    # 先尝试作为表达式
                    compiled = compile(code, '<string>', 'eval')
                    result = eval(compiled, exec_globals)
                except SyntaxError:
                    # 作为语句执行
                    exec(code, exec_globals)
                    result = None
                
                # 获取输出
                stdout_output = stdout_capture.getvalue()
                stderr_output = stderr_capture.getvalue()
                
                # 处理错误输出
                if stderr_output:
                    return f"Error: {stderr_output.strip()}"
                
                # 返回结果
                if stdout_output:
                    output = stdout_output.rstrip('\n')
                elif result is not None:
                    output = str(result)
                else:
                    output = ""
                
                # 限制输出长度
                if len(output) > self.max_output_length:
                    output = output[:self.max_output_length] + "... (truncated)"
                
                return output
                
            except Exception as e:
                return f"Error: {str(e)}"
    
    def execute_with_details(self, code: str) -> Dict[str, Any]:
        """
        执行代码并返回详细信息
        
        Args:
            code: 要执行的Python代码
            
        Returns:
            包含详细执行信息的字典
        """
        start_time = time.time()
        
        # 安全检查
        is_safe, error_msg = self._is_safe_code(code)
        if not is_safe:
            result = {
                "success": False,
                "error": error_msg,
                "output": "",
                "result": None,
                "execution_time": 0,
                "code": code
            }
            self.execution_history.append(result)
            return result
        
        # 执行代码
        with self._capture_output() as (stdout_capture, stderr_capture):
            try:
                exec_globals = self.safe_globals.copy()
                
                result_value = None
                try:
                    compiled = compile(code, '<string>', 'eval')
                    result_value = eval(compiled, exec_globals)
                except SyntaxError:
                    exec(code, exec_globals)
                    result_value = None
                
                stdout_output = stdout_capture.getvalue()
                stderr_output = stderr_capture.getvalue()
                execution_time = time.time() - start_time
                
                if stderr_output:
                    result = {
                        "success": False,
                        "error": stderr_output.strip(),
                        "output": stdout_output,
                        "result": None,
                        "execution_time": execution_time,
                        "code": code
                    }
                else:
                    result = {
                        "success": True,
                        "error": None,
                        "output": stdout_output,
                        "result": result_value,
                        "execution_time": execution_time,
                        "code": code
                    }
                
                self.execution_history.append(result)
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                result = {
                    "success": False,
                    "error": str(e),
                    "output": stdout_capture.getvalue(),
                    "result": None,
                    "execution_time": execution_time,
                    "code": code,
                    "traceback": traceback.format_exc()
                }
                self.execution_history.append(result)
                return result
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self.execution_history.copy()
    
    def clear_history(self):
        """清空执行历史"""
        self.execution_history.clear()
        logger.info("Execution history cleared")
    
    def get_available_modules(self) -> List[str]:
        """获取可用模块列表"""
        return [name for name in self.safe_globals.keys() if name != '__builtins__']
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": "PythonREPLTool",
            "version": "1.0.0",
            "description": "安全的Python代码执行工具，结合了deer-flow的简洁性和强大的安全性",
            "timeout": self.timeout,
            "max_output_length": self.max_output_length,
            "available_modules": self.get_available_modules(),
            "safety_features": [
                "AST代码分析",
                "沙箱执行环境",
                "危险函数阻止",
                "私有属性保护",
                "导入限制",
                "输出长度限制",
                "执行超时控制"
            ],
            "execution_count": len(self.execution_history)
        }


# 全局实例 - 类似deer-flow的设计模式
repl = PythonREPLTool()


@log_io
def python_repl_tool(
    code: Annotated[str, "要执行的Python代码用于数据分析或计算"]
) -> str:
    """
    Python REPL工具函数 - 兼容deer-flow接口
    
    使用此工具执行Python代码进行数据分析或计算。
    如果要查看值的输出，应该使用print(...)打印出来，这对用户是可见的。
    
    Args:
        code: 要执行的Python代码
        
    Returns:
        执行结果字符串，格式与deer-flow兼容
    """
    if not isinstance(code, str):
        error_msg = f"Invalid input: code must be a string, got {type(code)}"
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"

    logger.info("Executing Python code")
    try:
        result = repl.run(code)
        
        # 检查结果是否为错误
        if isinstance(result, str) and result.startswith("Error:"):
            logger.error(result)
            return f"Error executing code:\n```python\n{code}\n```\n{result}"
        
        logger.info("Code execution successful")
        return f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
        
    except Exception as e:
        error_msg = str(e)
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"


# 额外的工具函数
def execute_python_with_details(code: str) -> Dict[str, Any]:
    """执行Python代码并返回详细信息"""
    return repl.execute_with_details(code)


def get_python_repl_info() -> Dict[str, Any]:
    """获取Python REPL工具信息"""
    return repl.get_tool_info()


def reset_python_repl():
    """重置Python REPL环境"""
    global repl
    repl = PythonREPLTool()
    logger.info("Python REPL environment reset")


# 导出的主要接口
__all__ = [
    'PythonREPLTool',
    'python_repl_tool',
    'execute_python_with_details',
    'get_python_repl_info',
    'reset_python_repl',
    'repl'
]