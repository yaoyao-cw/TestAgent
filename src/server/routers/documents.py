#!/usr/bin/env python3
"""
文档管理API路由
"""

import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from ...config.logging_config import get_logger
from ...rag.document_manager import get_document_manager
from ...rag.vector_store import get_vector_store

logger = get_logger("documents_api")

router = APIRouter()


# 请求和响应模型
class DocumentInfo(BaseModel):
    """文档信息"""

    document_id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小（字节）")
    upload_time: str = Field(..., description="上传时间")
    status: str = Field(..., description="处理状态")
    chunk_count: Optional[int] = Field(None, description="文本块数量")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class DocumentListResponse(BaseModel):
    """文档列表响应"""

    documents: List[DocumentInfo] = Field(..., description="文档列表")
    total: int = Field(..., description="总文档数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""

    document_id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    status: str = Field(..., description="上传状态")
    message: str = Field(..., description="状态消息")


class DocumentSearchRequest(BaseModel):
    """文档搜索请求"""

    query: str = Field(..., description="搜索查询")
    top_k: int = Field(5, description="返回结果数量")
    threshold: float = Field(0.7, description="相似度阈值")
    document_ids: Optional[List[str]] = Field(None, description="限制搜索的文档ID")


class DocumentSearchResult(BaseModel):
    """文档搜索结果"""

    document_id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    content: str = Field(..., description="匹配内容")
    score: float = Field(..., description="相似度分数")
    metadata: Dict[str, Any] = Field(..., description="元数据")


class DocumentSearchResponse(BaseModel):
    """文档搜索响应"""

    query: str = Field(..., description="搜索查询")
    results: List[DocumentSearchResult] = Field(..., description="搜索结果")
    total_results: int = Field(..., description="总结果数")


# 依赖注入
async def get_document_manager_dep():
    """获取文档管理器依赖"""
    return get_document_manager()


async def get_vector_store_dep():
    """获取向量存储依赖"""
    return get_vector_store()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    document_manager=Depends(get_document_manager_dep),
):
    """上传文档"""
    try:
        # 验证文件类型
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "text/plain",
            "text/markdown",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {file.content_type}。支持的类型: {allowed_types}",
            )

        # 验证文件大小（最大50MB）
        max_size = 50 * 1024 * 1024  # 50MB
        if file.size and file.size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件过大: {file.size} 字节。最大允许: {max_size} 字节",
            )

        # 生成文档ID
        document_id = f"doc_{uuid4().hex[:8]}_{int(datetime.now().timestamp())}"

        # 保存文件
        upload_dir = "data/documents"
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")

        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # 准备元数据
        metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(content),
            "upload_time": datetime.now().isoformat(),
            "description": description,
            "tags": tags.split(",") if tags else [],
        }

        # 添加到文档管理器
        await document_manager.add_document(
            document_id=document_id, file_path=file_path, metadata=metadata
        )

        logger.info(f"文档上传成功: {document_id} - {file.filename}")

        return DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="uploaded",
            message="文档上传成功，正在处理中",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档上传失败: {str(e)}")


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="状态过滤"),
    document_manager=Depends(get_document_manager_dep),
):
    """列出文档"""
    try:
        # 获取文档列表
        documents = await document_manager.list_documents(
            page=page, page_size=page_size, status_filter=status
        )

        # 构建响应
        document_infos = []
        for doc in documents["documents"]:
            doc_info = DocumentInfo(
                document_id=doc["document_id"],
                filename=doc["metadata"]["filename"],
                file_type=doc["metadata"]["content_type"],
                file_size=doc["metadata"]["file_size"],
                upload_time=doc["metadata"]["upload_time"],
                status=doc["status"],
                chunk_count=doc.get("chunk_count"),
                metadata=doc["metadata"],
            )
            document_infos.append(doc_info)

        return DocumentListResponse(
            documents=document_infos,
            total=documents["total"],
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"列出文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出文档失败: {str(e)}")


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(
    document_id: str, document_manager=Depends(get_document_manager_dep)
):
    """获取文档信息"""
    try:
        # 获取文档信息
        doc = await document_manager.get_document(document_id)

        if not doc:
            raise HTTPException(status_code=404, detail=f"未找到文档: {document_id}")

        return DocumentInfo(
            document_id=doc["document_id"],
            filename=doc["metadata"]["filename"],
            file_type=doc["metadata"]["content_type"],
            file_size=doc["metadata"]["file_size"],
            upload_time=doc["metadata"]["upload_time"],
            status=doc["status"],
            chunk_count=doc.get("chunk_count"),
            metadata=doc["metadata"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档信息失败: {str(e)}")


@router.get("/{document_id}/download")
async def download_document(
    document_id: str, document_manager=Depends(get_document_manager_dep)
):
    """下载文档"""
    try:
        # 获取文档信息
        doc = await document_manager.get_document(document_id)

        if not doc:
            raise HTTPException(status_code=404, detail=f"未找到文档: {document_id}")

        # 获取文件路径
        file_path = doc["file_path"]

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文档文件不存在")

        # 返回文件
        return FileResponse(
            path=file_path,
            filename=doc["metadata"]["filename"],
            media_type=doc["metadata"]["content_type"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载文档失败: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(
    document_id: str, document_manager=Depends(get_document_manager_dep)
):
    """删除文档"""
    try:
        # 删除文档
        result = await document_manager.delete_document(document_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"未找到文档: {document_id}")

        logger.info(f"文档已删除: {document_id}")

        return {"message": "文档删除成功", "document_id": document_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    request: DocumentSearchRequest, vector_store=Depends(get_vector_store_dep)
):
    """搜索文档"""
    try:
        # 执行向量搜索
        search_results = await vector_store.similarity_search(
            query=request.query,
            k=request.top_k,
            score_threshold=request.threshold,
            filter_metadata=(
                {"document_id": request.document_ids} if request.document_ids else None
            ),
        )

        # 构建搜索结果
        results = []
        for result in search_results:
            search_result = DocumentSearchResult(
                document_id=result["metadata"]["document_id"],
                filename=result["metadata"]["filename"],
                content=result["content"],
                score=result["score"],
                metadata=result["metadata"],
            )
            results.append(search_result)

        return DocumentSearchResponse(
            query=request.query, results=results, total_results=len(results)
        )

    except Exception as e:
        logger.error(f"搜索文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索文档失败: {str(e)}")


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: str, document_manager=Depends(get_document_manager_dep)
):
    """重新处理文档"""
    try:
        # 重新处理文档
        result = await document_manager.reprocess_document(document_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"未找到文档: {document_id}")

        logger.info(f"文档重新处理: {document_id}")

        return {
            "message": "文档重新处理已开始",
            "document_id": document_id,
            "status": "processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新处理文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"重新处理文档失败: {str(e)}")


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    document_manager=Depends(get_document_manager_dep),
):
    """获取文档分块"""
    try:
        # 获取文档分块
        chunks = await document_manager.get_document_chunks(
            document_id=document_id, page=page, page_size=page_size
        )

        if not chunks:
            raise HTTPException(
                status_code=404, detail=f"未找到文档或分块: {document_id}"
            )

        return chunks

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档分块失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档分块失败: {str(e)}")


@router.post("/batch-upload")
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    document_manager=Depends(get_document_manager_dep),
):
    """批量上传文档"""
    try:
        results = []

        for file in files:
            try:
                # 为每个文件调用单个上传逻辑
                result = await upload_document(
                    file, description, tags, document_manager
                )
                results.append(
                    {
                        "filename": file.filename,
                        "status": "success",
                        "document_id": result.document_id,
                    }
                )
            except Exception as e:
                results.append(
                    {"filename": file.filename, "status": "failed", "error": str(e)}
                )

        return {
            "message": f"批量上传完成，成功: {sum(1 for r in results if r['status'] == 'success')}，失败: {sum(1 for r in results if r['status'] == 'failed')}",
            "results": results,
        }

    except Exception as e:
        logger.error(f"批量上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量上传失败: {str(e)}")
