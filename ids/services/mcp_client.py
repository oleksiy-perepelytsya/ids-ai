"""MCPSearchClient — fetch context from an MCP server for the Sourcer agent."""

from __future__ import annotations

import json
from typing import Optional

from ids.utils import get_logger

logger = get_logger(__name__)

# Tool names to try in order when auto-discovering the search tool.
_SEARCH_TOOL_CANDIDATES = [
    "search",
    "query",
    "retrieve",
    "find",
    "search_documents",
    "search_context",
    "search_knowledge",
]


class MCPSearchClient:
    """Connects to an MCP SSE server and calls its search tool.

    One instance per URL; caches the resolved tool name after first discovery.
    Connection is opened per call — acceptable for sourcer frequency.
    """

    def __init__(self, url: str, tool_name: Optional[str] = None):
        self.url = url
        self._tool_name: Optional[str] = tool_name  # None = auto-discover

    async def search(self, query: str, n: int = 5) -> list[dict]:
        """Return results in the learning_patterns shape: [{content, metadata, distance}]."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError:
            logger.error("mcp_package_missing", hint="poetry add mcp")
            return []

        try:
            async with sse_client(url=self.url) as (read, write):
                async with ClientSession(read, write) as sess:
                    await sess.initialize()
                    tool = await self._resolve_tool(sess)
                    if not tool:
                        logger.warning("mcp_no_search_tool_found", url=self.url)
                        return []
                    logger.info("mcp_search", url=self.url, tool=tool, query=query[:80])
                    result = await sess.call_tool(tool, {"query": query, "limit": n})
                    hits = _parse_tool_result(result, n)
                    logger.info("mcp_search_done", hits=len(hits))
                    return hits
        except Exception as e:
            logger.error("mcp_search_failed", url=self.url, error=str(e))
            return []

    async def _resolve_tool(self, sess) -> Optional[str]:
        if self._tool_name:
            return self._tool_name
        tools_result = await sess.list_tools()
        available = {t.name for t in tools_result.tools}
        for candidate in _SEARCH_TOOL_CANDIDATES:
            if candidate in available:
                self._tool_name = candidate
                return candidate
        # Fuzzy: first tool whose name contains "search"
        for name in available:
            if "search" in name.lower() or "query" in name.lower():
                self._tool_name = name
                return name
        # Last resort: first available tool
        if tools_result.tools:
            self._tool_name = tools_result.tools[0].name
            return self._tool_name
        return None


def _parse_tool_result(result, n: int) -> list[dict]:
    """Convert MCP CallToolResult content into learning_patterns dicts."""
    hits: list[dict] = []

    for block in result.content:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            hits.append({"content": text, "metadata": {"source": "mcp"}, "distance": 0.2})
            continue

        if isinstance(data, list):
            for item in data:
                hits.append(_item_to_pattern(item))
        elif isinstance(data, dict):
            # Unwrap common envelope keys
            items = (
                data.get("results")
                or data.get("documents")
                or data.get("hits")
                or data.get("items")
            )
            if isinstance(items, list):
                for item in items:
                    hits.append(_item_to_pattern(item))
            else:
                hits.append({"content": text, "metadata": {"source": "mcp"}, "distance": 0.2})
        else:
            hits.append({"content": text, "metadata": {"source": "mcp"}, "distance": 0.2})

    return hits[:n]


def _item_to_pattern(item: dict) -> dict:
    content = (
        item.get("content")
        or item.get("text")
        or item.get("page_content")
        or str(item)
    )
    score = item.get("score") or item.get("relevance") or item.get("similarity") or 0.8
    metadata = item.get("metadata") or {
        k: v for k, v in item.items() if k not in {"content", "text", "score", "relevance", "similarity", "page_content"}
    }
    metadata.setdefault("source", "mcp")
    return {"content": content, "metadata": metadata, "distance": round(1.0 - float(score), 4)}
