#!/usr/bin/env python3
"""
研究员节点演示脚本
"""

import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from langchain_core.messages import HumanMessage
from src.graph.nodes import ResearcherNode
from src.models.state import TaskType
from src.models.execution import ExecutionPlan, ExecutionStep, StepType
from src.tools.tool_manager import get_tool_manager


async def test_researcher_node():
    """测试研究员节点功能"""
    print("=== 研究员节点演示 ===")
    
    # 初始化工具管理器
    tool_manager = get_tool_manager()
    await tool_manager.initialize_tools()
    print("✅ 工具管理器初始化完成")
    
    # 创建研究员节点
    researcher = ResearcherNode()
    print("✅ 研究员节点创建完成")
    
    # 创建模拟执行计划
    steps = [
        ExecutionStep(
            title="需求分析",
            description="分析用户登录功能的需求文档，提取测试要点",
            step_type=StepType.RESEARCH
        ),
        ExecutionStep(
            title="测试思维导图",
            description="基于需求分析生成测试思维导图",
            step_type=StepType.RESEARCH
        ),
        ExecutionStep(
            title="测试用例设计",
            description="基于思维导图设计详细测试用例",
            step_type=StepType.RESEARCH
        ),
        ExecutionStep(
            title="边界条件分析",
            description="分析边界条件和异常情况",
            step_type=StepType.ANALYSIS
        ),
        ExecutionStep(
            title="结果验证",
            description="验证生成结果的完整性和准确性",
            step_type=StepType.ANALYSIS
        ),
        ExecutionStep(
            title="脚本实现",
            description="实现具体测试脚本",
            step_type=StepType.CODING
        )
    ]
    
    execution_plan = ExecutionPlan(
        title="用户登录功能测试用例生成计划",
        thought="基于需求分析生成完整的测试用例",
        locale="zh-CN",
        task_type=TaskType.TEST_CASE_GENERATION.value,
        steps=steps,
        has_enough_context=True
    )
    
    # 测试场景1：需求分析步骤
    print("\n--- 场景1: 需求分析步骤 ---")
    state1 = {
        "messages": [HumanMessage(content="请为用户登录功能生成测试用例")],
        "locale": "zh-CN",
        "task_topic": "用户登录功能",
        "task_type": TaskType.TEST_CASE_GENERATION,
        "current_plan": execution_plan,
        "current_step": 0,
        "observations": [],
        "resources": [],
        "rag_results": [],
        "final_report": "",
        "review_score": None
    }
    
    try:
        result1 = await researcher.process(state1)
        
        print("处理结果:")
        print(f"当前步骤: {result1['current_step']}")
        print(f"下一个节点: {result1['next_node']}")
        print(f"观察结果数量: {len(result1['observations'])}")
        
        if result1['observations']:
            obs = result1['observations'][0]
            print(f"步骤标题: {obs['step_title']}")
            print(f"步骤类型: {obs['step_type']}")
            print(f"结果类型: {obs['result']['type']}")
            print(f"任务主题: {obs['result']['task_topic']}")
            
            if 'analysis_result' in obs['result']:
                analysis = obs['result']['analysis_result']
                print(f"分析结果: {analysis[:200]}...")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 测试场景2：测试思维导图生成
    print("\n--- 场景2: 测试思维导图生成 ---")
    state2 = {
        "messages": [HumanMessage(content="请为用户登录功能生成测试用例")],
        "locale": "zh-CN",
        "task_topic": "用户登录功能",
        "task_type": TaskType.TEST_CASE_GENERATION,
        "current_plan": execution_plan,
        "current_step": 1,
        "observations": [
            {
                "step_index": 0,
                "step_title": "需求分析",
                "step_type": StepType.RESEARCH.value,
                "result": {
                    "type": "requirement_analysis",
                    "task_topic": "用户登录功能",
                    "analysis_result": "用户登录功能需求分析：包括用户名密码验证、登录状态管理、安全性要求等"
                }
            }
        ]
    }
    
    try:
        result2 = await researcher.process(state2)
        
        print("处理结果:")
        print(f"当前步骤: {result2['current_step']}")
        print(f"下一个节点: {result2['next_node']}")
        print(f"观察结果数量: {len(result2['observations'])}")
        
        if result2['observations']:
            latest_obs = result2['observations'][-1]
            print(f"最新步骤: {latest_obs['step_title']}")
            print(f"结果类型: {latest_obs['result']['type']}")
            
            if 'mind_map' in latest_obs['result']:
                mind_map = latest_obs['result']['mind_map']
                print(f"思维导图: {mind_map[:300]}...")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 测试场景3：测试用例生成
    print("\n--- 场景3: 测试用例生成 ---")
    state3 = {
        "messages": [HumanMessage(content="请为用户登录功能生成测试用例")],
        "locale": "zh-CN",
        "task_topic": "用户登录功能",
        "task_type": TaskType.TEST_CASE_GENERATION,
        "current_plan": execution_plan,
        "current_step": 2,
        "observations": [
            {
                "step_index": 0,
                "step_title": "需求分析",
                "step_type": StepType.RESEARCH.value,
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "用户登录功能需求分析结果"
                }
            },
            {
                "step_index": 1,
                "step_title": "测试思维导图",
                "step_type": StepType.RESEARCH.value,
                "result": {
                    "type": "test_mind_map",
                    "mind_map": "用户登录功能测试思维导图"
                }
            }
        ]
    }
    
    try:
        result3 = await researcher.process(state3)
        
        print("处理结果:")
        print(f"当前步骤: {result3['current_step']}")
        print(f"下一个节点: {result3['next_node']}")
        
        if result3['observations']:
            latest_obs = result3['observations'][-1]
            print(f"最新步骤: {latest_obs['step_title']}")
            print(f"结果类型: {latest_obs['result']['type']}")
            
            if 'test_cases' in latest_obs['result']:
                test_cases = latest_obs['result']['test_cases']
                print(f"测试用例: {test_cases[:300]}...")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 测试场景4：边界条件分析
    print("\n--- 场景4: 边界条件分析 ---")
    state4 = {
        "messages": [HumanMessage(content="请为用户登录功能生成测试用例")],
        "locale": "zh-CN",
        "task_topic": "用户登录功能",
        "task_type": TaskType.TEST_CASE_GENERATION,
        "current_plan": execution_plan,
        "current_step": 3,
        "observations": [
            {
                "step_index": 0,
                "step_title": "需求分析",
                "step_type": StepType.RESEARCH.value,
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "用户登录功能需求分析结果"
                }
            },
            {
                "step_index": 2,
                "step_title": "测试用例设计",
                "step_type": StepType.RESEARCH.value,
                "result": {
                    "type": "test_cases",
                    "test_cases": "用户登录功能测试用例"
                }
            }
        ]
    }
    
    try:
        result4 = await researcher.process(state4)
        
        print("处理结果:")
        print(f"当前步骤: {result4['current_step']}")
        print(f"下一个节点: {result4['next_node']}")
        
        if result4['observations']:
            latest_obs = result4['observations'][-1]
            print(f"最新步骤: {latest_obs['step_title']}")
            print(f"结果类型: {latest_obs['result']['type']}")
            
            if 'boundary_analysis' in latest_obs['result']:
                boundary = latest_obs['result']['boundary_analysis']
                print(f"边界条件分析: {boundary[:300]}...")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 测试场景5：编码步骤（应该移交给编码员）
    print("\n--- 场景5: 编码步骤（移交给编码员）---")
    state5 = {
        "messages": [HumanMessage(content="请为用户登录功能生成测试用例")],
        "locale": "zh-CN",
        "task_topic": "用户登录功能",
        "task_type": TaskType.TEST_CASE_GENERATION,
        "current_plan": execution_plan,
        "current_step": 5,  # 编码步骤
        "observations": []
    }
    
    try:
        result5 = await researcher.process(state5)
        
        print("处理结果:")
        print(f"当前步骤: {result5['current_step']}")
        print(f"下一个节点: {result5['next_node']}")
        print("✅ 成功识别编码步骤并移交给编码员")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 关闭工具管理器
    await tool_manager.shutdown()
    print("\n✅ 研究员节点演示完成")


