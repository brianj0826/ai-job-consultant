# tools.py
import datetime
import logging
from backend.services.rag import get_collection, search_document
from backend.services.deepseek_api import get_ai_response
from backend.services.crawler import fetch_url as crawl_url

logger = logging.getLogger("aiagent.tools")


# ==================== 工具函数 ====================

def get_knowledge_info(user_id: int):
    """返回当前用户知识库的信息，包含来源列表"""
    coll = get_collection(user_id)
    count = coll.count()
    if count == 0:
        return "当前知识库为空，尚未上传任何文档。"

    # 提取所有唯一来源
    sources = []
    try:
        all_data = coll.get(limit=min(count, 200))
        seen = set()
        for meta in all_data.get('metadatas', []):
            src = meta.get('source', '')
            title = meta.get('title', '')
            name = title or src
            if name and name not in seen:
                seen.add(name)
                src_type = meta.get('type', 'file')
                sources.append(f"  - {'🌐' if src_type == 'web' else '📄'} {name}")
    except Exception:
        pass

    src_text = "\n".join(sources[:10]) if sources else "  （无法获取来源信息）"
    return f"知识库统计：共 {count} 个文档块。\n\n已入库来源（{len(sources)} 个）：\n{src_text}"


def get_current_time():
    """返回当前日期和时间"""
    now = datetime.datetime.now()
    return now.strftime("今天是 %Y年%m月%d日，现在时间 %H:%M")


def summarize_document(user_id: int, batch_size=20, max_summary_length=500):
    """对当前用户的知识库文档进行分层摘要"""
    coll = get_collection(user_id)
    total = coll.count()
    if total == 0:
        return "知识库为空，无法生成摘要。"

    all_docs = coll.get(limit=total)['documents']
    if not all_docs:
        return "知识库中没有文本内容。"

    logger.info(f"开始分批摘要，共 {len(all_docs)} 个文档块")
    batch_summaries = []
    for i in range(0, len(all_docs), batch_size):
        batch = all_docs[i:i + batch_size]
        batch_text = "\n\n".join(batch)
        prompt = f"""请用100～200字总结以下文档片段的核心内容，只提取关键信息，不要添加解释。

文档片段：
{batch_text}

摘要："""
        try:
            summary = get_ai_response([{"role": "user", "content": prompt}], max_retries=1, timeout=60)
            batch_summaries.append(summary.strip())
        except Exception as e:
            batch_summaries.append("(本段摘要生成失败)")

    combined = "\n\n---\n\n".join(batch_summaries)
    final_prompt = f"""请根据以下多段摘要，整合出一份完整的文档整体摘要（{max_summary_length}字以内），
描述文档的主要内容、结构和关键点。

各段摘要：
{combined}

整体摘要："""
    try:
        return get_ai_response([{"role": "user", "content": final_prompt}], max_retries=2, timeout=120).strip()
    except Exception as e:
        return f"最终摘要生成失败：{e}"


def calculate(expression: str):
    """
    安全地计算数学表达式
    参数 expression: 数学表达式（支持 + - * / ** // % 和常用函数）
    """
    expr = expression.strip().strip('"').strip("'")
    # 安全白名单：只允许数字、运算符、括号、空格、小数点
    allowed = set('0123456789+-*/.() **%// ')
    # 额外允许的数学函数关键字
    safe_funcs = ['abs', 'round', 'min', 'max', 'pow', 'sqrt']
    import math
    safe_dict = {k: getattr(math, k, None) for k in safe_funcs}
    safe_dict['__builtins__'] = {}

    # 检查表达式安全性
    cleaned = expr.replace('**', '').replace('//', '')
    for ch in cleaned:
        if ch not in allowed and not ch.isalpha() and ch != '_':
            return f"表达式包含不允许的字符: {ch}"

    try:
        result = eval(expr, {"__builtins__": {}}, safe_dict)
        return f"计算结果：{expr} = {result}"
    except Exception as e:
        return f"计算失败：{e}"


def analyze_resume(user_id: int):
    """分析用户上传的简历，给出优缺点和改进建议"""
    coll = get_collection(user_id)
    total = coll.count()
    if total == 0:
        return "你还没有上传简历。请先上传简历PDF文件。"

    resume_text = "\n".join(coll.get(limit=min(total, 10))['documents'])
    prompt = f"""你是一位资深HR。请分析以下简历，给出具体、可操作的反馈：

简历内容：
{resume_text[:3000]}

请按以下格式回答：
1. 综合评分（1-10分）
2. 优点（列出3个，用具体例子说明）
3. 不足（列出3个，指出缺失的关键词或描述）
4. 改进建议（列出3条，用STAR法则示范改写）
5. 投递建议（适合什么类型的岗位）"""

    try:
        return get_ai_response([{"role": "user", "content": prompt}], max_retries=1, timeout=60).strip()
    except Exception as e:
        return f"简历分析失败：{e}"


def match_job(user_id: int, job_description: str = ""):
    """将简历与岗位描述进行匹配，返回匹配度评分和缺失技能"""
    if not job_description:
        return "请提供岗位描述（JD）内容。"

    coll = get_collection(user_id)
    total = coll.count()
    if total == 0:
        return "你还没有上传简历。请先上传简历PDF文件。"

    resume_text = "\n".join(coll.get(limit=min(total, 10))['documents'])
    prompt = f"""你是一位技术招聘专家。请对比简历和岗位JD，给出客观的匹配分析。

简历：
{resume_text[:2000]}

岗位JD：
{job_description[:2000]}

请按以下格式回答：
1. 综合匹配度（百分比，如 65%）
2. 匹配的技能（列出简历中有、JD要求的）
3. 缺失的技能（列出JD要求但简历没有的）
4. 加分项（简历中有但JD没提的亮点）
5. 建议（为这个岗位应该补充什么）"""

    try:
        return get_ai_response([{"role": "user", "content": prompt}], max_retries=1, timeout=60).strip()
    except Exception as e:
        return f"岗位匹配失败：{e}"


