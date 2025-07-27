"""质量保证工作流实现

实现测试用例质量评估标准和自动化检查，创建代码审查规则引擎和最佳实践验证，
建立反馈循环机制，支持迭代优化。
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from ..config.logging_config import get_logger
from ..models.review import (
    RequirementReview,
    ReviewScore,
    TestCaseReview,
    TestScriptReview,
)

logger = get_logger("quality_assurance")


class QualityMetric(Enum):
    """质量指标枚举"""

    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CLARITY = "clarity"
    CONSISTENCY = "consistency"
    MAINTAINABILITY = "maintainability"
    PERFORMANCE = "performance"
    SECURITY = "security"
    USABILITY = "usability"


class QualityLevel(Enum):
    """质量等级枚举"""

    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"  # 80-89
    FAIR = "fair"  # 70-79
    POOR = "poor"  # 60-69
    UNACCEPTABLE = "unacceptable"  # <60


@dataclass
class QualityRule:
    """质量规则"""

    rule_id: str
    name: str
    description: str
    category: str
    weight: float
    threshold: float
    check_function: str
    enabled: bool = True


@dataclass
class QualityCheckResult:
    """质量检查结果"""

    rule_id: str
    rule_name: str
    passed: bool
    score: float
    message: str
    suggestions: List[str]
    details: Dict[str, Any]


class TestCaseQualityChecker:
    """测试用例质量检查器"""

    def __init__(self):
        self.rules = self._initialize_test_case_rules()

    def _initialize_test_case_rules(self) -> List[QualityRule]:
        """初始化测试用例质量规则"""
        return [
            QualityRule(
                rule_id="TC001",
                name="测试用例标题完整性",
                description="测试用例应有清晰、描述性的标题",
                category="completeness",
                weight=0.15,
                threshold=80.0,
                check_function="check_title_completeness",
            ),
            QualityRule(
                rule_id="TC002",
                name="前置条件明确性",
                description="测试用例应明确列出前置条件",
                category="clarity",
                weight=0.20,
                threshold=75.0,
                check_function="check_preconditions",
            ),
            QualityRule(
                rule_id="TC003",
                name="测试步骤详细性",
                description="测试步骤应详细、可执行",
                category="clarity",
                weight=0.25,
                threshold=80.0,
                check_function="check_test_steps",
            ),
            QualityRule(
                rule_id="TC004",
                name="预期结果明确性",
                description="预期结果应明确、可验证",
                category="accuracy",
                weight=0.20,
                threshold=85.0,
                check_function="check_expected_results",
            ),
            QualityRule(
                rule_id="TC005",
                name="边界值覆盖",
                description="应包含边界值和异常情况测试",
                category="completeness",
                weight=0.20,
                threshold=70.0,
                check_function="check_boundary_coverage",
            ),
        ]

    def check_quality(self, test_case_content: str) -> TestCaseReview:
        """检查测试用例质量"""
        results = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            try:
                check_method = getattr(self, rule.check_function)
                result = check_method(test_case_content, rule)
                results.append(result)
            except AttributeError:
                logger.warning(f"质量检查方法不存在: {rule.check_function}")
                continue
            except Exception as e:
                logger.error(f"质量检查失败 {rule.rule_id}: {e}")
                continue

        return self._calculate_test_case_score(results)

    def check_title_completeness(
        self, content: str, rule: QualityRule
    ) -> QualityCheckResult:
        """检查标题完整性"""
        lines = content.split("\n")
        title_patterns = [
            r"^#\s+(.+)",  # Markdown标题
            r"^\*\*标题\*\*[:：]\s*(.+)",  # 粗体标题
            r"^标题[:：]\s*(.+)",  # 普通标题
            r"^\d+\.\s*(.+)",  # 编号标题
        ]

        title_found = False
        title_quality = 0
        suggestions = []

        for line in lines[:10]:  # 检查前10行
            for pattern in title_patterns:
                match = re.search(pattern, line.strip())
                if match:
                    title = match.group(1).strip()
                    title_found = True

                    # 评估标题质量
                    if len(title) >= 10:
                        title_quality += 40
                    if any(keyword in title for keyword in ["测试", "验证", "检查"]):
                        title_quality += 30
                    if re.search(r"[功能|性能|安全|界面]", title):
                        title_quality += 30

                    break
            if title_found:
                break

        if not title_found:
            suggestions.append("添加清晰的测试用例标题")
            title_quality = 0
        elif title_quality < 60:
            suggestions.append("改进标题描述性，包含测试目标和功能点")

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=title_quality >= rule.threshold,
            score=title_quality,
            message=f"标题质量评分: {title_quality}/100",
            suggestions=suggestions,
            details={"title_found": title_found, "title_quality": title_quality},
        )

    def check_preconditions(
        self, content: str, rule: QualityRule
    ) -> QualityCheckResult:
        """检查前置条件"""
        precondition_patterns = [
            r"前置条件[:：]",
            r"预备条件[:：]",
            r"准备工作[:：]",
            r"环境要求[:：]",
            r"Prerequisites?[:：]",
        ]

        precondition_found = False
        precondition_quality = 0
        suggestions = []

        content_lower = content.lower()
        for pattern in precondition_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                precondition_found = True
                break

        if precondition_found:
            # 检查前置条件的详细程度
            if re.search(r"(登录|权限|数据|环境|配置)", content):
                precondition_quality += 50
            if re.search(r"(具体|详细|明确)", content):
                precondition_quality += 30
            if len(re.findall(r"[。！？]", content)) >= 2:  # 至少2个句子
                precondition_quality += 20
        else:
            suggestions.append("添加明确的前置条件说明")

        if precondition_quality < 60:
            suggestions.append("详细描述测试环境、数据准备和权限要求")

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=precondition_quality >= rule.threshold,
            score=precondition_quality,
            message=f"前置条件质量评分: {precondition_quality}/100",
            suggestions=suggestions,
            details={"precondition_found": precondition_found},
        )

    def check_test_steps(self, content: str, rule: QualityRule) -> QualityCheckResult:
        """检查测试步骤"""
        step_patterns = [
            r"测试步骤[:：]",
            r"操作步骤[:：]",
            r"执行步骤[:：]",
            r"Steps?[:：]",
        ]

        steps_found = False
        steps_quality = 0
        suggestions = []

        for pattern in step_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                steps_found = True
                break

        if steps_found:
            # 检查步骤的数量和质量
            numbered_steps = re.findall(r"^\d+[\.、]\s*(.+)", content, re.MULTILINE)
            bullet_steps = re.findall(r"^[-*]\s*(.+)", content, re.MULTILINE)

            total_steps = len(numbered_steps) + len(bullet_steps)

            if total_steps >= 3:
                steps_quality += 40
            elif total_steps >= 1:
                steps_quality += 20

            # 检查步骤的详细程度
            action_words = ["点击", "输入", "选择", "验证", "检查", "确认"]
            action_count = sum(1 for word in action_words if word in content)
            steps_quality += min(action_count * 10, 40)

            # 检查步骤的逻辑性
            if re.search(r"(然后|接着|最后|验证)", content):
                steps_quality += 20
        else:
            suggestions.append("添加详细的测试执行步骤")

        if steps_quality < 60:
            suggestions.append("增加步骤的详细程度，使用具体的操作动词")

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=steps_quality >= rule.threshold,
            score=steps_quality,
            message=f"测试步骤质量评分: {steps_quality}/100",
            suggestions=suggestions,
            details={
                "steps_found": steps_found,
                "step_count": total_steps if steps_found else 0,
            },
        )

    def check_expected_results(
        self, content: str, rule: QualityRule
    ) -> QualityCheckResult:
        """检查预期结果"""
        result_patterns = [
            r"预期结果[:：]",
            r"期望结果[:：]",
            r"预期输出[:：]",
            r"Expected Result?s?[:：]",
        ]

        results_found = False
        results_quality = 0
        suggestions = []

        for pattern in result_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                results_found = True
                break

        if results_found:
            # 检查结果的具体性
            if re.search(r"(显示|出现|返回|成功|失败|错误)", content):
                results_quality += 40
            if re.search(r"(页面|界面|数据|状态|消息)", content):
                results_quality += 30
            if re.search(r"(应该|必须|能够|正确)", content):
                results_quality += 30
        else:
            suggestions.append("添加明确的预期结果描述")

        if results_quality < 70:
            suggestions.append("详细描述预期的界面变化、数据状态或系统响应")

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=results_quality >= rule.threshold,
            score=results_quality,
            message=f"预期结果质量评分: {results_quality}/100",
            suggestions=suggestions,
            details={"results_found": results_found},
        )

    def check_boundary_coverage(
        self, content: str, rule: QualityRule
    ) -> QualityCheckResult:
        """检查边界值覆盖"""
        boundary_keywords = [
            "边界",
            "最大",
            "最小",
            "空值",
            "空字符串",
            "特殊字符",
            "异常",
            "错误",
            "非法",
            "无效",
            "超长",
            "负数",
        ]

        boundary_coverage = 0
        suggestions = []
        found_keywords = []

        for keyword in boundary_keywords:
            if keyword in content:
                boundary_coverage += 15
                found_keywords.append(keyword)

        # 限制最大分数
        boundary_coverage = min(boundary_coverage, 100)

        if boundary_coverage < 30:
            suggestions.append("增加边界值和异常情况的测试覆盖")
        if "空值" not in found_keywords:
            suggestions.append("考虑添加空值和空字符串的测试")
        if "最大" not in found_keywords and "最小" not in found_keywords:
            suggestions.append("考虑添加最大值和最小值的边界测试")

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=boundary_coverage >= rule.threshold,
            score=boundary_coverage,
            message=f"边界覆盖评分: {boundary_coverage}/100",
            suggestions=suggestions,
            details={"found_keywords": found_keywords},
        )

    def _calculate_test_case_score(
        self, results: List[QualityCheckResult]
    ) -> TestCaseReview:
        """计算测试用例总分"""
        if not results:
            return TestCaseReview(
                overall_score=0,
                completeness=0,
                accuracy=0,
                maintainability=0,
                coverage_score=0,
                clarity_score=0,
                executability_score=0,
                suggestions=["无法进行质量评估"],
            )

        # 按类别计算分数
        category_scores = {}
        category_weights = {}

        for result in results:
            rule = next(r for r in self.rules if r.rule_id == result.rule_id)
            category = rule.category

            if category not in category_scores:
                category_scores[category] = 0
                category_weights[category] = 0

            category_scores[category] += result.score * rule.weight
            category_weights[category] += rule.weight

        # 计算各维度分数
        completeness = category_scores.get("completeness", 0) / category_weights.get(
            "completeness", 1
        )
        accuracy = category_scores.get("accuracy", 0) / category_weights.get(
            "accuracy", 1
        )
        clarity = category_scores.get("clarity", 0) / category_weights.get("clarity", 1)

        # 计算总分
        total_weight = sum(r.weight for r in self.rules if r.enabled)
        overall_score = (
            sum(
                r.score
                * (
                    next(
                        rule for rule in self.rules if rule.rule_id == r.rule_id
                    ).weight
                )
                for r in results
            )
            / total_weight
            if total_weight > 0
            else 0
        )

        # 收集所有建议
        all_suggestions = []
        for result in results:
            all_suggestions.extend(result.suggestions)

        return TestCaseReview(
            overall_score=round(overall_score, 2),
            completeness=round(completeness, 2),
            accuracy=round(accuracy, 2),
            maintainability=round((completeness + clarity) / 2, 2),
            coverage_score=round(completeness, 2),
            clarity_score=round(clarity, 2),
            executability_score=round((clarity + accuracy) / 2, 2),
            suggestions=list(set(all_suggestions)),  # 去重
        )


class TestScriptQualityChecker:
    """测试脚本质量检查器"""

    def __init__(self):
        self.rules = self._initialize_test_script_rules()

    def _initialize_test_script_rules(self) -> List[QualityRule]:
        """初始化测试脚本质量规则"""
        return [
            QualityRule(
                rule_id="TS001",
                name="语法正确性",
                description="代码语法应该正确无误",
                category="syntax",
                weight=0.30,
                threshold=95.0,
                check_function="check_syntax_correctness",
            ),
            QualityRule(
                rule_id="TS002",
                name="函数命名规范",
                description="函数名应该清晰、符合命名规范",
                category="maintainability",
                weight=0.15,
                threshold=80.0,
                check_function="check_function_naming",
            ),
            QualityRule(
                rule_id="TS003",
                name="注释完整性",
                description="关键代码应有适当注释",
                category="maintainability",
                weight=0.15,
                threshold=70.0,
                check_function="check_comments",
            ),
            QualityRule(
                rule_id="TS004",
                name="异常处理",
                description="应包含适当的异常处理",
                category="reliability",
                weight=0.20,
                threshold=75.0,
                check_function="check_exception_handling",
            ),
            QualityRule(
                rule_id="TS005",
                name="测试断言",
                description="应包含明确的测试断言",
                category="logic",
                weight=0.20,
                threshold=85.0,
                check_function="check_assertions",
            ),
        ]

    def check_quality(self, script_content: str) -> TestScriptReview:
        """检查测试脚本质量"""
        results = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            try:
                check_method = getattr(self, rule.check_function)
                result = check_method(script_content, rule)
                results.append(result)
            except AttributeError:
                logger.warning(f"质量检查方法不存在: {rule.check_function}")
                continue
            except Exception as e:
                logger.error(f"质量检查失败 {rule.rule_id}: {e}")
                continue

        return self._calculate_test_script_score(results)

    def check_syntax_correctness(
        self, content: str, rule: QualityRule
    ) -> QualityCheckResult:
        """检查语法正确性"""
        syntax_score = 100
        suggestions = []
        syntax_errors = []

        # 基本语法检查
        try:
            # 尝试编译Python代码
            compile(content, "<string>", "exec")
        except SyntaxError as e:
            syntax_score = 0
            syntax_errors.append(f"语法错误: {e}")
            suggestions.append("修复Python语法错误")
        except Exception as e:
            syntax_score = 50
            syntax_errors.append(f"编译警告: {e}")
            suggestions.append("检查代码结构和导入语句")

        # 检查常见语法问题
        if re.search(r"^\s*def\s+\w+\([^)]*\)\s*$", content, re.MULTILINE):
            if ":" not in content:
                syntax_score -= 20
                suggestions.append("函数定义缺少冒号")

        # 检查缩进一致性
        lines = content.split("\n")
        indent_levels = []
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                indent_levels.append(indent)

        if len(set(indent_levels)) > 6:  # 缩进层次过多
            syntax_score -= 10
            suggestions.append("简化代码结构，减少嵌套层次")

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=syntax_score >= rule.threshold,
            score=syntax_score,
            message=f"语法正确性评分: {syntax_score}/100",
            suggestions=suggestions,
            details={"syntax_errors": syntax_errors},
        )

    def check_function_naming(
        self, content: str, rule: QualityRule
    ) -> QualityCheckResult:
        """检查函数命名规范"""
        function_pattern = r"def\s+(\w+)\s*\("
        functions = re.findall(function_pattern, content)

        naming_score = 100
        suggestions = []

        if not functions:
            naming_score = 0
            suggestions.append("代码中未发现函数定义")
        else:
            good_names = 0
            for func_name in functions:
                # 检查命名规范
                if re.match(r"^[a-z_][a-z0-9_]*$", func_name):
                    good_names += 1
                if len(func_name) >= 4:  # 名称长度合理
                    good_names += 0.5
                if any(word in func_name for word in ["test", "check", "verify"]):
                    good_names += 0.5

            naming_score = min(100, (good_names / len(functions)) * 100)

            if naming_score < 80:
                suggestions.append("改进函数命名，使用描述性的名称")
                suggestions.append("遵循Python命名规范（小写+下划线）")

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=naming_score >= rule.threshold,
            score=naming_score,
            message=f"函数命名规范评分: {naming_score}/100",
            suggestions=suggestions,
            details={"function_count": len(functions), "functions": functions},
        )

    def check_comments(self, content: str, rule: QualityRule) -> QualityCheckResult:
        """检查注释完整性"""
        lines = content.split("\n")
        total_lines = len([line for line in lines if line.strip()])
        comment_lines = len([line for line in lines if line.strip().startswith("#")])

        comment_ratio = (comment_lines / total_lines * 100) if total_lines > 0 else 0

        comment_score = min(100, comment_ratio * 5)  # 20%注释率得满分
        suggestions = []

        # 检查文档字符串
        if '"""' in content or "'''" in content:
            comment_score += 20
        else:
            suggestions.append("添加函数和类的文档字符串")

        # 检查关键部分注释
        if re.search(r"#.*(?:TODO|FIXME|NOTE)", content):
            comment_score += 10

        if comment_score < 60:
            suggestions.append("增加代码注释，解释复杂逻辑")

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=comment_score >= rule.threshold,
            score=comment_score,
            message=f"注释完整性评分: {comment_score}/100",
            suggestions=suggestions,
            details={"comment_ratio": round(comment_ratio, 2)},
        )

    def check_exception_handling(
        self, content: str, rule: QualityRule
    ) -> QualityCheckResult:
        """检查异常处理"""
        exception_score = 0
        suggestions = []

        # 检查try-except块
        try_blocks = len(re.findall(r"\btry\s*:", content))
        except_blocks = len(re.findall(r"\bexcept\b", content))

        if try_blocks > 0 and except_blocks > 0:
            exception_score += 60
        elif try_blocks > 0 or except_blocks > 0:
            exception_score += 30
            suggestions.append("完善异常处理结构")
        else:
            suggestions.append("添加适当的异常处理")

        # 检查具体异常类型
        if re.search(r"except\s+\w+Error", content):
            exception_score += 20
        else:
            suggestions.append("使用具体的异常类型而不是通用except")

        # 检查finally块
        if "finally:" in content:
            exception_score += 20

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=exception_score >= rule.threshold,
            score=exception_score,
            message=f"异常处理评分: {exception_score}/100",
            suggestions=suggestions,
            details={"try_blocks": try_blocks, "except_blocks": except_blocks},
        )

    def check_assertions(self, content: str, rule: QualityRule) -> QualityCheckResult:
        """检查测试断言"""
        assertion_patterns = [
            r"\bassert\s+",
            r"\.assert\w+\(",
            r"self\.assert\w+\(",
            r"assertEqual\(",
            r"assertTrue\(",
            r"assertFalse\(",
        ]

        assertion_count = 0
        for pattern in assertion_patterns:
            assertion_count += len(re.findall(pattern, content))

        assertion_score = min(100, assertion_count * 25)  # 4个断言得满分
        suggestions = []

        if assertion_count == 0:
            suggestions.append("添加测试断言来验证结果")
        elif assertion_count < 2:
            suggestions.append("增加更多断言来提高测试覆盖率")

        # 检查断言类型多样性
        assertion_types = []
        for pattern in assertion_patterns:
            if re.search(pattern, content):
                assertion_types.append(pattern)

        if len(assertion_types) > 1:
            assertion_score += 10  # 奖励多样性

        return QualityCheckResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=assertion_score >= rule.threshold,
            score=assertion_score,
            message=f"测试断言评分: {assertion_score}/100",
            suggestions=suggestions,
            details={
                "assertion_count": assertion_count,
                "assertion_types": len(assertion_types),
            },
        )

    def _calculate_test_script_score(
        self, results: List[QualityCheckResult]
    ) -> TestScriptReview:
        """计算测试脚本总分"""
        if not results:
            return TestScriptReview(
                overall_score=0,
                completeness=0,
                accuracy=0,
                maintainability=0,
                syntax_score=0,
                logic_score=0,
                performance_score=0,
                suggestions=["无法进行质量评估"],
            )

        # 按类别计算分数
        category_scores = {
            "syntax": 0,
            "logic": 0,
            "maintainability": 0,
            "reliability": 0,
        }
        category_weights = {
            "syntax": 0,
            "logic": 0,
            "maintainability": 0,
            "reliability": 0,
        }

        for result in results:
            rule = next(r for r in self.rules if r.rule_id == result.rule_id)
            category = rule.category

            if category in category_scores:
                category_scores[category] += result.score * rule.weight
                category_weights[category] += rule.weight

        # 计算各维度分数
        syntax_score = (
            category_scores["syntax"] / category_weights["syntax"]
            if category_weights["syntax"] > 0
            else 0
        )
        logic_score = (
            category_scores["logic"] / category_weights["logic"]
            if category_weights["logic"] > 0
            else 0
        )
        maintainability = (
            category_scores["maintainability"] / category_weights["maintainability"]
            if category_weights["maintainability"] > 0
            else 0
        )
        performance_score = (syntax_score + logic_score) / 2  # 性能基于语法和逻辑

        # 计算总分
        total_weight = sum(r.weight for r in self.rules if r.enabled)
        overall_score = (
            sum(
                r.score
                * (
                    next(
                        rule for rule in self.rules if rule.rule_id == r.rule_id
                    ).weight
                )
                for r in results
            )
            / total_weight
            if total_weight > 0
            else 0
        )

        # 收集所有建议
        all_suggestions = []
        for result in results:
            all_suggestions.extend(result.suggestions)

        return TestScriptReview(
            overall_score=round(overall_score, 2),
            completeness=round(maintainability, 2),
            accuracy=round(logic_score, 2),
            maintainability=round(maintainability, 2),
            syntax_score=round(syntax_score, 2),
            logic_score=round(logic_score, 2),
            performance_score=round(performance_score, 2),
            suggestions=list(set(all_suggestions)),  # 去重
        )


