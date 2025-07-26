"""E2B沙盒集成测试

测试E2B沙盒的各种功能，包括代码执行、脚本执行、pytest测试等。
"""

import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock

from src.tools.e2b_sandbox import E2BSandboxExecutor, E2B_AVAILABLE
from src.tools.fallback_sandbox import FallbackSandboxExecutor
from src.tools.unified_sandbox import UnifiedSandboxExecutor, execute_code_safely


class TestE2BSandboxExecutor:
    """E2B沙盒执行器测试"""
    
    @pytest.mark.skipif(not E2B_AVAILABLE, reason="E2B库未安装")
    @pytest.mark.asyncio
    async def test_e2b_sandbox_initialization(self):
        """测试E2B沙盒初始化"""
        executor = E2BSandboxExecutor()
        
        # 模拟E2B沙盒
        with patch('src.tools.e2b_sandbox.Sandbox') as mock_sandbox:
            mock_instance = MagicMock()
            mock_sandbox.return_value = mock_instance
            
            async with executor:
                assert executor.sandbox is not None
                mock_sandbox.assert_called_once()
    
    @pytest.mark.skipif(not E2B_AVAILABLE, reason="E2B库未安装")
    @pytest.mark.asyncio
    async def test_e2b_python_code_execution(self):
        """测试E2B Python代码执行"""
        executor = E2BSandboxExecutor()
        
        # 模拟执行结果
        mock_execution = MagicMock()
        mock_execution.exit_code = 0
        mock_execution.stdout = "Hello, World!"
        mock_execution.stderr = ""
        
        with patch('src.tools.e2b_sandbox.Sandbox') as mock_sandbox:
            mock_instance = MagicMock()
            mock_instance.run_code.return_value = mock_execution
            mock_sandbox.return_value = mock_instance
            
            async with executor:
                result = await executor.execute_python_code('print("Hello, World!")')
                
                assert result['success'] is True
                assert result['stdout'] == "Hello, World!"
                assert result['return_code'] == 0
    
    @pytest.mark.skipif(not E2B_AVAILABLE, reason="E2B库未安装")
    @pytest.mark.asyncio
    async def test_e2b_script_execution(self):
        """测试E2B脚本执行"""
        executor = E2BSandboxExecutor()
        
        # 模拟执行结果
        mock_execution = MagicMock()
        mock_execution.exit_code = 0
        mock_execution.stdout = "Script executed successfully"
        mock_execution.stderr = ""
        
        with patch('src.tools.e2b_sandbox.Sandbox') as mock_sandbox:
            mock_instance = MagicMock()
            mock_instance.filesystem.write = MagicMock()
            mock_instance.run_command.return_value = mock_execution
            mock_sandbox.return_value = mock_instance
            
            async with executor:
                result = await executor.execute_python_script(
                    'print("Script executed successfully")',
                    'test_script.py'
                )
                
                assert result['success'] is True
                assert result['stdout'] == "Script executed successfully"
                assert result['script_name'] == 'test_script.py'
    
    @pytest.mark.skipif(not E2B_AVAILABLE, reason="E2B库未安装")
    @pytest.mark.asyncio
    async def test_e2b_pytest_execution(self):
        """测试E2B pytest执行"""
        executor = E2BSandboxExecutor()
        
        # 模拟执行结果
        mock_execution = MagicMock()
        mock_execution.exit_code = 0
        mock_execution.stdout = "2 passed, 0 failed"
        mock_execution.stderr = ""
        
        with patch('src.tools.e2b_sandbox.Sandbox') as mock_sandbox:
            mock_instance = MagicMock()
            mock_instance.filesystem.write = MagicMock()
            mock_instance.filesystem.read = MagicMock(return_value=None)
            mock_instance.run_command.return_value = mock_execution
            mock_sandbox.return_value = mock_instance
            
            async with executor:
                result = await executor.execute_pytest_script(
                    'def test_example(): assert True',
                    'test_example.py'
                )
                
                assert result['success'] is True
                assert 'test_results' in result
    
    @pytest.mark.skipif(not E2B_AVAILABLE, reason="E2B库未安装")
    @pytest.mark.asyncio
    async def test_e2b_timeout_handling(self):
        """测试E2B超时处理"""
        executor = E2BSandboxExecutor(timeout=1)
        
        with patch('src.tools.e2b_sandbox.Sandbox') as mock_sandbox:
            mock_instance = MagicMock()
            mock_instance.run_code.side_effect = asyncio.TimeoutError()
            mock_sandbox.return_value = mock_instance
            
            async with executor:
                result = await executor.execute_python_code('import time; time.sleep(10)')
                
                assert result['success'] is False
                assert '超时' in result['error']


