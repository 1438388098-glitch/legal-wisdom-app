"""数据导入：扫描法律目录，解析并导入 SQLite"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data.database.schema import init_db, get_connection
from data.parsers.pdf_parser import parse_pdf
from data.parsers.docx_parser import parse_docx
from services.law_refs import build_reference_index

# 法律文件根目录 — 默认为项目根目录下的 "中国法律" 文件夹
LEGAL_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "中国法律")

CATEGORY_MAP = {
    "法律": "law",
    "行政法规": "admin_regulation",
    "司法解释": "judicial_interpretation",
    "监察法规": "supervision_regulation",
}


def scan_legal_files(base_dir):
    """扫描法律目录，返回 [(category_dir, file_path), ...]"""
    files = []
    for cat_dir in os.listdir(base_dir):
        cat_path = os.path.join(base_dir, cat_dir)
        if not os.path.isdir(cat_path):
            continue
        if cat_dir not in CATEGORY_MAP:
            continue
        for fname in os.listdir(cat_path):
            if fname.endswith((".pdf", ".PDF", ".docx", ".DOCX")):
                files.append((cat_dir, os.path.join(cat_path, fname)))
    return files


def category_id(cursor, cat_name):
    cursor.execute("SELECT id FROM categories WHERE name=?", (CATEGORY_MAP[cat_name],))
    row = cursor.fetchone()
    return row[0] if row else None


def import_all(base_dir=None, db_path=None, progress_callback=None):
    """导入所有法律文件到数据库"""
    if base_dir is None:
        base_dir = LEGAL_BASE

    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    files = scan_legal_files(base_dir)
    total = len(files)
    imported = 0
    errors = []

    start = time.time()

    # 禁用自动提交加速批量导入
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA journal_mode=WAL")

    for idx, (cat_name, file_path) in enumerate(files):
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".pdf":
                title, content = parse_pdf(file_path)
            else:
                title, content = parse_docx(file_path)

            cid = category_id(cursor, cat_name)
            if cid is None:
                errors.append((file_path, f"未知分类: {cat_name}"))
                continue

            # 从文件名提取日期
            fname = os.path.basename(file_path)
            date_str = fname[:10] if len(fname) >= 10 and fname[4] == "-" else ""

            cursor.execute(
                "INSERT INTO documents (title, category_id, publish_date, file_name, content) VALUES (?, ?, ?, ?, ?)",
                (title, cid, date_str, fname, content),
            )
            imported += 1

        except Exception as e:
            errors.append((file_path, str(e)))

        if progress_callback:
            progress_callback(idx + 1, total, title)

    conn.commit()
    elapsed = time.time() - start
    conn.close()

    # 构建法条关联索引
    try:
        ref_count = build_reference_index(db_path)
        print(f"  法条关联: {ref_count} 条")
    except Exception as e:
        print(f"Warning: reference index build failed: {e}")

    return {
        "total": total,
        "imported": imported,
        "errors": errors,
        "elapsed": f"{elapsed:.1f}s",
    }


if __name__ == "__main__":
    result = import_all(progress_callback=lambda i, t, ttl: print(f"[{i}/{t}] {ttl}"))
    print(f"\n导入完成: {result['imported']}/{result['total']} 条, 耗时 {result['elapsed']}")
    if result["errors"]:
        print(f"\n错误 ({len(result['errors'])}):")
        for path, err in result["errors"][:10]:
            print(f"  {path}: {err}")
