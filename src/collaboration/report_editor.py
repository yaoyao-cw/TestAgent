#!/usr/bin/env python3
"""
报告后编辑API接口
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import re

from ..config.logging_config import get_logger
from ..exceptions import TestAgentException

logger = get_logger("report_editor")


class EditOperation:
    """编辑操作"""
    
    def __init__(
        self,
        operation_type: str,
        target: str,
        content: str,
        position: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ):
        self.operation_type = operation_type  # insert, replace, delete, format
        self.target = target  # section, paragraph, line, etc.
        self.content = content
        self.position = position
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
        self.id = f"edit_{int(self.timestamp.timestamp())}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "operation_type": self.operation_type,
            "target": self.target,
            "content": self.content,
            "position": self.position,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EditOperation":
        """从字典创建"""
        operation = cls(
            operation_type=data["operation_type"],
            target=data["target"],
            content=data["content"],
            position=data.get("position"),
            metadata=data.get("metadata", {})
        )
        operation.id = data["id"]
        operation.timestamp = datetime.fromisoformat(data["timestamp"])
        return operation


class ReportEditor:
    """报告编辑器"""
    
    def __init__(self):
        self.edit_history: Dict[str, List[EditOperation]] = {}
        self.report_versions: Dict[str, List[Dict[str, Any]]] = {}
        self.section_templates = self._init_section_templates()
        
        logger.info("Report editor initialized")
    
    def _init_section_templates(self) -> Dict[str, str]:
        """初始化章节模板"""
        return {
            "executive_summary": """## 执行摘要

### 任务概述
{task_overview}

### 主要发现
{key_findings}

### 建议
{recommendations}
""",
            "test_results": """## 测试结果

### 测试执行情况
- 总测试用例数: {total_cases}
- 通过用例数: {passed_cases}
- 失败用例数: {failed_cases}
- 成功率: {success_rate}%

### 详细结果
{detailed_results}
""",
            "code_analysis": """## 代码分析

### 代码质量评估
{quality_assessment}

### 发现的问题
{issues_found}

### 改进建议
{improvement_suggestions}
""",
            "conclusion": """## 结论

### 总结
{summary}

