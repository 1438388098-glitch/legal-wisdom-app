"""全文搜索 - 混合策略：FTS5 + LIKE 合并去重"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data.database.schema import get_connection


def search(query, category=None, limit=100, offset=0, db_path=None):
    """
    混合搜索结果，合并 FTS5（精确）和 LIKE（宽泛）结果，按匹配质量排序。
    返回 (results, total)
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    like_pattern = f"%{query}%"

    # ---- FTS5 精确搜索（主力，带错误日志） ----
    results = []
    try:
        safe_query = query.replace('"', '""')
        fts_sql = """
            SELECT d.id, d.title, c.display_name AS category,
                   snippet(documents_fts, 1, '<b>', '</b>', '...', 40) AS snippet,
                   rank
            FROM documents_fts
            JOIN documents d ON documents_fts.rowid = d.id
            JOIN categories c ON d.category_id = c.id
            WHERE documents_fts MATCH ?
        """
        fts_params = [f'"{safe_query}"']
        if category:
            fts_sql += " AND c.name = ?"
            fts_params.append(category)
        fts_sql += " ORDER BY rank"

        cursor.execute(fts_sql, fts_params)

        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "title": row[1],
                "category": row[2],
                "snippet": row[3] or "",
                "score": 10,  # FTS5 匹配获得高分
                "fts_rank": row[4],
            })
    except Exception as e:
        print(f"Warning: FTS5 search failed: {e}", file=sys.stderr)

    # ---- LIKE 宽泛搜索（FTS5 无结果时降级，加 LIMIT 避免全表扫描） ----
    if not results:
        like_sql = """
            SELECT DISTINCT d.id, d.title, c.display_name AS category
            FROM documents d
            JOIN categories c ON d.category_id = c.id
            WHERE (d.content LIKE ? OR d.title LIKE ?)
        """
        like_params = [like_pattern, like_pattern]
        if category:
            like_sql += " AND c.name = ?"
            like_params.append(category)
        like_sql += " ORDER BY d.id LIMIT ?"
        like_params.append(limit)

        try:
            cursor.execute(like_sql, like_params)
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "category": row[2],
                    "snippet": "",
                    "score": 5,  # LIKE-only 匹配获得较低分
                })
        except Exception as e:
            print(f"Warning: LIKE search failed: {e}", file=sys.stderr)

    conn.close()

    # ---- 批量提取 snippet（避免逐条打开数据库连接） ----
    no_snippet_ids = [r["id"] for r in results if not r.get("snippet")]
    if no_snippet_ids:
        conn2 = get_connection(db_path)
        c2 = conn2.cursor()
        placeholders = ",".join("?" * len(no_snippet_ids))
        c2.execute(f"SELECT id, content FROM documents WHERE id IN ({placeholders})", no_snippet_ids)
        content_map = {row[0]: row[1] for row in c2.fetchall()}
        conn2.close()
        for r in results:
            if not r.get("snippet") and r["id"] in content_map:
                r["snippet"] = _extract_snippet_from_content(content_map[r["id"]], query)

    # ---- 排序和分页 ----
    results.sort(key=lambda r: (-r.get("score", 0), r["id"]))

    total = len(results)
    results = results[offset:offset + limit]

    return results, total


def _extract_snippet_from_content(content, query):
    """从文档内容中提取包含关键词的上下文片段"""
    if not content:
        return ""

    # 尝试精确匹配
    idx = content.find(query)
    if idx == -1:
        # PDF 文本可能有空格，尝试去空格匹配
        compact = content.replace(" ", "").replace("\n", "").replace("\r", "")
        compact_query = query.replace(" ", "").replace("\n", "")
        idx = compact.find(compact_query)
        if idx >= 0:
            # 近似定位到原文
            approx = max(0, idx - 30)
            raw_approx = int(approx * len(content) / max(len(compact), 1))
            start = max(0, raw_approx - 60)
            end = min(len(content), raw_approx + 120)
            snippet = content[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet += "..."
            return snippet
        return content[:150] + "..." if len(content) > 150 else content

    start = max(0, idx - 40)
    end = min(len(content), idx + len(query) + 100)
    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet += "..."
    return snippet


def _extract_snippet(doc_id, query, db_path=None):
    """从文档中提取包含关键词的上下文片段（单条，打开独立连接）"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM documents WHERE id=?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return ""
    return _extract_snippet_from_content(row[0], query)


def get_document(doc_id, db_path=None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.title, c.display_name AS category_name,
               d.publish_date, d.content, d.file_name
        FROM documents d
        JOIN categories c ON d.category_id = c.id
        WHERE d.id=?
    """, (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "category": row[2],
        "date": row[3] or "",
        "content": row[4],
        "file_name": row[5] or "",
    }


def get_documents_by_category(category, db_path=None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.title, d.publish_date
        FROM documents d
        JOIN categories c ON d.category_id = c.id
        WHERE c.name=?
        ORDER BY d.publish_date DESC, d.title
    """, (category,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "date": r[2] or ""} for r in rows]


def get_categories(db_path=None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, display_name FROM categories ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "display_name": r[2]} for r in rows]
