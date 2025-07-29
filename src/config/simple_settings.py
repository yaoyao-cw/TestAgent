#!/usr/bin/env python3
"""
简化的配置设置
"""

import os
from typing import Optional


class SimpleSettings:
    """简化的配置类"""

    def __init__(self):
        # LLM配置
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL")

        # RAG配置
        self.vector_db_persist_directory = os.getenv(
            "VECTOR_DB_PATH", "./data/vectordb"
        )
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
        self.max_search_results = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
        self.default_collection_name = os.getenv("DEFAULT_COLLECTION", "default")


# 全局设置实例
_settings_instance = None


def get_settings() -> SimpleSettings:
    """获取设置实例（单例模式）"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = SimpleSettings()
    return _settings_instance


# 为了兼容性，创建别名
Settings = SimpleSettings
LoggingSettings = SimpleSettings
LLMSettings = SimpleSettings
VectorDBSettings = SimpleSettings
MCPSettings = SimpleSettings
CollaborationSettings = SimpleSettings
APISettings = SimpleSettings
CacheSettings = SimpleSettings

settings = get_settings()
reload_settings = get_settings
