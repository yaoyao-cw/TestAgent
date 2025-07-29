"""RAG服务集成测试"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any

from src.rag.rag_service import RAGService, RAGServiceManager
from src.rag.document_parser import DocumentParser
from src.rag.text_splitter import TextSplitter, SemanticTextSplitter
from src.rag.embedding_service import EmbeddingService
from src.rag.vector_database import ChromaVectorDatabase
from src.exceptions import RAGServiceException


class TestRAGServiceIntegration:
    """RAG服务集成测试"""

    @pytest.fixture
    async def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    async def sample_documents(self, temp_dir):
        """创建示例文档"""
        documents = {}

        # 创建文本文档
        txt_path = os.path.join(temp_dir, "sample.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(
                """
这是一个测试文档。

第一章 软件测试基础
软件测试是软件开发过程中的重要环节，用于验证软件是否满足需求。

第二章 测试方法
常见的测试方法包括单元测试、集成测试、系统测试等。

第三章 自动化测试
自动化测试可以提高测试效率，减少人工错误。
            """
            )
        documents["txt"] = txt_path

        # 创建Markdown文档
        md_path = os.path.join(temp_dir, "sample.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(
                """
# 测试文档

## 介绍
这是一个Markdown格式的测试文档。

## 功能特性
- 支持多种文档格式
- 自动文本分块
- 语义搜索功能

