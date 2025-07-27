"""RAG知识库服务模块

提供统一的RAG服务接口和多服务管理功能
"""

# 导出适配器
from .adapters import (
    ChromaDBAdapter,
    CustomRAGAdapter,
    QAnythingAdapter,
    RAGFlowAdapter,
)
from .config_manager import RAGConfigManager
from .document_parser import DocumentParser
from .embedding_service import EmbeddingService

# 导出核心接口
from .interfaces import (
    Document,
    RAGServiceInterface,
    RAGServiceStatus,
    SearchResult,
    ServiceHealthInfo,
)

# 导出原有组件（向后兼容）
from .rag_service import RAGService
from .rag_service import RAGServiceManager as LegacyRAGServiceManager

# 导出管理器
from .service_manager import RAGServiceManager, ServiceConfig, ServicePriority
from .text_splitter import SemanticTextSplitter, TextChunk, TextSplitter
from .vector_database import ChromaVectorDatabase, VectorDatabase

__all__ = [
    # 核心接口
    "RAGServiceInterface",
    "Document",
    "SearchResult",
    "ServiceHealthInfo",
    "RAGServiceStatus",
    # 适配器
    "ChromaDBAdapter",
    "RAGFlowAdapter",
    "QAnythingAdapter",
    "CustomRAGAdapter",
    # 管理器
    "RAGServiceManager",
    "ServiceConfig",
    "ServicePriority",
    "RAGConfigManager",
    # 向后兼容
    "RAGService",
    "LegacyRAGServiceManager",
    "VectorDatabase",
    "ChromaVectorDatabase",
    "EmbeddingService",
    "DocumentParser",
    "TextSplitter",
    "SemanticTextSplitter",
    "TextChunk",
]
