"""网络搜索工具模块"""

import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus, urljoin
import re
from bs4 import BeautifulSoup

from ..config.logging_config import get_logger
from ..config.settings import get_settings
from ..exceptions import ToolException
from ..utils.performance import async_monitor_performance

logger = get_logger("web_search")


class WebSearchTool:
    """网络搜索工具，支持多种搜索引擎"""

    def __init__(self, timeout: int = 30, max_results: int = 10):
        """初始化网络搜索工具

        Args:
            timeout: 请求超时时间
            max_results: 最大搜索结果数量
        """
        self.timeout = timeout
        self.max_results = max_results
        self.session = None

        # 搜索引擎配置
        self.search_engines = {
            "duckduckgo": {
                "url": "https://api.duckduckgo.com/",
                "params": {"format": "json", "no_html": "1", "skip_disambig": "1"},
            },
            "bing": {
                "url": "https://api.bing.microsoft.com/v7.0/search",
                "headers": {"Ocp-Apim-Subscription-Key": ""},  # 需要API密钥
            },
        }

        logger.info("Web search tool initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
        return self.session

    @async_monitor_performance
    async def search_duckduckgo(
        self, query: str, max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """使用DuckDuckGo搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数量

        Returns:
            搜索结果
        """
        try:
            logger.info(f"Searching DuckDuckGo for: {query}")

            max_results = max_results or self.max_results
            session = await self._get_session()

            # DuckDuckGo Instant Answer API
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            }

            async with session.get(
                "https://api.duckduckgo.com/", params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    results = []

                    # 处理即时答案
                    if data.get("Answer"):
                        results.append(
                            {
                                "title": "即时答案",
                                "content": data["Answer"],
                                "url": data.get("AnswerURL", ""),
                                "type": "instant_answer",
                            }
                        )

                    # 处理摘要
                    if data.get("Abstract"):
                        results.append(
                            {
                                "title": data.get("Heading", "摘要"),
                                "content": data["Abstract"],
                                "url": data.get("AbstractURL", ""),
                                "type": "abstract",
                            }
                        )

                    # 处理相关主题
                    for topic in data.get("RelatedTopics", [])[:max_results]:
                        if isinstance(topic, dict) and topic.get("Text"):
                            results.append(
                                {
                                    "title": topic.get("Text", "").split(" - ")[0],
                                    "content": topic.get("Text", ""),
                                    "url": topic.get("FirstURL", ""),
                                    "type": "related_topic",
                                }
                            )

                    return {
                        "success": True,
                        "query": query,
                        "engine": "duckduckgo",
                        "results_count": len(results),
                        "results": results[:max_results],
                    }
                else:
                    return {
                        "success": False,
                        "error": f"DuckDuckGo API返回状态码: {response.status}",
                        "query": query,
                        "results": [],
                    }

        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return {
                "success": False,
                "error": f"DuckDuckGo搜索失败: {str(e)}",
                "query": query,
                "results": [],
            }

    @async_monitor_performance
    async def search_web_scraping(
        self, query: str, max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """通过网页抓取进行搜索（备用方案）

        Args:
            query: 搜索查询
            max_results: 最大结果数量

        Returns:
            搜索结果
        """
        try:
            logger.info(f"Web scraping search for: {query}")

            max_results = max_results or self.max_results
            session = await self._get_session()

            # 使用DuckDuckGo的HTML搜索页面
            search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"

            async with session.get(search_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    results = []

                    # 解析搜索结果
                    for result_div in soup.find_all("div", class_="result")[
                        :max_results
                    ]:
                        try:
                            # 提取标题和链接
                            title_link = result_div.find("a", class_="result__a")
                            if title_link:
                                title = title_link.get_text(strip=True)
                                url = title_link.get("href", "")

                                # 提取描述
                                snippet_div = result_div.find(
                                    "div", class_="result__snippet"
                                )
                                content = (
                                    snippet_div.get_text(strip=True)
                                    if snippet_div
                                    else ""
                                )

                                if title and url:
                                    results.append(
                                        {
                                            "title": title,
                                            "content": content,
                                            "url": url,
                                            "type": "web_result",
                                        }
                                    )
                        except Exception as e:
                            logger.warning(f"Failed to parse search result: {e}")
                            continue

                    return {
                        "success": True,
                        "query": query,
                        "engine": "web_scraping",
                        "results_count": len(results),
                        "results": results,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"网页搜索返回状态码: {response.status}",
                        "query": query,
                        "results": [],
                    }

        except Exception as e:
            logger.error(f"Web scraping search failed: {e}")
            return {
                "success": False,
                "error": f"网页搜索失败: {str(e)}",
                "query": query,
                "results": [],
            }

    @async_monitor_performance
    async def search(
        self, query: str, engine: str = "auto", max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """执行网络搜索

        Args:
            query: 搜索查询
            engine: 搜索引擎 (auto, duckduckgo, web_scraping)
            max_results: 最大结果数量

        Returns:
            搜索结果
        """
        try:
            if not query or not query.strip():
                return {
                    "success": False,
                    "error": "搜索查询不能为空",
                    "query": query,
                    "results": [],
                }

            query = query.strip()
            max_results = max_results or self.max_results

            if engine == "auto":
                # 自动选择搜索引擎，优先使用DuckDuckGo API
                result = await self.search_duckduckgo(query, max_results)

                # 如果DuckDuckGo失败或结果为空，尝试网页抓取
                if not result["success"] or len(result["results"]) == 0:
                    logger.info("DuckDuckGo failed, trying web scraping")
                    result = await self.search_web_scraping(query, max_results)

                return result

            elif engine == "duckduckgo":
                return await self.search_duckduckgo(query, max_results)

            elif engine == "web_scraping":
                return await self.search_web_scraping(query, max_results)

            else:
                return {
                    "success": False,
                    "error": f"不支持的搜索引擎: {engine}",
                    "query": query,
                    "results": [],
                }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                "success": False,
                "error": f"搜索失败: {str(e)}",
                "query": query,
                "results": [],
            }

    @async_monitor_performance
    async def get_webpage_content(
        self, url: str, max_length: int = 5000
    ) -> Dict[str, Any]:
        """获取网页内容

        Args:
            url: 网页URL
            max_length: 最大内容长度

        Returns:
            网页内容
        """
        try:
            logger.info(f"Fetching webpage: {url}")

            session = await self._get_session()

            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # 移除脚本和样式标签
                    for script in soup(["script", "style"]):
                        script.decompose()

                    # 提取文本内容
                    text = soup.get_text()

                    # 清理文本
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (
                        phrase.strip() for line in lines for phrase in line.split("  ")
                    )
                    text = " ".join(chunk for chunk in chunks if chunk)

                    # 限制长度
                    if len(text) > max_length:
                        text = text[:max_length] + "..."

                    # 提取标题
                    title = soup.find("title")
                    title_text = title.get_text(strip=True) if title else ""

                    return {
                        "success": True,
                        "url": url,
                        "title": title_text,
                        "content": text,
                        "content_length": len(text),
                        "status_code": response.status,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP状态码: {response.status}",
                        "url": url,
                        "content": "",
                        "status_code": response.status,
                    }

        except Exception as e:
            logger.error(f"Failed to fetch webpage {url}: {e}")
            return {
                "success": False,
                "error": f"获取网页失败: {str(e)}",
                "url": url,
                "content": "",
            }

    @async_monitor_performance
    async def search_and_summarize(
        self, query: str, max_results: int = 5, include_content: bool = False
    ) -> Dict[str, Any]:
        """搜索并总结结果

        Args:
            query: 搜索查询
            max_results: 最大结果数量
            include_content: 是否包含网页内容

        Returns:
            搜索和总结结果
        """
        try:
            # 执行搜索
            search_result = await self.search(query, max_results=max_results)

            if not search_result["success"]:
                return search_result

            # 如果需要包含网页内容，获取前几个结果的内容
            if include_content and search_result["results"]:
                enhanced_results = []

                for result in search_result["results"][:3]:  # 只获取前3个结果的内容
                    enhanced_result = result.copy()

                    if result.get("url"):
                        content_result = await self.get_webpage_content(
                            result["url"], max_length=1000
                        )

                        if content_result["success"]:
                            enhanced_result["webpage_content"] = content_result[
                                "content"
                            ]
                            enhanced_result["webpage_title"] = content_result["title"]

                    enhanced_results.append(enhanced_result)

                search_result["results"] = enhanced_results

            # 生成简单的总结
            summary_parts = []
            for result in search_result["results"][:3]:
                if result.get("content"):
                    summary_parts.append(
                        f"• {result['title']}: {result['content'][:200]}..."
                    )

            search_result["summary"] = "\n".join(summary_parts)

            return search_result

        except Exception as e:
            logger.error(f"Search and summarize failed: {e}")
            return {
                "success": False,
                "error": f"搜索总结失败: {str(e)}",
                "query": query,
                "results": [],
            }

    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": "WebSearchTool",
            "description": "网络搜索工具，支持多种搜索引擎",
            "timeout": self.timeout,
            "max_results": self.max_results,
            "supported_engines": ["duckduckgo", "web_scraping"],
            "capabilities": ["search", "get_webpage_content", "search_and_summarize"],
        }

    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# 工具装饰器函数
def web_search_tool(timeout: int = 30, max_results: int = 10):
    """网络搜索工具装饰器"""
    tool = WebSearchTool(timeout=timeout, max_results=max_results)

    async def search_wrapper(
        query: str, engine: str = "auto", max_results: Optional[int] = None
    ) -> str:
        """搜索包装函数，返回格式化的结果"""
        result = await tool.search(query, engine, max_results)

        if result["success"]:
            if result["results"]:
                formatted_results = []
                for i, item in enumerate(result["results"], 1):
                    formatted_results.append(
                        f"{i}. {item['title']}\n"
                        f"   {item['content'][:200]}...\n"
                        f"   链接: {item.get('url', 'N/A')}\n"
                    )

                return (
                    f"搜索 '{query}' 找到 {len(result['results'])} 个结果:\n\n"
                    + "\n".join(formatted_results)
                )
            else:
                return f"未找到与 '{query}' 相关的搜索结果"
        else:
            return f"搜索失败: {result['error']}"

    return search_wrapper


def webpage_content_tool(timeout: int = 30):
    """网页内容获取工具装饰器"""
    tool = WebSearchTool(timeout=timeout)

    async def content_wrapper(url: str, max_length: int = 3000) -> str:
        """网页内容获取包装函数"""
        result = await tool.get_webpage_content(url, max_length)

        if result["success"]:
            return f"网页标题: {result['title']}\n\n网页内容:\n{result['content']}"
        else:
            return f"获取网页内容失败: {result['error']}"

    return content_wrapper
