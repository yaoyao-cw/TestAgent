#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestAgent Docker Compose 平台选择器
根据当前平台自动选择合适的docker-compose配置文件
"""

import os
import sys
import platform
import subprocess
import argparse
from pathlib import Path


class DockerComposePlatformSelector:
    """Docker Compose平台选择器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.platform_info = self._detect_platform()
        
    def _detect_platform(self):
        """检测平台信息"""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # 标准化架构名称
        arch_map = {
            'x86_64': 'amd64',
            'amd64': 'amd64',
            'aarch64': 'arm64',
            'arm64': 'arm64',
            'armv7l': 'arm',
            'armv6l': 'arm'
        }
        
        arch = arch_map.get(machine, machine)
        
        return {
            'os': system,
            'arch': arch,
            'platform': f"{system}/{arch}"
        }
    
    def get_compose_files(self, env='prod'):
        """获取适合当前平台的compose文件列表"""
        files = []
        
        # 基础compose文件
        if env == 'dev':
            base_file = self.project_root / 'docker-compose.dev.yml'
        else:
            base_file = self.project_root / 'docker-compose.yml'
        
        if base_file.exists():
            files.append(str(base_file))
        
        # 平台特定的compose文件
        platform_file = self.project_root / f'docker-compose.{self.platform_info["os"]}-{self.platform_info["arch"]}.yml'
        if platform_file.exists():
            files.append(str(platform_file))
        
        return files
    
    def get_docker_compose_command(self, env='prod'):
        """获取docker-compose命令"""
        # 检查docker-compose命令
        compose_cmd = None
        
        # 尝试docker-compose
        try:
            subprocess.run(['docker-compose', '--version'], 
                         capture_output=True, check=True)
            compose_cmd = ['docker-compose']
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # 尝试docker compose
        if not compose_cmd:
            try:
                subprocess.run(['docker', 'compose', 'version'], 
                             capture_output=True, check=True)
                compose_cmd = ['docker', 'compose']
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        
        if not compose_cmd:
            raise RuntimeError("Docker Compose未安装")
        
        # 添加compose文件参数
        files = self.get_compose_files(env)
        for file in files:
            compose_cmd.extend(['-f', file])
        
        return compose_cmd
    
    def run_command(self, args, env='prod'):
        """运行docker-compose命令"""
        try:
            cmd = self.get_docker_compose_command(env)
            cmd.extend(args)
            
            print(f"执行命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=self.project_root)
            return result.returncode
        except Exception as e:
            print(f"错误: {e}", file=sys.stderr)
            return 1
    
    def show_platform_info(self):
        """显示平台信息"""
        print("平台信息:")
        print(f"  操作系统: {self.platform_info['os']}")
        print(f"  架构: {self.platform_info['arch']}")
        print(f"  平台: {self.platform_info['platform']}")
        print()
        
        print("可用的Compose文件:")
        for env in ['prod', 'dev']:
            files = self.get_compose_files(env)
            print(f"  {env}环境:")
            for file in files:
                if Path(file).exists():
                    print(f"    ✅ {file}")
                else:
                    print(f"    ❌ {file} (不存在)")
        print()
    
    def create_platform_compose_file(self):
        """创建平台特定的compose文件（如果不存在）"""
        platform_file = self.project_root / f'docker-compose.{self.platform_info["os"]}-{self.platform_info["arch"]}.yml'
        
        if platform_file.exists():
            print(f"平台特定文件已存在: {platform_file}")
            return
        
        # 基于模板创建平台特定文件
        template_content = self._get_platform_compose_template()
        
        try:
            with open(platform_file, 'w', encoding='utf-8') as f:
                f.write(template_content)
            print(f"创建平台特定文件: {platform_file}")
        except Exception as e:
            print(f"创建文件失败: {e}", file=sys.stderr)
    
    def _get_platform_compose_template(self):
        """获取平台特定的compose模板"""
        platform = self.platform_info['platform']
        arch = self.platform_info['arch']
        
        # 根据架构调整资源限制
        if arch in ['arm64', 'arm']:
            memory_limits = {
                'testagent': '2G',
                'redis': '512M',
                'chroma': '1G',
                'nginx': '256M',
                'prometheus': '512M',
                'grafana': '512M'
            }
            redis_maxmemory = '512mb'
            prometheus_retention = '72h'
        else:
            memory_limits = {
                'testagent': '4G',
                'redis': '1G',
                'chroma': '2G',
                'nginx': '512M',
                'prometheus': '1G',
                'grafana': '1G'
            }
            redis_maxmemory = '1gb'
            prometheus_retention = '200h'
        
        template = f"""# TestAgent Docker Compose 配置 - {platform.upper()}
version: '3.8'

services:
  testagent:
    build:
      context: .
      dockerfile: Dockerfile
      platforms:
        - {platform}
      args:
        TARGETPLATFORM: {platform}
        TARGETOS: {self.platform_info['os']}
        TARGETARCH: {arch}
    image: testagent:{self.platform_info['os']}-{arch}
    platform: {platform}
    environment:
      - PLATFORM={platform}
    deploy:
      resources:
        limits:
          memory: {memory_limits['testagent']}
        reservations:
          memory: {int(memory_limits['testagent'][:-1])//2}G

  redis:
    image: redis:7-alpine
    platform: {platform}
    command: redis-server --appendonly yes --maxmemory {redis_maxmemory} --maxmemory-policy allkeys-lru
    deploy:
      resources:
        limits:
          memory: {memory_limits['redis']}
        reservations:
          memory: {int(memory_limits['redis'][:-1])//2}M

  chroma:
    image: chromadb/chroma:latest
    platform: {platform}
    deploy:
      resources:
        limits:
          memory: {memory_limits['chroma']}
        reservations:
          memory: {int(memory_limits['chroma'][:-1])//2}G

  nginx:
    image: nginx:alpine
    platform: {platform}
    deploy:
      resources:
        limits:
          memory: {memory_limits['nginx']}
        reservations:
          memory: {int(memory_limits['nginx'][:-1])//2}M

  prometheus:
    image: prom/prometheus:latest
    platform: {platform}
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time={prometheus_retention}'
      - '--web.enable-lifecycle'
      - '--storage.tsdb.wal-compression'
    deploy:
      resources:
        limits:
          memory: {memory_limits['prometheus']}
        reservations:
          memory: {int(memory_limits['prometheus'][:-1])//2}M

  grafana:
    image: grafana/grafana:latest
    platform: {platform}
    environment:
      - GF_ANALYTICS_REPORTING_ENABLED=false
      - GF_ANALYTICS_CHECK_FOR_UPDATES=false
    deploy:
      resources:
        limits:
          memory: {memory_limits['grafana']}
        reservations:
          memory: {int(memory_limits['grafana'][:-1])//2}M
"""
        return template


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='TestAgent Docker Compose 平台选择器')
    parser.add_argument('command', nargs='*', help='Docker Compose命令')
    parser.add_argument('--env', choices=['prod', 'dev'], default='prod', 
                       help='环境类型 (默认: prod)')
    parser.add_argument('--info', action='store_true', 
                       help='显示平台信息')
    parser.add_argument('--create-platform-file', action='store_true',
                       help='创建平台特定的compose文件')
    
    args = parser.parse_args()
    
    selector = DockerComposePlatformSelector()
    
    if args.info:
        selector.show_platform_info()
        return 0
    
    if args.create_platform_file:
        selector.create_platform_compose_file()
        return 0
    
    if not args.command:
        parser.print_help()
        return 1
    
    return selector.run_command(args.command, args.env)


if __name__ == '__main__':
    sys.exit(main())