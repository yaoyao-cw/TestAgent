#!/usr/bin/env python3
"""
协调器节点演示脚本
"""

import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from langchain_core.messages import HumanMessage
from src.graph.nodes import CoordinatorNode
from src.tools.tool_manager import get_tool_manager


async def test_coordinator_node():
    """测试协调器节点功能"""
    print("=== 协调器节点演示 ===")
    
    # 初始化工具管理器
    tool_manager = get_tool_manager()
    await tool_manager.initialize_tools()
    print("✅ 工具管理器初始化完成")
    
    # 创建协调器节点
    coordinator = CoordinatorNode()
    print("✅ 协调器节点创建完成")
    
    # 测试场景1：测试相关输入（中文）
    print("\n--- 场景1: 测试相关输入（中文）---")
    state1 = {
        "messages": [HumanMessage(content="请为用户登录功能生成测试用例")]
    }
    
    try:
        result1 = await coordinator.process(state1)
        
        print("处理结果:")
        print(f"语言检测: {result1.get('locale', '未检测到')}")
        print(f"任务主题: {result1.get('task_topic', '未提取到')}")
        print(f"任务类型: {result1.get('task_type', '未识别')}")
        print(f"下一个节点: {result1.get('next_node', '无')}")
        
        if result1.get('messages'):
            last_message = result1['messages'][-1]
            print(f"回复消息: {last_message.content[:100]}...")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 测试场景2：测试相关输入（英文）
    print("\n--- 场景2: 测试相关输入（英文）---")
    state2 = {
        "messages": [HumanMessage(content="Generate test scripts for payment functionality")]
    }
    
    try:
        result2 = await coordinator.process(state2)
        
        print("处理结果:")
        print(f"语言检测: {result2.get('locale', '未检测到')}")
        print(f"任务主题: {result2.get('task_topic', '未提取到')}")
        print(f"任务类型: {result2.get('task_type', '未识别')}")
        print(f"下一个节点: {result2.get('next_node', '无')}")
        
        if result2.get('messages'):
            last_message = result2['messages'][-1]
            print(f"回复消息: {last_message.content[:100]}...")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 测试场景3：非测试相关输入（问候）
    print("\n--- 场景3: 非测试相关输入（问候）---")
    state3 = {
        "messages": [HumanMessage(content="你好，请问你能做什么？")]
    }
    
    try:
        result3 = await coordinator.process(state3)
        
        print("处理结果:")
        if result3.get('final_report'):
            print(f"简单回复: {result3['final_report'][:200]}...")
        
        if result3.get('messages'):
            last_message = result3['messages'][-1]
            print(f"回复消息: {last_message.content[:200]}...")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 测试场景4：非测试相关输入（其他话题）
    print("\n--- 场景4: 非测试相关输入（其他话题）---")
    state4 = {
        "messages": [HumanMessage(content="今天天气怎么样？")]
    }
    
    try:
        result4 = await coordinator.process(state4)
        
        print("处理结果:")
        if result4.get('final_report'):
            print(f"简单回复: {result4['final_report'][:200]}...")
        
        if result4.get('messages'):
            last_message = result4['messages'][-1]
            print(f"回复消息: {last_message.content[:200]}...")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    # 关闭工具管理器
    await tool_manager.shutdown()
    print("\n✅ 协调器节点演示完成")


async def test_coordinator_enhanced_features():
    """测试协调器节点的增强功能"""
    print("\n=== 协调器增强功能演示 ===")
    
    coordinator = CoordinatorNode()
    
    # 测试语言检测
    print("\n--- 语言检测测试 ---")
    test_texts = [
        "请为用户登录功能生成测试用例",
        "Generate test cases for user login",
        "测试 test 混合语言",
        "Hello 你好 world"
    ]
    
    for text in test_texts:
        detected_lang = coordinator._detect_language(text)
        print(f"文本: '{text}' -> 语言: {detected_lang}")
    
    # 测试关键词提取
    print("\n--- 关键词提取测试 ---")
    test_inputs = [
        "请为用户登录功能生成测试用例",
        "需要编写自动化测试脚本",
        "分析需求文档并提取关键信息",
        "执行测试脚本并生成报告"
    ]
    
    for input_text in test_inputs:
        keywords = coordinator._extract_keywords(input_text)
        print(f"输入: '{input_text}'")
        print(f"关键词: {keywords}")
        print()
    
    # 测试任务类型分析
    print("\n--- 任务类型分析测试 ---")
    task_inputs = [
        "生成测试用例",
        "编写测试脚本",
        "提取需求文档",
        "运行测试脚本",
        "创建自动化测试"
    ]
    
    for task_input in task_inputs:
        task_type = coordinator._analyze_task_type_by_keywords(task_input)
        print(f"输入: '{task_input}' -> 任务类型: {task_type.value}")
    
    # 测试上下文记忆功能
    print("\n--- 上下文记忆测试 ---")
    
    # 模拟多轮对话
    conversation_inputs = [
        "请为登录功能生成测试用例",
        "还需要包括边界条件测试",
        "另外添加安全性测试",
        "最后生成测试报告"
    ]
    
    for i, input_text in enumerate(conversation_inputs):
        print(f"第{i+1}轮对话: {input_text}")
        coordinator._update_conversation_context(input_text)
        
        # 显示当前上下文
        if coordinator.conversation_context:
            latest_context = coordinator.conversation_context[-1]
            print(f"  关键词: {latest_context['contains_keywords']}")
            print(f"  输入长度: {latest_context['input_length']}")
        
        # 测试增强版测试相关性判断
        is_related = await coordinator._is_test_related_enhanced(input_text)
        print(f"  测试相关性: {is_related}")
        print()
    
    # 显示学习到的用户偏好
    print("--- 用户偏好学习结果 ---")
    if coordinator.user_preferences:
        print(f"偏好语言: {coordinator.user_preferences.get('preferred_language', '未设置')}")
        if 'task_type_history' in coordinator.user_preferences:
            print(f"任务类型历史: {coordinator.user_preferences['task_type_history']}")
        if 'expression_patterns' in coordinator.user_preferences:
            patterns = coordinator.user_preferences['expression_patterns']
            print(f"平均输入长度: {patterns['avg_input_length']:.1f}")
            print(f"使用正式语言: {patterns['uses_formal_language']}")
    
    # 测试上下文摘要生成
    print("\n--- 上下文摘要生成 ---")
    context_summary = coordinator._get_context_summary()
    print(f"上下文摘要: {context_summary}")


async def test_error_handling():
    """测试错误处理功能"""
    print("\n=== 错误处理测试 ===")
    
    coordinator = CoordinatorNode()
    
    # 测试无消息状态
    print("\n--- 无消息状态测试 ---")
    empty_state = {"messages": []}
    
    try:
        result = await coordinator.process(empty_state)
        print("处理结果:")
        if result.get('final_report'):
            print(f"错误回复: {result['final_report'][:100]}...")
    except Exception as e:
        print(f"捕获异常: {e}")
    
    # 测试错误响应生成
    print("\n--- 错误响应生成测试 ---")
    error_msg = "测试错误信息"
    
    chinese_error = coordinator._generate_error_response(error_msg, "zh-CN")
    english_error = coordinator._generate_error_response(error_msg, "en-US")
    
    print(f"中文错误响应: {chinese_error[:100]}...")
    print(f"英文错误响应: {english_error[:100]}...")


if __name__ == "__main__":
    async def main():
        await test_coordinator_node()
        await test_coordinator_enhanced_features()
        await test_error_handling()
    
    asyncio.run(main())