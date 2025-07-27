#!/usr/bin/env python3
"""
规划器节点演示脚本
"""

import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from langchain_core.messages import HumanMessage
from src.graph.nodes import PlannerNode
from src.models.state import TaskType
from src.tools.tool_manager import get_tool_manager


async def test_planner_node():
    """测试规划器节点功能"""
    print("=== 规划器节点演示 ===")

    # 初始化工具管理器
    tool_manager = get_tool_manager()
    await tool_manager.initialize_tools()
    print("✅ 工具管理器初始化完成")

    # 创建规划器节点
    planner = PlannerNode()
    print("✅ 规划器节点创建完成")

    # 测试场景1：生成测试用例计划
    print("\n--- 场景1: 生成测试用例计划 ---")
    state1 = {
        "messages": [HumanMessage(content="请为用户登录功能生成测试用例")],
        "locale": "zh-CN",
        "task_topic": "用户登录功能",
        "task_type": TaskType.TEST_CASE_GENERATION,
        "plan_iterations": 0,
        "current_plan": None,
        "observations": [],
        "resources": [],
        "rag_results": [],
        "final_report": "",
        "review_score": None,
        "auto_accepted_plan": False,
        "enable_rag_search": True,
        "enable_human_feedback": True,
    }

    try:
        result1 = await planner.process(state1)

        print("生成的执行计划:")
        plan = result1["current_plan"]
        print(f"标题: {plan.title}")
        print(f"思路: {plan.thought[:100]}...")
        print(f"步骤数量: {len(plan.steps)}")

        print("\n步骤详情:")
        for i, step in enumerate(plan.steps):
            print(f"步骤 {i+1}: {step.title} ({step.step_type})")
            print(f"  描述: {step.description[:50]}...")

        print(f"\n计划迭代次数: {result1['plan_iterations']}")
        print(f"下一个节点: {result1['next_node']}")

    except Exception as e:
        print(f"❌ 处理失败: {e}")

    # 测试场景2：生成测试脚本计划
    print("\n--- 场景2: 生成测试脚本计划 ---")
    state2 = {
        "messages": [HumanMessage(content="请为支付功能编写自动化测试脚本")],
        "locale": "zh-CN",
        "task_topic": "支付功能自动化测试",
        "task_type": TaskType.TEST_SCRIPT_GENERATION,
        "plan_iterations": 0,
        "current_plan": None,
        "observations": [],
        "resources": [],
        "rag_results": [],
        "final_report": "",
        "review_score": None,
        "auto_accepted_plan": False,
        "enable_rag_search": True,
        "enable_human_feedback": True,
    }

    try:
        result2 = await planner.process(state2)

        print("生成的执行计划:")
        plan = result2["current_plan"]
        print(f"标题: {plan.title}")
        print(f"思路: {plan.thought[:100]}...")
        print(f"步骤数量: {len(plan.steps)}")

        print("\n步骤详情:")
        for i, step in enumerate(plan.steps):
            print(f"步骤 {i+1}: {step.title} ({step.step_type})")
            print(f"  描述: {step.description[:50]}...")

        print(f"\n计划迭代次数: {result2['plan_iterations']}")
        print(f"下一个节点: {result2['next_node']}")

    except Exception as e:
        print(f"❌ 处理失败: {e}")

    # 测试场景3：测试缓存功能
    print("\n--- 场景3: 测试缓存功能 ---")
    # 使用与场景1相同的任务类型和主题
    state3 = {
        "messages": [HumanMessage(content="请为用户登录功能生成测试用例")],
        "locale": "zh-CN",
        "task_topic": "用户登录功能",
        "task_type": TaskType.TEST_CASE_GENERATION,
        "plan_iterations": 0,
        "current_plan": None,
        "observations": [],
        "resources": [],
        "rag_results": [],
        "final_report": "",
        "review_score": None,
        "auto_accepted_plan": False,
        "enable_rag_search": True,
        "enable_human_feedback": True,
    }

    try:
        # 记录开始时间
        import time

        start_time = time.time()

        result3 = await planner.process(state3)

        end_time = time.time()
        execution_time = end_time - start_time

        print(f"执行时间: {execution_time:.2f}秒 (应该比第一次快，因为使用了缓存)")
        print(f"计划标题: {result3['current_plan'].title}")
        print(f"计划迭代次数: {result3['plan_iterations']}")

    except Exception as e:
        print(f"❌ 处理失败: {e}")

    # 测试场景4：测试最大迭代次数限制
    print("\n--- 场景4: 测试最大迭代次数限制 ---")
    state4 = {
        "messages": [HumanMessage(content="请为用户注册功能生成测试用例")],
        "locale": "zh-CN",
        "task_topic": "用户注册功能",
        "task_type": TaskType.TEST_CASE_GENERATION,
        "plan_iterations": 5,  # 超过默认的3次迭代
        "current_plan": None,
        "observations": [],
        "resources": [],
        "rag_results": [],
        "final_report": "",
        "review_score": None,
        "auto_accepted_plan": False,
        "enable_rag_search": True,
        "enable_human_feedback": True,
    }

    try:
        result4 = await planner.process(state4)

        print(f"计划标题: {result4['current_plan'].title}")
        print(f"计划迭代次数: {result4['plan_iterations']}")
        print(
            f"是否使用默认计划: {'是' if not result4['current_plan'].has_enough_context else '否'}"
        )

    except Exception as e:
        print(f"❌ 处理失败: {e}")

    # 关闭工具管理器
    await tool_manager.shutdown()
    print("\n✅ 规划器节点演示完成")


