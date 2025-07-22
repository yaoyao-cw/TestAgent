"""文本分块器模块"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import logging
from ..config.simple_settings import get_settings

logger = logging.getLogger("text_splitter")


@dataclass
class TextChunk:
    """文本块数据类"""
    content: str
    metadata: Dict[str, Any]
    start_index: int
    end_index: int
    chunk_id: str


class TextSplitter:
    """文本分块器，将长文本分割成适合向量化的块"""
    
    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        separators: Optional[List[str]] = None
    ):
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        
        # 默认分隔符，按优先级排序
        self.separators = separators or [
            "\n\n",  # 段落分隔
            "\n",    # 行分隔
            "。",    # 中文句号
            ".",     # 英文句号
            "！",    # 中文感叹号
            "!",     # 英文感叹号
            "？",    # 中文问号
            "?",     # 英文问号
            "；",    # 中文分号
            ";",     # 英文分号
            "，",    # 中文逗号
            ",",     # 英文逗号
            " ",     # 空格
            ""       # 字符级分割
        ]
    
    def split_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[TextChunk]:
        """分割文本为块
        
        Args:
            text: 要分割的文本
            metadata: 文档元数据
            
        Returns:
            文本块列表
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        chunks = []
        
        # 预处理文本
        text = self._preprocess_text(text)
        
        # 如果文本长度小于块大小，直接返回
        if len(text) <= self.chunk_size:
            chunk = TextChunk(
                content=text,
                metadata=metadata,
                start_index=0,
                end_index=len(text),
                chunk_id=f"{metadata.get('file_name', 'unknown')}_chunk_0"
            )
            return [chunk]
        
        # 递归分割文本
        text_chunks = self._split_text_recursive(text, self.separators)
        
        # 创建TextChunk对象
        current_index = 0
        for i, chunk_text in enumerate(text_chunks):
            chunk = TextChunk(
                content=chunk_text,
                metadata={**metadata, "chunk_index": i},
                start_index=current_index,
                end_index=current_index + len(chunk_text),
                chunk_id=f"{metadata.get('file_name', 'unknown')}_chunk_{i}"
            )
            chunks.append(chunk)
            current_index += len(chunk_text)
        
        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        # 移除多余的空白字符
        text = re.sub(r'\n\s*\n', '\n\n', text)  # 规范化段落分隔
        text = re.sub(r' +', ' ', text)  # 合并多个空格
        text = text.strip()
        
        return text
    
    def _split_text_recursive(self, text: str, separators: List[str]) -> List[str]:
        """递归分割文本"""
        if not separators:
            # 如果没有分隔符，按字符分割
            return self._split_by_character(text)
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        if separator == "":
            # 字符级分割
            return self._split_by_character(text)
        
        # 按当前分隔符分割
        splits = text.split(separator)
        
        # 重新组合分割后的文本
        chunks = []
        current_chunk = ""
        
        for i, split in enumerate(splits):
            # 添加分隔符（除了最后一个）
            if i < len(splits) - 1:
                split_with_sep = split + separator
            else:
                split_with_sep = split
            
            # 检查当前块加上新分割是否超过大小限制
            if len(current_chunk + split_with_sep) <= self.chunk_size:
                current_chunk += split_with_sep
            else:
                # 如果当前块不为空，添加到结果中
                if current_chunk:
                    chunks.append(current_chunk)
                
                # 如果单个分割就超过大小限制，需要进一步分割
                if len(split_with_sep) > self.chunk_size:
                    sub_chunks = self._split_text_recursive(split_with_sep, remaining_separators)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = split_with_sep
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)
        
        # 处理重叠
        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._add_overlap(chunks)
        
        return chunks
    
    def _split_by_character(self, text: str) -> List[str]:
        """按字符分割文本"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
        
        return chunks
    
    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """为文本块添加重叠"""
        if not chunks or self.chunk_overlap <= 0:
            return chunks
        
        overlapped_chunks = [chunks[0]]
        
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            current_chunk = chunks[i]
            
            # 从前一个块的末尾取重叠部分
            if len(prev_chunk) > self.chunk_overlap:
                overlap = prev_chunk[-self.chunk_overlap:]
                overlapped_chunk = overlap + current_chunk
            else:
                overlapped_chunk = current_chunk
            
            overlapped_chunks.append(overlapped_chunk)
        
        return overlapped_chunks
    
    def split_documents(self, documents: List[Dict[str, Any]]) -> List[TextChunk]:
        """批量分割多个文档
        
        Args:
            documents: 文档列表，每个文档包含content和metadata
            
        Returns:
            所有文档的文本块列表
        """
        all_chunks = []
        
        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            
            if content:
                chunks = self.split_text(content, metadata)
                all_chunks.extend(chunks)
        
        logger.info(f"Split {len(documents)} documents into {len(all_chunks)} chunks")
        return all_chunks
    
    def get_chunk_statistics(self, chunks: List[TextChunk]) -> Dict[str, Any]:
        """获取分块统计信息"""
        if not chunks:
            return {
                "total_chunks": 0,
                "total_characters": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0
            }
        
        chunk_sizes = [len(chunk.content) for chunk in chunks]
        
        return {
            "total_chunks": len(chunks),
            "total_characters": sum(chunk_sizes),
            "avg_chunk_size": sum(chunk_sizes) / len(chunk_sizes),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes),
            "chunk_size_setting": self.chunk_size,
            "chunk_overlap_setting": self.chunk_overlap
        }


class SemanticTextSplitter(TextSplitter):
    """语义感知的文本分块器"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 语义边界标识符
        self.semantic_separators = [
            "\n# ",      # Markdown标题
            "\n## ",     # Markdown二级标题
            "\n### ",    # Markdown三级标题
            "\n#### ",   # Markdown四级标题
            "\n第",      # 中文章节
            "\n一、",    # 中文编号
            "\n二、",
            "\n三、",
            "\n四、",
            "\n五、",
            "\n1.",      # 数字编号
            "\n2.",
            "\n3.",
            "\n4.",
            "\n5.",
        ]
    
    def split_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[TextChunk]:
        """语义感知的文本分割"""
        # 首先尝试按语义边界分割
        semantic_separators = self.semantic_separators + self.separators
        return super().split_text(text, metadata)
    
    def _preprocess_text(self, text: str) -> str:
        """增强的文本预处理"""
        text = super()._preprocess_text(text)
        
        # 保护重要的语义标记
        text = re.sub(r'\n(#+\s)', r'\n\n\1', text)  # Markdown标题前加空行
        text = re.sub(r'\n([第一二三四五六七八九十]+[、.])', r'\n\n\1', text)  # 中文章节前加空行
        text = re.sub(r'\n(\d+\.)', r'\n\n\1', text)  # 数字列表前加空行
        
        return text