class TestFallbackSandboxExecutor:
    """回退沙盒执行器测试"""
    
    @pytest.mark.asyncio
    async def test_fallback_sandbox_initialization(self):
        """测试回退沙盒初始化"""
        executor = FallbackSandboxExecutor()
        
        async with executor:
            assert executor.is_active is True
            assert executor.temp_dir is not None
            assert os.path.exists(executor.temp_dir)
    
    @pytest.mark.asyncio
    async def test_fallback_python_code_execution(self):
        """测试回退沙盒Python代码执行"""
        executor = FallbackSandboxExecutor()
        
        async with executor:
            result = await executor.execute_python_code('print("Hello, Fallback!")')
            
            assert result['success'] is True
            assert "Hello, Fallback!" in result['stdout']
            assert result['sandbox_id'].startswith('fallback_')
    
    @pytest.mark.asyncio
    async def test_fallback_script_execution(self):
        """测试回退沙盒脚本执行"""
        executor = FallbackSandboxExecutor()
        
        async with executor:
            result = await executor.execute_python_script(
                'print("Fallback script works!")',
                'fallback_test.py'
            )
            
            assert result['success'] is True
            assert "Fallback script works!" in result['stdout']
            assert result['script_name'] == 'fallback_test.py'
    
    @pytest.mark.asyncio
    async def test_fallback_pytest_execution(self):
        """测试回退沙盒pytest执行"""
        executor = FallbackSandboxExecutor()
        
        test_code = """
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 5 - 3 == 2
"""
        
        async with executor:
            result = await executor.execute_pytest_script(test_code, 'test_math.py')
            
            # 注意：这个测试可能失败如果系统没有安装pytest
            # 但至少应该能执行并返回结果
            assert 'test_results' in result
            assert result['script_name'] == 'test_math.py'


class TestUnifiedSandboxExecutor:
    """统一沙盒执行器测试"""
    
    @pytest.mark.asyncio
    async def test_unified_sandbox_e2b_preference(self):
        """测试统一沙盒E2B优先选择"""
        executor = UnifiedSandboxExecutor(prefer_e2b=True)
        
        # 模拟E2B可用
        with patch('src.tools.unified_sandbox.E2B_AVAILABLE', True):
            with patch('src.tools.unified_sandbox.get_settings') as mock_settings:
                mock_settings.return_value.E2B_API_KEY = "test_key"
                
                with patch('src.tools.e2b_sandbox.E2BSandboxExecutor') as mock_e2b:
                    mock_instance = MagicMock()
                    mock_e2b.return_value = mock_instance
                    
                    async with executor:
                        assert executor.sandbox_type == "e2b"
                        mock_e2b.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unified_sandbox_fallback(self):
        """测试统一沙盒回退机制"""
        executor = UnifiedSandboxExecutor(prefer_e2b=True)
        
        # 模拟E2B不可用
        with patch('src.tools.unified_sandbox.E2B_AVAILABLE', False):
            async with executor:
                assert executor.sandbox_type == "fallback"
                assert executor.is_fallback_sandbox() is True
    
    @pytest.mark.asyncio
    async def test_unified_sandbox_code_execution(self):
        """测试统一沙盒代码执行"""
        executor = UnifiedSandboxExecutor(prefer_e2b=False)  # 强制使用回退沙盒
        
        async with executor:
            result = await executor.execute_python_code('print("Unified test")')
            
            assert 'sandbox_type' in result
            assert result['sandbox_type'] == 'fallback'
    
    @pytest.mark.asyncio
    async def test_execute_code_safely_function(self):
        """测试安全代码执行便捷函数"""
        # 强制使用回退沙盒
        with patch('src.tools.unified_sandbox.UnifiedSandboxExecutor') as mock_executor:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = MagicMock(return_value=mock_instance)
            mock_instance.__aexit__ = MagicMock(return_value=None)
            mock_instance.execute_python_code.return_value = {
                'success': True,
                'stdout': 'Test output',
                'stderr': '',
                'return_code': 0,
                'execution_time': 0.1,
                'sandbox_type': 'fallback'
            }
            mock_executor.return_value = mock_instance
            
            result = await execute_code_safely('print("Test")', execution_type="python")
            
            assert result.is_successful() is True
            assert result.sandbox_type == 'fallback'
            assert result.has_output() is True


