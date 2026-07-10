import os
import logging
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader
from backend.services.preprocessing import preprocess

logger = logging.getLogger("aiagent.rag")

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
_collection_cache = {}

# 分块参数（可从环境变量覆盖）
DEFAULT_CHUNK_SIZE = int(os.getenv('RAG_CHUNK_SIZE', '500'))
DEFAULT_CHUNK_OVERLAP = int(os.getenv('RAG_CHUNK_OVERLAP', '100'))
# 支持的文件类型
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.md', '.docx'}

def get_collection(user_id: int):
    if user_id not in _collection_cache:
        logger.info(f"为用户 {user_id} 创建新集合")
        client = chromadb.PersistentClient(path="./chroma_db")
        collection_name = f"kb_user_{user_id}"
        _collection_cache[user_id] = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL_NAME
            )
        )
    return _collection_cache[user_id]


def extract_text_from_pdf(file_path):
    """从 PDF 提取文本"""
    reader = PdfReader(file_path)
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"
    return full_text


def extract_text_from_txt(file_path):
    """从纯文本文件提取（尝试多种编码）"""
    for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    # 最后兜底
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def extract_text_from_md(file_path):
    """从 Markdown 提取文本（保留原始格式，去标记在后续处理）"""
    return extract_text_from_txt(file_path)


def extract_text_from_docx(file_path):
    """从 Word 文档提取文本"""
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n'.join(paragraphs)
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")


def extract_text(file_path, file_type: str = None):
    """
    根据文件扩展名自动选择提取方式
    file_type: '.pdf', '.txt', '.md', '.docx'
    """
    if file_type is None:
        _, file_type = os.path.splitext(file_path)
        file_type = file_type.lower()

    extractors = {
        '.pdf': extract_text_from_pdf,
        '.txt': extract_text_from_txt,
        '.md': extract_text_from_md,
        '.docx': extract_text_from_docx,
    }

    if file_type not in extractors:
        raise ValueError(f"不支持的文件类型: {file_type}，支持: {list(extractors.keys())}")

    logger.info(f"读取文档 ({file_type}): {file_path}")
    return extractors[file_type](file_path)


def split_text_into_chunks(text, chunk_size=None, overlap=None):
    chunk_size = chunk_size or DEFAULT_CHUNK_SIZE
    overlap = overlap or DEFAULT_CHUNK_OVERLAP
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks


