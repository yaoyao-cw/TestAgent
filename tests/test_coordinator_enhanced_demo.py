#!/usr/bin/env python3
"""
协调器节点增强功能演示脚本
展示上下文记忆、用户偏好学习、智能任务识别等功能
"""

import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from langchain_core.messages import HumanMessage
from src.graph.nodes import CoordinatorNode
from src.models.state import TestAgentState, TaskType
from src.tools.tool_manager import get_tool_manager


async def test_coordinator_enhanced_features():
    """测试协调器增强功能"""
    print("=== 协调器节点增强功能演示 ===")
    
    # 初始化工具管理器
    tool_manager = get_tool_manager()
    await tool_manager.initialize_tools()
    print("✅ 工具管理器初始化完成")
    
    # 创建协调器节点
    coordinator = CoordinatorNode()
    print("✅ 协调器节点创建完成")
    
    # 模拟多轮对话，展示上下文记忆和用户偏好学习
    conversation_scenarios = [
        {
            "round": 1,
            "input": "你好，我需要为用户登录功能生成测试用例",
            "description": "首次交互，建立基础偏好"
        },
        {
            "round": 2,
            "input": "还需要为注册功能生成测试脚本",
            "description": "学习任务类型偏好"
        },
        {
            "round": 3,
            "input": "继续生成支付功能的自动化测试",
            "description": "基于上下文的延续对话"
        },
        {
            "round": 4,
            "input": "这个系统还有什么功能需要测试",
            "description": "模糊输入，基于历史偏好判断"
        },
        {
            "round": 5,
            "input": "今天天气怎么样？",
            "description": "非测试相关内容"
        }
    ]
    
    for scenario in conversation_scenarios:
        print(f"\n--- 第 {scenario['round']} 轮对话：{scenario['description']} ---")
        print(f"用户输入: {scenario['input']}")
        
        # 创建状态
        state = TestAgentState(
            messages=[HumanMessage(content=scenario['input'])],
            locale="",
            task_topic="",
            task_type=None,
            plan_iterations=0,
            current_plan=None,
            observations=[],
            resources=[],
            rag_results=[],
            final_report="",
            review_score=None,
            auto_accepted_plan=False,
            enable_rag_search=True,
            enable_human_feedback=True
        )
        
        try:
            result = await coordinator.process(state)
            
            # 显示处理结果
            print(f"🔍 语言检测: {result.get('locale', '未检测')}")
            print(f"🎯 任务类型: {result.get('task_type', '无')}")
            print(f"📝 任务主题: {result.get('task_topic', '无')}")
            print(f"➡️  下一节点: {result.get('next_node', '无')}")
            
            # 显示对话上下文信息
            print(f"💭 对话上下文数量: {len(coordinator.conversation_context)}")
            
            # 显示用户偏好信息
            if coordinator.user_preferences:
                print("👤 用户偏好:")
                if "preferred_language" in coordinator.user_preferences:
                    print(f"   - 偏好语言: {coordinator.user_preferences['preferred_language']}")
                
                if "task_type_history" in coordinator.user_preferences:
                    history = coordinator.user_preferences["task_type_history"]
                    print(f"   - 任务历史: {history[-3:] if len(history) > 3 else history}")
                
                if "expression_patterns" in coordinator.user_preferences:
                    patterns = coordinator.user_preferences["expression_patterns"]
                    print(f"   - 平均输入长度: {patterns.get('avg_input_length', 0):.1f}")
                    print(f"   - 使用正式语言: {patterns.get('uses_formal_language', False)}")
            
            # 显示上下文摘要
            context_summary = coordinator._get_context_summary()
            if context_summary:
                print(f"📊 上下文摘要: {context_summary}")
            
            # 显示最后一条消息（AI回复）
            if len(result.get("messages", [])) > 1:
                ai_message = result["messages"][-1].content
                print(f"🤖 AI回复: {ai_message[:100]}{'...' if len(ai_message) > 100 else ''}")
            
        except Exception as e:
            print(f"❌ 处理失败: {e}")
    
    # 展示关键词提取功能
    print(f"\n--- 关键词提取功能演示 ---")
    test_texts = [
        "请为用户登录功能生成完整的测试用例",
        "需要编写自动化测试脚本来验证API接口",
        "分析需求文档并提取关键测试点",
        "今天天气很好，适合出去走走"
    ]
    
    for text in test_texts:
        keywords = coordinator._extract_keywords(text)
        print(f"文本: {text}")
        print(f"关键词: {keywords if keywords else '无'}")
        print()
    
    # 展示语言检测功能
    print(f"--- 语言检测功能演示 ---")
    test_languages = [
        "请生成测试用例",
        "Please generate test cases",
        "请generate测试用例for login",
        "继续"  # 短文本，依赖上下文
    ]
    
    for text in test_languages:
        basic_detection = coordinator._detect_language(text)
        context_detection = coordinator._detect_language_with_context(text)
        print(f"文本: '{text}'")
        print(f"基础检测: {basic_detection}, 上下文检测: {context_detection}")
        print()
    
    # 关闭工具管理器
    await tool_manager.shutdown()
    print("\n✅ 协调器增强功能演示完成")


