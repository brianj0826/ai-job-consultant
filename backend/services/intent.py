# intent.py
from backend.services.deepseek_api import get_ai_response

def should_use_rag(question, max_retries=0):
    """
    快速判断用户问题是否需要检索知识库（PDF文档）。
    返回 True 或 False。
    """
    judge_prompt = f"""你是一个意图分类助手。请判断以下用户问题是否需要从PDF文档中检索答案。
只需要回答“是”或“否”，不要解释。

用户问题：{question}

需要检索文档吗？（是/否）"""
    try:
        response = get_ai_response(
            [{"role": "user", "content": judge_prompt}],
            max_retries=max_retries
        )
        return "是" in response
    except Exception:
        # 如果判断出错，默认检索（宁可多查也不要漏掉）
        return True