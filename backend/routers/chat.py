from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from typing import Optional
import sys
import json
import time
sys.path.append("..")
from backend.services.database import (
    ChatRequestOwnershipError,
    chat_request_lease_seconds,
    complete_chat_request,
    get_session_messages,
    release_chat_request,
    renew_chat_request_lease,
    reserve_chat_request,
    save_message,
)
from backend.services.rag import search_document, build_rag_context
from backend.services.deepseek_api import get_ai_response, get_ai_response_with_tools, get_ai_response_stream
from backend.services.memory import trim_history, generate_summary
from backend.services.tools import TOOLS, execute_tool
from backend.services.security import moderate_text, check_rate_limit, sanitize_input
from backend.services.access import current_user_id, require_owned_session
from backend.services.auth import require_business_csrf, require_current_user

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: int
    client_request_id: Optional[str] = Field(default=None, min_length=1, max_length=128)


def _request_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="client_request_id 不能为空")
    return normalized


def _reserve_request(
    user_id: int,
    session_id: int,
    prompt: str,
    client_request_id: Optional[str],
) -> tuple[Optional[dict], Optional[str]]:
    if not client_request_id:
        save_message(user_id, session_id, "user", prompt)
        return None, None
    state, owner_token, assistant = reserve_chat_request(
        user_id,
        session_id,
        prompt,
        client_request_id,
    )
    if state == "completed":
        return assistant, None
    if state == "mismatch":
        raise HTTPException(
            status_code=409,
            detail="client_request_id 已用于不同的消息内容",
        )
    if state == "processing":
        raise HTTPException(
            status_code=409,
            detail="相同请求正在处理中",
            headers={"Retry-After": "2"},
        )
    return None, owner_token


def _release_request(
    user_id: int,
    session_id: int,
    client_request_id: Optional[str],
    owner_token: Optional[str],
) -> None:
    if client_request_id and owner_token:
        release_chat_request(
            user_id,
            session_id,
            client_request_id,
            owner_token,
        )


def _renew_request(
    user_id: int,
    session_id: int,
    client_request_id: Optional[str],
    owner_token: Optional[str],
) -> None:
    if client_request_id and owner_token:
        renew_chat_request_lease(
            user_id,
            session_id,
            client_request_id,
            owner_token,
        )


def _complete_request(
    user_id: int,
    session_id: int,
    client_request_id: Optional[str],
    owner_token: Optional[str],
    content: str,
) -> int:
    if client_request_id:
        if not owner_token:
            raise ChatRequestOwnershipError("Missing chat request owner")
        return complete_chat_request(
            user_id,
            session_id,
            client_request_id,
            owner_token,
            content,
        )
    return save_message(user_id, session_id, "assistant", content)


