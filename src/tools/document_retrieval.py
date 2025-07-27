"""文档检索工具模块"""

import asyncio
from typing import Any, Dict, List, Optional

from ..config.logging_config import get_logger
from ..exceptions import RAGServiceException
from ..rag.rag_service import RAGService
from ..utils.performance import async_monitor_performance

logger = get_logger("document_retrieval")


class DocumentRetrievalTool:
    """文档检索工具，为智能体提供文档搜索和检索功能"""

    def __init__(self, rag_service: RAGService):
        """初始化文档检索工具

        Args:
            rag_service: RAG服务实例
        """
        self.rag_service = rag_service
        self.name = "document_retrieval"
        self.description = "搜索和检索相关文档内容"

    @async_monitor_performance
    async def search_documents(
        self,
        query: str,
        collection_name: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """搜索相关文档

        Args:
            query: 搜索查询
            collection_name: 集合名称
            top_k: 返回结果数量
            similarity_threshold: 相似度阈值
            include_metadata: 是否包含元数据

        Returns:
            搜索结果
        """
        try:
            logger.info(f"Searching documents for query: {query}")

            results = await self.rag_service.search(
                query=query,
                collection_name=collection_name,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                include_metadata=include_metadata,
            )

            return {
                "success": True,
                "query": query,
                "collection": collection_name or "default",
                "results_count": len(results),
                "results": results,
                "parameters": {
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                },
            }

        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results_count": 0,
                "results": [],
            }

    @async_monitor_performance
    async def get_document_by_id(
        self, document_id: str, collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """根据ID获取文档

        Args:
            document_id: 文档ID
            collection_name: 集合名称

        Returns:
            文档信息
        """
        try:
            logger.info(f"Retrieving document: {document_id}")

            document = await self.rag_service.get_document_by_id(
                document_id, collection_name
            )

            if document:
                return {
                    "success": True,
                    "document_id": document_id,
                    "collection": collection_name or "default",
                    "document": document,
                }
            else:
                return {
                    "success": False,
                    "error": "Document not found",
                    "document_id": document_id,
                    "document": None,
                }

        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "document_id": document_id,
                "document": None,
            }

    @async_monitor_performance
    async def search_by_keywords(
        self,
        keywords: List[str],
        collection_name: Optional[str] = None,
        top_k: int = 5,
        combine_results: bool = True,
    ) -> Dict[str, Any]:
        """根据关键词搜索文档

        Args:
            keywords: 关键词列表
            collection_name: 集合名称
            top_k: 每个关键词返回的结果数量
            combine_results: 是否合并结果

        Returns:
            搜索结果
        """
        try:
            logger.info(f"Searching by keywords: {keywords}")

            all_results = {}
            combined_results = []

            # 为每个关键词搜索
            for keyword in keywords:
                results = await self.rag_service.search(
                    query=keyword, collection_name=collection_name, top_k=top_k
                )
                all_results[keyword] = results

                if combine_results:
                    combined_results.extend(results)

            # 如果合并结果，去重并按相似度排序
            if combine_results:
                seen_ids = set()
                unique_results = []

                for result in combined_results:
                    result_id = result.get("chunk_id", "")
                    if result_id not in seen_ids:
                        seen_ids.add(result_id)
                        unique_results.append(result)

                # 按相似度排序
                unique_results.sort(
                    key=lambda x: x.get("similarity_score", 0), reverse=True
                )

                return {
                    "success": True,
                    "keywords": keywords,
                    "collection": collection_name or "default",
                    "combined_results": unique_results[: top_k * 2],  # 返回更多结果
                    "keyword_results": all_results,
                    "total_unique_results": len(unique_results),
                }
            else:
                return {
                    "success": True,
                    "keywords": keywords,
                    "collection": collection_name or "default",
                    "keyword_results": all_results,
                    "total_keywords": len(keywords),
                }

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "keywords": keywords,
                "keyword_results": {},
            }

    @async_monitor_performance
    async def search_similar_content(
        self,
        reference_content: str,
        collection_name: Optional[str] = None,
        top_k: int = 5,
        exclude_exact_match: bool = True,
    ) -> Dict[str, Any]:
        """搜索与参考内容相似的文档

        Args:
            reference_content: 参考内容
            collection_name: 集合名称
            top_k: 返回结果数量
            exclude_exact_match: 是否排除完全匹配的内容

        Returns:
            相似内容搜索结果
        """
        try:
            logger.info(f"Searching for similar content")

            results = await self.rag_service.search(
                query=reference_content,
                collection_name=collection_name,
                top_k=top_k
                + (5 if exclude_exact_match else 0),  # 多获取一些结果用于过滤
            )

            # 如果需要排除完全匹配，过滤结果
            if exclude_exact_match:
                filtered_results = []
                for result in results:
                    # 简单的完全匹配检查
                    if result["content"].strip() != reference_content.strip():
                        filtered_results.append(result)
                        if len(filtered_results) >= top_k:
                            break
                results = filtered_results

            return {
                "success": True,
                "reference_content_length": len(reference_content),
                "collection": collection_name or "default",
                "results_count": len(results),
                "results": results,
                "exclude_exact_match": exclude_exact_match,
            }

        except Exception as e:
            logger.error(f"Similar content search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results_count": 0,
                "results": [],
            }

    @async_monitor_performance
    async def get_collection_summary(
        self, collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取集合摘要信息

        Args:
            collection_name: 集合名称

        Returns:
            集合摘要信息
        """
        try:
            logger.info(f"Getting collection summary")

            # 获取集合基本信息
            collection_info = await self.rag_service.get_collection_info(
                collection_name
            )

            # 获取服务信息
            service_info = self.rag_service.get_service_info()

            return {
                "success": True,
                "collection_info": collection_info,
                "service_info": service_info,
                "available_collections": await self.rag_service.list_collections(),
            }

        except Exception as e:
            logger.error(f"Failed to get collection summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "collection_info": {},
                "service_info": {},
            }

    @async_monitor_performance
    async def batch_search(
        self, queries: List[str], collection_name: Optional[str] = None, top_k: int = 3
    ) -> Dict[str, Any]:
        """批量搜索多个查询

        Args:
            queries: 查询列表
            collection_name: 集合名称
            top_k: 每个查询返回的结果数量

        Returns:
            批量搜索结果
        """
        try:
            logger.info(f"Batch searching {len(queries)} queries")

            # 并发执行搜索
            tasks = []
            for query in queries:
                task = asyncio.create_task(
                    self.rag_service.search(
                        query=query, collection_name=collection_name, top_k=top_k
                    )
                )
                tasks.append((query, task))

            # 收集结果
            batch_results = {}
            total_results = 0

            for query, task in tasks:
                try:
                    results = await task
                    batch_results[query] = {
                        "success": True,
                        "results": results,
                        "count": len(results),
                    }
                    total_results += len(results)
                except Exception as e:
                    batch_results[query] = {
                        "success": False,
                        "error": str(e),
                        "results": [],
                        "count": 0,
                    }

            return {
                "success": True,
                "total_queries": len(queries),
                "total_results": total_results,
                "collection": collection_name or "default",
                "batch_results": batch_results,
            }

        except Exception as e:
            logger.error(f"Batch search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_queries": len(queries),
                "batch_results": {},
            }

    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": self.name,
            "description": self.description,
            "available_methods": [
                "search_documents",
                "get_document_by_id",
                "search_by_keywords",
                "search_similar_content",
                "get_collection_summary",
                "batch_search",
            ],
            "rag_service_info": self.rag_service.get_service_info(),
        }


class DocumentRetrievalToolFactory:
    """文档检索工具工厂"""

    @staticmethod
    def create_tool(rag_service: RAGService) -> DocumentRetrievalTool:
        """创建文档检索工具实例

        Args:
            rag_service: RAG服务实例

        Returns:
            文档检索工具实例
        """
        return DocumentRetrievalTool(rag_service)

    @staticmethod
    def create_multiple_tools(
        rag_services: Dict[str, RAGService],
    ) -> Dict[str, DocumentRetrievalTool]:
        """创建多个文档检索工具实例

        Args:
            rag_services: RAG服务实例字典

        Returns:
            文档检索工具实例字典
        """
        tools = {}
        for name, service in rag_services.items():
            tools[name] = DocumentRetrievalTool(service)
        return tools


# 工具装饰器，用于智能体调用
def document_search_tool(rag_service: RAGService):
    """文档搜索工具装饰器"""
    tool = DocumentRetrievalTool(rag_service)

    async def search_wrapper(
        query: str, collection_name: Optional[str] = None, top_k: int = 5
    ) -> str:
        """搜索文档的包装函数，返回格式化的结果"""
        result = await tool.search_documents(
            query=query, collection_name=collection_name, top_k=top_k
        )

        if result["success"]:
            if result["results"]:
                formatted_results = []
                for i, doc in enumerate(result["results"], 1):
                    formatted_results.append(
                        f"{i}. 相似度: {doc['similarity_score']:.3f}\n"
                        f"   内容: {doc['content'][:200]}...\n"
                        f"   来源: {doc.get('metadata', {}).get('file_name', 'Unknown')}\n"
                    )

                return f"找到 {len(result['results'])} 个相关文档:\n\n" + "\n".join(
                    formatted_results
                )
            else:
                return f"未找到与查询 '{query}' 相关的文档"
        else:
            return f"搜索失败: {result['error']}"

    return search_wrapper


def keyword_search_tool(rag_service: RAGService):
    """关键词搜索工具装饰器"""
    tool = DocumentRetrievalTool(rag_service)

    async def keyword_wrapper(
        keywords: str,  # 逗号分隔的关键词
        collection_name: Optional[str] = None,
        top_k: int = 3,
    ) -> str:
        """关键词搜索的包装函数"""
        keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]

        result = await tool.search_by_keywords(
            keywords=keyword_list,
            collection_name=collection_name,
            top_k=top_k,
            combine_results=True,
        )

        if result["success"]:
            combined_results = result.get("combined_results", [])
            if combined_results:
                formatted_results = []
                for i, doc in enumerate(combined_results[:10], 1):  # 最多显示10个结果
                    formatted_results.append(
                        f"{i}. 相似度: {doc['similarity_score']:.3f}\n"
                        f"   内容: {doc['content'][:150]}...\n"
                    )

                return (
                    f"关键词 {keyword_list} 搜索结果 ({len(combined_results)} 个):\n\n"
                    + "\n".join(formatted_results)
                )
            else:
                return f"未找到包含关键词 {keyword_list} 的文档"
        else:
            return f"关键词搜索失败: {result['error']}"

    return keyword_wrapper
