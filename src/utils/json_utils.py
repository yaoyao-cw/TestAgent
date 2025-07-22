"""JSON处理工具函数"""

import json
import re
from typing import Any, Optional, Dict
# from json_repair import repair_json  # 模块不可用时的降级方案

import logging

logger = logging.getLogger("json_utils")


def repair_json_output(json_str: str) -> str:
    """修复可能损坏的JSON字符串
    
    Args:
        json_str: 待修复的JSON字符串
        
    Returns:
        修复后的JSON字符串
        
    Raises:
        ValueError: 如果无法修复JSON
    """
    if not json_str or not json_str.strip():
        raise ValueError("Empty JSON string")
    
    try:
        # 首先尝试直接解析
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        logger.debug("JSON parsing failed, attempting repair")
    
    try:
        # 简单的JSON修复尝试
        repaired = _simple_json_repair(json_str)
        # 验证修复结果
        json.loads(repaired)
        logger.debug("JSON repair successful")
        return repaired
    except Exception as e:
        logger.error(f"JSON repair failed: {e}")
        raise ValueError(f"Unable to repair JSON: {e}")


def _simple_json_repair(json_str: str) -> str:
    """简单的JSON修复方法"""
    # 移除多余的逗号
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # 修复未闭合的引号
    if json_str.count('"') % 2 != 0:
        json_str += '"'
    
    # 修复未闭合的括号
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
    
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')
    if open_brackets > close_brackets:
        json_str += ']' * (open_brackets - close_brackets)
    
    return json_str


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全的JSON解析
    
    Args:
        json_str: JSON字符串
        default: 解析失败时的默认值
        
    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON parsing failed: {e}")
        return default


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取JSON对象
    
    Args:
        text: 包含JSON的文本
        
    Returns:
        提取的JSON对象，如果未找到则返回None
    """
    # 查找JSON代码块
    json_pattern = r'```json\s*(\{.*?\})\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    
    if match:
        json_str = match.group(1)
    else:
        # 查找可能的JSON对象
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        if matches:
            json_str = matches[-1]  # 取最后一个匹配
        else:
            return None
    
    try:
        return safe_json_loads(json_str)
    except Exception:
        return None


def format_json_response(data: Any, indent: int = 2) -> str:
    """格式化JSON响应
    
    Args:
        data: 要格式化的数据
        indent: 缩进空格数
        
    Returns:
        格式化的JSON字符串
    """
    try:
        return json.dumps(
            data,
            ensure_ascii=False,
            indent=indent,
            separators=(',', ': ')
        )
    except TypeError as e:
        logger.error(f"JSON serialization failed: {e}")
        return str(data)