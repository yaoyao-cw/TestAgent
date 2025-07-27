#!/usr/bin/env python3
"""
智能体行为测试运行器

集成运行所有智能体行为测试，包括ReAct循环测试、质量验证和回归检测。
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class BehaviorTestRunner:
    """行为测试运行器"""

    def __init__(self, output_dir: str = "test_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.test_suites = {
            "basic_behavior": "tests/test_agent_behavior_testing.py",
            "react_quality": "tests/test_react_loop_quality.py",
            "regression": "tests/test_agent_behavior_regression.py",
        }

    def run_all_tests(self, verbose: bool = True) -> Dict[str, any]:
        """运行所有行为测试"""
        print("🚀 开始运行智能体行为测试套件...")

        overall_results = {
            "start_time": time.time(),
            "test_results": {},
            "summary": {},
        }

        for suite_name, test_file in self.test_suites.items():
            print(f"\n📋 运行测试套件: {suite_name}")
            print(f"   文件: {test_file}")

            result = self._run_test_suite(test_file, suite_name, verbose)
            overall_results["test_results"][suite_name] = result

        overall_results["end_time"] = time.time()
        overall_results["total_duration"] = (
            overall_results["end_time"] - overall_results["start_time"]
        )

        # 生成汇总
        overall_results["summary"] = self._generate_summary(
            overall_results["test_results"]
        )

        # 保存结果
        self._save_results(overall_results)

        # 打印汇总
        self._print_summary(overall_results["summary"])

        return overall_results

    def run_specific_test(self, test_name: str, verbose: bool = True) -> Dict[str, any]:
        """运行特定测试套件"""
        if test_name not in self.test_suites:
            print(f"❌ 未找到测试套件: {test_name}")
            print(f"可用的测试套件: {list(self.test_suites.keys())}")
            return {}

        test_file = self.test_suites[test_name]
        print(f"🚀 运行测试套件: {test_name}")
        print(f"   文件: {test_file}")

        result = self._run_test_suite(test_file, test_name, verbose)

        # 保存单个测试结果
        result_file = self.output_dir / f"{test_name}_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result

    def _run_test_suite(
        self, test_file: str, suite_name: str, verbose: bool
    ) -> Dict[str, any]:
        """运行单个测试套件"""
        start_time = time.time()

        # 构建pytest参数
        pytest_args = [test_file]
        if verbose:
            pytest_args.append("-v")
        pytest_args.extend(["-s", "--tb=short"])

        # 添加输出文件
        result_file = self.output_dir / f"{suite_name}_pytest.xml"
        pytest_args.extend(["--junitxml", str(result_file)])

        # 运行pytest
        try:
            exit_code = pytest.main(pytest_args)
            success = exit_code == 0
        except Exception as e:
            print(f"❌ 测试套件 {suite_name} 运行出错: {e}")
            success = False
            exit_code = -1

        end_time = time.time()
        duration = end_time - start_time

        result = {
            "suite_name": suite_name,
            "test_file": test_file,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "success": success,
            "exit_code": exit_code,
        }

        # 解析pytest结果（如果有的话）
        if result_file.exists():
            result["junit_file"] = str(result_file)

        status_icon = "✅" if success else "❌"
        print(f"{status_icon} 测试套件 {suite_name} 完成 (耗时: {duration:.2f}s)")

        return result

    def _generate_summary(self, test_results: Dict[str, Dict]) -> Dict[str, any]:
        """生成测试汇总"""
        total_suites = len(test_results)
        successful_suites = sum(
            1 for result in test_results.values() if result["success"]
        )
        failed_suites = total_suites - successful_suites

        total_duration = sum(result["duration"] for result in test_results.values())

        summary = {
            "total_suites": total_suites,
            "successful_suites": successful_suites,
            "failed_suites": failed_suites,
            "success_rate": successful_suites / total_suites if total_suites > 0 else 0,
            "total_duration": total_duration,
            "average_duration": (
                total_duration / total_suites if total_suites > 0 else 0
            ),
        }

        return summary

    def _save_results(self, results: Dict[str, any]):
        """保存测试结果"""
        result_file = self.output_dir / "behavior_test_results.json"

        # 转换时间戳为可读格式
        readable_results = results.copy()
        readable_results["start_time_str"] = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(results["start_time"])
        )
        readable_results["end_time_str"] = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(results["end_time"])
        )

        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(readable_results, f, ensure_ascii=False, indent=2)

        print(f"\n📄 测试结果已保存到: {result_file}")

    def _print_summary(self, summary: Dict[str, any]):
        """打印测试汇总"""
        print("\n" + "=" * 60)
        print("📊 智能体行为测试汇总")
        print("=" * 60)

        print(f"总测试套件数: {summary['total_suites']}")
        print(f"成功套件数: {summary['successful_suites']}")
        print(f"失败套件数: {summary['failed_suites']}")
        print(f"成功率: {summary['success_rate']:.1%}")
        print(f"总耗时: {summary['total_duration']:.2f}秒")
        print(f"平均耗时: {summary['average_duration']:.2f}秒")

        if summary["failed_suites"] == 0:
            print("\n🎉 所有智能体行为测试通过！")
        else:
            print(f"\n⚠️  有 {summary['failed_suites']} 个测试套件失败，请检查详细结果")

    def generate_report(self) -> str:
        """生成HTML测试报告"""
        result_file = self.output_dir / "behavior_test_results.json"

        if not result_file.exists():
            print("❌ 未找到测试结果文件，请先运行测试")
            return ""

        with open(result_file, "r", encoding="utf-8") as f:
            results = json.load(f)

        html_content = self._generate_html_report(results)

        report_file = self.output_dir / "behavior_test_report.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"📄 HTML报告已生成: {report_file}")
        return str(report_file)

    def _generate_html_report(self, results: Dict[str, any]) -> str:
        """生成HTML报告内容"""
        summary = results.get("summary", {})
        test_results = results.get("test_results", {})

        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能体行为测试报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .summary {{ margin: 20px 0; }}
        .test-suite {{ margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .success {{ background-color: #d4edda; border-color: #c3e6cb; }}
        .failure {{ background-color: #f8d7da; border-color: #f5c6cb; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #e9ecef; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 智能体行为测试报告</h1>
        <p>生成时间: {results.get('start_time_str', 'N/A')}</p>
        <p>总耗时: {summary.get('total_duration', 0):.2f}秒</p>
    </div>

    <div class="summary">
        <h2>📊 测试汇总</h2>
        <div class="metric">总套件数: {summary.get('total_suites', 0)}</div>
        <div class="metric">成功数: {summary.get('successful_suites', 0)}</div>
        <div class="metric">失败数: {summary.get('failed_suites', 0)}</div>
        <div class="metric">成功率: {summary.get('success_rate', 0):.1%}</div>
    </div>

    <div class="test-results">
        <h2>🧪 测试套件详情</h2>
"""

        for suite_name, result in test_results.items():
            status_class = "success" if result["success"] else "failure"
            status_icon = "✅" if result["success"] else "❌"

            html += f"""
        <div class="test-suite {status_class}">
            <h3>{status_icon} {suite_name}</h3>
            <p><strong>文件:</strong> {result['test_file']}</p>
            <p><strong>耗时:</strong> {result['duration']:.2f}秒</p>
            <p><strong>状态:</strong> {'成功' if result['success'] else '失败'}</p>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""
        return html

    def list_available_tests(self):
        """列出可用的测试套件"""
        print("📋 可用的智能体行为测试套件:")
        print("-" * 50)

        for suite_name, test_file in self.test_suites.items():
            print(f"  {suite_name:20} -> {test_file}")

        print(f"\n总共 {len(self.test_suites)} 个测试套件")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能体行为测试运行器")
    parser.add_argument(
        "--test",
        type=str,
        help="运行特定测试套件 (basic_behavior, react_quality, regression)",
    )
    parser.add_argument("--all", action="store_true", help="运行所有测试套件")
    parser.add_argument("--list", action="store_true", help="列出所有可用的测试套件")
    parser.add_argument("--report", action="store_true", help="生成HTML测试报告")
    parser.add_argument(
        "--output",
        type=str,
        default="test_results",
        help="输出目录 (默认: test_results)",
    )
    parser.add_argument("--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    runner = BehaviorTestRunner(args.output)

    if args.list:
        runner.list_available_tests()
    elif args.report:
        runner.generate_report()
    elif args.test:
        runner.run_specific_test(args.test, args.verbose)
    elif args.all:
        runner.run_all_tests(args.verbose)
    else:
        print("请指定要执行的操作。使用 --help 查看帮助信息。")
        runner.list_available_tests()


if __name__ == "__main__":
    main()