async def test_researcher_functions():
    """测试研究员节点的各种功能"""
    print("\n=== 研究员功能测试 ===")
    
    researcher = ResearcherNode()
    
    # 测试需求分析功能
    print("\n--- 需求分析功能测试 ---")
    step = ExecutionStep(
        title="需求分析",
        description="分析用户登录功能的需求文档，提取测试要点",
        step_type=StepType.RESEARCH
    )
    
    state = {
        "task_topic": "用户登录功能",
        "locale": "zh-CN"
    }
    
    try:
        result = await researcher._perform_requirement_analysis(step, state)
        print(f"需求分析结果类型: {result['type']}")
        print(f"任务主题: {result['task_topic']}")
        print(f"步骤标题: {result['step_title']}")
        
        if 'analysis_result' in result:
            print(f"分析结果: {result['analysis_result'][:200]}...")
        
    except Exception as e:
        print(f"❌ 需求分析失败: {e}")
    
    # 测试文档研究功能
    print("\n--- 文档研究功能测试 ---")
    doc_step = ExecutionStep(
        title="文档检索",
        description="检索相关需求文档",
        step_type=StepType.RESEARCH
    )
    
    try:
        doc_result = await researcher._perform_document_research(doc_step, state)
        print(f"文档研究结果类型: {doc_result['type']}")
        print(f"找到文档数量: {doc_result['documents_found']}")
        
        if 'analysis_result' in doc_result:
            print(f"文档分析结果: {doc_result['analysis_result'][:200]}...")
        
    except Exception as e:
        print(f"❌ 文档研究失败: {e}")
    
    # 测试通用研究功能
    print("\n--- 通用研究功能测试 ---")
    general_step = ExecutionStep(
        title="通用研究",
        description="进行通用研究分析",
        step_type=StepType.RESEARCH
    )
    
    try:
        general_result = await researcher._perform_general_research(general_step, state)
        print(f"通用研究结果类型: {general_result['type']}")
        
        if 'research_result' in general_result:
            print(f"研究结果: {general_result['research_result'][:200]}...")
        
    except Exception as e:
        print(f"❌ 通用研究失败: {e}")