async def test_plan_validation():
    """测试计划验证功能"""
    print("\n=== 计划验证功能演示 ===")

    planner = PlannerNode()

    # 创建有效计划
    from src.models.execution import ExecutionPlan, ExecutionStep, StepType

    valid_steps = [
        ExecutionStep(
            title="需求分析",
            description="分析用户需求文档，提取测试要点",
            step_type=StepType.RESEARCH,
        ),
        ExecutionStep(
            title="测试设计",
            description="设计测试用例，包括正常流程和异常流程",
            step_type=StepType.ANALYSIS,
        ),
        ExecutionStep(
            title="测试实现",
            description="实现自动化测试脚本",
            step_type=StepType.CODING,
        ),
    ]

    valid_plan = ExecutionPlan(
        title="有效的测试计划",
        thought="这是一个有效的测试计划，包含了研究、分析和编码步骤",
        locale="zh-CN",
        task_type=TaskType.TEST_SCRIPT_GENERATION.value,
        steps=valid_steps,
        has_enough_context=True,
    )

    # 创建无效计划（步骤顺序不合理）
    invalid_steps = [
        ExecutionStep(
            title="测试实现",
            description="实现自动化测试脚本",
            step_type=StepType.CODING,
        ),
        ExecutionStep(
            title="需求分析",
            description="分析用户需求文档，提取测试要点",
            step_type=StepType.RESEARCH,
        ),
    ]

    invalid_plan = ExecutionPlan(
        title="无效的测试计划",
        thought="这是一个无效的测试计划，步骤顺序不合理",
        locale="zh-CN",
        task_type=TaskType.TEST_SCRIPT_GENERATION.value,
        steps=invalid_steps,
        has_enough_context=True,
    )

    # 验证计划
    valid_result = planner._validate_execution_plan(valid_plan)
    invalid_result = planner._validate_execution_plan(invalid_plan)

    print(f"有效计划验证结果: {valid_result}")
    print(f"无效计划验证结果: {invalid_result}")

    # 测试步骤序列验证
    print("\n步骤序列验证:")
    sequences = [
        ("研究->分析->编码", [StepType.RESEARCH, StepType.ANALYSIS, StepType.CODING]),
        ("研究->编码", [StepType.RESEARCH, StepType.CODING]),
        ("编码->研究", [StepType.CODING, StepType.RESEARCH]),
        ("只有编码", [StepType.CODING]),
        ("只有研究", [StepType.RESEARCH]),
    ]

    for name, sequence in sequences:
        steps = [
            ExecutionStep(title=f"步骤{i+1}", description="描述", step_type=step_type)
            for i, step_type in enumerate(sequence)
        ]
        result = planner._validate_step_sequence(steps)
        print(f"{name}: {'有效' if result else '无效'}")


if __name__ == "__main__":

    async def main():
        await test_planner_node()
        await test_plan_validation()

    asyncio.run(main())
