"""PDF 解析器 - 基于 pdfminer.six"""
import os
import re
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams


def clean_content(text):
    """Merge consecutive empty lines into at most one blank line."""
    result = []
    prev_empty = False
    for line in text.split("\n"):
        line = line.strip()
        if line == "":
            if not prev_empty:
                result.append("")
                prev_empty = True
        else:
            result.append(line)
            prev_empty = False
    return "\n".join(result)


def extract_title(filename):
    """Extract statute name from filename, stripping date prefix and extension."""
    name = filename.rsplit('.', 1)[0]
    name = re.sub(r"^\d{4}-\d{2}-\d{2}[_ ]?", "", name)
    return name.strip()


def parse_pdf(file_path):
    """解析 PDF 文件，返回 (title, content)"""
    try:
        laparams = LAParams(
            all_texts=True,
            detect_vertical=True,
            word_margin=0.1,
            char_margin=2.0,
            line_margin=0.5,
        )
        text = extract_text(file_path, laparams=laparams, codec="utf-8")
    except Exception as e:
        raise RuntimeError(f"PDF解析失败: {file_path} — {e}")

    if not text.strip():
        raise RuntimeError(f"PDF内容为空: {file_path}")

    content = clean_content(text)

    # 从文件名推断标题（去掉日期前缀）
    basename = os.path.basename(file_path)
    title = extract_title(basename)

    return title, content


def parse_pdf_batch(file_paths):
    results = []
    errors = []
    for fp in file_paths:
        try:
            results.append((fp, *parse_pdf(fp)))
        except Exception as e:
            errors.append((fp, str(e)))
    return results, errors