async def test_enhanced_test_related_detection():
    """测试增强版测试相关性检测"""
    print("\n=== 增强版测试相关性检测演示 ===")
    
    coordinator = CoordinatorNode()
    
    # 建立测试相关的对话上下文
    test_contexts = [
        "请为用户登录功能生成测试用例",
        "需要单元测试覆盖所有边界条件",
        "还要添加集成测试验证整个流程"
    ]
    
    for context in test_contexts:
        coordinator._update_conversation_context(context)
        coordinator._learn_user_preferences(context, "zh-CN")
    
    print("已建立测试相关的对话上下文和用户偏好")
    
    # 测试各种输入的相关性判断
    test_inputs = [
        ("还有其他需要注意的吗", "延续性表达"),
        ("这个系统功能", "基于历史偏好的模糊输入"),
        ("继续优化代码质量", "延续性 + 相关关键词"),
        ("今天天气怎么样", "完全无关的内容"),
        ("软件架构设计", "技术相关但非测试")
    ]
    
    for input_text, description in test_inputs:
        try:
            # 基础判断
            basic_result = await coordinator._is_test_related(input_text)
            # 增强判断
            enhanced_result = await coordinator._is_test_related_enhanced(input_text)
            
            print(f"输入: '{input_text}' ({description})")
            print(f"基础判断: {basic_result}, 增强判断: {enhanced_result}")
            print()
            
        except Exception as e:
            print(f"判断失败: {e}")


async def test_task_info_extraction_enhancement():
    """测试任务信息提取增强功能"""
    print("\n=== 任务信息提取增强功能演示 ===")
    
    coordinator = CoordinatorNode()
    
    # 建立用户偏好历史
    script_preferences = ["test_script_generation"] * 5
    coordinator.user_preferences["task_type_history"] = script_preferences
    
    # 建立上下文
    coordinator._update_conversation_context("需要单元测试和集成测试覆盖")
    
    test_inputs = [
        ("生成代码", "模糊输入，应基于偏好调整为脚本生成"),
        ("继续", "延续性输入，应丰富主题"),
        ("为登录功能创建测试", "明确输入")
    ]
    
    for input_text, description in test_inputs:
        try:
            # 基础提取
            basic_info = await coordinator._extract_task_info(input_text, "zh-CN")
            # 增强提取
            enhanced_info = await coordinator._extract_task_info_enhanced(input_text, "zh-CN")
            
            print(f"输入: '{input_text}' ({description})")
            print(f"基础提取: {basic_info}")
            print(f"增强提取: {enhanced_info}")
            print()
            
        except Exception as e:
            print(f"提取失败: {e}")


if __name__ == "__main__":
    async def main():
        await test_coordinator_enhanced_features()
        await test_enhanced_test_related_detection()
        await test_task_info_extraction_enhancement()
    
    asyncio.run(main())