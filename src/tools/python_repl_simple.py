"""简化的Python REPL工具 - 基于deer-flow设计"""

import sys
import io
import ast
import time
import logging
from typing import Dict, Any, Optional, Tuple, Annotated
from functools import wraps

logger = logging.getLogger(__name__)


def log_io(func):
    """输入输出日志装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        # 记录函数调用
        if args and len(args) > 0:
            # 对于python_repl_tool，第一个参数是代码
            if len(args) > 0 and isinstance(args[0], str):
                code_preview = args[0][:100] + "..." if len(args[0]) > 100 else args[0]
                logger.info(f"Tool {func_name} executing code: {code_preview}")
            # 对于类方法，第二个参数可能是代码
            elif len(args) > 1 and isinstance(args[1], str):
                code_preview = args[1][:100] + "..." if len(args[1]) > 100 else args[1]
                logger.info(f"Tool {func_name} executing code: {code_preview}")
        
        result = func(*args, **kwargs)
        
        # 记录执行结果的简要信息
        if isinstance(result, dict):
            success = result.get('success', False)
            error = result.get('error', '')
            logger.info(f"Tool {func_name} result: success={success}, error={error[:100] if error else 'None'}")
        elif isinstance(result, str):
            logger.info(f"Tool {func_name} returned string result (length: {len(result)})")
        
        return result
    return wrapper


class SimplePythonREPL:
    """简化的Python REPL工具"""
    
    def __init__(self, timeout: int = 30, max_output_length: int = 10000):
        self.timeout = timeout
        self.max_output_length = max_output_length
        
        # 安全的执行环境
        self.safe_globals = self._create_safe_globals()
        logger.info("Simple Python REPL initialized")
    
    def _create_safe_globals(self) -> Dict[str, Any]:
        """创建安全的全局环境"""
        safe_builtins = {
            # 基本类型和函数
            'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
            'chr': chr, 'dict': dict, 'enumerate': enumerate, 'filter': filter,
            'float': float, 'format': format, 'frozenset': frozenset,
            'int': int, 'len': len, 'list': list, 'map': map,
            'max': max, 'min': min, 'oct': oct, 'ord': ord,
            'pow': pow, 'print': print, 'range': range, 'repr': repr,
            'reversed': reversed, 'round': round, 'set': set, 'slice': slice,
            'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
            'type': type, 'zip': zip,
            # 异常类
            'Exception': Exception, 'ValueError': ValueError,
            'TypeError': TypeError, 'IndexError': IndexError,
            'KeyError': KeyError, 'AttributeError': AttributeError,
        }
        
        # 安全模块
        safe_modules = {}
        try:
            import math
            import random
            import datetime
            import json
            import re
            
            safe_modules.update({
                'math': math,
                'random': random,
                'datetime': datetime,
                'json': json,
                're': re,
            })
        except ImportError as e:
            logger.warning(f"Failed to import some modules: {e}")
        
        return {
            '__builtins__': safe_builtins,
            **safe_modules
        }
    
    def _is_safe_code(self, code: str) -> Tuple[bool, str]:
        """检查代码安全性"""
        try:
            tree = ast.parse(code)
            
            # 危险操作检查
            dangerous_nodes = [
                ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Global, ast.Nonlocal
            ]
            
            dangerous_calls = {
                'exec', 'eval', 'compile', '__import__', 'open', 'file',
                'input', 'raw_input', 'vars', 'locals', 'globals'
            }
            
            for node in ast.walk(tree):
                # 检查危险节点
                if any(isinstance(node, dangerous_type) for dangerous_type in dangerous_nodes):
                    return False, f"不允许的操作: {type(node).__name__}"
                
                # 检查危险函数调用
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in dangerous_calls:
                        return False, f"不允许调用: {node.func.id}"
                
                # 检查导入
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return False, "不允许导入模块"
                
                # 检查私有属性访问
                if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
                    return False, f"不允许访问私有属性: {node.attr}"
            
            return True, ""
            
        except SyntaxError as e:
            return False, f"语法错误: {e}"
        except Exception as e:
            return False, f"代码检查失败: {e}"
    
    @log_io
    def run(self, code: str) -> str:
        """执行Python代码 - 兼容deer-flow接口"""
        result = self.execute_code(code)
        
        if result['success']:
            output = result.get('output', '')
            if result.get('result') is not None:
                # 如果有返回值，添加到输出中
                if output:
                    output += f"\n{result['result']}"
                else:
                    output = str(result['result'])
            return output
        else:
            # 返回错误信息
            error_msg = result.get('error', '未知错误')
            return f"Error: {error_msg}"
    
    @log_io
    def execute_code(self, code: str) -> Dict[str, Any]:
        """执行Python代码"""
        start_time = time.time()
        
        try:
            # 安全检查
            is_safe, error_msg = self._is_safe_code(code)
            if not is_safe:
                return {
                    "success": False,
                    "error": f"安全检查失败: {error_msg}",
                    "output": "",
                    "result": None,
                    "execution_time": 0
                }
            
            # 执行代码
            return self._execute_code_sync(code)
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Code execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "result": None,
                "execution_time": execution_time
            }
    
    def _execute_code_sync(self, code: str) -> Dict[str, Any]:
        """同步执行代码"""
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
            
            # 复制安全环境
            exec_globals = self.safe_globals.copy()
            
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
                output += f"Error: {stderr_output}"
            
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
                "execution_time": execution_time
            }
            
        finally:
            # 恢复输出
            sys.stdout = old_stdout
            sys.stderr = old_stderr


# 创建全局实例，类似deer-flow的设计
repl = SimplePythonREPL()


@log_io
def python_repl_tool(
    code: Annotated[str, "要执行的Python代码"]
) -> str:
    """Python REPL工具函数 - 兼容deer-flow接口
    
    Args:
        code: 要执行的Python代码
        
    Returns:
        执行结果字符串
    """
    if not isinstance(code, str):
        error_msg = f"Invalid input: code must be a string, got {type(code)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"
    
    logger.info("Executing Python code")
    try:
        result = repl.run(code)
        
        # 检查结果是否包含错误
        if isinstance(result, str) and result.startswith("Error:"):
            logger.error(result)
            return f"Error executing code:\n```python\n{code}\n```\n{result}"
        
        logger.info("Code execution successful")
        return f"Successfully executed:\n```python\n{code}\n```\nOutput: {result}"
        
    except Exception as e:
        error_msg = str(e)
        logger.error(error_msg)
        return f"Error executing code:\n```python\n{code}\n```\nError: {error_msg}"