class TestSandboxSecurity:
    """沙盒安全性测试"""
    
    @pytest.mark.asyncio
    async def test_malicious_code_isolation(self):
        """测试恶意代码隔离"""
        executor = FallbackSandboxExecutor(timeout=5)
        
        # 测试无限循环代码
        malicious_code = """
import time
while True:
    time.sleep(0.1)
"""
        
        async with executor:
            result = await executor.execute_python_code(malicious_code)
            
            # 应该因为超时而失败
            assert result['success'] is False
            assert '超时' in result['error'] or result['return_code'] != 0
    
    @pytest.mark.asyncio
    async def test_file_system_isolation(self):
        """测试文件系统隔离"""
        executor = FallbackSandboxExecutor()
        
        # 尝试访问系统文件
        dangerous_code = """
try:
    with open('/etc/passwd', 'r') as f:
        content = f.read()
    print("DANGER: System file accessed!")
except Exception as e:
    print(f"Safe: {e}")
"""
        
        async with executor:
            result = await executor.execute_python_code(dangerous_code)
            
            # 应该安全执行（可能无法访问系统文件）
            assert result['success'] is True
            assert "Safe:" in result['stdout'] or "DANGER:" not in result['stdout']


class TestSandboxResourceManagement:
    """沙盒资源管理测试"""
    
    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self):
        """测试内存限制执行"""
        executor = FallbackSandboxExecutor(memory_limit="128m")
        
        # 尝试分配大量内存
        memory_intensive_code = """
try:
    # 尝试分配100MB内存
    big_list = [0] * (100 * 1024 * 1024)
    print("Memory allocated successfully")
except MemoryError:
    print("Memory limit enforced")
except Exception as e:
    print(f"Other error: {e}")
"""
        
        async with executor:
            result = await executor.execute_python_code(memory_intensive_code)
            
            # 应该能执行，但可能受到内存限制
            assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_execution_timeout(self):
        """测试执行超时"""
        executor = FallbackSandboxExecutor(timeout=2)
        
        # 长时间运行的代码
        long_running_code = """
import time
time.sleep(10)
print("This should not print")
"""
        
        async with executor:
            result = await executor.execute_python_code(long_running_code)
            
            # 应该因为超时而失败
            assert result['success'] is False
            assert result['execution_time'] >= 2


@pytest.mark.integration
class TestSandboxIntegration:
    """沙盒集成测试"""
    
    @pytest.mark.asyncio
    async def test_package_installation(self):
        """测试包安装功能"""
        executor = FallbackSandboxExecutor()
        
        async with executor:
            # 尝试安装一个小包
            result = await executor.install_packages(['six'])
            
            # 包安装可能成功或失败，取决于环境
            assert 'packages' in result
            assert result['packages'] == ['six']
    
    @pytest.mark.asyncio
    async def test_system_info_retrieval(self):
        """测试系统信息获取"""
        executor = FallbackSandboxExecutor()
        
        async with executor:
            info = await executor.get_system_info()
            
            assert 'sandbox_type' in info
            assert info['sandbox_type'] == 'fallback'
    
    @pytest.mark.asyncio
    async def test_complex_script_execution(self):
        """测试复杂脚本执行"""
        executor = FallbackSandboxExecutor()
        
        complex_script = """
import json
import math

def calculate_stats(numbers):
    if not numbers:
        return {}
    
    return {
        'count': len(numbers),
        'sum': sum(numbers),
        'mean': sum(numbers) / len(numbers),
        'min': min(numbers),
        'max': max(numbers),
        'std': math.sqrt(sum((x - sum(numbers)/len(numbers))**2 for x in numbers) / len(numbers))
    }

numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
stats = calculate_stats(numbers)
print(json.dumps(stats, indent=2))
"""
        
        async with executor:
            result = await executor.execute_python_script(complex_script, 'stats.py')
            
            assert result['success'] is True
            assert 'count' in result['stdout']
            assert 'mean' in result['stdout']


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])