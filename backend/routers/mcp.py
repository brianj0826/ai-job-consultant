# backend/routers/mcp.py
"""
MCP (Model Context Protocol) 服务端点
遵循 JSON-RPC 2.0 规范，暴露工具和资源给 MCP 客户端
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional, Any
import json

from backend.services.tools import TOOLS, execute_tool
from backend.services.rag import get_collection

router = APIRouter()

# ==================== MCP 协议常量 ====================
MCP_VERSION = "0.1.0"
SERVER_NAME = "ai-assistant-mcp"
SERVER_DESCRIPTION = "AI 文档助手 MCP Server - 提供文档检索、网页抓取、计算等工具"


# ==================== JSON-RPC 请求模型 ====================
class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict] = None
    id: Optional[Any] = None


# ==================== 工具定义转换 ====================
def _tool_to_mcp_format(tool: dict) -> dict:
    """将内部工具定义转为 MCP 标准格式"""
    fn = tool["function"]
    return {
        "name": fn["name"],
        "description": fn["description"],
        "inputSchema": {
            "type": "object",
            "properties": fn.get("parameters", {}).get("properties", {}),
            "required": fn.get("parameters", {}).get("required", [])
        }
    }


# ==================== 资源列表构建 ====================
def _list_kb_resources(user_id: int = None) -> list:
    """列出知识库作为 MCP 资源"""
    if user_id is None:
        return []
    try:
        coll = get_collection(user_id)
        count = coll.count()
        if count == 0:
            return []
        all_data = coll.get(limit=min(count, 100))
        sources = {}
        for meta in all_data.get('metadatas', []):
            src = meta.get('source', '')
            if src and src not in sources:
                sources[src] = meta.get('title', src)
        return [
            {
                "uri": f"kb://{user_id}/{src}",
                "name": title or src,
                "description": f"知识库文档: {title or src}",
                "mimeType": "text/plain"
            }
            for src, title in sources.items()
        ]
    except Exception:
        return []


# ==================== MCP 方法处理 ====================
def _handle_method(method: str, params: dict) -> dict:
    """分发 MCP 方法调用"""

    if method == "initialize":
        return {
            "protocolVersion": MCP_VERSION,
            "serverInfo": {
                "name": SERVER_NAME,
                "version": MCP_VERSION
            },
            "capabilities": {
                "tools": {},
                "resources": {}
            }
        }

    elif method == "tools/list":
        return {
            "tools": [_tool_to_mcp_format(t) for t in TOOLS]
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        user_id = params.get("user_id", 0)
        result = execute_tool(tool_name, user_id, arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": result
                }
            ]
        }

    elif method == "resources/list":
        user_id = params.get("user_id", 0) if params else 0
        return {
            "resources": _list_kb_resources(user_id)
        }

    elif method == "resources/read":
        # 读取知识库内容作为资源
        uri = params.get("uri", "")
        user_id = params.get("user_id", 0)
        coll = get_collection(user_id)
        all_data = coll.get(limit=min(coll.count(), 100))
        contents = []
        for doc, meta in zip(all_data.get('documents', []), all_data.get('metadatas', [])):
            if meta.get('source', '') in uri:
                contents.append({"uri": uri, "mimeType": "text/plain", "text": doc})
        return {"contents": contents[:3]}

    else:
        return {"error": f"未知方法: {method}"}


# ==================== MCP 端点 ====================
@router.post("/")
async def mcp_endpoint(request: Request):
    """
    MCP JSON-RPC 端点
    支持: initialize, tools/list, tools/call, resources/list, resources/read
    """
    try:
        body = await request.json()
        rpc = JsonRpcRequest(**body)
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": f"解析请求失败: {str(e)}"},
            "id": None
        }

    try:
        result = _handle_method(rpc.method, rpc.params or {})
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": rpc.id
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)},
            "id": rpc.id
        }


@router.get("/")
def mcp_info():
    """MCP 服务信息"""
    return {
        "name": SERVER_NAME,
        "version": MCP_VERSION,
        "protocol": "JSON-RPC 2.0",
        "endpoint": "/api/mcp/",
        "description": SERVER_DESCRIPTION,
        "methods": ["initialize", "tools/list", "tools/call", "resources/list", "resources/read"],
        "tools_count": len(TOOLS)
    }
