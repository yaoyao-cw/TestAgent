#!/usr/bin/env python3
"""
TestAgent集成测试运行脚本
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_command(command, cwd=None, timeout=300):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"命令超时 ({timeout}秒)"
    except Exception as e:
        return False, "", str(e)

def check_dependencies():
    """检查依赖是否安装"""
    print("🔍 检查依赖...")
    
    required_packages = [
        "pytest",
        "pytest-asyncio",
        "fastapi",
        "uvicorn",
        "langchain",
        "langgraph"
    ]
    
    missing_packages = []
    for package in required_packages:
        success, _, _ = run_command(f"python -c 'import {package.replace('-', '_')}'")
        if not success:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -e .")
        return False
    
    print("✅ 所有依赖已安装")
    return True

def setup_test_environment():
    """设置测试环境"""
    print("🔧 设置测试环境...")
    
    # 创建必要的目录
    directories = [
        "data/vectordb",
        "logs",
        "config"
    ]
    
    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # 设置测试环境变量
    test_env = {
        "TESTING": "true",
        "LOG_LEVEL": "DEBUG",
        "VECTOR_DB_PATH": str(project_root / "data" / "test_vectordb"),
        "LLM_PROVIDER": "mock",  # 使用模拟LLM提供商
        "DEFAULT_MODEL": "mock-model"
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
    
    print("✅ 测试环境设置完成")
    return True

def run_unit_tests():
    """运行单元测试"""
    print("🧪 运行单元测试...")
    
    success, stdout, stderr = run_command(
        "python -m pytest tests/ -v --tb=short -x",
        cwd=project_root
    )
    
    if success:
        print("✅ 单元测试通过")
        return True
    else:
        print("❌ 单元测试失败")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        return False

def run_integration_tests():
    """运行集成测试"""
    print("🔗 运行集成测试...")
    
    success, stdout, stderr = run_command(
        "python -m pytest tests/test_integration.py -v --tb=short",
        cwd=project_root
    )
    
    if success:
        print("✅ 集成测试通过")
        return True
    else:
        print("❌ 集成测试失败")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        return False

def start_test_server():
    """启动测试服务器"""
    print("🚀 启动测试服务器...")
    
    # 启动API服务器（后台运行）
    server_process = subprocess.Popen([
        "python", "-m", "uvicorn", 
        "src.server.main:app",
        "--host", "localhost",
        "--port", "8001",  # 使用不同端口避免冲突
        "--log-level", "warning"
    ], cwd=project_root)
    
    # 等待服务器启动
    time.sleep(5)
    
    # 检查服务器是否启动成功
    success, _, _ = run_command("curl -f http://localhost:8001/health")
    
    if success:
        print("✅ 测试服务器启动成功")
        return server_process
    else:
        print("❌ 测试服务器启动失败")
        server_process.terminate()
        return None

def run_api_tests(server_process):
    """运行API测试"""
    print("🌐 运行API测试...")
    
    try:
        # 设置API测试环境变量
        os.environ["TEST_API_BASE_URL"] = "http://localhost:8001"
        
        success, stdout, stderr = run_command(
            "python -m pytest tests/test_integration.py::TestEndToEndFlow::test_api_endpoints -v",
            cwd=project_root
        )
        
        if success:
            print("✅ API测试通过")
            return True
        else:
            print("❌ API测试失败")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            return False
    
    finally:
        # 停止测试服务器
        if server_process:
            server_process.terminate()
            server_process.wait()
            print("🛑 测试服务器已停止")

def run_performance_tests():
    """运行性能测试"""
    print("⚡ 运行性能测试...")
    
    # 简单的性能测试
    performance_script = """
import time
import asyncio
from src.llm.service import get_llm_service
from unittest.mock import Mock, AsyncMock, patch

async def test_llm_performance():
    with patch('src.llm.service.get_provider') as mock_provider:
        mock_provider.return_value.generate = AsyncMock(return_value="测试响应")
        
        llm_service = get_llm_service()
        
        # 测试并发请求
        start_time = time.time()
        tasks = []
        for i in range(10):
            task = llm_service.generate_response(f"测试请求 {i}")
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"10个并发请求耗时: {duration:.2f}秒")
        
        if duration < 5.0:  # 期望在5秒内完成
            print("✅ 性能测试通过")
            return True
        else:
            print("❌ 性能测试失败 - 响应时间过长")
            return False

if __name__ == "__main__":
    result = asyncio.run(test_llm_performance())
    exit(0 if result else 1)
"""
    
    # 写入临时性能测试文件
    perf_test_file = project_root / "temp_perf_test.py"
    with open(perf_test_file, 'w', encoding='utf-8') as f:
        f.write(performance_script)
    
    try:
        success, stdout, stderr = run_command(
            f"python {perf_test_file}",
            cwd=project_root
        )
        
        if success:
            print("✅ 性能测试通过")
            return True
        else:
            print("❌ 性能测试失败")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            return False
    
    finally:
        # 清理临时文件
        if perf_test_file.exists():
            perf_test_file.unlink()

def generate_test_report(results):
    """生成测试报告"""
    print("\n" + "="*50)
    print("📊 测试报告")
    print("="*50)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print("-"*50)
    print(f"总计: {total_tests} 个测试")
    print(f"通过: {passed_tests} 个")
    print(f"失败: {failed_tests} 个")
    print(f"成功率: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests == 0:
        print("\n🎉 所有测试都通过了！")
        return True
    else:
        print(f"\n⚠️  有 {failed_tests} 个测试失败")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="TestAgent集成测试运行器")
    parser.add_argument("--skip-unit", action="store_true", help="跳过单元测试")
    parser.add_argument("--skip-integration", action="store_true", help="跳过集成测试")
    parser.add_argument("--skip-api", action="store_true", help="跳过API测试")
    parser.add_argument("--skip-performance", action="store_true", help="跳过性能测试")
    parser.add_argument("--quick", action="store_true", help="快速测试（跳过性能测试）")
    
    args = parser.parse_args()
    
    print("🚀 TestAgent集成测试开始")
    print("="*50)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 设置测试环境
    if not setup_test_environment():
        sys.exit(1)
    
    # 运行测试
    results = {}
    
    if not args.skip_unit:
        results["单元测试"] = run_unit_tests()
    
    if not args.skip_integration:
        results["集成测试"] = run_integration_tests()
    
    if not args.skip_api:
        server_process = start_test_server()
        if server_process:
            results["API测试"] = run_api_tests(server_process)
        else:
            results["API测试"] = False
    
    if not args.skip_performance and not args.quick:
        results["性能测试"] = run_performance_tests()
    
    # 生成报告
    success = generate_test_report(results)
    
    # 清理
    print("\n🧹 清理测试环境...")
    test_vectordb = project_root / "data" / "test_vectordb"
    if test_vectordb.exists():
        import shutil
        shutil.rmtree(test_vectordb)
    
    print("✅ 清理完成")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()