"""工具使用示例"""

import asyncio
from typing import Dict, Any

from .python_repl import PythonREPL
from .web_search import WebSearchTool
from .document_retrieval import DocumentRetrievalTool
from .decorators import tool, rate_limit, validate_input, cache_result
from ..rag import RAGService
from ..config.logging_config import get_logger

logger = get_logger("tool_examples")


class ToolExamples:
    """工具使用示例类"""
    
    def __init__(self):
        self.python_repl = PythonREPL()
        self.web_search = WebSearchTool()
        self.rag_service = RAGService()
        self.doc_retrieval = DocumentRetrievalTool(self.rag_service)
    
    async def python_repl_examples(self):
        """Python REPL工具使用示例"""
        print("=== Python REPL 工具示例 ===")
        
        # 1. 简单计算
        result = await self.python_repl.execute_code("2 + 3 * 4")
        print(f"计算结果: {result['result']}")
        
        # 2. 使用数学库
        result = await self.python_repl.execute_code("import math; math.sqrt(16)")
        print(f"平方根: {result['result']}")
        
        # 3. 字符串操作
        code = """
text = "Hello, World!"
print(text.upper())
print(text[:5])
"""
        result = await self.python_repl.execute_code(code)
        print(f"字符串操作输出:\n{result['output']}")
        
        # 4. 列表操作
        code = """
numbers = [1, 2, 3, 4, 5]
squared = [x**2 for x in numbers]
print(f"原数组: {numbers}")
print(f"平方数组: {squared}")
"""
        result = await self.python_repl.execute_code(code)
        print(f"列表操作输出:\n{result['output']}")
        
        # 5. 测试安全限制
        result = await self.python_repl.execute_code("import os")
        print(f"安全限制测试: {result['success']}, 错误: {result['error']}")
    
    async def web_search_examples(self):
        """网络搜索工具使用示例"""
        print("\n=== 网络搜索工具示例 ===")
        
        try:
            # 1. 基本搜索
            result = await self.web_search.search("Python编程语言", max_results=3)
            if result["success"]:
                print(f"搜索到 {result['results_count']} 个结果:")
                for i, item in enumerate(result["results"][:2], 1):
                    print(f"{i}. {item['title']}")
                    print(f"   {item['content'][:100]}...")
            
            # 2. 获取网页内容
            if result["success"] and result["results"]:
                first_url = result["results"][0].get("url")
                if first_url:
                    content_result = await self.web_search.get_webpage_content(first_url, max_length=500)
                    if content_result["success"]:
                        print(f"\n网页标题: {content_result['title']}")
                        print(f"网页内容预览: {content_result['content'][:200]}...")
            
        except Exception as e:
            print(f"网络搜索示例失败: {e}")
    
    async def document_retrieval_examples(self):
        """文档检索工具使用示例"""
        print("\n=== 文档检索工具示例 ===")
        
        try:
            # 1. 添加示例文本到知识库
            sample_text = """
            软件测试是软件开发过程中的重要环节。
            
            主要的测试类型包括：
            1. 单元测试 - 测试单个组件或模块
            2. 集成测试 - 测试组件间的交互
            3. 系统测试 - 测试整个系统的功能
            4. 验收测试 - 验证系统是否满足用户需求
            
            自动化测试可以提高测试效率，减少人工错误。
            常用的测试框架包括pytest、unittest等。
            """
            
            await self.rag_service.add_text_directly(
                sample_text,
                {"source": "example", "type": "testing_guide"},
                collection_name="examples"
            )
            
            # 2. 搜索相关文档
            search_result = await self.doc_retrieval.search_documents(
                "自动化测试框架",
                collection_name="examples",
                top_k=3
            )
            
            if search_result["success"]:
                print(f"找到 {search_result['results_count']} 个相关文档:")
                for i, doc in enumerate(search_result["results"], 1):
                    print(f"{i}. 相似度: {doc['similarity_score']:.3f}")
                    print(f"   内容: {doc['content'][:100]}...")
            
            # 3. 关键词搜索
            keyword_result = await self.doc_retrieval.search_by_keywords(
                ["单元测试", "集成测试"],
                collection_name="examples"
            )
            
            if keyword_result["success"]:
                print(f"\n关键词搜索结果:")
                combined_results = keyword_result.get("combined_results", [])
                for i, doc in enumerate(combined_results[:2], 1):
                    print(f"{i}. {doc['content'][:80]}...")
            
        except Exception as e:
            print(f"文档检索示例失败: {e}")
    
    async def decorator_examples(self):
        """装饰器使用示例"""
        print("\n=== 装饰器使用示例 ===")
        
        # 1. 基本工具装饰器
        @tool(name="example_calculator", description="示例计算器", category="math")
        def calculate(expression: str) -> float:
            """安全的表达式计算"""
            try:
                # 只允许基本的数学运算
                allowed_chars = set("0123456789+-*/.() ")
                if all(c in allowed_chars for c in expression):
                    return eval(expression)
                else:
                    raise ValueError("不允许的字符")
            except Exception as e:
                raise ValueError(f"计算错误: {e}")
        
        result = calculate("2 + 3 * 4")
        print(f"计算结果: {result}")
        
        # 2. 速率限制装饰器
        @rate_limit(calls_per_minute=3)
        def limited_function(x: int) -> int:
            return x * 2
        
        print("测试速率限制:")
        for i in range(3):
            result = limited_function(i)
            print(f"调用 {i+1}: {result}")
        
        # 3. 输入验证装饰器
        @validate_input(
            name={'type': str, 'min_length': 1},
            age={'type': int}
        )
        def create_user(name: str, age: int) -> str:
            return f"用户: {name}, 年龄: {age}"
        
        try:
            result = create_user("张三", 25)
            print(f"创建用户: {result}")
        except Exception as e:
            print(f"验证失败: {e}")
        
        # 4. 缓存装饰器
        @cache_result(ttl=60)
        def expensive_calculation(n: int) -> int:
            """模拟耗时计算"""
            import time
            time.sleep(0.1)  # 模拟耗时
            return n ** 2
        
        import time
        start = time.time()
        result1 = expensive_calculation(10)
        time1 = time.time() - start
        
        start = time.time()
        result2 = expensive_calculation(10)  # 应该使用缓存
        time2 = time.time() - start
        
        print(f"第一次计算: {result1}, 耗时: {time1:.3f}s")
        print(f"第二次计算: {result2}, 耗时: {time2:.3f}s (使用缓存)")
    
    async def run_all_examples(self):
        """运行所有示例"""
        print("开始运行工具示例...")
        
        await self.python_repl_examples()
        await self.web_search_examples()
        await self.document_retrieval_examples()
        await self.decorator_examples()
        
        print("\n所有示例运行完成!")
    
    async def cleanup(self):
        """清理资源"""
        await self.web_search.close()


