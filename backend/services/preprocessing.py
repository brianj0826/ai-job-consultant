# backend/services/preprocessing.py
"""文本预处理工具 —— 清洗、规范化、去噪"""
import re


def clean_text(text: str) -> str:
    """
    基础文本清洗：
    1. 合并多余空白行（3个以上连续换行 → 2个换行）
    2. 去除行首行尾多余空格
    3. 去除控制字符（保留常用换行/制表符）
    4. 统一换行为 \n
    """
    if not text:
        return ""

    # 统一换行符
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 去除控制字符（保留 \n 和 \t）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 合并过多连续换行（3+ → 2）
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 去除每行首尾空格
    text = '\n'.join(line.strip() for line in text.split('\n'))

    # 去除首尾空白
    text = text.strip()

    return text


def remove_noise(text: str) -> str:
    """
    去除常见文档噪音：页码、页眉页脚模式、URL等
    """
    # 独立成行的纯数字（页码）
    text = re.sub(r'^\d{1,4}$', '', text, flags=re.MULTILINE)

    # 常见的页眉/页脚模式
    patterns = [
        r'^\s*第\s*\d+\s*页\s*$',           # "第 1 页"
        r'^\s*Page\s+\d+\s*$',               # "Page 1"
        r'^\s*\d+\s*/\s*\d+\s*$',            # "1 / 10"
        r'^\s*版权所有\s*.{0,20}$',           # 版权声明
    ]
    for p in patterns:
        text = re.sub(p, '', text, flags=re.MULTILINE | re.IGNORECASE)

    # 再次清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text


def preprocess(text: str) -> str:
    """完整的预处理管道：清洗 → 去噪"""
    return remove_noise(clean_text(text))
