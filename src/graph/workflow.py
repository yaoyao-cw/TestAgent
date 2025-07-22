#!/usr/bin/env python3
"""
TestAgent LangGraph工作流实现
基于LangGraph构建的多智能体测试工作流
"""

import logging
from typing import Dict, Any, List, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.state import TestAgentState
from ..models.types import TaskType, AgentType
from ..exceptions import TestAgentException, WorkflowException
from .coder_node import CoderNode
from .reporter_node import ReporterNode
from .reviewer_node import ReviewerNode

logger = logging.getLogger(__name__)


class TestAgentWorkflow:
    """TestAgent工作流管理器"""
    
    def __init__(self):
        """初始化工作流"""
        self.graph = None
        self.checkpointer = MemorySaver()
        self.nodes = {}
        self._initialize_nodes()
        self._build_graph()
        logger.info("TestAgent工作流初始化完成")
    
    def _initialize_nodes(self):
        """初始化所有节点"""
        try:
            # 初始化各个节点
            self.nodes = {
                "coordinator": self._create_coordinator_node,
                "planner": self._create_planner_node,
                "researcher": self._create_researcher_node,
                "coder": CoderNode(),
                "reporter": ReporterNode(),
                "reviewer": ReviewerNode()
            }
            logger.info("所有节点初始化完成")
        except Exception as e:
            logger.error(f"节点初始化失败: {e}")
            raise WorkflowException(f"节点初始化失败: {e}")
    
    def _create_coordinator_node(self, state: TestAgentState) -> Dict[str, Any]:
        """创建协调器节点处理函数"""
        import time
        
        # 模拟实际的协调器处理时间
        time.sleep(3)
        
        task_type = state.get("task_type", TaskType.TEST_CASE_GENERATION.value)
        task_topic = state.get("task_topic", "")
        context = state.get("context", "")
        
        logger.info(f"协调器正在分析任务: {task_topic} (类型: {task_type})")
        
        # 分析任务类型和复杂度
        complexity_analysis = {
            "task_complexity": "medium",
            "estimated_time": "8-12分钟",
            "required_resources": ["测试用例生成", "代码分析", "质量评审"],
            "task_breakdown": [
                "需求分析和理解",
                "测试场景识别和分类", 
                "测试用例详细设计",
                "测试数据准备",
                "质量评审和优化"
            ]
        }
        
        # 添加观察记录
        observations = state.get("observations", [])
        observations.append({
            "step_title": "任务协调",
            "step_type": "coordination",
            "timestamp": time.time(),
            "result": {
                "type": "task_analysis",
                "task_identified": True,
                "complexity": complexity_analysis["task_complexity"],
                "breakdown": complexity_analysis["task_breakdown"]
            }
        })
        
        return {
            "next_node": "planner",
            "task_identified": True,
            "task_type": task_type,
            "complexity_analysis": complexity_analysis,
            "coordinator_notes": f"已识别任务类型为 {task_type}，主题: {task_topic}，上下文: {context[:100]}...",
            "observations": observations
        }
    
    def _create_planner_node(self, state: TestAgentState) -> Dict[str, Any]:
        """创建规划器节点处理函数"""
        import time
        
        # 模拟规划器处理时间
        time.sleep(3)
        
        task_type = state.get("task_type", "")
        task_topic = state.get("task_topic", "")
        complexity_analysis = state.get("complexity_analysis", {})
        
        logger.info(f"规划器正在制定执行计划: {task_topic}")
        
        # 根据任务类型制定详细的执行计划
        if task_type == TaskType.TEST_CASE_GENERATION.value:
            execution_plan = {
                "phases": [
                    {
                        "phase": "需求分析",
                        "description": "分析测试需求和业务逻辑",
                        "estimated_time": "2分钟",
                        "deliverables": ["需求文档", "业务规则"]
                    },
                    {
                        "phase": "测试设计",
                        "description": "设计测试用例和测试场景",
                        "estimated_time": "3分钟",
                        "deliverables": ["测试用例", "测试数据"]
                    },
                    {
                        "phase": "质量评审",
                        "description": "评审测试用例的完整性和有效性",
                        "estimated_time": "2分钟",
                        "deliverables": ["评审报告", "改进建议"]
                    }
                ],
                "total_estimated_time": "7分钟",
                "success_criteria": [
                    "测试用例覆盖所有关键功能",
                    "测试数据准备充分",
                    "测试步骤清晰可执行"
                ]
            }
        else:
            execution_plan = {
                "phases": [
                    {
                        "phase": "任务分析",
                        "description": f"分析{task_type}任务的具体要求",
                        "estimated_time": "2分钟",
                        "deliverables": ["任务分析报告"]
                    },
                    {
                        "phase": "方案设计",
                        "description": "设计解决方案和实施步骤",
                        "estimated_time": "3分钟",
                        "deliverables": ["解决方案", "实施计划"]
                    },
                    {
                        "phase": "质量保证",
                        "description": "确保输出质量符合要求",
                        "estimated_time": "2分钟",
                        "deliverables": ["质量报告"]
                    }
                ],
                "total_estimated_time": "7分钟",
                "success_criteria": ["满足任务要求", "输出质量合格"]
            }
        
        return {
            "next_node": "researcher",
            "plan_created": True,
            "execution_plan": execution_plan,
            "planner_notes": f"已为任务 '{task_topic}' 制定详细执行计划，预计耗时 {execution_plan['total_estimated_time']}"
        }
    
    def _create_researcher_node(self, state: TestAgentState) -> Dict[str, Any]:
        """创建研究员节点处理函数"""
        import time
        
        # 模拟研究员处理时间
        time.sleep(4)
        
        task_type = state.get("task_type", "")
        task_topic = state.get("task_topic", "")
        execution_plan = state.get("execution_plan", {})
        context = state.get("context", "")
        
        logger.info(f"研究员正在收集信息: {task_topic}")
        
        # 模拟研究过程
        research_findings = {
            "domain_analysis": {
                "business_domain": "软件测试",
                "technical_domain": task_type,
                "complexity_level": "中等",
                "key_concepts": ["测试用例", "边界值", "等价类", "异常处理"]
            },
            "requirements_analysis": {
                "functional_requirements": [
                    "生成完整的测试用例",
                    "覆盖正常和异常场景",
                    "包含测试数据和预期结果"
                ],
                "non_functional_requirements": [
                    "测试用例应该易于理解",
                    "测试步骤应该清晰明确",
                    "测试数据应该真实可用"
                ]
            },
            "best_practices": [
                "遵循测试用例设计原则",
                "使用边界值分析方法",
                "考虑异常情况处理",
                "确保测试数据的有效性"
            ],
            "potential_challenges": [
                "需求理解可能不够准确",
                "测试场景可能遗漏",
                "测试数据准备复杂"
            ]
        }
        
        # 生成观察记录
        observations = state.get("observations", [])
        observations.append({
            "step_title": "需求研究",
            "step_type": "research",
            "timestamp": time.time(),
            "result": {
                "type": "requirement_analysis",
                "analysis_result": f"深入分析了任务 '{task_topic}' 的业务需求和技术要求",
                "functional_requirements": research_findings['requirements_analysis']['functional_requirements'],
                "non_functional_requirements": research_findings['requirements_analysis']['non_functional_requirements'],
                "best_practices": research_findings['best_practices']
            }
        })
        
        return {
            "next_node": "reporter",  # 大多数情况下直接生成报告
            "research_completed": True,
            "research_findings": research_findings,
            "observations": observations,
            "researcher_notes": f"已完成对任务 '{task_topic}' 的深入研究，收集了相关的业务知识和技术要求"
        }
    
    def _build_graph(self):
        """构建LangGraph状态图"""
        try:
            # 创建状态图
            workflow = StateGraph(TestAgentState)
            
            # 添加节点
            workflow.add_node("coordinator", self._coordinator_wrapper)
            workflow.add_node("planner", self._planner_wrapper)
            workflow.add_node("researcher", self._researcher_wrapper)
            workflow.add_node("coder", self._coder_wrapper)
            workflow.add_node("reporter", self._reporter_wrapper)
            workflow.add_node("reviewer", self._reviewer_wrapper)
            
            # 设置入口点
            workflow.set_entry_point("coordinator")
            
            # 添加条件路由
            workflow.add_conditional_edges(
                "coordinator",
                self._coordinator_router,
                {
                    "planner": "planner",
                    "end": END
                }
            )
            
            workflow.add_conditional_edges(
                "planner",
                self._planner_router,
                {
                    "researcher": "researcher",
                    "end": END
                }
            )
            
            workflow.add_conditional_edges(
                "researcher",
                self._researcher_router,
                {
                    "coder": "coder",
                    "reporter": "reporter"
                }
            )
            
            workflow.add_conditional_edges(
                "coder",
                self._coder_router,
                {
                    "coder": "coder",  # 继续编码
                    "reporter": "reporter"
                }
            )
            
            workflow.add_conditional_edges(
                "reporter",
                self._reporter_router,
                {
                    "reviewer": "reviewer",
                    "end": END
                }
            )
            
            workflow.add_edge("reviewer", END)
            
            # 编译图
            self.graph = workflow.compile(checkpointer=self.checkpointer)
            logger.info("LangGraph状态图构建完成")
            
        except Exception as e:
            logger.error(f"构建状态图失败: {e}")
            raise WorkflowException(f"构建状态图失败: {e}")
    
    # 节点包装器函数
    async def _coordinator_wrapper(self, state: TestAgentState) -> TestAgentState:
        """协调器节点包装器"""
        try:
            logger.info("执行协调器节点")
            result = self._create_coordinator_node(state)
            
            # 更新状态
            updated_state = dict(state)
            updated_state.update(result)
            
            return updated_state
        except Exception as e:
            logger.error(f"协调器节点执行失败: {e}")
            raise WorkflowException(f"协调器节点执行失败: {e}")
    
    async def _planner_wrapper(self, state: TestAgentState) -> TestAgentState:
        """规划器节点包装器"""
        try:
            logger.info("执行规划器节点")
            result = self._create_planner_node(state)
            
            # 更新状态
            updated_state = dict(state)
            updated_state.update(result)
            
            return updated_state
        except Exception as e:
            logger.error(f"规划器节点执行失败: {e}")
            raise WorkflowException(f"规划器节点执行失败: {e}")
    
    async def _researcher_wrapper(self, state: TestAgentState) -> TestAgentState:
        """研究员节点包装器"""
        try:
            logger.info("执行研究员节点")
            result = self._create_researcher_node(state)
            
            # 更新状态
            updated_state = dict(state)
            updated_state.update(result)
            
            return updated_state
        except Exception as e:
            logger.error(f"研究员节点执行失败: {e}")
            raise WorkflowException(f"研究员节点执行失败: {e}")
    
    async def _coder_wrapper(self, state: TestAgentState) -> TestAgentState:
        """编码员节点包装器"""
        try:
            logger.info("执行编码员节点")
            result = await self.nodes["coder"].process(state)
            
            # 更新状态
            updated_state = dict(state)
            updated_state.update(result)
            
            return updated_state
        except Exception as e:
            logger.error(f"编码员节点执行失败: {e}")
            raise WorkflowException(f"编码员节点执行失败: {e}")
    
    async def _reporter_wrapper(self, state: TestAgentState) -> TestAgentState:
        """报告员节点包装器"""
        try:
            logger.info("执行报告员节点")
            
            # 添加一些模拟的观察结果，如果状态中没有的话
            observations = state.get("observations", [])
            if not observations:
                # 生成一些示例测试用例内容
                task_topic = state.get("task_topic", "示例任务")
                task_type = state.get("task_type", "test_case_generation")
                
                sample_observations = [
                    {
                        "step_title": "需求分析",
                        "step_type": "analysis",
                        "result": {
                            "type": "requirement_analysis",
                            "analysis_result": f"分析了任务 '{task_topic}' 的功能需求和非功能需求"
                        }
                    },
                    {
                        "step_title": "测试用例生成",
                        "step_type": "generation",
                        "result": {
                            "type": "test_case_generation",
                            "test_cases": f"""
## 测试用例：{task_topic}

### 测试用例1：正常功能测试
- **测试目标**: 验证基本功能正常工作
- **前置条件**: 系统正常启动
- **测试步骤**: 
  1. 输入有效数据
  2. 执行操作
  3. 验证结果
- **预期结果**: 功能正常执行，返回预期结果

### 测试用例2：边界值测试
- **测试目标**: 验证边界条件处理
- **前置条件**: 系统正常启动
- **测试步骤**:
  1. 输入边界值数据
  2. 执行操作
  3. 验证结果
- **预期结果**: 系统正确处理边界值

### 测试用例3：异常处理测试
- **测试目标**: 验证异常情况处理
- **前置条件**: 系统正常启动
- **测试步骤**:
  1. 输入无效数据
  2. 执行操作
  3. 验证错误处理
- **预期结果**: 系统正确处理异常，返回适当错误信息
"""
                        }
                    }
                ]
                
                # 更新状态中的观察结果
                updated_state = dict(state)
                updated_state["observations"] = sample_observations
                state = updated_state
            
            result = await self.nodes["reporter"].process(state)
            
            # 更新状态
            updated_state = dict(state)
            updated_state.update(result)
            
            return updated_state
        except Exception as e:
            logger.error(f"报告员节点执行失败: {e}")
            raise WorkflowException(f"报告员节点执行失败: {e}")
    
    async def _reviewer_wrapper(self, state: TestAgentState) -> TestAgentState:
        """评审员节点包装器"""
        try:
            logger.info("执行评审员节点")
            result = await self.nodes["reviewer"].process(state)
            
            # 更新状态
            updated_state = dict(state)
            updated_state.update(result)
            
            return updated_state
        except Exception as e:
            logger.error(f"评审员节点执行失败: {e}")
            raise WorkflowException(f"评审员节点执行失败: {e}")
    
    # 路由函数
    def _coordinator_router(self, state: TestAgentState) -> Literal["planner", "end"]:
        """协调器路由逻辑"""
        try:
            # 检查是否识别到测试相关任务
            if state.get("task_identified", False):
                return "planner"
            else:
                return "end"
        except Exception as e:
            logger.error(f"协调器路由失败: {e}")
            return "end"
    
    def _planner_router(self, state: TestAgentState) -> Literal["researcher", "end"]:
        """规划器路由逻辑"""
        try:
            # 检查是否创建了执行计划
            if state.get("plan_created", False):
                return "researcher"
            else:
                return "end"
        except Exception as e:
            logger.error(f"规划器路由失败: {e}")
            return "end"
    
    def _researcher_router(self, state: TestAgentState) -> Literal["coder", "reporter"]:
        """研究员路由逻辑"""
        try:
            # 根据任务类型决定下一步
            task_type = state.get("task_type", "")
            
            # 如果需要代码生成，转到编码员
            if task_type in [TaskType.TEST_SCRIPT_GENERATION.value]:
                return "coder"
            else:
                # 其他情况直接生成报告
                return "reporter"
        except Exception as e:
            logger.error(f"研究员路由失败: {e}")
            return "reporter"
    
    def _coder_router(self, state: TestAgentState) -> Literal["coder", "reporter"]:
        """编码员路由逻辑"""
        try:
            # 检查是否还有更多编码任务
            next_node = state.get("next_node", "reporter")
            
            if next_node == "coder":
                return "coder"
            else:
                return "reporter"
        except Exception as e:
            logger.error(f"编码员路由失败: {e}")
            return "reporter"
    
    def _reporter_router(self, state: TestAgentState) -> Literal["reviewer", "end"]:
        """报告员路由逻辑"""
        try:
            # 检查是否需要质量评审
            if state.get("task_completed", False):
                return "reviewer"
            else:
                return "end"
        except Exception as e:
            logger.error(f"报告员路由失败: {e}")
            return "end"
    
    async def execute(self, initial_state: TestAgentState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行工作流
        
        Args:
            initial_state: 初始状态
            config: 配置参数
            
        Returns:
            Dict: 执行结果
        """
        try:
            logger.info("开始执行TestAgent工作流")
            
            # 设置默认配置
            if config is None:
                config = {"configurable": {"thread_id": "default"}}
            
            # 执行工作流
            final_state = None
            step_count = 0
            max_steps = 20  # 防止无限循环
            
            async for state in self.graph.astream(initial_state, config):
                step_count += 1
                if step_count > max_steps:
                    logger.warning("工作流执行步数超过限制，强制结束")
                    break
                
                final_state = state
                logger.info(f"工作流步骤 {step_count}: {list(state.keys())}")
            
            if final_state is None:
                raise WorkflowException("工作流执行失败，未获得最终状态")
            
            logger.info("TestAgent工作流执行完成")
            return final_state
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            raise WorkflowException(f"工作流执行失败: {e}")
    
    def get_graph_visualization(self) -> str:
        """
        获取工作流图的可视化表示
        
        Returns:
            str: 图的Mermaid格式表示
        """
        try:
            mermaid_graph = """
graph TD
    A[Coordinator] --> B{Task Identified?}
    B -->|Yes| C[Planner]
    B -->|No| END1[End]
    
    C --> D{Plan Created?}
    D -->|Yes| E[Researcher]
    D -->|No| END2[End]
    
    E --> F{Task Type?}
    F -->|Code Generation| G[Coder]
    F -->|Other| H[Reporter]
    
    G --> I{More Coding?}
    I -->|Yes| G
    I -->|No| H
    
    H --> J{Task Completed?}
    J -->|Yes| K[Reviewer]
    J -->|No| END3[End]
    
    K --> END4[End]
"""
            return mermaid_graph
        except Exception as e:
            logger.error(f"生成图可视化失败: {e}")
            return "图可视化生成失败"
    
    def get_workflow_status(self, thread_id: str = "default") -> Dict[str, Any]:
        """
        获取工作流状态
        
        Args:
            thread_id: 线程ID
            
        Returns:
            Dict: 工作流状态信息
        """
        try:
            # 这里可以添加更详细的状态检查逻辑
            return {
                "thread_id": thread_id,
                "status": "ready",
                "nodes_count": len(self.nodes),
                "graph_compiled": self.graph is not None
            }
        except Exception as e:
            logger.error(f"获取工作流状态失败: {e}")
            return {
                "thread_id": thread_id,
                "status": "error",
                "error": str(e)
            }


# 全局工作流实例
_workflow_instance = None


def get_workflow() -> TestAgentWorkflow:
    """获取工作流实例（单例模式）"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = TestAgentWorkflow()
    return _workflow_instance


async def execute_workflow(initial_state: TestAgentState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    执行TestAgent工作流的便捷函数
    
    Args:
        initial_state: 初始状态
        config: 配置参数
        
    Returns:
        Dict: 执行结果
    """
    workflow = get_workflow()
    return await workflow.execute(initial_state, config)