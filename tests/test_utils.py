"""工具函数测试"""

import pytest
import json
import tempfile
from pathlib import Path

from src.utils.json_utils import (
    repair_json_output,
    safe_json_loads,
    extract_json_from_text,
)
from src.utils.file_utils import ensure_directory, get_file_extension, is_supported_file
from src.utils.performance import timer, performance_tracker


class TestJsonUtils:
    """JSON工具测试"""

    def test_repair_json_output_valid(self):
        """测试修复有效JSON"""
        valid_json = '{"key": "value"}'
        result = repair_json_output(valid_json)
        assert result == valid_json

    def test_repair_json_output_invalid(self):
        """测试修复无效JSON"""
        invalid_json = '{"key": "value"'  # 缺少结束括号
        result = repair_json_output(invalid_json)
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_safe_json_loads_valid(self):
        """测试安全JSON解析 - 有效JSON"""
        valid_json = '{"key": "value"}'
        result = safe_json_loads(valid_json)
        assert result == {"key": "value"}

    def test_safe_json_loads_invalid(self):
        """测试安全JSON解析 - 无效JSON"""
        invalid_json = '{"key": "value"'
        result = safe_json_loads(invalid_json, default={})
        assert result == {}

    def test_extract_json_from_text(self):
        """测试从文本中提取JSON"""
        text = """
        Here is some text with JSON:
        ```json
        {"task": "test", "status": "complete"}
        ```
        More text here.
        """
        result = extract_json_from_text(text)
        assert result == {"task": "test", "status": "complete"}


class TestFileUtils:
    """文件工具测试"""

    def test_ensure_directory(self):
        """测试确保目录存在"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_dir = Path(tmp_dir) / "test" / "nested"
            result = ensure_directory(str(test_dir))
            assert result.exists()
            assert result.is_dir()

    def test_get_file_extension(self):
        """测试获取文件扩展名"""
        assert get_file_extension("test.pdf") == ".pdf"
        assert get_file_extension("test.DOCX") == ".docx"
        assert get_file_extension("test") == ""

    def test_is_supported_file(self):
        """测试文件格式支持检查"""
        assert is_supported_file("test.pdf") is True
        assert is_supported_file("test.docx") is True
        assert is_supported_file("test.xyz") is False


class TestPerformance:
    """性能工具测试"""

    def test_timer_context(self):
        """测试计时器上下文"""
        performance_tracker.clear()

        with timer("test_operation"):
            pass  # 模拟操作

        stats = performance_tracker.get_stats("test_operation")
        assert stats is not None
        assert stats["count"] == 1
        assert stats["success_count"] == 1
        assert stats["success_rate"] == 1.0

    def test_timer_context_with_exception(self):
        """测试计时器上下文异常处理"""
        performance_tracker.clear()

        try:
            with timer("test_operation_fail"):
                raise ValueError("Test error")
        except ValueError:
            pass

        stats = performance_tracker.get_stats("test_operation_fail")
        assert stats is None  # 因为没有成功的记录


if __name__ == "__main__":
    pytest.main([__file__])
