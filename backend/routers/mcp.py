"""Authenticated MCP (Model Context Protocol) endpoint.

MCP clients must authenticate with the same browser session as the application.
The protocol's arbitrary ``params`` object is never trusted for a user ID.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.services.access import current_user_id
from backend.services.auth import require_csrf, require_current_user
from backend.services.rag import get_collection
from backend.services.tools import TOOLS, execute_tool


router = APIRouter()

MCP_VERSION = "0.1.0"
SERVER_NAME = "ai-assistant-mcp"
SERVER_DESCRIPTION = "AI 文档助手 MCP Server - 提供文档检索、网页抓取、计算等工具"


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict] = None
    id: Optional[Any] = None


def _tool_to_mcp_format(tool: dict) -> dict:
    function = tool["function"]
    return {
        "name": function["name"],
        "description": function["description"],
        "inputSchema": {
            "type": "object",
            "properties": function.get("parameters", {}).get("properties", {}),
            "required": function.get("parameters", {}).get("required", []),
        },
    }


def _list_kb_resources(user_id: int) -> list:
    """List only the authenticated user's knowledge-base sources."""
    try:
        collection = get_collection(user_id)
        count = collection.count()
        if count == 0:
            return []
        all_data = collection.get(limit=min(count, 100))
        sources: dict[str, str] = {}
        for metadata in all_data.get("metadatas", []):
            source = metadata.get("source", "")
            if source and source not in sources:
                sources[source] = metadata.get("title", source)
        return [
            {
                "uri": f"kb://{user_id}/{source}",
                "name": title or source,
                "description": f"知识库文档 {title or source}",
                "mimeType": "text/plain",
            }
            for source, title in sources.items()
        ]
    except Exception:
        return []


def _read_kb_resource(uri: str, user_id: int) -> dict:
    """Read a resource only if its URI belongs to the current user."""
    prefix = f"kb://{user_id}/"
    if not uri.startswith(prefix):
        raise ValueError("资源不属于当前用户")

    source = uri[len(prefix) :]
    if not source:
        raise ValueError("资源 URI 无效")

    collection = get_collection(user_id)
    all_data = collection.get(limit=min(collection.count(), 100))
    contents = []
    for document, metadata in zip(
        all_data.get("documents", []), all_data.get("metadatas", [])
    ):
        if metadata.get("source", "") == source:
            contents.append({"uri": uri, "mimeType": "text/plain", "text": document})
    return {"contents": contents[:3]}


def _handle_method(method: str, params: dict, user_id: int) -> dict:
    """Dispatch a JSON-RPC MCP operation for the authenticated user."""
    if method == "initialize":
        return {
            "protocolVersion": MCP_VERSION,
            "serverInfo": {"name": SERVER_NAME, "version": MCP_VERSION},
            "capabilities": {"tools": {}, "resources": {}},
        }
    if method == "tools/list":
        return {"tools": [_tool_to_mcp_format(tool) for tool in TOOLS]}
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = execute_tool(tool_name, user_id, arguments)
        return {"content": [{"type": "text", "text": result}]}
    if method == "resources/list":
        return {"resources": _list_kb_resources(user_id)}
    if method == "resources/read":
        return _read_kb_resource(params.get("uri", ""), user_id)
    return {"error": f"未知方法: {method}"}


@router.post("/", dependencies=[Depends(require_csrf)])
async def mcp_endpoint(
    request: Request,
    current_user: dict = Depends(require_current_user),
):
    """Serve JSON-RPC after binding all work to the authenticated user."""
    try:
        rpc = JsonRpcRequest(**(await request.json()))
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": f"解析请求失败: {exc}"},
            "id": None,
        }

    try:
        result = _handle_method(
            rpc.method,
            rpc.params or {},
            current_user_id(current_user),
        )
        return {"jsonrpc": "2.0", "result": result, "id": rpc.id}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(exc)},
            "id": rpc.id,
        }


@router.get("/")
def mcp_info(current_user: dict = Depends(require_current_user)):
    """Return protocol metadata to a signed-in client only."""
    current_user_id(current_user)
    return {
        "name": SERVER_NAME,
        "version": MCP_VERSION,
        "protocol": "JSON-RPC 2.0",
        "endpoint": "/api/mcp/",
        "description": SERVER_DESCRIPTION,
        "methods": [
            "initialize",
            "tools/list",
            "tools/call",
            "resources/list",
            "resources/read",
        ],
        "tools_count": len(TOOLS),
    }
