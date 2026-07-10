from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import sys
import json
sys.path.append("..")
from backend.services.database import save_message, get_session_messages
from backend.services.rag import search_document, build_rag_context
from backend.services.deepseek_api import get_ai_response, get_ai_response_with_tools, get_ai_response_stream
from backend.services.memory import trim_history, generate_summary
from backend.services.tools import TOOLS, execute_tool
from backend.services.security import moderate_text, check_rate_limit, sanitize_input

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    user_id: int
    session_id: int

@router.post("/")
def chat(request: ChatRequest):
    user_id = request.user_id
    session_id = request.session_id
    prompt = request.message

    # 0a. 频率限制检查
    allowed, wait = check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"请求太频繁，请 {wait} 秒后再试。"
        )

    # 0b. 输入净化
    prompt = sanitize_input(prompt)
    if not prompt:
        raise HTTPException(status_code=400, detail="消息内容不能为空。")

    # 0c. 内容审核（用户输入）
    is_safe, reason = moderate_text(prompt, user_id)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    # 1. 保存用户消息
    save_message(user_id, session_id, "user", prompt)

    # 2. 始终检索知识库（有内容就用，没有则正常对话）
    rag_sources = []
    context_text, rag_sources = build_rag_context(prompt, user_id=user_id, top_k=10)

    # 3. 构建消息包
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

    # 加载历史并应用窗口
    history = get_session_messages(session_id, limit=50)
    history_list = [{"role": r, "content": c} for mid, r, c, fb, ts in history]
    recent = trim_history(history_list, max_turns=5)
    if len(history_list) > len(recent):
        summary = generate_summary(history_list)
        if summary:
            api_messages[0]["content"] = f"[对话历史摘要] {summary}\n\n{api_messages[0]['content']}"
    api_messages.extend(recent)

    # 4. 工具调用循环
    max_iter = 3
    response_text = ""
    for _ in range(max_iter):
        result = get_ai_response_with_tools(api_messages, tools=TOOLS)
        if not result:
            response_text = "抱歉，AI 服务暂时不可用。"
            break
        choice = result['choices'][0]
        if choice.get('finish_reason') == 'tool_calls':
            tool_calls = choice['message'].get('tool_calls', [])
            api_messages.append(choice['message'])
            for tc in tool_calls:
                fn_name = tc['function']['name']
                # 解析工具参数（大模型传来的 JSON 字符串）
                try:
                    import json
                    tool_args = json.loads(tc['function'].get('arguments', '{}'))
                except json.JSONDecodeError:
                    tool_args = {}
                tool_result = execute_tool(fn_name, user_id, tool_args)
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": fn_name,
                    "content": tool_result
                })
        else:
            response_text = choice['message']['content']
            break
    else:
        response_text = "处理工具调用时出现循环超限。"

    # 5. 内容审核（AI 输出），标记不安全内容
    is_safe, reason = moderate_text(response_text, user_id)
    if not is_safe:
        response_text = f"[系统提示] 回复内容已被安全策略拦截（{reason}），请重新提问。"

    # 6. 保存 AI 回复
    msg_id = save_message(user_id, session_id, "assistant", response_text)
    return {
        "response": response_text,
        "msg_id": msg_id,
        "sources": [{"id": s['id'], "source": s['source'], "title": s['title']} for s in rag_sources]
    }


@router.post("/stream")
def chat_stream(request: ChatRequest):
    """流式聊天端点（SSE），含工具调用预检"""
    user_id = request.user_id
    session_id = request.session_id
    prompt = request.message

    # 安全检查
    allowed, wait = check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"请求太频繁，请 {wait} 秒后再试。")

    prompt = sanitize_input(prompt)
    if not prompt:
        raise HTTPException(status_code=400, detail="消息内容不能为空。")

    is_safe, reason = moderate_text(prompt, user_id)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    # 保存用户消息
    save_message(user_id, session_id, "user", prompt)

    # RAG 检索（始终检索）
    context_text, rag_sources = build_rag_context(prompt, user_id=user_id, top_k=10)

    # 构建消息
    api_messages = []
    if context_text:
        source_list = "\n".join([f"- 来源{s['id']}: {s['source']}" for s in rag_sources])
        system_prompt = f"""你是"职达"AI求职顾问。工具调用优先于参考资料。
参考资料：
{context_text}
可引用文件：
{source_list}"""
    else:
        system_prompt = '你是"职达"AI求职顾问。请专业、具体地回答用户关于求职的问题。'

    api_messages.append({"role": "system", "content": system_prompt})

    # 加载历史
    history = get_session_messages(session_id, limit=30)
    history_list = [{"role": r, "content": c} for mid, r, c, fb, ts in history]
    recent = trim_history(history_list, max_turns=5)
    if len(history_list) > len(recent):
        summary = generate_summary(history_list)
        if summary:
            api_messages[0]["content"] = f"[历史摘要] {summary}\n\n{api_messages[0]['content']}"
    api_messages.extend(recent)

    # 构建 sources 数据
    sources_data = [{"id": s['id'], "source": s['source'], "title": s['title']} for s in rag_sources]

    # 工具调用预检（检测是否需要调用工具，如果需要则先执行）
    tool_messages = [api_messages[0].copy()]  # system prompt
    tool_messages.extend(api_messages[1:])      # history + user message
    tool_result = get_ai_response_with_tools(tool_messages, tools=TOOLS, max_retries=0)
    tool_executed = False
    if tool_result:
        choice = tool_result['choices'][0]
        if choice.get('finish_reason') == 'tool_calls':
            tool_calls = choice['message'].get('tool_calls', [])
            api_messages.append(choice['message'])  # 添加助手消息(含 tool_calls)
            for tc in tool_calls[:3]:  # 最多执行3个工具
                fn_name = tc['function']['name']
                try:
                    tool_args = json.loads(tc['function'].get('arguments', '{}'))
                except json.JSONDecodeError:
                    tool_args = {}
                tool_result_text = execute_tool(fn_name, user_id, tool_args)
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": fn_name,
                    "content": tool_result_text
                })
            tool_executed = True

    def generate():
        full_text = ""
        try:
            for token in get_ai_response_stream(api_messages):
                full_text += token
                yield f"data: {json.dumps({'token': token})}\n\n"

            msg_id = save_message(user_id, session_id, "assistant", full_text)
            yield f"data: {json.dumps({'done': True, 'msg_id': msg_id, 'sources': sources_data})}\n\n"
        except Exception as e:
            if full_text:
                msg_id = save_message(user_id, session_id, "assistant", full_text)
                yield f"data: {json.dumps({'done': True, 'msg_id': msg_id, 'sources': sources_data})}\n\n"
            else:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")