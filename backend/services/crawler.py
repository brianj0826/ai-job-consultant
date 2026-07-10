# backend/services/crawler.py
"""轻量网页爬虫 —— 抓取网页并提取文本内容（仅用标准库）"""
import re
import logging
import requests
from html.parser import HTMLParser

logger = logging.getLogger("aiagent.crawler")


class TextExtractor(HTMLParser):
    """从 HTML 中提取纯文本，跳过 script/style 标签"""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'noscript', 'iframe', 'svg', 'nav', 'footer'}
        self.current_skip = None

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip = tag

    def handle_endtag(self, tag):
        if tag == self.current_skip:
            self.current_skip = None
        # 块级元素后加换行
        if tag in {'p', 'br', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr'}:
            self.text_parts.append('\n')

    def handle_data(self, data):
        if self.current_skip:
            return
        text = data.strip()
        if text:
            self.text_parts.append(text + ' ')


def extract_text_from_html(html: str) -> str:
    """从 HTML 字符串中提取纯文本"""
    extractor = TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    raw = ''.join(extractor.text_parts)
    # 清理多余空白
    raw = re.sub(r'[ \t]+', ' ', raw)
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    raw = re.sub(r' \n', '\n', raw)
    return raw.strip()


def extract_title_from_html(html: str) -> str:
    """从 HTML 中提取标题"""
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def fetch_url(url: str, timeout: int = 15) -> dict:
    """
    抓取网页内容
    返回: {"success": bool, "title": str, "text": str, "error": str}
    """
    # 补全协议
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()

        # 检测编码
        resp.encoding = resp.apparent_encoding or 'utf-8'
        html = resp.text

        title = extract_title_from_html(html)
        text = extract_text_from_html(html)

        # 清理网页中的导航/页脚/版权等垃圾文字
        import re as _re
        noise = [
            r'关于我们.*?$', r'加入我们.*?$', r'企业服务.*?$',
            r'免责声明.*?$', r'友情链接.*?$', r'京ICP备.*?$',
            r'京公网安备.*?$', r'增值电信.*?$', r'营业执照.*?$',
            r'扫描二维码.*?$', r'All rights reserved.*?$',
            r'我要招人.*?$', r'发布职位.*?$', r'收藏.*?$',
            r'举报.*?$', r'发送.*?$', r'取消.*?$', r'确定.*?$',
            r'移动版.*?$', r'关于牛客.*?$',
        ]
        for pat in noise:
            text = _re.sub(pat, '', text, flags=_re.MULTILINE)
        text = _re.sub(r'\n{3,}', '\n\n', text).strip()

        # 限制文本长度
        text = text[:5000]

        if not text.strip():
            return {"success": False, "title": "", "text": "", "error": "网页内容为空"}

        return {"success": True, "title": title, "text": text, "error": ""}

    except requests.exceptions.Timeout:
        return {"success": False, "title": "", "text": "", "error": "请求超时"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "title": "", "text": "", "error": "无法连接到目标网站"}
    except Exception as e:
        return {"success": False, "title": "", "text": "", "error": str(e)}


def fetch_and_index(url: str, user_id: int) -> dict:
    """
    抓取网页内容并导入用户知识库
    返回: {"success": bool, "title": str, "chunks": int, "error": str}
    """
    from backend.services.preprocessing import preprocess
    from backend.services.rag import split_text_into_chunks, get_collection

    # 1. 抓取
    result = fetch_url(url)
    if not result['success']:
        return {"success": False, "title": "", "chunks": 0, "error": result['error']}

    # 2. 预处理
    text = result['text']
    clean = preprocess(text)
    if len(clean.strip()) < 50:
        return {"success": False, "title": result['title'], "chunks": 0, "error": "网页有效内容太少"}

    # 3. 分块
    chunks = split_text_into_chunks(clean)
    if not chunks:
        return {"success": False, "title": result['title'], "chunks": 0, "error": "文本分块失败"}

    # 4. 存入知识库（不清空旧内容，追加模式）
    coll = get_collection(user_id)
    import hashlib
    prefix = "web_" + hashlib.md5(url.encode()).hexdigest()[:8]
    ids = [f"{prefix}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": url, "title": result['title'], "type": "web", "index": i} for i in range(len(chunks))]
    coll.add(documents=chunks, ids=ids, metadatas=metadatas)

    logger.info(f"网页已导入知识库: {result['title']} ({len(chunks)} 块)")
    return {"success": True, "title": result['title'], "chunks": len(chunks), "error": ""}
