#!/usr/bin/env python3
"""
恶意代码检测器

检测和过滤潜在的恶意代码，防止在沙盒环境中执行危险操作
"""

import ast
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..config.logging_config import get_logger

logger = get_logger("malicious_code_detector")


class ThreatLevel(Enum):
    """威胁级别"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityThreat:
    """安全威胁信息"""

    threat_type: str
    level: ThreatLevel
    description: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None


class MaliciousCodeDetector:
    """恶意代码检测器"""

    def __init__(self):
        self.dangerous_imports = {
            # 系统操作
            "os": ThreatLevel.HIGH,
            "subprocess": ThreatLevel.CRITICAL,
            "shutil": ThreatLevel.HIGH,
            "pathlib": ThreatLevel.MEDIUM,
            # 网络操作
            "socket": ThreatLevel.HIGH,
            "urllib": ThreatLevel.MEDIUM,
            "requests": ThreatLevel.MEDIUM,
            "http": ThreatLevel.MEDIUM,
            # 文件系统
            "glob": ThreatLevel.MEDIUM,
            "tempfile": ThreatLevel.MEDIUM,
            # 进程和线程
            "threading": ThreatLevel.MEDIUM,
            "multiprocessing": ThreatLevel.HIGH,
            # 系统信息
            "platform": ThreatLevel.LOW,
            "sys": ThreatLevel.MEDIUM,
            # 危险的内置函数
            "__import__": ThreatLevel.HIGH,
            "eval": ThreatLevel.CRITICAL,
            "exec": ThreatLevel.CRITICAL,
            "compile": ThreatLevel.HIGH,
        }

        self.dangerous_functions = {
            # 文件操作
            "open": ThreatLevel.MEDIUM,
            "file": ThreatLevel.MEDIUM,
            # 系统调用
            "system": ThreatLevel.CRITICAL,
            "popen": ThreatLevel.CRITICAL,
            "spawn": ThreatLevel.CRITICAL,
            # 动态执行
            "eval": ThreatLevel.CRITICAL,
            "exec": ThreatLevel.CRITICAL,
            "compile": ThreatLevel.HIGH,
            "__import__": ThreatLevel.HIGH,
            "getattr": ThreatLevel.MEDIUM,
            "setattr": ThreatLevel.MEDIUM,
            "delattr": ThreatLevel.MEDIUM,
            "hasattr": ThreatLevel.LOW,
            # 内存操作
            "memoryview": ThreatLevel.MEDIUM,
            "bytearray": ThreatLevel.LOW,
            # 网络
            "urlopen": ThreatLevel.MEDIUM,
            "urlretrieve": ThreatLevel.MEDIUM,
        }

        self.dangerous_patterns = [
            # 系统命令执行
            (r"os\.system\s*\(", ThreatLevel.CRITICAL, "系统命令执行"),
            (
                r"subprocess\.(run|call|check_output|Popen)",
                ThreatLevel.CRITICAL,
                "子进程执行",
            ),
            (r"eval\s*\(", ThreatLevel.CRITICAL, "动态代码执行"),
            (r"exec\s*\(", ThreatLevel.CRITICAL, "动态代码执行"),
            # 文件系统操作
            (r"open\s*\([^)]*['\"][/\\]", ThreatLevel.HIGH, "绝对路径文件访问"),
            (r"shutil\.(rmtree|move|copy)", ThreatLevel.HIGH, "文件系统修改"),
            # 网络访问
            (r"socket\.socket\s*\(", ThreatLevel.HIGH, "网络套接字创建"),
            (r"urllib\.request\.urlopen", ThreatLevel.MEDIUM, "网络请求"),
            (r"requests\.(get|post|put|delete)", ThreatLevel.MEDIUM, "HTTP请求"),
            # 危险的内置函数
            (r"__import__\s*\(", ThreatLevel.HIGH, "动态导入"),
            (r"globals\s*\(\)", ThreatLevel.MEDIUM, "全局变量访问"),
            (r"locals\s*\(\)", ThreatLevel.LOW, "局部变量访问"),
            (r"vars\s*\(", ThreatLevel.LOW, "变量访问"),
            # 反射和元编程
            (r"getattr\s*\(", ThreatLevel.MEDIUM, "属性反射访问"),
            (r"setattr\s*\(", ThreatLevel.MEDIUM, "属性反射设置"),
            (r"delattr\s*\(", ThreatLevel.MEDIUM, "属性反射删除"),
            # 潜在的代码注入
            (r"['\"].*\+.*['\"].*exec", ThreatLevel.CRITICAL, "潜在代码注入"),
            (r"['\"].*\+.*['\"].*eval", ThreatLevel.CRITICAL, "潜在代码注入"),
            # 环境变量操作
            (r"os\.environ", ThreatLevel.MEDIUM, "环境变量访问"),
            (r"os\.getenv", ThreatLevel.MEDIUM, "环境变量读取"),
            # 进程操作
            (r"os\.kill", ThreatLevel.HIGH, "进程终止"),
            (r"os\.killpg", ThreatLevel.HIGH, "进程组终止"),
            # 权限提升
            (r"os\.setuid", ThreatLevel.CRITICAL, "用户ID设置"),
            (r"os\.setgid", ThreatLevel.CRITICAL, "组ID设置"),
        ]

        self.allowed_imports = {
            # 数据处理
            "json",
            "csv",
            "xml",
            "yaml",
            "pickle",
            # 数学和科学计算
            "math",
            "random",
            "statistics",
            "decimal",
            "fractions",
            "numpy",
            "pandas",
            "scipy",
            "matplotlib",
            "seaborn",
            # 日期时间
            "datetime",
            "time",
            "calendar",
            # 字符串和正则
            "string",
            "re",
            "unicodedata",
            # 数据结构
            "collections",
            "heapq",
            "bisect",
            "array",
            # 函数工具
            "functools",
            "itertools",
            "operator",
            # 测试框架
            "unittest",
            "pytest",
            "mock",
            # 类型提示
            "typing",
            "dataclasses",
            # 日志
            "logging",
            # 编码解码
            "base64",
            "binascii",
            "codecs",
            # 压缩
            "gzip",
            "zipfile",
            "tarfile",
            # 哈希
            "hashlib",
            "hmac",
            # 配置
            "configparser",
            "argparse",
        }

    def detect_threats(
        self, code: str, filename: str = "unknown"
    ) -> List[SecurityThreat]:
        """检测代码中的安全威胁

        Args:
            code: 要检测的代码
            filename: 文件名（用于日志）

        Returns:
            检测到的威胁列表
        """
        threats = []

        logger.info(f"开始检测代码安全威胁: {filename}")

        # 基于正则表达式的模式匹配
        threats.extend(self._detect_pattern_threats(code))

        # 基于AST的语法分析
        try:
            threats.extend(self._detect_ast_threats(code))
        except SyntaxError as e:
            threats.append(
                SecurityThreat(
                    threat_type="syntax_error",
                    level=ThreatLevel.HIGH,
                    description=f"代码语法错误，可能是混淆或恶意代码: {e}",
                    line_number=getattr(e, "lineno", None),
                )
            )

        # 检测导入威胁
        threats.extend(self._detect_import_threats(code))

        # 检测函数调用威胁
        threats.extend(self._detect_function_threats(code))

        logger.info(f"威胁检测完成，发现 {len(threats)} 个威胁")

        return threats

    def _detect_pattern_threats(self, code: str) -> List[SecurityThreat]:
        """基于正则表达式检测威胁"""
        threats = []
        lines = code.split("\n")

        for pattern, level, description in self.dangerous_patterns:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    threats.append(
                        SecurityThreat(
                            threat_type="pattern_match",
                            level=level,
                            description=f"{description}: {pattern}",
                            line_number=line_num,
                            code_snippet=line.strip(),
                            suggestion=f"避免使用 {description.lower()}",
                        )
                    )

        return threats

    def _detect_ast_threats(self, code: str) -> List[SecurityThreat]:
        """基于AST语法分析检测威胁"""
        threats = []

        try:
            tree = ast.parse(code)
            visitor = ThreatVisitor(self)
            visitor.visit(tree)
            threats.extend(visitor.threats)
        except Exception as e:
            logger.warning(f"AST分析失败: {e}")

        return threats

    def _detect_import_threats(self, code: str) -> List[SecurityThreat]:
        """检测导入威胁"""
        threats = []
        lines = code.split("\n")

        import_patterns = [
            r"import\s+(\w+)",
            r"from\s+(\w+)\s+import",
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in import_patterns:
                matches = re.findall(pattern, line)
                for module in matches:
                    if module in self.dangerous_imports:
                        level = self.dangerous_imports[module]
                        threats.append(
                            SecurityThreat(
                                threat_type="dangerous_import",
                                level=level,
                                description=f"导入危险模块: {module}",
                                line_number=line_num,
                                code_snippet=line.strip(),
                                suggestion=f"避免导入 {module} 模块，或使用更安全的替代方案",
                            )
                        )
                    elif module not in self.allowed_imports and not module.startswith(
                        "_"
                    ):
                        threats.append(
                            SecurityThreat(
                                threat_type="unknown_import",
                                level=ThreatLevel.LOW,
                                description=f"导入未知模块: {module}",
                                line_number=line_num,
                                code_snippet=line.strip(),
                                suggestion=f"确认 {module} 模块的安全性",
                            )
                        )

        return threats

    def _detect_function_threats(self, code: str) -> List[SecurityThreat]:
        """检测函数调用威胁"""
        threats = []
        lines = code.split("\n")

        for line_num, line in enumerate(lines, 1):
            for func_name, level in self.dangerous_functions.items():
                pattern = rf"\b{re.escape(func_name)}\s*\("
                if re.search(pattern, line):
                    threats.append(
                        SecurityThreat(
                            threat_type="dangerous_function",
                            level=level,
                            description=f"调用危险函数: {func_name}",
                            line_number=line_num,
                            code_snippet=line.strip(),
                            suggestion=f"避免使用 {func_name} 函数，或确保安全使用",
                        )
                    )

        return threats

    def is_code_safe(
        self, code: str, max_threat_level: ThreatLevel = ThreatLevel.MEDIUM
    ) -> bool:
        """判断代码是否安全

        Args:
            code: 要检测的代码
            max_threat_level: 允许的最大威胁级别

        Returns:
            代码是否安全
        """
        threats = self.detect_threats(code)

        # 检查是否有超过允许级别的威胁
        threat_levels = [
            ThreatLevel.LOW,
            ThreatLevel.MEDIUM,
            ThreatLevel.HIGH,
            ThreatLevel.CRITICAL,
        ]
        max_level_index = threat_levels.index(max_threat_level)

        for threat in threats:
            threat_index = threat_levels.index(threat.level)
            if threat_index > max_level_index:
                return False

        return True

    def filter_code(self, code: str) -> str:
        """过滤代码中的危险部分

        Args:
            code: 原始代码

        Returns:
            过滤后的代码
        """
        threats = self.detect_threats(code)
        lines = code.split("\n")
        filtered_lines = []

        dangerous_lines = set()
        for threat in threats:
            if (
                threat.level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
                and threat.line_number
            ):
                dangerous_lines.add(threat.line_number - 1)  # 转换为0索引

        for i, line in enumerate(lines):
            if i in dangerous_lines:
                filtered_lines.append(f"# FILTERED: {line}")
                logger.warning(f"过滤危险代码行 {i+1}: {line.strip()}")
            else:
                filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def generate_security_report(
        self, code: str, filename: str = "unknown"
    ) -> Dict[str, Any]:
        """生成安全检测报告

        Args:
            code: 检测的代码
            filename: 文件名

        Returns:
            安全报告
        """
        threats = self.detect_threats(code, filename)

        # 按威胁级别分组
        threat_by_level = {level: [] for level in ThreatLevel}
        for threat in threats:
            threat_by_level[threat.level].append(threat)

        # 计算安全评分 (0-100)
        score = 100
        for threat in threats:
            if threat.level == ThreatLevel.CRITICAL:
                score -= 30
            elif threat.level == ThreatLevel.HIGH:
                score -= 20
            elif threat.level == ThreatLevel.MEDIUM:
                score -= 10
            elif threat.level == ThreatLevel.LOW:
                score -= 5

        score = max(0, score)

        return {
            "filename": filename,
            "total_threats": len(threats),
            "security_score": score,
            "is_safe": score >= 70,
            "threats_by_level": {
                level.value: len(threat_list)
                for level, threat_list in threat_by_level.items()
            },
            "threats": [
                {
                    "type": threat.threat_type,
                    "level": threat.level.value,
                    "description": threat.description,
                    "line_number": threat.line_number,
                    "code_snippet": threat.code_snippet,
                    "suggestion": threat.suggestion,
                }
                for threat in threats
            ],
            "recommendations": self._generate_recommendations(threats),
        }

    def _generate_recommendations(self, threats: List[SecurityThreat]) -> List[str]:
        """生成安全建议"""
        recommendations = []

        if any(t.level == ThreatLevel.CRITICAL for t in threats):
            recommendations.append("发现严重安全威胁，建议重新审查代码逻辑")

        if any(t.threat_type == "dangerous_import" for t in threats):
            recommendations.append("避免导入危险模块，使用沙盒环境提供的安全替代方案")

        if any(t.threat_type == "dangerous_function" for t in threats):
            recommendations.append("避免使用危险函数，或确保在受控环境中安全使用")

        if any("exec" in t.description or "eval" in t.description for t in threats):
            recommendations.append("避免动态代码执行，使用静态代码分析和预定义函数")

        if any("system" in t.description for t in threats):
            recommendations.append("避免系统命令执行，使用Python内置函数替代")

        return recommendations


class ThreatVisitor(ast.NodeVisitor):
    """AST威胁检测访问器"""

    def __init__(self, detector: MaliciousCodeDetector):
        self.detector = detector
        self.threats = []

    def visit_Import(self, node):
        """访问import语句"""
        for alias in node.names:
            module_name = alias.name.split(".")[0]  # 获取顶级模块名
            if module_name in self.detector.dangerous_imports:
                level = self.detector.dangerous_imports[module_name]
                self.threats.append(
                    SecurityThreat(
                        threat_type="ast_dangerous_import",
                        level=level,
                        description=f"AST检测到危险导入: {module_name}",
                        line_number=node.lineno,
                        suggestion=f"避免导入 {module_name} 模块",
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """访问from...import语句"""
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name in self.detector.dangerous_imports:
                level = self.detector.dangerous_imports[module_name]
                self.threats.append(
                    SecurityThreat(
                        threat_type="ast_dangerous_import_from",
                        level=level,
                        description=f"AST检测到危险导入: from {module_name}",
                        line_number=node.lineno,
                        suggestion=f"避免从 {module_name} 模块导入",
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node):
        """访问函数调用"""
        func_name = None

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name and func_name in self.detector.dangerous_functions:
            level = self.detector.dangerous_functions[func_name]
            self.threats.append(
                SecurityThreat(
                    threat_type="ast_dangerous_call",
                    level=level,
                    description=f"AST检测到危险函数调用: {func_name}",
                    line_number=node.lineno,
                    suggestion=f"避免调用 {func_name} 函数",
                )
            )

        self.generic_visit(node)

    def visit_Exec(self, node):
        """访问exec语句"""
        self.threats.append(
            SecurityThreat(
                threat_type="ast_exec",
                level=ThreatLevel.CRITICAL,
                description="AST检测到exec语句",
                line_number=node.lineno,
                suggestion="避免使用exec动态执行代码",
            )
        )
        self.generic_visit(node)

    def visit_Eval(self, node):
        """访问eval表达式"""
        self.threats.append(
            SecurityThreat(
                threat_type="ast_eval",
                level=ThreatLevel.CRITICAL,
                description="AST检测到eval表达式",
                line_number=node.lineno,
                suggestion="避免使用eval动态执行代码",
            )
        )
        self.generic_visit(node)


# 全局恶意代码检测器实例
_malicious_code_detector = MaliciousCodeDetector()


def get_malicious_code_detector() -> MaliciousCodeDetector:
    """获取全局恶意代码检测器"""
    return _malicious_code_detector


def detect_malicious_code(code: str, filename: str = "unknown") -> List[SecurityThreat]:
    """检测恶意代码的便捷函数"""
    return _malicious_code_detector.detect_threats(code, filename)


def is_code_safe(code: str, max_threat_level: ThreatLevel = ThreatLevel.MEDIUM) -> bool:
    """判断代码是否安全的便捷函数"""
    return _malicious_code_detector.is_code_safe(code, max_threat_level)