### 后续行动
{next_actions}
"""
        }
    
    def create_report_version(
        self,
        report_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """创建报告版本
        
        Args:
            report_id: 报告ID
            content: 报告内容
            metadata: 元数据
            
        Returns:
            版本ID
        """
        try:
            version_id = f"v{int(datetime.now().timestamp())}"
            
            if report_id not in self.report_versions:
                self.report_versions[report_id] = []
                self.edit_history[report_id] = []
            
            version_data = {
                "version_id": version_id,
                "content": content,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat(),
                "word_count": len(content.split()),
                "section_count": len(re.findall(r'^#+\s', content, re.MULTILINE))
            }
            
            self.report_versions[report_id].append(version_data)
            
            logger.info(f"已创建报告版本: {report_id}/{version_id}")
            return version_id
            
        except Exception as e:
            logger.error(f"创建报告版本失败: {e}")
            raise TestAgentException(f"创建报告版本失败: {e}")
    
    def edit_report(
        self,
        report_id: str,
        operations: List[EditOperation]
    ) -> Tuple[str, str]:
        """编辑报告
        
        Args:
            report_id: 报告ID
            operations: 编辑操作列表
            
        Returns:
            (新版本ID, 编辑后的内容)
        """
        try:
            if report_id not in self.report_versions:
                raise ValueError(f"报告不存在: {report_id}")
            
            # 获取最新版本的内容
            latest_version = self.report_versions[report_id][-1]
            current_content = latest_version["content"]
            
            # 应用编辑操作
            edited_content = self._apply_edit_operations(current_content, operations)
            
            # 记录编辑历史
            self.edit_history[report_id].extend(operations)
            
            # 创建新版本
            new_version_id = self.create_report_version(
                report_id,
                edited_content,
                {"edit_operations": len(operations)}
            )
            
            logger.info(f"报告编辑完成: {report_id}, 应用了 {len(operations)} 个操作")
            return new_version_id, edited_content
            
        except Exception as e:
            logger.error(f"编辑报告失败: {e}")
            raise TestAgentException(f"编辑报告失败: {e}")
    
    def _apply_edit_operations(
        self,
        content: str,
        operations: List[EditOperation]
    ) -> str:
        """应用编辑操作"""
        lines = content.split('\n')
        
        # 按位置排序操作（从后往前，避免位置偏移）
        sorted_operations = sorted(
            operations,
            key=lambda op: op.position or 0,
            reverse=True
        )
        
        for operation in sorted_operations:
            try:
                if operation.operation_type == "insert":
                    lines = self._apply_insert_operation(lines, operation)
                elif operation.operation_type == "replace":
                    lines = self._apply_replace_operation(lines, operation)
                elif operation.operation_type == "delete":
                    lines = self._apply_delete_operation(lines, operation)
                elif operation.operation_type == "format":
                    lines = self._apply_format_operation(lines, operation)
                
            except Exception as e:
                logger.error(f"应用编辑操作失败 {operation.id}: {e}")
                continue
        
        return '\n'.join(lines)
    
    def _apply_insert_operation(
        self,
        lines: List[str],
        operation: EditOperation
    ) -> List[str]:
        """应用插入操作"""
        if operation.target == "line":
            position = operation.position or len(lines)
            lines.insert(position, operation.content)
        elif operation.target == "section":
            # 在指定章节后插入
            section_line = self._find_section_line(lines, operation.metadata.get("section_name", ""))
            if section_line >= 0:
                lines.insert(section_line + 1, operation.content)
            else:
                lines.append(operation.content)
        
        return lines
    
    def _apply_replace_operation(
        self,
        lines: List[str],
        operation: EditOperation
    ) -> List[str]:
        """应用替换操作"""
        if operation.target == "line":
            position = operation.position or 0
            if 0 <= position < len(lines):
                lines[position] = operation.content
        elif operation.target == "section":
            # 替换整个章节
            start_line, end_line = self._find_section_range(
                lines,
                operation.metadata.get("section_name", "")
            )
            if start_line >= 0 and end_line >= 0:
                lines[start_line:end_line+1] = operation.content.split('\n')
        
        return lines
    
    def _apply_delete_operation(
        self,
        lines: List[str],
        operation: EditOperation
    ) -> List[str]:
        """应用删除操作"""
        if operation.target == "line":
            position = operation.position or 0
            if 0 <= position < len(lines):
                del lines[position]
        elif operation.target == "section":
            # 删除整个章节
            start_line, end_line = self._find_section_range(
                lines,
                operation.metadata.get("section_name", "")
            )
            if start_line >= 0 and end_line >= 0:
                del lines[start_line:end_line+1]
        
        return lines
    
    def _apply_format_operation(
        self,
        lines: List[str],
        operation: EditOperation
    ) -> List[str]:
        """应用格式化操作"""
        format_type = operation.metadata.get("format_type", "")
        
        if format_type == "markdown_table":
            # 格式化为Markdown表格
            table_data = operation.metadata.get("table_data", [])
            formatted_table = self._format_markdown_table(table_data)
            position = operation.position or len(lines)
            lines.insert(position, formatted_table)
        
        elif format_type == "code_block":
            # 格式化为代码块
            language = operation.metadata.get("language", "")
            code_content = operation.content
            formatted_code = f"```{language}\n{code_content}\n```"
            position = operation.position or len(lines)
            lines.insert(position, formatted_code)
        
        elif format_type == "bullet_list":
            # 格式化为项目列表
            items = operation.content.split('\n')
            formatted_items = [f"- {item.strip()}" for item in items if item.strip()]
            position = operation.position or len(lines)
            lines[position:position] = formatted_items
        
        return lines
    
    def _find_section_line(self, lines: List[str], section_name: str) -> int:
        """查找章节行号"""
        for i, line in enumerate(lines):
            if re.match(r'^#+\s+' + re.escape(section_name), line, re.IGNORECASE):
                return i
        return -1
    
    def _find_section_range(self, lines: List[str], section_name: str) -> Tuple[int, int]:
        """查找章节范围"""
        start_line = self._find_section_line(lines, section_name)
        if start_line < 0:
            return -1, -1
        
        # 查找章节结束位置
        section_level = len(re.match(r'^(#+)', lines[start_line]).group(1))
        end_line = len(lines) - 1
        
        for i in range(start_line + 1, len(lines)):
            line = lines[i]
            if re.match(r'^#+\s', line):
                current_level = len(re.match(r'^(#+)', line).group(1))
                if current_level <= section_level:
                    end_line = i - 1
                    break
        
        return start_line, end_line
    
    def _format_markdown_table(self, table_data: List[List[str]]) -> str:
        """格式化Markdown表格"""
        if not table_data:
            return ""
        
        # 计算列宽
        col_widths = []
        for col_idx in range(len(table_data[0])):
            max_width = max(len(str(row[col_idx])) for row in table_data)
            col_widths.append(max(max_width, 3))  # 最小宽度为3
        
        # 生成表格
        lines = []
        
        # 表头
        header_line = "| " + " | ".join(
            str(table_data[0][i]).ljust(col_widths[i])
            for i in range(len(table_data[0]))
        ) + " |"
        lines.append(header_line)
        
        # 分隔线
        separator_line = "| " + " | ".join(
            "-" * col_widths[i] for i in range(len(table_data[0]))
        ) + " |"
        lines.append(separator_line)
        
        # 数据行
        for row in table_data[1:]:
            data_line = "| " + " | ".join(
                str(row[i]).ljust(col_widths[i])
                for i in range(len(row))
            ) + " |"
            lines.append(data_line)
        
        return '\n'.join(lines)
    
    def add_section(
        self,
        report_id: str,
        section_name: str,
        section_type: str,
        content_data: Dict[str, Any],
        position: Optional[int] = None
    ) -> str:
        """添加章节
        
        Args:
            report_id: 报告ID
            section_name: 章节名称
            section_type: 章节类型
            content_data: 内容数据
            position: 插入位置
            
        Returns:
            新版本ID
        """
        try:
            # 获取章节模板
            template = self.section_templates.get(section_type, "## {section_name}\n\n{content}")
            
            # 填充模板
            section_content = template.format(section_name=section_name, **content_data)
            
            # 创建插入操作
            operation = EditOperation(
                operation_type="insert",
                target="section",
                content=section_content,
                position=position,
                metadata={"section_name": section_name, "section_type": section_type}
            )
            
            # 应用编辑
            new_version_id, _ = self.edit_report(report_id, [operation])
            
            logger.info(f"已添加章节: {section_name} 到报告 {report_id}")
            return new_version_id
            
        except Exception as e:
            logger.error(f"添加章节失败: {e}")
            raise TestAgentException(f"添加章节失败: {e}")
    
    def get_report_versions(self, report_id: str) -> List[Dict[str, Any]]:
        """获取报告版本列表"""
        return self.report_versions.get(report_id, [])
    
    def get_report_content(self, report_id: str, version_id: str = None) -> Optional[str]:
        """获取报告内容
        
        Args:
            report_id: 报告ID
            version_id: 版本ID，如果为None则返回最新版本
            
        Returns:
            报告内容或None
        """
        versions = self.report_versions.get(report_id, [])
        if not versions:
            return None
        
        if version_id is None:
            return versions[-1]["content"]
        
        for version in versions:
            if version["version_id"] == version_id:
                return version["content"]
        
        return None
    
    def get_edit_history(self, report_id: str) -> List[Dict[str, Any]]:
        """获取编辑历史"""
        operations = self.edit_history.get(report_id, [])
        return [op.to_dict() for op in operations]
    
    def compare_versions(
        self,
        report_id: str,
        version1_id: str,
        version2_id: str
    ) -> Dict[str, Any]:
        """比较版本差异
        
        Args:
            report_id: 报告ID
            version1_id: 版本1 ID
            version2_id: 版本2 ID
            
        Returns:
            差异信息
        """
        try:
            content1 = self.get_report_content(report_id, version1_id)
            content2 = self.get_report_content(report_id, version2_id)
            
            if content1 is None or content2 is None:
                raise ValueError("版本不存在")
            
            # 简单的差异计算
            lines1 = content1.split('\n')
            lines2 = content2.split('\n')
            
            added_lines = []
            removed_lines = []
            modified_lines = []
            
            # 简化的差异算法
            max_lines = max(len(lines1), len(lines2))
            for i in range(max_lines):
                line1 = lines1[i] if i < len(lines1) else None
                line2 = lines2[i] if i < len(lines2) else None
                
                if line1 is None:
                    added_lines.append({"line": i, "content": line2})
                elif line2 is None:
                    removed_lines.append({"line": i, "content": line1})
                elif line1 != line2:
                    modified_lines.append({
                        "line": i,
                        "old_content": line1,
                        "new_content": line2
                    })
            
            return {
                "version1_id": version1_id,
                "version2_id": version2_id,
                "added_lines": added_lines,
                "removed_lines": removed_lines,
                "modified_lines": modified_lines,
                "total_changes": len(added_lines) + len(removed_lines) + len(modified_lines)
            }
            
        except Exception as e:
            logger.error(f"比较版本差异失败: {e}")
            raise TestAgentException(f"比较版本差异失败: {e}")
    
    def export_report(
        self,
        report_id: str,
        format_type: str = "markdown",
        version_id: str = None
    ) -> str:
        """导出报告
        
        Args:
            report_id: 报告ID
            format_type: 导出格式 (markdown, html, pdf)
            version_id: 版本ID
            
        Returns:
            导出的内容
        """
        try:
            content = self.get_report_content(report_id, version_id)
            if content is None:
                raise ValueError("报告不存在")
            
            if format_type == "markdown":
                return content
            elif format_type == "html":
                return self._convert_to_html(content)
            elif format_type == "pdf":
                # 这里可以集成PDF生成库
                return self._convert_to_pdf(content)
            else:
                raise ValueError(f"不支持的导出格式: {format_type}")
                
        except Exception as e:
            logger.error(f"导出报告失败: {e}")
            raise TestAgentException(f"导出报告失败: {e}")
    
    def _convert_to_html(self, markdown_content: str) -> str:
        """转换为HTML格式"""
        # 简化的Markdown到HTML转换
        html_content = markdown_content
        
        # 转换标题
        html_content = re.sub(r'^### (.*)', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^## (.*)', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^# (.*)', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
        
        # 转换段落
        html_content = re.sub(r'\n\n', '</p>\n<p>', html_content)
        html_content = f'<p>{html_content}</p>'
        
        # 转换列表
        html_content = re.sub(r'^- (.*)', r'<li>\1</li>', html_content, flags=re.MULTILINE)
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TestAgent Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
    
    def _convert_to_pdf(self, markdown_content: str) -> str:
        """转换为PDF格式"""
        # 这里应该集成PDF生成库，如reportlab或weasyprint
        # 目前返回占位符
        return f"PDF conversion not implemented. Content length: {len(markdown_content)} characters"