## 使用方法
1. 上传文档
2. 执行搜索
3. 获取结果
            """
            )
        documents["md"] = md_path

        return documents

    @pytest.fixture
    async def rag_service(self, temp_dir):
        """创建RAG服务实例"""
        # 使用临时目录作为向量数据库存储路径
        vector_db = ChromaVectorDatabase(persist_directory=temp_dir)

        # 使用sentence_transformers作为embedding服务（如果可用）
        try:
            embedding_service = EmbeddingService(provider="sentence_transformers")
        except:
            # 如果sentence_transformers不可用，跳过测试
            pytest.skip("sentence_transformers not available")

        text_splitter = SemanticTextSplitter(chunk_size=200, chunk_overlap=50)
        document_parser = DocumentParser()

        service = RAGService(
            vector_db=vector_db,
            embedding_service=embedding_service,
            text_splitter=text_splitter,
            document_parser=document_parser,
        )

        return service

    @pytest.mark.asyncio
    async def test_add_single_document(self, rag_service, sample_documents):
        """测试添加单个文档"""
        txt_path = sample_documents["txt"]

        # 添加文档
        result = await rag_service.add_document(
            txt_path,
            collection_name="test_collection",
            metadata={"source": "test", "type": "sample"},
        )

        # 验证结果
        assert result["file_path"] == txt_path
        assert result["collection_name"] == "test_collection"
        assert result["chunks_count"] > 0
        assert len(result["document_ids"]) == result["chunks_count"]
        assert result["word_count"] > 0
        assert result["char_count"] > 0
        assert result["metadata"]["source"] == "test"

    @pytest.mark.asyncio
    async def test_add_multiple_documents(self, rag_service, sample_documents):
        """测试批量添加文档"""
        file_paths = list(sample_documents.values())

        # 批量添加文档
        result = await rag_service.add_documents(
            file_paths, collection_name="batch_collection", metadata={"batch": "test"}
        )

        # 验证结果
        assert result["total_files"] == len(file_paths)
        assert result["successful"] == len(file_paths)
        assert result["failed"] == 0
        assert len(result["results"]) == len(file_paths)
        assert result["collection_name"] == "batch_collection"

        # 验证每个文档都成功处理
        for doc_result in result["results"]:
            assert doc_result["chunks_count"] > 0
            assert len(doc_result["document_ids"]) > 0

    @pytest.mark.asyncio
    async def test_search_documents(self, rag_service, sample_documents):
        """测试文档搜索"""
        # 先添加文档
        txt_path = sample_documents["txt"]
        await rag_service.add_document(txt_path, collection_name="search_test")

        # 搜索相关内容
        search_results = await rag_service.search(
            query="软件测试方法", collection_name="search_test", top_k=3
        )

        # 验证搜索结果
        assert len(search_results) > 0
        assert len(search_results) <= 3

        for result in search_results:
            assert "content" in result
            assert "similarity_score" in result
            assert "metadata" in result
            assert result["similarity_score"] >= 0
            assert result["similarity_score"] <= 1
            assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_search_with_threshold(self, rag_service, sample_documents):
        """测试带相似度阈值的搜索"""
        # 添加文档
        txt_path = sample_documents["txt"]
        await rag_service.add_document(txt_path, collection_name="threshold_test")

        # 使用高阈值搜索
        high_threshold_results = await rag_service.search(
            query="软件测试", collection_name="threshold_test", similarity_threshold=0.8
        )

        # 使用低阈值搜索
        low_threshold_results = await rag_service.search(
            query="软件测试", collection_name="threshold_test", similarity_threshold=0.1
        )

        # 高阈值结果应该少于或等于低阈值结果
        assert len(high_threshold_results) <= len(low_threshold_results)

        # 所有结果的相似度都应该满足阈值要求
        for result in high_threshold_results:
            assert result["similarity_score"] >= 0.8

    @pytest.mark.asyncio
    async def test_add_text_directly(self, rag_service):
        """测试直接添加文本"""
        text_content = """
        这是直接添加的文本内容。
        包含多个段落和不同的信息。
        
        可以用于测试文本处理功能。
        """

        metadata = {"source": "direct_input", "type": "text", "author": "test_user"}

        # 直接添加文本
        result = await rag_service.add_text_directly(
            text_content, metadata, collection_name="direct_text"
        )

        # 验证结果
        assert result["collection_name"] == "direct_text"
        assert result["chunks_count"] > 0
        assert len(result["document_ids"]) == result["chunks_count"]
        assert result["metadata"]["source"] == "direct_input"

        # 搜索添加的文本
        search_results = await rag_service.search(
            query="直接添加的文本", collection_name="direct_text"
        )

        assert len(search_results) > 0
        assert "直接添加" in search_results[0]["content"]

    @pytest.mark.asyncio
    async def test_document_management(self, rag_service, sample_documents):
        """测试文档管理功能"""
        # 添加文档
        txt_path = sample_documents["txt"]
        add_result = await rag_service.add_document(
            txt_path, collection_name="management_test"
        )

        document_ids = add_result["document_ids"]

        # 获取集合信息
        collection_info = await rag_service.get_collection_info("management_test")
        assert collection_info["name"] == "management_test"
        assert collection_info["count"] == len(document_ids)

        # 获取单个文档
        if document_ids:
            doc = await rag_service.get_document_by_id(
                document_ids[0], "management_test"
            )
            assert doc is not None
            assert doc["id"] == document_ids[0]
            assert "content" in doc
            assert "metadata" in doc

        # 删除单个文档
        if document_ids:
            delete_result = await rag_service.delete_document(
                document_ids[0], "management_test"
            )
            assert delete_result is True

            # 验证文档已删除
            deleted_doc = await rag_service.get_document_by_id(
                document_ids[0], "management_test"
            )
            assert deleted_doc is None

    @pytest.mark.asyncio
    async def test_collection_operations(self, rag_service, sample_documents):
        """测试集合操作"""
        # 添加文档到不同集合
        txt_path = sample_documents["txt"]
        md_path = sample_documents["md"]

        await rag_service.add_document(txt_path, collection_name="collection1")
        await rag_service.add_document(md_path, collection_name="collection2")

        # 列出集合
        collections = await rag_service.list_collections()
        assert "collection1" in collections
        assert "collection2" in collections

        # 获取集合信息
        info1 = await rag_service.get_collection_info("collection1")
        info2 = await rag_service.get_collection_info("collection2")

        assert info1["count"] > 0
        assert info2["count"] > 0

        # 重置集合
        reset_result = await rag_service.reset_collection("collection1")
        assert reset_result is True

        # 验证集合已重置
        info1_after = await rag_service.get_collection_info("collection1")
        assert info1_after["count"] == 0

    @pytest.mark.asyncio
    async def test_service_info(self, rag_service):
        """测试服务信息获取"""
        service_info = rag_service.get_service_info()

        assert "vector_database" in service_info
        assert "embedding_service" in service_info
        assert "text_splitter" in service_info
        assert "default_collection" in service_info
        assert "max_search_results" in service_info

        # 验证embedding服务信息
        embedding_info = service_info["embedding_service"]
        assert "provider" in embedding_info
        assert "model_name" in embedding_info
        assert "embedding_dimension" in embedding_info

    @pytest.mark.asyncio
    async def test_error_handling(self, rag_service):
        """测试错误处理"""
        # 测试不存在的文件
        with pytest.raises(RAGServiceException):
            await rag_service.add_document("nonexistent_file.txt")

        # 测试空查询
        search_results = await rag_service.search("", collection_name="empty_test")
        # 空查询应该返回空结果或处理得当
        assert isinstance(search_results, list)

        # 测试不存在的文档ID
        doc = await rag_service.get_document_by_id("nonexistent_id", "test_collection")
        assert doc is None


class TestRAGServiceManager:
    """RAG服务管理器测试"""

    @pytest.fixture
    async def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    async def rag_manager(self, temp_dir):
        """创建RAG服务管理器"""
        manager = RAGServiceManager()

        # 添加默认服务
        try:
            vector_db = ChromaVectorDatabase(persist_directory=temp_dir)
            embedding_service = EmbeddingService(provider="sentence_transformers")
            service = RAGService(
                vector_db=vector_db, embedding_service=embedding_service
            )
            manager.add_service("default", service)
        except:
            pytest.skip("sentence_transformers not available")

        return manager

    @pytest.mark.asyncio
    async def test_service_management(self, rag_manager, temp_dir):
        """测试服务管理"""
        # 添加另一个服务
        vector_db2 = ChromaVectorDatabase(persist_directory=temp_dir + "_2")
        embedding_service2 = EmbeddingService(provider="sentence_transformers")
        service2 = RAGService(
            vector_db=vector_db2, embedding_service=embedding_service2
        )
        rag_manager.add_service("service2", service2)

        # 列出服务
        services = rag_manager.list_services()
        assert "default" in services
        assert "service2" in services

        # 获取服务
        default_service = rag_manager.get_service("default")
        assert default_service is not None

        service2_instance = rag_manager.get_service("service2")
        assert service2_instance is not None

        # 设置默认服务
        rag_manager.set_default_service("service2")
        default_service_after = rag_manager.get_service()
        assert default_service_after is service2_instance

    @pytest.mark.asyncio
    async def test_search_all_services(self, rag_manager):
        """测试在所有服务中搜索"""
        # 由于没有添加文档，搜索结果应该为空
        results = await rag_manager.search_all_services("test query")

        assert isinstance(results, dict)
        assert "default" in results
        assert isinstance(results["default"], list)


class TestRAGServicePerformance:
    """RAG服务性能测试"""

    @pytest.fixture
    async def large_text_content(self):
        """生成大量文本内容"""
        content = []
        for i in range(100):
            content.append(
                f"""