def _complete_nonstream_chat(
    user_id: int,
    session_id: int,
    prompt: str,
    client_request_id: Optional[str],
    owner_token: Optional[str],
) -> dict:
    _renew_request(user_id, session_id, client_request_id, owner_token)
    context_text, rag_sources = build_rag_context(prompt, user_id=user_id, top_k=10)
    api_messages = []
    if context_text:
        source_list = "\n".join([f"- 来源{s['id']}: {s['source']}" for s in rag_sources])
        system_prompt = f"""你是"职达"AI求职顾问，由资深HR和技术面试官团队打造。你的职责是帮助用户提升求职竞争力。

核心能力：
1. 简历分析：指出优缺点，给出具体修改建议（STAR法则、量化成果、关键词优化）
2. 岗位匹配：对比简历和JD，评估匹配度，指出缺失技能
3. 面试模拟：出题、倾听回答、打分、给出改进建议
4. 职业建议：根据行业趋势给方向建议

风格：专业但亲切，用具体例子说明，避免空泛评价。
工具优先于参考资料，用户要求操作时务必调用工具。

仅当用户询问上传文档的具体内容时，参考以下资料：
{context_text}

可引用的来源：
{source_list}"""
    else:
        system_prompt = '你是"职达"AI求职顾问。你帮助用户分析简历、匹配岗位、模拟面试。请专业、具体、有建设性地回答。'
    system_prompt += "\n\n你可以使用提供的工具（如查询知识库信息、获取当前时间）来更好地服务用户。"
    api_messages.append({"role": "system", "content": system_prompt})

    history = get_session_messages(session_id, limit=50)
    history_list = [{"role": role, "content": content} for _, role, content, _, _ in history]
    recent = trim_history(history_list, max_turns=5)
    if len(history_list) > len(recent):
        summary = generate_summary(history_list)
        if summary:
            api_messages[0]["content"] = f"[对话历史摘要] {summary}\n\n{api_messages[0]['content']}"
    api_messages.extend(recent)

    response_text = ""
    for _ in range(3):
        _renew_request(user_id, session_id, client_request_id, owner_token)
        result = get_ai_response_with_tools(api_messages, tools=TOOLS)
        if not result:
            response_text = "抱歉，AI 服务暂时不可用。"
            break
        choice = result["choices"][0]
        if choice.get("finish_reason") == "tool_calls":
            tool_calls = choice["message"].get("tool_calls", [])
            api_messages.append(choice["message"])
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                try:
                    tool_args = json.loads(tool_call["function"].get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}
                tool_result = execute_tool(function_name, user_id, tool_args)
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": tool_result,
                    }
                )
        else:
            response_text = choice["message"]["content"]
            break
    else:
        response_text = "处理工具调用时出现循环超限。"

    is_safe, reason = moderate_text(response_text, user_id)
    if not is_safe:
        response_text = f"[系统提示] 回复内容已被安全策略拦截（{reason}），请重新提问。"
    message_id = _complete_request(
        user_id,
        session_id,
        client_request_id,
        owner_token,
        response_text,
    )
    return {
        "response": response_text,
        "msg_id": message_id,
        "sources": [
            {"id": source["id"], "source": source["source"], "title": source["title"]}
            for source in rag_sources
        ],
    }


def _prepare_stream_chat(
    user_id: int,
    session_id: int,
    prompt: str,
    client_request_id: Optional[str],
    owner_token: Optional[str],
) -> tuple[list, list]:
    _renew_request(user_id, session_id, client_request_id, owner_token)
    context_text, rag_sources = build_rag_context(prompt, user_id=user_id, top_k=10)
    if context_text:
        source_list = "\n".join([f"- 来源{s['id']}: {s['source']}" for s in rag_sources])
        system_prompt = f"""你是"职达"AI求职顾问。工具调用优先于参考资料。
参考资料：
{context_text}
可引用文件：
{source_list}"""
    else:
        system_prompt = '你是"职达"AI求职顾问。请专业、具体地回答用户关于求职的问题。'

    api_messages = [{"role": "system", "content": system_prompt}]
    history = get_session_messages(session_id, limit=30)
    history_list = [{"role": role, "content": content} for _, role, content, _, _ in history]
    recent = trim_history(history_list, max_turns=5)
    if len(history_list) > len(recent):
        summary = generate_summary(history_list)
        if summary:
            api_messages[0]["content"] = f"[历史摘要] {summary}\n\n{api_messages[0]['content']}"
    api_messages.extend(recent)
    sources_data = [
        {"id": source["id"], "source": source["source"], "title": source["title"]}
        for source in rag_sources
    ]

    tool_messages = [message.copy() for message in api_messages]
    _renew_request(user_id, session_id, client_request_id, owner_token)
    tool_result = get_ai_response_with_tools(tool_messages, tools=TOOLS, max_retries=0)
    if tool_result:
        choice = tool_result["choices"][0]
        if choice.get("finish_reason") == "tool_calls":
            tool_calls = choice["message"].get("tool_calls", [])
            api_messages.append(choice["message"])
            for tool_call in tool_calls[:3]:
                function_name = tool_call["function"]["name"]
                try:
                    tool_args = json.loads(tool_call["function"].get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": execute_tool(function_name, user_id, tool_args),
                    }
                )
    return api_messages, sources_data


