#!/usr/bin/env python3
"""
配置管理CLI工具

提供命令行界面来管理TestAgent配置
"""

import os
import sys
import argparse
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.config import (
        get_settings,
        get_config_manager,
        get_env_manager,
        validate_config,
        auto_fix_config,
        get_logger,
    )
except ImportError as e:
    print(f"无法导入配置模块: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)

logger = get_logger("config_cli")


def print_config(config_data: Dict[str, Any], indent: int = 0) -> None:
    """打印配置数据"""
    for key, value in config_data.items():
        if isinstance(value, dict):
            print("  " * indent + f"{key}:")
            print_config(value, indent + 1)
        else:
            print("  " * indent + f"{key}: {value}")


def show_current_config():
    """显示当前配置"""
    try:
        settings = get_settings()
        if hasattr(settings, "model_dump"):
            config_dict = settings.model_dump()
        elif hasattr(settings, "dict"):
            config_dict = settings.dict()
        else:
            config_dict = {}

        print("当前配置:")
        print("=" * 50)
        print_config(config_dict)

    except Exception as e:
        print(f"获取配置失败: {e}")


def validate_current_config():
    """验证当前配置"""
    try:
        settings = get_settings()
        validation_results = validate_config(settings)

        if not validation_results:
            print("✅ 配置验证通过，没有发现问题")
            return

        errors = [r for r in validation_results if r.severity == "error"]
        warnings = [r for r in validation_results if r.severity == "warning"]

        if errors:
            print(f"❌ 发现 {len(errors)} 个错误:")
            for error in errors:
                print(f"  - {error}")

        if warnings:
            print(f"⚠️  发现 {len(warnings)} 个警告:")
            for warning in warnings:
                print(f"  - {warning}")

        if errors:
            print("\n建议运行 'auto-fix' 命令尝试自动修复问题")

    except Exception as e:
        print(f"配置验证失败: {e}")


def auto_fix_current_config():
    """自动修复配置问题"""
    try:
        settings = get_settings()
        fixed_issues, remaining_errors = auto_fix_config(settings)

        if fixed_issues:
            print(f"✅ 自动修复了 {len(fixed_issues)} 个问题:")
            for issue in fixed_issues:
                print(f"  - {issue}")

        if remaining_errors:
            errors = [r for r in remaining_errors if r.severity == "error"]
            warnings = [r for r in remaining_errors if r.severity == "warning"]

            if errors:
                print(f"\n❌ 仍有 {len(errors)} 个错误需要手动处理:")
                for error in errors:
                    print(f"  - {error}")

            if warnings:
                print(f"\n⚠️  仍有 {len(warnings)} 个警告:")
                for warning in warnings:
                    print(f"  - {warning}")

        if not fixed_issues and not remaining_errors:
            print("✅ 没有发现需要修复的问题")

    except Exception as e:
        print(f"自动修复失败: {e}")


def get_config_value(key: str):
    """获取配置值"""
    try:
        config_manager = get_config_manager()
        value = config_manager.get_value(key)

        if value is not None:
            print(f"{key}: {value}")
        else:
            print(f"配置键 '{key}' 不存在")

    except Exception as e:
        print(f"获取配置值失败: {e}")


def set_config_value(key: str, value: str, persist: bool = False):
    """设置配置值"""
    try:
        config_manager = get_config_manager()

        # 尝试解析值的类型
        parsed_value = value
        if value.lower() in ("true", "false"):
            parsed_value = value.lower() == "true"
        elif value.isdigit():
            parsed_value = int(value)
        elif "." in value and value.replace(".", "").isdigit():
            parsed_value = float(value)

        success = config_manager.set_value(key, parsed_value, persist=persist)

        if success:
            print(f"✅ 配置已更新: {key} = {parsed_value}")
            if persist:
                print("配置已保存到文件")
        else:
            print(f"❌ 无法更新配置键: {key}")

    except Exception as e:
        print(f"设置配置值失败: {e}")


def export_config(format_type: str = "yaml", output_file: str = None):
    """导出配置"""
    try:
        config_manager = get_config_manager()
        config_data = config_manager.export_config(format=format_type)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(config_data)
            print(f"✅ 配置已导出到: {output_file}")
        else:
            print("导出的配置:")
            print("=" * 50)
            print(config_data)

    except Exception as e:
        print(f"导出配置失败: {e}")


def import_config(config_file: str, format_type: str = "yaml", persist: bool = False):
    """导入配置"""
    try:
        if not os.path.exists(config_file):
            print(f"❌ 配置文件不存在: {config_file}")
            return

        with open(config_file, "r", encoding="utf-8") as f:
            config_data = f.read()

        config_manager = get_config_manager()
        success = config_manager.import_config(
            config_data, format=format_type, persist=persist
        )

        if success:
            print(f"✅ 配置已从 {config_file} 导入")
            if persist:
                print("配置已保存到文件")
        else:
            print(f"❌ 配置导入失败")

    except Exception as e:
        print(f"导入配置失败: {e}")


def list_env_vars(prefix: str = None):
    """列出环境变量"""
    try:
        env_manager = get_env_manager()
        env_vars = env_manager.list_vars(prefix=prefix)

        if not env_vars:
            print("没有找到环境变量")
            return

        print(f"环境变量 ({len(env_vars)} 个):")
        print("=" * 50)

        # 屏蔽敏感信息
        sensitive_keys = ["api_key", "password", "secret", "token"]
        for key, value in sorted(env_vars.items()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                print(f"{key}: ***")
            else:
                print(f"{key}: {value}")

    except Exception as e:
        print(f"列出环境变量失败: {e}")


def set_env_var(key: str, value: str, persist: bool = False):
    """设置环境变量"""
    try:
        env_manager = get_env_manager()
        env_manager.set(key, value, persist=persist)

        print(f"✅ 环境变量已设置: {key}")
        if persist:
            print("环境变量已保存到文件")

    except Exception as e:
        print(f"设置环境变量失败: {e}")


def delete_env_var(key: str, persist: bool = False):
    """删除环境变量"""
    try:
        env_manager = get_env_manager()
        success = env_manager.delete(key, persist=persist)

        if success:
            print(f"✅ 环境变量已删除: {key}")
            if persist:
                print("更改已保存到文件")
        else:
            print(f"❌ 环境变量不存在: {key}")

    except Exception as e:
        print(f"删除环境变量失败: {e}")


def backup_env_vars(backup_file: str = None):
    """备份环境变量"""
    try:
        env_manager = get_env_manager()

        if not backup_file:
            from datetime import datetime

            backup_file = f"env_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.env"

        success = env_manager.backup_to_file(backup_file)

        if success:
            print(f"✅ 环境变量已备份到: {backup_file}")
        else:
            print("❌ 环境变量备份失败")

    except Exception as e:
        print(f"备份环境变量失败: {e}")


def restore_env_vars(backup_file: str):
    """恢复环境变量"""
    try:
        if not os.path.exists(backup_file):
            print(f"❌ 备份文件不存在: {backup_file}")
            return

        env_manager = get_env_manager()
        success = env_manager.restore_from_file(backup_file)

        if success:
            print(f"✅ 环境变量已从 {backup_file} 恢复")
        else:
            print("❌ 环境变量恢复失败")

    except Exception as e:
        print(f"恢复环境变量失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="TestAgent配置管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 显示配置
    subparsers.add_parser("show", help="显示当前配置")

    # 验证配置
    subparsers.add_parser("validate", help="验证当前配置")

    # 自动修复配置
    subparsers.add_parser("auto-fix", help="自动修复配置问题")

    # 获取配置值
    get_parser = subparsers.add_parser("get", help="获取配置值")
    get_parser.add_argument("key", help="配置键")

    # 设置配置值
    set_parser = subparsers.add_parser("set", help="设置配置值")
    set_parser.add_argument("key", help="配置键")
    set_parser.add_argument("value", help="配置值")
    set_parser.add_argument("--persist", action="store_true", help="保存到文件")

    # 导出配置
    export_parser = subparsers.add_parser("export", help="导出配置")
    export_parser.add_argument(
        "--format", choices=["yaml", "json"], default="yaml", help="导出格式"
    )
    export_parser.add_argument("--output", help="输出文件")

    # 导入配置
    import_parser = subparsers.add_parser("import", help="导入配置")
    import_parser.add_argument("file", help="配置文件")
    import_parser.add_argument(
        "--format", choices=["yaml", "json"], default="yaml", help="配置格式"
    )
    import_parser.add_argument("--persist", action="store_true", help="保存到文件")

    # 环境变量管理
    env_parser = subparsers.add_parser("env", help="环境变量管理")
    env_subparsers = env_parser.add_subparsers(dest="env_command", help="环境变量命令")

    # 列出环境变量
    list_env_parser = env_subparsers.add_parser("list", help="列出环境变量")
    list_env_parser.add_argument("--prefix", help="前缀过滤")

    # 设置环境变量
    set_env_parser = env_subparsers.add_parser("set", help="设置环境变量")
    set_env_parser.add_argument("key", help="环境变量名")
    set_env_parser.add_argument("value", help="环境变量值")
    set_env_parser.add_argument("--persist", action="store_true", help="保存到文件")

    # 删除环境变量
    del_env_parser = env_subparsers.add_parser("delete", help="删除环境变量")
    del_env_parser.add_argument("key", help="环境变量名")
    del_env_parser.add_argument("--persist", action="store_true", help="保存到文件")

    # 备份环境变量
    backup_env_parser = env_subparsers.add_parser("backup", help="备份环境变量")
    backup_env_parser.add_argument("--file", help="备份文件")

    # 恢复环境变量
    restore_env_parser = env_subparsers.add_parser("restore", help="恢复环境变量")
    restore_env_parser.add_argument("file", help="备份文件")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行命令
    try:
        if args.command == "show":
            show_current_config()
        elif args.command == "validate":
            validate_current_config()
        elif args.command == "auto-fix":
            auto_fix_current_config()
        elif args.command == "get":
            get_config_value(args.key)
        elif args.command == "set":
            set_config_value(args.key, args.value, args.persist)
        elif args.command == "export":
            export_config(args.format, args.output)
        elif args.command == "import":
            import_config(args.file, args.format, args.persist)
        elif args.command == "env":
            if args.env_command == "list":
                list_env_vars(args.prefix)
            elif args.env_command == "set":
                set_env_var(args.key, args.value, args.persist)
            elif args.env_command == "delete":
                delete_env_var(args.key, args.persist)
            elif args.env_command == "backup":
                backup_env_vars(args.file)
            elif args.env_command == "restore":
                restore_env_vars(args.file)
            else:
                env_parser.print_help()

    except KeyboardInterrupt:
        print("\n操作已取消")
    except Exception as e:
        print(f"执行命令时发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
