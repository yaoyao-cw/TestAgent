"""RAG知识库服务模块

提供统一的RAG服务接口和多服务管理功能
"""

# 导出核心接口
from .interfaces import RAGServiceInterface, Document, SearchResult, ServiceHealthInfo, RAGServiceStatus

# 导出适配器
from .adapters import ChromaDBAdapter, RAGFlowAdapter, QAnythingAdapter, CustomRAGAdapter

# 导出管理器
from .service_manager import RAGServiceManager, ServiceConfig, ServicePriority
from .config_manager import RAGConfigManager

# 导出原有组件（向后兼容）
from .rag_service import RAGService, RAGServiceManager as LegacyRAGServiceManager
from .vector_database import VectorDatabase, ChromaVectorDatabase
from .embedding_service import EmbeddingService
from .document_parser import DocumentParser
from .text_splitter import TextSplitter, SemanticTextSplitter, TextChunk

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
    "TextChunk"
]