def _stream_events(
    api_messages: list,
    sources_data: list,
    user_id: int,
    session_id: int,
    client_request_id: Optional[str],
    owner_token: Optional[str],
):
    full_text = ""
    renewal_interval = max(5.0, chat_request_lease_seconds() / 3)
    renew_at = time.monotonic() + renewal_interval
    try:
        for token in get_ai_response_stream(api_messages):
            if time.monotonic() >= renew_at:
                _renew_request(user_id, session_id, client_request_id, owner_token)
                renew_at = time.monotonic() + renewal_interval
            full_text += token
            yield f"data: {json.dumps({'token': token})}\n\n"

        message_id = _complete_request(
            user_id,
            session_id,
            client_request_id,
            owner_token,
            full_text,
        )
        yield f"data: {json.dumps({'done': True, 'msg_id': message_id, 'sources': sources_data})}\n\n"
    except GeneratorExit:
        _release_request(user_id, session_id, client_request_id, owner_token)
        raise
    except Exception as error:
        if full_text:
            try:
                message_id = _complete_request(
                    user_id,
                    session_id,
                    client_request_id,
                    owner_token,
                    full_text,
                )
            except Exception as save_error:
                _release_request(user_id, session_id, client_request_id, owner_token)
                yield f"data: {json.dumps({'error': str(save_error)})}\n\n"
            else:
                yield f"data: {json.dumps({'done': True, 'msg_id': message_id, 'sources': sources_data})}\n\n"
        else:
            _release_request(user_id, session_id, client_request_id, owner_token)
            yield f"data: {json.dumps({'error': str(error)})}\n\n"

@router.post("/", dependencies=[Depends(require_business_csrf)])
def chat(
    request: ChatRequest,
    current_user: dict = Depends(require_current_user),
):
    user_id = current_user_id(current_user)
    session_id = request.session_id
    require_owned_session(session_id, current_user)
    prompt = request.message
    client_request_id = _request_id(request.client_request_id)

    # 0a. 频率限制检查
    allowed, wait = check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"请求太频繁，请 {wait} 秒后再试。",
            headers={"Retry-After": str(wait)},
        )

    # 0b. 输入净化
    prompt = sanitize_input(prompt)
    if not prompt:
        raise HTTPException(status_code=400, detail="消息内容不能为空。")

    # 0c. 内容审核（用户输入）
    is_safe, reason = moderate_text(prompt, user_id)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    # 1. Reserve the optional idempotency key before invoking the model.
    replay, owner_token = _reserve_request(
        user_id,
        session_id,
        prompt,
        client_request_id,
    )
    if replay:
        return {
            "response": replay["content"],
            "msg_id": replay["id"],
            "sources": [],
            "replayed": True,
        }

    try:
        return _complete_nonstream_chat(
            user_id,
            session_id,
            prompt,
            client_request_id,
            owner_token,
        )
    except ChatRequestOwnershipError as error:
        _release_request(user_id, session_id, client_request_id, owner_token)
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception:
        _release_request(user_id, session_id, client_request_id, owner_token)
        raise


@router.post("/stream", dependencies=[Depends(require_business_csrf)])
def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(require_current_user),
):
    """流式聊天端点（SSE），含工具调用预检"""
    user_id = current_user_id(current_user)
    session_id = request.session_id
    require_owned_session(session_id, current_user)
    prompt = request.message
    client_request_id = _request_id(request.client_request_id)

    # 安全检查
    allowed, wait = check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"请求太频繁，请 {wait} 秒后再试。",
            headers={"Retry-After": str(wait)},
        )

    prompt = sanitize_input(prompt)
    if not prompt:
        raise HTTPException(status_code=400, detail="消息内容不能为空。")

    is_safe, reason = moderate_text(prompt, user_id)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    replay, owner_token = _reserve_request(
        user_id,
        session_id,
        prompt,
        client_request_id,
    )
    if replay:
        def replay_completed():
            yield f"data: {json.dumps({'token': replay['content']})}\n\n"
            yield f"data: {json.dumps({'done': True, 'msg_id': replay['id'], 'sources': [], 'replayed': True})}\n\n"

        return StreamingResponse(replay_completed(), media_type="text/event-stream")

    try:
        api_messages, sources_data = _prepare_stream_chat(
            user_id,
            session_id,
            prompt,
            client_request_id,
            owner_token,
        )
    except ChatRequestOwnershipError as error:
        _release_request(user_id, session_id, client_request_id, owner_token)
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception:
        _release_request(user_id, session_id, client_request_id, owner_token)
        raise

    return StreamingResponse(
        _stream_events(
            api_messages,
            sources_data,
            user_id,
            session_id,
            client_request_id,
            owner_token,
        ),
        media_type="text/event-stream",
        background=BackgroundTask(
            _release_request,
            user_id,
            session_id,
            client_request_id,
            owner_token,
        ),
    )
