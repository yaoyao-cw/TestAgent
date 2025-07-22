#!/usr/bin/env python3
"""
文件工具函数
"""

import os
from pathlib import Path
from typing import List


def get_file_extension(file_path: str) -> str:
    """获取文件扩展名"""
    return Path(file_path).suffix.lower()


def is_supported_file(file_path: str) -> bool:
    """检查文件是否支持"""
    supported_extensions = {
        '.txt', '.md', '.pdf', '.docx', '.doc', 
        '.xlsx', '.xls', '.py', '.js', '.html', 
        '.css', '.json', '.xml', '.csv'
    }
    
    extension = get_file_extension(file_path)
    return extension in supported_extensions


def get_file_size(file_path: str) -> int:
    """获取文件大小"""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def ensure_directory(directory: str) -> None:
    """确保目录存在"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def list_files_in_directory(directory: str, extensions: List[str] = None) -> List[str]:
    """列出目录中的文件"""
    directory_path = Path(directory)
    if not directory_path.exists():
        return []
    
    files = []
    for file_path in directory_path.iterdir():
        if file_path.is_file():
            if extensions is None or get_file_extension(str(file_path)) in extensions:
                files.append(str(file_path))
    
    return files