# 智能体工具集成示例
class AgentToolkit:
    """智能体工具包"""
    
    def __init__(self):
        self.tools = {}
        self._setup_tools()
    
    def _setup_tools(self):
        """设置工具"""
        # Python代码执行工具
        @tool(name="execute_python", description="执行Python代码", category="code")
        async def execute_python(code: str) -> Dict[str, Any]:
            repl = PythonREPL()
            return await repl.execute_code(code)
        
        # 网络搜索工具
        @tool(name="web_search", description="网络搜索", category="search")
        async def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
            search_tool = WebSearchTool()
            try:
                return await search_tool.search(query, max_results=max_results)
            finally:
                await search_tool.close()
        
        # 文档搜索工具
        @tool(name="document_search", description="文档搜索", category="search")
        async def document_search(query: str, collection: str = "default") -> Dict[str, Any]:
            rag_service = RAGService()
            doc_tool = DocumentRetrievalTool(rag_service)
            return await doc_tool.search_documents(query, collection_name=collection)
        
        self.tools = {
            "execute_python": execute_python,
            "web_search": web_search,
            "document_search": document_search
        }
    
    async def use_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """使用工具"""
        if tool_name not in self.tools:
            return {"success": False, "error": f"工具 '{tool_name}' 不存在"}
        
        try:
            result = await self.tools[tool_name](**kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_tools(self) -> list:
        """列出可用工具"""
        return list(self.tools.keys())


async def main():
    """主函数，运行示例"""
    examples = ToolExamples()
    
    try:
        await examples.run_all_examples()
        
        # 测试智能体工具包
        print("\n=== 智能体工具包示例 ===")
        toolkit = AgentToolkit()
        
        print(f"可用工具: {toolkit.list_tools()}")
        
        # 测试Python执行
        result = await toolkit.use_tool("execute_python", code="print('Hello from agent toolkit!')")
        if result["success"]:
            print(f"Python执行结果: {result['result']['output']}")
        
    finally:
        await examples.cleanup()


if __name__ == "__main__":
    asyncio.run(main())