#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestAgent 平台检测工具
自动检测操作系统、架构和环境配置
"""

import os
import sys
import platform
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class PlatformDetector:
    """平台检测器"""
    
    def __init__(self):
        self.info = self._detect_platform()
    
    def _detect_platform(self) -> Dict:
        """检测平台信息"""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # 标准化操作系统名称
        os_map = {
            'windows': 'windows',
            'linux': 'linux',
            'darwin': 'macos',
            'freebsd': 'freebsd',
            'openbsd': 'openbsd'
        }
        
        # 标准化架构名称
        arch_map = {
            'x86_64': 'amd64',
            'amd64': 'amd64',
            'i386': 'i386',
            'i686': 'i386',
            'arm64': 'arm64',
            'aarch64': 'arm64',
            'armv7l': 'arm',
            'armv6l': 'arm'
        }
        
        os_name = os_map.get(system, system)
        arch_name = arch_map.get(machine, machine)
        
        return {
            'os': os_name,
            'arch': arch_name,
            'system': system,
            'machine': machine,
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'python_implementation': platform.python_implementation(),
        }
    
    def detect_shell(self) -> str:
        """检测当前Shell"""
        if self.is_windows():
            # Windows环境检测
            if os.environ.get('PSModulePath'):
                return 'powershell'
            else:
                return 'cmd'
        else:
            # Unix-like环境检测
            shell = os.environ.get('SHELL', '/bin/bash')
            return os.path.basename(shell)
    
    def detect_package_managers(self) -> Dict[str, bool]:
        """检测可用的包管理器"""
        managers = {}
        
        if self.is_windows():
            # Windows包管理器
            managers.update({
                'choco': self._command_exists('choco'),
                'scoop': self._command_exists('scoop'),
                'winget': self._command_exists('winget'),
            })
        elif self.is_linux():
            # Linux包管理器
            managers.update({
                'apt': self._command_exists('apt-get'),
                'yum': self._command_exists('yum'),
                'dnf': self._command_exists('dnf'),
                'pacman': self._command_exists('pacman'),
                'zypper': self._command_exists('zypper'),
                'apk': self._command_exists('apk'),
                'snap': self._command_exists('snap'),
                'flatpak': self._command_exists('flatpak'),
            })
        elif self.is_macos():
            # macOS包管理器
            managers.update({
                'brew': self._command_exists('brew'),
                'port': self._command_exists('port'),
            })
        
        return managers
    
    def detect_python_info(self) -> Dict:
        """检测Python环境信息"""
        info = {
            'version': sys.version,
            'version_info': sys.version_info,
            'executable': sys.executable,
            'prefix': sys.prefix,
            'path': sys.path[:3],  # 只显示前3个路径
        }
        
        # 检测虚拟环境
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            info['virtual_env'] = True
            info['virtual_env_path'] = sys.prefix
        else:
            info['virtual_env'] = False
        
        # 检测pip
        try:
            import pip
            info['pip_version'] = pip.__version__
        except ImportError:
            info['pip_version'] = None
        
        return info
    
    def detect_node_info(self) -> Optional[Dict]:
        """检测Node.js环境信息"""
        if not self._command_exists('node'):
            return None
        
        try:
            node_version = subprocess.check_output(['node', '--version'], text=True).strip()
            npm_version = subprocess.check_output(['npm', '--version'], text=True).strip()
            
            # 检测Node.js安装路径
            node_path = subprocess.check_output(['which', 'node'] if not self.is_windows() else ['where', 'node'], 
                                              text=True).strip().split('\n')[0]
            
            return {
                'node_version': node_version,
                'npm_version': npm_version,
                'node_path': node_path,
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def detect_docker_info(self) -> Optional[Dict]:
        """检测Docker环境信息"""
        if not self._command_exists('docker'):
            return None
        
        try:
            docker_version = subprocess.check_output(['docker', '--version'], text=True).strip()
            
            # 检测Docker Compose
            compose_version = None
            if self._command_exists('docker-compose'):
                compose_version = subprocess.check_output(['docker-compose', '--version'], text=True).strip()
            elif self._command_exists('docker'):
                try:
                    compose_version = subprocess.check_output(['docker', 'compose', 'version'], text=True).strip()
                except subprocess.CalledProcessError:
                    pass
            
            return {
                'docker_version': docker_version,
                'compose_version': compose_version,
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def detect_git_info(self) -> Optional[Dict]:
        """检测Git环境信息"""
        if not self._command_exists('git'):
            return None
        
        try:
            git_version = subprocess.check_output(['git', '--version'], text=True).strip()
            
            # 检测Git配置
            try:
                git_user = subprocess.check_output(['git', 'config', 'user.name'], text=True).strip()
                git_email = subprocess.check_output(['git', 'config', 'user.email'], text=True).strip()
            except subprocess.CalledProcessError:
                git_user = None
                git_email = None
            
            return {
                'git_version': git_version,
                'user_name': git_user,
                'user_email': git_email,
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def get_recommended_scripts(self) -> List[str]:
        """获取推荐的安装脚本"""
        scripts = []
        
        if self.is_windows():
            scripts.extend([
                'scripts/install.bat',
                'scripts/install.ps1',
                'scripts/start.bat',
                'scripts/start.ps1'
            ])
        else:
            scripts.extend([
                'scripts/install.sh',
                'scripts/start.sh',
                'Makefile'
            ])
        
        return scripts
    
    def get_installation_commands(self) -> Dict[str, List[str]]:
        """获取安装命令建议"""
        commands = {}
        
        if self.is_windows():
            commands['powershell'] = [
                'Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser',
                '.\\scripts\\install.ps1',
                '.\\scripts\\start.ps1 dev'
            ]
            commands['cmd'] = [
                'scripts\\install.bat',
                'scripts\\start.bat dev'
            ]
        elif self.is_linux():
            commands['bash'] = [
                'chmod +x scripts/install.sh',
                './scripts/install.sh',
                './scripts/start.sh dev'
            ]
            commands['make'] = [
                'make install',
                'make dev'
            ]
        elif self.is_macos():
            commands['bash'] = [
                'chmod +x scripts/install.sh',
                './scripts/install.sh',
                './scripts/start.sh dev'
            ]
            commands['make'] = [
                'make install',
                'make dev'
            ]
        
        return commands
    
    def _command_exists(self, command: str) -> bool:
        """检查命令是否存在"""
        try:
            if self.is_windows():
                subprocess.check_output(['where', command], stderr=subprocess.DEVNULL)
            else:
                subprocess.check_output(['which', command], stderr=subprocess.DEVNULL)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def is_windows(self) -> bool:
        """是否为Windows系统"""
        return self.info['os'] == 'windows'
    
    def is_linux(self) -> bool:
        """是否为Linux系统"""
        return self.info['os'] == 'linux'
    
    def is_macos(self) -> bool:
        """是否为macOS系统"""
        return self.info['os'] == 'macos'
    
    def is_unix_like(self) -> bool:
        """是否为Unix-like系统"""
        return self.info['os'] in ['linux', 'macos', 'freebsd', 'openbsd']
    
    def get_full_report(self) -> Dict:
        """获取完整的平台报告"""
        return {
            'platform': self.info,
            'shell': self.detect_shell(),
            'package_managers': self.detect_package_managers(),
            'python': self.detect_python_info(),
            'node': self.detect_node_info(),
            'docker': self.detect_docker_info(),
            'git': self.detect_git_info(),
            'recommended_scripts': self.get_recommended_scripts(),
            'installation_commands': self.get_installation_commands(),
        }
    
    def print_report(self):
        """打印平台报告"""
        report = self.get_full_report()
        
        print("=" * 60)
        print("TestAgent 平台检测报告")
        print("=" * 60)
        
        # 基本平台信息
        print(f"\n🖥️  平台信息:")
        print(f"   操作系统: {report['platform']['os']} ({report['platform']['system']})")
        print(f"   架构: {report['platform']['arch']} ({report['platform']['machine']})")
        print(f"   Shell: {report['shell']}")
        print(f"   平台: {report['platform']['platform']}")
        
        # Python信息
        print(f"\n🐍 Python环境:")
        python_info = report['python']
        print(f"   版本: {python_info['version_info'].major}.{python_info['version_info'].minor}.{python_info['version_info'].micro}")
        print(f"   实现: {self.info['python_implementation']}")
        print(f"   可执行文件: {python_info['executable']}")
        print(f"   虚拟环境: {'是' if python_info['virtual_env'] else '否'}")
        if python_info['pip_version']:
            print(f"   pip版本: {python_info['pip_version']}")
        
        # Node.js信息
        if report['node']:
            print(f"\n🟢 Node.js环境:")
            node_info = report['node']
            print(f"   Node.js版本: {node_info['node_version']}")
            print(f"   npm版本: {node_info['npm_version']}")
            print(f"   安装路径: {node_info['node_path']}")
        else:
            print(f"\n❌ Node.js: 未安装")
        
        # Docker信息
        if report['docker']:
            print(f"\n🐳 Docker环境:")
            docker_info = report['docker']
            print(f"   Docker版本: {docker_info['docker_version']}")
            if docker_info['compose_version']:
                print(f"   Compose版本: {docker_info['compose_version']}")
        else:
            print(f"\n❌ Docker: 未安装")
        
        # Git信息
        if report['git']:
            print(f"\n📦 Git环境:")
            git_info = report['git']
            print(f"   Git版本: {git_info['git_version']}")
            if git_info['user_name']:
                print(f"   用户: {git_info['user_name']} <{git_info['user_email']}>")
        else:
            print(f"\n❌ Git: 未安装")
        
        # 包管理器
        available_managers = [k for k, v in report['package_managers'].items() if v]
        if available_managers:
            print(f"\n📦 可用包管理器: {', '.join(available_managers)}")
        
        # 推荐脚本
        print(f"\n🚀 推荐使用的脚本:")
        for script in report['recommended_scripts']:
            if Path(script).exists():
                print(f"   ✅ {script}")
            else:
                print(f"   ❌ {script} (不存在)")
        
        # 安装命令
        print(f"\n💻 安装命令:")
        for shell, commands in report['installation_commands'].items():
            print(f"   {shell.upper()}:")
            for cmd in commands:
                print(f"     {cmd}")
        
        print("\n" + "=" * 60)


def main():
    """主函数"""
    detector = PlatformDetector()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == '--json':
            # 输出JSON格式
            print(json.dumps(detector.get_full_report(), indent=2, ensure_ascii=False))
            return
        elif sys.argv[1] == '--os':
            # 只输出操作系统
            print(detector.info['os'])
            return
        elif sys.argv[1] == '--arch':
            # 只输出架构
            print(detector.info['arch'])
            return
        elif sys.argv[1] == '--shell':
            # 只输出Shell
            print(detector.detect_shell())
            return
        elif sys.argv[1] == '--help':
            print("用法: python platform_detect.py [选项]")
            print("选项:")
            print("  --json    输出JSON格式的完整报告")
            print("  --os      只输出操作系统名称")
            print("  --arch    只输出架构名称")
            print("  --shell   只输出Shell名称")
            print("  --help    显示帮助信息")
            return
    
    # 默认输出完整报告
    detector.print_report()


if __name__ == "__main__":
    main()