async def test_error_handling():
    """测试错误处理功能"""
    print("\n=== 错误处理测试 ===")
    
    # 测试没有LLM和RAG服务的情况
    print("\n--- 无服务情况测试 ---")
    researcher = ResearcherNode()
    researcher.llm_service = None
    researcher.rag_service = None
    
    step = ExecutionStep(
        title="需求分析",
        description="分析需求",
        step_type=StepType.RESEARCH
    )
    
    state = {
        "task_topic": "测试功能",
        "locale": "zh-CN"
    }
    
    try:
        result = await researcher._perform_requirement_analysis(step, state)
        print(f"无服务情况下的结果类型: {result['type']}")
        print(f"分析结果包含错误信息: {'失败' in result.get('analysis_result', '')}")
        
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
    
    # 测试无效执行计划的情况
    print("\n--- 无效执行计划测试 ---")
    researcher_with_service = ResearcherNode()
    
    invalid_state = {
        "current_plan": None,
        "current_step": 0
    }
    
    try:
        await researcher_with_service.process(invalid_state)
        print("❌ 应该抛出异常但没有抛出")
    except Exception as e:
        print(f"✅ 正确捕获异常: {type(e).__name__}")


if __name__ == "__main__":
    async def main():
        await test_researcher_node()
        await test_researcher_functions()
        await test_error_handling()
    
    asyncio.run(main())