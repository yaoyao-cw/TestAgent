#!/usr/bin/env python3
"""
测试修复后的功能
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.rag.document_manager import get_document_manager
from src.graph.workflow_manager import get_workflow_manager
from src.server.routers.tasks import TaskSubmissionRequest


async def test_document_upload():
    """测试文档上传功能"""
    print("=== 测试文档上传功能 ===")
    
    try:
        # 创建测试文档
        test_file = "test_document.txt"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""
这是一个测试文档。

## 功能需求
1. 用户登录功能
2. 数据查询功能
3. 报表生成功能

## 技术要求
- 支持多用户并发
- 响应时间小于2秒
- 数据安全性保证

## 测试场景
- 正常登录测试
- 异常登录测试
- 性能压力测试
""")
        
        # 测试文档管理器
        doc_manager = get_document_manager()
        
        # 添加文档
        result = await doc_manager.add_document(
            document_id="test_doc_001",
            file_path=test_file,
            metadata={
                "filename": "test_document.txt",
                "content_type": "text/plain",
                "description": "测试文档"
            }
        )
        
        print(f"✅ 文档上传成功: {result['document_id']}")
        print(f"   - 状态: {result['status']}")
        print(f"   - 文本块数量: {result['chunk_count']}")
        print(f"   - 内容预览: {result.get('content_preview', '')[:100]}...")
        
        # 获取文档信息
        doc_info = await doc_manager.get_document("test_doc_001")
        if doc_info:
            print(f"✅ 文档信息获取成功: {doc_info['status']}")
        
        # 清理测试文件
        os.remove(test_file)
        
        return True
        
    except Exception as e:
        print(f"❌ 文档上传测试失败: {e}")
        return False


async def test_task_execution():
    """测试任务执行功能"""
    print("\n=== 测试任务执行功能 ===")
    
    try:
        # 创建任务请求
        request = TaskSubmissionRequest(
            task_type="test_case_generation",
            task_topic="用户登录功能测试",
            context="这是一个Web应用的用户登录功能，需要生成完整的测试用例",
            locale="zh-CN",
            timeout=60
        )
        
        # 获取工作流管理器
        workflow_manager = get_workflow_manager()
        
        # 准备初始状态
        initial_state = {
            "task_type": request.task_type,
            "task_topic": request.task_topic,
            "locale": request.locale,
            "context": request.context,
            "observations": []
        }
        
        print(f"🚀 开始执行任务: {request.task_topic}")
        
        # 执行工作流
        result = await workflow_manager.execute_workflow(
            initial_state=initial_state,
            execution_id="test_task_001",
            config={"configurable": {"thread_id": "test_task_001"}},
            timeout=60
        )
        
        print(f"✅ 任务执行完成")
        print(f"   - 任务类型: {result.get('task_type')}")
        print(f"   - 观察记录数量: {len(result.get('observations', []))}")
        
        # 检查报告内容
        if 'report' in result:
            report = result['report']
            print(f"   - 报告类型: {report.get('type')}")
            print(f"   - 报告内容长度: {len(report.get('content', ''))}")
            print(f"   - 报告预览: {report.get('content', '')[:200]}...")
        
        # 获取执行状态
        status = workflow_manager.get_execution_status("test_task_001")
        if status:
            print(f"✅ 任务状态获取成功")
            print(f"   - 状态: {status['status']}")
            print(f"   - 执行时间: {status['duration_seconds']:.2f}秒")
            print(f"   - 步骤数量: {status['steps_count']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 任务执行测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("开始测试修复后的功能...\n")
    
    # 测试文档上传
    doc_test_result = await test_document_upload()
    
    # 测试任务执行
    task_test_result = await test_task_execution()
    
    # 总结
    print("\n=== 测试结果总结 ===")
    print(f"文档上传功能: {'✅ 通过' if doc_test_result else '❌ 失败'}")
    print(f"任务执行功能: {'✅ 通过' if task_test_result else '❌ 失败'}")
    
    if doc_test_result and task_test_result:
        print("\n🎉 所有功能测试通过！")
        return True
    else:
        print("\n⚠️ 部分功能测试失败，需要进一步检查")
        return False


if __name__ == "__main__":
    asyncio.run(main())