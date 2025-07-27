"""依赖管理和虚拟环境配置

实现跨平台的依赖管理和虚拟环境配置。
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .data_models import get_global_config, create_cross_platform_command


@dataclass
class DependencyInfo:
    """依赖信息"""

    name: str
    version: Optional[str] = None
    required: bool = True
    description: str = ""


class VirtualEnvironmentManager:
    """虚拟环境管理器"""

    def __init__(self, venv_path: Optional[str] = None):
        self.config = get_global_config()
        self.venv_path = Path(venv_path) if venv_path else Path.cwd() / "venv"

    def create_virtual_environment(self) -> bool:
        """创建虚拟环境"""
        try:
            if self.venv_path.exists():
                print(f"虚拟环境已存在: {self.venv_path}")
                return True

            # 创建虚拟环境
            cmd = [sys.executable, "-m", "venv", str(self.venv_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"虚拟环境创建成功: {self.venv_path}")
                return True
            else:
                print(f"虚拟环境创建失败: {result.stderr}")
                return False

        except Exception as e:
            print(f"创建虚拟环境时出错: {e}")
            return False

    def get_python_executable(self) -> str:
        """获取虚拟环境中的Python可执行文件路径"""
        if self.config.is_windows():
            return str(self.venv_path / "Scripts" / "python.exe")
        else:
            return str(self.venv_path / "bin" / "python")

    def get_pip_executable(self) -> str:
        """获取虚拟环境中的pip可执行文件路径"""
        if self.config.is_windows():
            return str(self.venv_path / "Scripts" / "pip.exe")
        else:
            return str(self.venv_path / "bin" / "pip")

    def is_virtual_environment_active(self) -> bool:
        """检查虚拟环境是否激活"""
        return hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        )

    def activate_virtual_environment(self) -> str:
        """获取激活虚拟环境的命令"""
        if self.config.is_windows():
            activate_script = self.venv_path / "Scripts" / "activate.bat"
            return str(activate_script)
        else:
            activate_script = self.venv_path / "bin" / "activate"
            return f"source {activate_script}"

    def install_requirements(self, requirements_file: str = "requirements.txt") -> bool:
        """安装依赖包"""
        try:
            requirements_path = Path(requirements_file)
            if not requirements_path.exists():
                print(f"依赖文件不存在: {requirements_file}")
                return False

            pip_executable = self.get_pip_executable()
            cmd = [pip_executable, "install", "-r", str(requirements_path)]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"依赖安装成功: {requirements_file}")
                return True
            else:
                print(f"依赖安装失败: {result.stderr}")
                return False

        except Exception as e:
            print(f"安装依赖时出错: {e}")
            return False


class DependencyChecker:
    """依赖检查器"""

    def __init__(self):
        self.config = get_global_config()
        self.required_dependencies = self._get_required_dependencies()

    def _get_required_dependencies(self) -> List[DependencyInfo]:
        """获取必需的依赖列表"""
        return [
            DependencyInfo("fastapi", ">=0.104.0", True, "Web框架"),
            DependencyInfo("uvicorn", ">=0.24.0", True, "ASGI服务器"),
            DependencyInfo("pydantic", ">=2.0.0", True, "数据验证"),
            DependencyInfo("langchain", ">=0.1.0", True, "AI框架"),
            DependencyInfo("langgraph", ">=0.0.40", True, "图工作流"),
            DependencyInfo("chromadb", ">=0.4.0", True, "向量数据库"),
            DependencyInfo("redis", ">=5.0.0", True, "缓存数据库"),
            DependencyInfo("litellm", ">=1.0.0", True, "LLM统一接口"),
            DependencyInfo("sentence-transformers", ">=2.2.0", True, "文本嵌入"),
            DependencyInfo("pytest", ">=7.0.0", False, "测试框架"),
            DependencyInfo("black", ">=23.0.0", False, "代码格式化"),
            DependencyInfo("flake8", ">=6.0.0", False, "代码检查"),
        ]

    def check_python_version(self) -> Tuple[bool, str]:
        """检查Python版本"""
        current_version = sys.version_info
        required_version = (3, 11)

        if current_version >= required_version:
            return (
                True,
                f"Python版本满足要求: {current_version.major}.{current_version.minor}.{current_version.micro}",
            )
        else:
            return (
                False,
                f"Python版本不满足要求，需要 >= {required_version[0]}.{required_version[1]}",
            )

    def check_dependency(self, dependency: DependencyInfo) -> Tuple[bool, str]:
        """检查单个依赖"""
        try:
            import importlib

            module = importlib.import_module(dependency.name)

            # 尝试获取版本信息
            version = getattr(module, "__version__", "unknown")
            return True, f"{dependency.name} {version} 已安装"

        except ImportError:
            return False, f"{dependency.name} 未安装"

    def check_all_dependencies(self) -> Dict[str, Tuple[bool, str]]:
        """检查所有依赖"""
        results = {}

        # 检查Python版本
        python_ok, python_msg = self.check_python_version()
        results["python"] = (python_ok, python_msg)

        # 检查各个依赖
        for dep in self.required_dependencies:
            dep_ok, dep_msg = self.check_dependency(dep)
            results[dep.name] = (dep_ok, dep_msg)

        return results

    def get_missing_dependencies(self) -> List[DependencyInfo]:
        """获取缺失的依赖"""
        missing = []

        for dep in self.required_dependencies:
            dep_ok, _ = self.check_dependency(dep)
            if not dep_ok and dep.required:
                missing.append(dep)

        return missing

    def generate_requirements_file(self, output_file: str = "requirements.txt"):
        """生成requirements.txt文件"""
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("# TestAgent项目依赖\n")
                f.write("# 自动生成，请勿手动修改\n\n")

                # 核心依赖
                f.write("# 核心依赖\n")
                for dep in self.required_dependencies:
                    if dep.required:
                        version_spec = dep.version if dep.version else ""
                        f.write(f"{dep.name}{version_spec}  # {dep.description}\n")

                f.write("\n# 开发依赖\n")
                for dep in self.required_dependencies:
                    if not dep.required:
                        version_spec = dep.version if dep.version else ""
                        f.write(f"{dep.name}{version_spec}  # {dep.description}\n")

            print(f"requirements.txt文件生成成功: {output_file}")

        except Exception as e:
            print(f"生成requirements.txt文件失败: {e}")


class ProjectInitializer:
    """项目初始化器"""

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.config = get_global_config()
        self.venv_manager = VirtualEnvironmentManager(self.project_root / "venv")
        self.dependency_checker = DependencyChecker()

    def initialize_project(self) -> bool:
        """初始化项目"""
        print("开始初始化TestAgent项目...")

        # 1. 检查Python版本
        python_ok, python_msg = self.dependency_checker.check_python_version()
        print(f"Python版本检查: {python_msg}")
        if not python_ok:
            return False

        # 2. 创建项目目录结构
        if not self._create_project_structure():
            return False

        # 3. 创建虚拟环境
        if not self.venv_manager.create_virtual_environment():
            return False

        # 4. 生成requirements.txt
        self.dependency_checker.generate_requirements_file(
            str(self.project_root / "requirements.txt")
        )

        # 5. 安装依赖
        if not self.venv_manager.install_requirements(
            str(self.project_root / "requirements.txt")
        ):
            print("警告: 依赖安装失败，请手动安装")

        # 6. 创建配置文件
        self._create_config_files()

        print("项目初始化完成!")
        print(f"激活虚拟环境: {self.venv_manager.activate_virtual_environment()}")

        return True

    def _create_project_structure(self) -> bool:
        """创建项目目录结构"""
        try:
            directories = [
                "src",
                "tests",
                "config",
                "data/tasks",
                "data/vectordb",
                "data/cache",
                "logs",
                "docs",
                "scripts",
                "frontend",
            ]

            for directory in directories:
                dir_path = self.project_root / directory
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"创建目录: {dir_path}")

            return True

        except Exception as e:
            print(f"创建项目结构失败: {e}")
            return False

    def _create_config_files(self):
        """创建配置文件"""
        try:
            # 创建.env.example文件
            env_example = self.project_root / ".env.example"
            with open(env_example, "w", encoding="utf-8") as f:
                f.write(
                    """# TestAgent环境配置示例