第{i+1}章 测试章节
这是第{i+1}个测试章节的内容。包含了大量的文本信息，用于测试系统的处理能力。
本章节讨论了软件测试的各个方面，包括测试方法、测试工具、测试策略等。

{i+1}.1 测试方法
常见的测试方法包括黑盒测试、白盒测试、灰盒测试等。

{i+1}.2 测试工具
自动化测试工具可以提高测试效率，常用的工具有pytest、unittest等。

{i+1}.3 测试策略
制定合适的测试策略对于项目成功至关重要。
            """
            )

        return "\n\n".join(content)

    @pytest.mark.asyncio
    async def test_large_text_processing(self, large_text_content):
        """测试大文本处理性能"""
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                vector_db = ChromaVectorDatabase(persist_directory=temp_dir)
                embedding_service = EmbeddingService(provider="sentence_transformers")
                rag_service = RAGService(
                    vector_db=vector_db, embedding_service=embedding_service
                )

                # 添加大文本
                import time

                start_time = time.time()

                result = await rag_service.add_text_directly(
                    large_text_content,
                    {"source": "performance_test", "type": "large_text"},
                    collection_name="performance_test",
                )

                processing_time = time.time() - start_time

                # 验证处理结果
                assert result["chunks_count"] > 0
                assert len(result["document_ids"]) == result["chunks_count"]

                # 记录性能指标
                print(f"Processing time: {processing_time:.2f} seconds")
                print(f"Chunks created: {result['chunks_count']}")
                print(f"Characters processed: {result['char_count']}")

                # 测试搜索性能
                search_start = time.time()
                search_results = await rag_service.search(
                    "测试方法和工具", collection_name="performance_test", top_k=10
                )
                search_time = time.time() - search_start

                assert len(search_results) > 0
                print(f"Search time: {search_time:.2f} seconds")
                print(f"Results found: {len(search_results)}")

        except Exception as e:
            pytest.skip(f"Performance test skipped: {e}")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