class QualityAssuranceWorkflow:
    """质量保证工作流"""

    def __init__(self):
        self.test_case_checker = TestCaseQualityChecker()
        self.test_script_checker = TestScriptQualityChecker()
        self.feedback_history: List[Dict[str, Any]] = []

    def evaluate_test_cases(self, test_case_content: str) -> TestCaseReview:
        """评估测试用例质量"""
        logger.info("开始评估测试用例质量")

        try:
            review = self.test_case_checker.check_quality(test_case_content)

            # 记录评估历史
            self._record_evaluation(
                "test_case", review.overall_score, review.suggestions
            )

            logger.info(f"测试用例质量评估完成，总分: {review.overall_score}")
            return review

        except Exception as e:
            logger.error(f"测试用例质量评估失败: {e}")
            return TestCaseReview(
                overall_score=0,
                completeness=0,
                accuracy=0,
                maintainability=0,
                coverage_score=0,
                clarity_score=0,
                executability_score=0,
                suggestions=[f"评估失败: {str(e)}"],
            )

    def evaluate_test_scripts(self, script_content: str) -> TestScriptReview:
        """评估测试脚本质量"""
        logger.info("开始评估测试脚本质量")

        try:
            review = self.test_script_checker.check_quality(script_content)

            # 记录评估历史
            self._record_evaluation(
                "test_script", review.overall_score, review.suggestions
            )

            logger.info(f"测试脚本质量评估完成，总分: {review.overall_score}")
            return review

        except Exception as e:
            logger.error(f"测试脚本质量评估失败: {e}")
            return TestScriptReview(
                overall_score=0,
                completeness=0,
                accuracy=0,
                maintainability=0,
                syntax_score=0,
                logic_score=0,
                performance_score=0,
                suggestions=[f"评估失败: {str(e)}"],
            )

    def create_feedback_loop(
        self,
        evaluation_result: Union[TestCaseReview, TestScriptReview],
        improvement_actions: List[str],
    ) -> Dict[str, Any]:
        """创建反馈循环"""
        feedback = {
            "timestamp": datetime.now().isoformat(),
            "evaluation_score": evaluation_result.overall_score,
            "suggestions": evaluation_result.suggestions,
            "improvement_actions": improvement_actions,
            "feedback_id": f"feedback_{int(datetime.now().timestamp())}",
        }

        self.feedback_history.append(feedback)

        # 分析改进趋势
        trend_analysis = self._analyze_improvement_trend()
        feedback["trend_analysis"] = trend_analysis

        logger.info(f"创建反馈循环: {feedback['feedback_id']}")
        return feedback

    def get_quality_recommendations(
        self, content_type: str, current_score: float
    ) -> List[str]:
        """获取质量改进建议"""
        recommendations = []

        if content_type == "test_case":
            if current_score < 60:
                recommendations.extend(
                    [
                        "重新设计测试用例结构",
                        "明确测试目标和范围",
                        "详细描述测试步骤和预期结果",
                    ]
                )
            elif current_score < 80:
                recommendations.extend(
                    [
                        "增加边界值和异常情况测试",
                        "改进测试用例的可读性",
                        "完善前置条件和环境要求",
                    ]
                )
            else:
                recommendations.extend(
                    [
                        "考虑添加性能测试用例",
                        "增加用户体验相关测试",
                        "优化测试用例的维护性",
                    ]
                )

        elif content_type == "test_script":
            if current_score < 60:
                recommendations.extend(
                    ["修复语法错误和基本问题", "重构代码结构", "添加基本的异常处理"]
                )
            elif current_score < 80:
                recommendations.extend(
                    [
                        "改进函数命名和代码注释",
                        "增加测试断言的覆盖率",
                        "优化异常处理机制",
                    ]
                )
            else:
                recommendations.extend(
                    ["考虑代码性能优化", "增加日志记录功能", "实现更复杂的测试场景"]
                )

        return recommendations

    def _record_evaluation(
        self, content_type: str, score: float, suggestions: List[str]
    ):
        """记录评估历史"""
        evaluation_record = {
            "timestamp": datetime.now().isoformat(),
            "content_type": content_type,
            "score": score,
            "suggestions": suggestions,
        }

        # 保持历史记录在合理范围内
        if len(self.feedback_history) > 100:
            self.feedback_history = self.feedback_history[-100:]

    def _analyze_improvement_trend(self) -> Dict[str, Any]:
        """分析改进趋势"""
        if len(self.feedback_history) < 2:
            return {"trend": "insufficient_data", "improvement_rate": 0}

        recent_scores = [
            f.get("evaluation_score", 0) for f in self.feedback_history[-5:]
        ]

        if len(recent_scores) >= 2:
            improvement_rate = (recent_scores[-1] - recent_scores[0]) / len(
                recent_scores
            )

            if improvement_rate > 5:
                trend = "improving"
            elif improvement_rate < -5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
            improvement_rate = 0

        return {
            "trend": trend,
            "improvement_rate": round(improvement_rate, 2),
            "recent_scores": recent_scores,
            "average_score": (
                round(sum(recent_scores) / len(recent_scores), 2)
                if recent_scores
                else 0
            ),
        }

    def get_quality_metrics(self) -> Dict[str, Any]:
        """获取质量指标统计"""
        if not self.feedback_history:
            return {
                "total_evaluations": 0,
                "average_score": 0,
                "improvement_trend": "no_data",
            }

        scores = [f.get("evaluation_score", 0) for f in self.feedback_history]

        return {
            "total_evaluations": len(self.feedback_history),
            "average_score": round(sum(scores) / len(scores), 2),
            "highest_score": max(scores),
            "lowest_score": min(scores),
            "improvement_trend": self._analyze_improvement_trend()["trend"],
            "recent_evaluations": self.feedback_history[-10:],  # 最近10次评估
        }


# 全局质量保证工作流实例
_qa_workflow: Optional[QualityAssuranceWorkflow] = None


def get_quality_assurance_workflow() -> QualityAssuranceWorkflow:
    """获取质量保证工作流单例"""
    global _qa_workflow
    if _qa_workflow is None:
        _qa_workflow = QualityAssuranceWorkflow()
    return _qa_workflow
