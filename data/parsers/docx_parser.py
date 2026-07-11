"""DOCX 解析器 - 基于 python-docx"""
import os
from docx import Document
from data.parsers.pdf_parser import clean_content, extract_title as extract_title_from_filename


def parse_docx(file_path):
    """解析 DOCX 文件，返回 (title, content)"""
    try:
        doc = Document(file_path)
    except Exception as e:
        raise RuntimeError(f"DOCX解析失败: {file_path} — {e}")

    paragraphs = []
    for p in doc.paragraphs:
        text = p.text.strip()
        paragraphs.append(text)

    content = clean_content("\n".join(paragraphs))

    if not content.strip():
        raise RuntimeError(f"DOCX内容为空: {file_path}")

    basename = os.path.basename(file_path)
    title = extract_title_from_filename(basename)

    return title, content


def parse_docx_batch(file_paths):
    results = []
    errors = []
    for fp in file_paths:
        try:
            results.append((fp, *parse_docx(fp)))
        except Exception as e:
            errors.append((fp, str(e)))
    return results, errors