# 复制此文件为.env并填入实际值

# 运行环境
TESTAGENT_ENV=development
TESTAGENT_DEBUG=true
TESTAGENT_LOG_LEVEL=INFO

# LLM配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# 数据库配置
CHROMA_URL=http://localhost:8001
REDIS_URL=redis://localhost:6379

# 服务器配置
HOST=0.0.0.0
PORT=8000
"""
                )

            # 创建config.yaml示例
            config_yaml = self.project_root / "config" / "config.example.yaml"
            with open(config_yaml, "w", encoding="utf-8") as f:
                f.write(
                    """# TestAgent配置文件示例
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4

llm:
  provider: "openai"
  model: "gpt-3.5-turbo"
  max_tokens: 2048
  temperature: 0.7

database:
  vector_db_url: "http://localhost:8001"
  redis_url: "redis://localhost:6379"
  collection_name: "testagent_documents"

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
"""
                )

            print("配置文件创建成功")

        except Exception as e:
            print(f"创建配置文件失败: {e}")


# 便捷函数
def check_system_requirements() -> bool:
    """检查系统要求"""
    checker = DependencyChecker()
    results = checker.check_all_dependencies()

    print("系统要求检查结果:")
    print("-" * 50)

    all_ok = True
    for name, (ok, msg) in results.items():
        status = "✓" if ok else "✗"
        print(f"{status} {msg}")
        if not ok and name in ["python"] + [
            dep.name for dep in checker.required_dependencies if dep.required
        ]:
            all_ok = False

    return all_ok


def initialize_testagent_project(project_root: Optional[str] = None) -> bool:
    """初始化TestAgent项目"""
    initializer = ProjectInitializer(project_root)
    return initializer.initialize_project()


if __name__ == "__main__":
    # 命令行使用
    import argparse

    parser = argparse.ArgumentParser(description="TestAgent项目依赖管理")
    parser.add_argument("--check", action="store_true", help="检查系统要求")
    parser.add_argument("--init", action="store_true", help="初始化项目")
    parser.add_argument("--project-root", help="项目根目录")

    args = parser.parse_args()

    if args.check:
        check_system_requirements()
    elif args.init:
        initialize_testagent_project(args.project_root)
    else:
        parser.print_help()
