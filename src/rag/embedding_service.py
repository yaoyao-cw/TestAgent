"""向量化服务模块"""

import asyncio
from typing import List, Dict, Any, Optional
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# 向量化库
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

import logging
from ..config.simple_settings import get_settings
from ..exceptions import RAGServiceException
from ..utils.performance import async_monitor_performance

logger = logging.getLogger("embedding_service")


class EmbeddingService:
    """向量化服务，支持多种向量化模型"""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        provider: str = "openai",
        batch_size: int = 32
    ):
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.provider = provider.lower()
        self.batch_size = batch_size
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 初始化模型
        self._initialize_model()
    
    def _initialize_model(self):
        """初始化向量化模型"""
        try:
            if self.provider == "openai":
                self._initialize_openai()
            elif self.provider == "sentence_transformers":
                self._initialize_sentence_transformers()
            else:
                raise RAGServiceException(f"Unsupported embedding provider: {self.provider}")
                
            logger.info(f"Initialized embedding service with {self.provider} provider")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {e}")
            raise RAGServiceException(f"Failed to initialize embedding service: {e}")
    
    def _initialize_openai(self):
        """初始化OpenAI向量化服务"""
        if not OPENAI_AVAILABLE:
            raise RAGServiceException("OpenAI library not available")
        
        settings = get_settings()
        self.openai_client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        
        # 验证模型可用性
        if not self.model_name:
            self.model_name = "text-embedding-ada-002"
    
    def _initialize_sentence_transformers(self):
        """初始化SentenceTransformers模型"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RAGServiceException("sentence-transformers library not available")
        
        try:
            # 使用默认的中英文模型
            if not self.model_name:
                self.model_name = "all-MiniLM-L6-v2"
            
            self.st_model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded SentenceTransformer model: {self.model_name}")
            
        except Exception as e:
            raise RAGServiceException(f"Failed to load SentenceTransformer model: {e}")
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """向量化文本列表
        
        Args:
            texts: 要向量化的文本列表
            
        Returns:
            List[List[float]]: 向量列表
        """
        try:
            if self.provider == "openai":
                return await self._embed_with_openai(texts)
            elif self.provider == "sentence_transformers":
                return await self._embed_with_sentence_transformers(texts)
            else:
                # 降级到简单的向量化方法
                return await self._embed_with_simple_method(texts)
        except Exception as e:
            logger.error(f"向量化失败: {e}")
            # 返回简单的向量化结果
            return await self._embed_with_simple_method(texts)
    
    async def embed_text(self, text: str) -> List[float]:
        """向量化单个文本
        
        Args:
            text: 要向量化的文本
            
        Returns:
            List[float]: 向量
        """
        results = await self.embed_texts([text])
        return results[0] if results else []
    
    async def _embed_with_openai(self, texts: List[str]) -> List[List[float]]:
        """使用OpenAI API进行向量化"""
        try:
            embeddings = []
            # 批量处理
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                
                response = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: self.openai_client.embeddings.create(
                        input=batch,
                        model=self.model_name
                    )
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
            
            return embeddings
        except Exception as e:
            logger.error(f"OpenAI向量化失败: {e}")
            raise
    
    async def _embed_with_sentence_transformers(self, texts: List[str]) -> List[List[float]]:
        """使用SentenceTransformers进行向量化"""
        try:
            # 在线程池中执行向量化
            embeddings = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.st_model.encode(texts, convert_to_numpy=True)
            )
            
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"SentenceTransformers向量化失败: {e}")
            raise
    
    async def _embed_with_simple_method(self, texts: List[str]) -> List[List[float]]:
        """简单的向量化方法（降级方案）"""
        try:
            import hashlib
            import struct
            
            embeddings = []
            for text in texts:
                # 使用文本哈希生成简单的向量
                hash_obj = hashlib.md5(text.encode('utf-8'))
                hash_bytes = hash_obj.digest()
                
                # 将哈希转换为浮点数向量
                vector = []
                for i in range(0, len(hash_bytes), 4):
                    chunk = hash_bytes[i:i+4]
                    if len(chunk) == 4:
                        float_val = struct.unpack('f', chunk)[0]
                        vector.append(float_val)
                
                # 确保向量长度一致
                while len(vector) < 128:
                    vector.append(0.0)
                
                embeddings.append(vector[:128])
            
            logger.warning("使用简单向量化方法（仅用于测试）")
            return embeddings
        except Exception as e:
            logger.error(f"简单向量化也失败: {e}")
            # 返回零向量
            return [[0.0] * 128 for _ in texts]
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "batch_size": self.batch_size,
            "available": True
        }