def index_document(file_path, user_id: int, original_filename: str = None, file_type: str = None):
    # 自动检测文件类型
    if file_type is None:
        _, file_type = os.path.splitext(file_path)
        file_type = file_type.lower()

    # 提取原始文本
    raw_text = extract_text(file_path, file_type)
    logger.debug(f"原始字符数: {len(raw_text)}")

    # 预处理：清洗 + 去噪
    clean = preprocess(raw_text)
    logger.debug(f"清洗后字符数: {len(clean)}")

    if len(clean.strip()) == 0:
        raise ValueError(f"❌ 文档中没有提取到有效文字！请检查文件内容。")

    chunks = split_text_into_chunks(clean)
    logger.info(f"分块完成，共 {len(chunks)} 块")

    if not chunks:
        raise ValueError("文本分块失败！")

    coll = get_collection(user_id)

    source_name = original_filename if original_filename else os.path.basename(file_path)

    # 只删除同一来源的旧记录
    try:
        existing = coll.get()
        if existing and existing.get('ids'):
            to_delete = []
            for i, meta in enumerate(existing.get('metadatas', [])):
                if meta and meta.get('source') == source_name:
                    to_delete.append(existing['ids'][i])
            if to_delete:
                coll.delete(ids=to_delete)
                logger.info(f"清理 {len(to_delete)} 条旧记录（来源: {source_name}）")
    except Exception as e:
        logger.warning(f"清理旧记录异常: {e}")

    import hashlib
    prefix = hashlib.md5(source_name.encode()).hexdigest()[:8]
    ids = [f"{prefix}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source_name, "file_type": file_type, "index": i} for i in range(len(chunks))]
    coll.add(documents=chunks, ids=ids, metadatas=metadatas)
    logger.info(f"已存入 {len(chunks)} 个文档块（来源: {source_name}）")

    # 暂时注释掉可能导致问题的 modify，文件名在前端显示即可
    # try:
    #     source_name = original_filename if original_filename else pdf_path
    #     coll.modify(metadata={"source": source_name})
    # except Exception as e:
    #     print(f"设置文件名元数据失败（不影响索引）: {e}")


def search_document(query, user_id: int, top_k=3):
    """基础语义搜索，兼容旧接口"""
    coll = get_collection(user_id)
    results = coll.query(query_texts=[query], n_results=top_k)
    if results and results['documents']:
        return results['documents'][0]
    return []


def search_with_metadata(query, user_id: int, top_k=10):
    """
    增强搜索：返回结构化结果，去重 + 保证每个来源至少有代表性 chunk
    """
    coll = get_collection(user_id)
    total = coll.count()
    if total == 0:
        return []

    # 尽可能多地拉取，保证覆盖所有来源
    fetch_n = min(total, max(top_k * 3, 30))
    results = coll.query(query_texts=[query], n_results=fetch_n)

    if not results or not results['documents'] or not results['documents'][0]:
        return []

    docs = results['documents'][0]
    metas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(docs)
    distances = results.get('distances', [[]])[0] if results.get('distances') else [0.5] * len(docs)

    # 去重
    structured = []
    seen_fingerprints = set()
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, distances)):
        fp = doc[:80].strip().lower()
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)
        relevance = round(max(0, 1 - dist), 2) if dist else 0.5
        structured.append({
            'text': doc,
            'source': meta.get('source', '未知来源'),
            'title': meta.get('title', ''),
            'relevance': relevance,
        })

    # 按相关性降序
    structured.sort(key=lambda x: x['relevance'], reverse=True)

    # 保证来源多样性：先取每个来源的 top-1，再按相关性补齐
    selected = []
    used_sources = set()
    for item in structured:
        if item['source'] not in used_sources:
            selected.append(item)
            used_sources.add(item['source'])
            if len(selected) >= top_k:
                break
    # 补齐剩余名额
    for item in structured:
        if len(selected) >= top_k:
            break
        if item not in selected:
            selected.append(item)

    return selected[:top_k]


def build_rag_context(question, user_id: int, top_k=10):
    """
    构建带引用标记的 RAG 上下文
    返回: (context_text, sources_list)
      - context_text: 带 [来源N] 标记的上下文
      - sources_list: [{id, source, title}, ...]
    """
    results = search_with_metadata(question, user_id, top_k)
    if not results:
        return "", []

    parts = []
    sources = []
    seen_sources = set()

    for i, r in enumerate(results):
        ref_id = i + 1
        label = r['title'] or r['source'].split('/')[-1].split('\\')[-1] or f'来源{ref_id}'
        parts.append(f"【来源{ref_id}: {label}】{r['text']}")
        # 收集唯一来源
        src_key = r['source']
        if src_key not in seen_sources:
            sources.append({
                'id': ref_id,
                'source': src_key,
                'title': r['title'] or src_key
            })
            seen_sources.add(src_key)

    context = "\n\n---\n\n".join(parts)
    return context, sources


def ask_with_rag(question, user_id: int, top_k=3):
    """兼容旧接口"""
    docs = search_document(question, user_id, top_k)
    if not docs:
        return "抱歉，在您的PDF文档中没有找到与这个问题相关的内容。"
    context = "\n\n---\n\n".join(docs)
    system_prompt = f"""你是一个基于用户提供的文档进行回答的助手。
请严格根据下面的参考资料来回答用户的问题。
--- 参考资料开始 ---
{context}
--- 参考资料结束 ---
用户问题：{question}
回答："""
    return system_prompt