def generate_questions(job_description: str = "", count: int = 5):
    """根据岗位JD生成面试题目"""
    if not job_description:
        return "请提供岗位描述（JD）内容，以便生成针对性的面试题。"

    prompt = f"""你是一位资深面试官。请根据以下岗位JD，生成{count}道面试题。

岗位JD：
{job_description[:2000]}

要求：
- 包含技术题和行为题，比例约 6:4
- 每题标注类型（技术基础/系统设计/项目经验/行为面试）
- 每题附参考答案要点（50字以内）"""

    try:
        return get_ai_response([{"role": "user", "content": prompt}], max_retries=1, timeout=60).strip()
    except Exception as e:
        return f"题目生成失败：{e}"


def mock_interview_feedback(question: str = "", answer: str = ""):
    """评价用户的面试回答，给出改进建议"""
    if not question or not answer:
        return "请提供面试题目和你的回答。"

    prompt = f"""你是一位资深面试官。请评价以下面试回答。

面试题目：
{question[:1000]}

候选人回答：
{answer[:2000]}

请按以下格式回答：
1. 评分（1-10分）
2. 好的地方（至少2点）
3. 不足的地方（至少2点）
4. 改进建议（具体示范如何更好地回答）
5. 追问建议（接下来可以追问什么）"""

    try:
        return get_ai_response([{"role": "user", "content": prompt}], max_retries=1, timeout=60).strip()
    except Exception as e:
        return f"面试评价失败：{e}"


def search_knowledge(query: str, user_id: int):
    """
    在知识库中搜索相关内容
    参数 query: 搜索查询词
    """
    query = query.strip().strip('"').strip("'")
    if not query:
        return "请提供搜索关键词。"
    results = search_document(query, user_id, top_k=3)
    if not results:
        return f"在知识库中未找到与「{query}」相关的内容。"
    return "在知识库中找到以下相关内容：\n\n" + "\n\n---\n\n".join(results)


def fetch_job_page(url: str):
    """
    抓取招聘网页内容
    参数 url: 招聘页面的URL地址
    """
    url = url.strip().strip('"').strip("'")
    result = crawl_url(url)
    if not result['success']:
        return f"抓取失败：{result['error']}"
    title = result['title'] or '无标题'
    text = result['text']
    return f"📄 网页标题：{title}\n\n📝 页面内容：\n{text[:3000]}"


# ==================== 工具定义（大模型可见） ====================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_knowledge_info",
            "description": "查询用户知识库的状态信息，包括文档块数量等。当用户询问'我的知识库有什么'时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前日期和时间。当用户询问'现在几点'、'今天日期'时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_document",
            "description": "对用户上传的文档生成完整摘要。当用户要求'总结'、'概括'、'摘要'文档时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "执行数学计算，支持加减乘除、幂运算、括号等。当用户需要进行数学计算时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如 '(3+5)*2'"}
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_resume",
            "description": "分析用户上传的简历，给出综合评分、优缺点、改进建议和投递方向。当用户说'分析我的简历'、'简历怎么样'、'帮我看看简历'时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "match_job",
            "description": "将用户简历与岗位JD进行匹配，返回匹配度百分比、匹配技能、缺失技能。当用户说'匹配岗位'、'我能投这个吗'、'帮我看看匹配度'时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_description": {"type": "string", "description": "岗位描述（JD）内容"}
                },
                "required": ["job_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_questions",
            "description": "根据岗位JD生成面试题目。当用户说'生成面试题'、'出题'、'帮我模拟面试'时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_description": {"type": "string", "description": "岗位描述（JD）内容"},
                    "count": {"type": "integer", "description": "生成题目数量，默认5"}
                },
                "required": ["job_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_interview_feedback",
            "description": "评价用户的面试回答，给出评分和改进建议。当用户回答完面试题后要求点评时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "面试题目"},
                    "answer": {"type": "string", "description": "用户的回答"}
                },
                "required": ["question", "answer"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在用户的知识库中搜索相关内容。当用户需要查找特定主题的文档内容时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_job_page",
            "description": "抓取指定URL的网页内容并返回文本。当用户说'帮我看看这个职位链接'、'打开这个招聘页面'、'抓取这个网址'时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要抓取的网页URL地址"}
                },
                "required": ["url"]
            }
        }
    },
]


# ==================== 工具调度 ====================
def execute_tool(tool_name: str, user_id: int, arguments: dict = None):
    """根据工具名和参数执行对应的函数，返回结果字符串"""
    args = arguments or {}

    if tool_name == "get_knowledge_info":
        return get_knowledge_info(user_id)
    elif tool_name == "get_current_time":
        return get_current_time()
    elif tool_name == "summarize_document":
        return summarize_document(user_id)
    elif tool_name == "calculate":
        return calculate(args.get("expression", ""))
    elif tool_name == "analyze_resume":
        return analyze_resume(user_id)
    elif tool_name == "match_job":
        return match_job(user_id, args.get("job_description", ""))
    elif tool_name == "generate_questions":
        return generate_questions(args.get("job_description", ""), args.get("count", 5))
    elif tool_name == "mock_interview_feedback":
        return mock_interview_feedback(args.get("question", ""), args.get("answer", ""))
    elif tool_name == "search_knowledge":
        return search_knowledge(args.get("query", ""), user_id)
    elif tool_name == "fetch_job_page":
        return fetch_job_page(args.get("url", ""))
    else:
        return f"未知工具: {tool_name}"
