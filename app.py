"""法律智库 - Flask 后端"""
import json
import os
import re
import sys
import html
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from flask import Flask, request, jsonify, Response, stream_with_context

sys.path.insert(0, os.path.dirname(__file__))
from data.database.schema import DB_PATH, get_connection
from services.ai_service import load_config, SYSTEM_PROMPT

app = Flask(__name__, static_folder=None)

# ============================================================
# 工具函数
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def clean_html_tags(text):
    return text.replace('<b>', '*').replace('</b>', '*')
    # 只替换 <b> 标签，保留纯文本


# ============================================================
# API: 搜索
# ============================================================

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    doc_id = request.args.get('doc_id', type=int)
    page = request.args.get('page', 1, type=int)
    limit = 50
    offset = (page - 1) * limit

    if not q:
        return jsonify({"results": [], "total": 0, "page": 1})

    conn = get_db()
    c = conn.cursor()

    like = f'%{q}%'

    sql = """
        SELECT a.id, a.article_num, a.content, a.doc_id, a.chapter_id,
               d.title AS doc_title, c.heading AS chapter_heading
        FROM articles a
        JOIN documents d ON a.doc_id = d.id
        LEFT JOIN chapters c ON a.chapter_id = c.id
        WHERE a.content LIKE ? OR a.article_num LIKE ?
    """
    params = [like, like]

    if doc_id:
        sql += " AND a.doc_id = ?"
        params.append(doc_id)

    # COUNT
    c2 = conn.cursor()
    count_sql = f"SELECT COUNT(*) FROM ({sql}) AS sub"
    c2.execute(count_sql, params)
    total = c2.fetchone()[0]
    c2.close()

    sql += " ORDER BY a.doc_id, a.order_idx LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    c.execute(sql, params)
    rows = c.fetchall()

    results = []
    for r in rows:
        snippet = r["content"][:150] if r["content"] else ""
        idx = snippet.lower().find(q.lower())
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(snippet), idx + len(q) + 60)
            snippet = snippet[start:end]
            if start > 0: snippet = "…" + snippet
            if end < len(snippet): snippet += "…"
        else:
            snippet = snippet[:120]

        results.append({
            "id": r["id"],
            "article_num": r["article_num"],
            "doc_title": r["doc_title"],
            "doc_id": r["doc_id"],
            "chapter_heading": r["chapter_heading"] or "",
            "snippet": snippet,
        })

    conn.close()
    return jsonify({"results": results, "total": total, "page": page})


# ============================================================
# API: 文档列表
# ============================================================

@app.route('/api/documents')
def api_documents():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT d.id, d.title, c.display_name AS category,
               (SELECT COUNT(*) FROM articles WHERE doc_id = d.id) AS article_count
        FROM documents d
        JOIN categories c ON d.category_id = c.id
        ORDER BY c.id, d.title
    """)
    docs = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(docs)


# ============================================================
# API: 文档树（章节→条）
# ============================================================

@app.route('/api/documents/<int:doc_id>/tree')
def api_document_tree(doc_id):
    conn = get_db()
    c = conn.cursor()

    # 文档信息
    c.execute("SELECT id, title FROM documents WHERE id=?", (doc_id,))
    doc = c.fetchone()
    if not doc:
        conn.close()
        return jsonify({"error": "not found"}), 404

    # 章节
    c.execute("SELECT id, title, heading, order_idx FROM chapters WHERE doc_id=? ORDER BY order_idx", (doc_id,))
    chapters = [dict(r) for r in c.fetchall()]

    # 给每个章节挂上条
    for ch in chapters:
        c.execute(
            "SELECT id, article_num FROM articles WHERE chapter_id=? ORDER BY order_idx",
            (ch["id"],),
        )
        ch["articles"] = [dict(r) for r in c.fetchall()]

    conn.close()
    return jsonify({"id": doc["id"], "title": doc["title"], "chapters": chapters})


# ============================================================
# API: 文章详情
# ============================================================

@app.route('/api/documents/<int:doc_id>/articles')
def api_document_articles(doc_id):
    """返回某部法律的全部条文（连续全文）"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT a.id, a.article_num, a.content, c.heading as chapter_heading "
              "FROM articles a LEFT JOIN chapters c ON a.chapter_id = c.id "
              "WHERE a.doc_id = ? ORDER BY a.order_idx", (doc_id,))
    articles = []
    for r in c.fetchall():
        articles.append({
            "id": r["id"],
            "article_num": r["article_num"],
            "content": r["content"],
            "chapter_heading": r["chapter_heading"] or "",
        })
    conn.close()
    return jsonify(articles)


@app.route('/api/articles/<int:article_id>')
def api_article_detail(article_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT a.id, a.article_num, a.content, a.doc_id, a.chapter_id,
               d.title AS doc_title, c.heading AS chapter_heading,
               a.order_idx
        FROM articles a
        JOIN documents d ON a.doc_id = d.id
        LEFT JOIN chapters c ON a.chapter_id = c.id
        WHERE a.id=?
    """, (article_id,))
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({"error": "not found"}), 404

    row = dict(r)
    # 上下条
    c.execute("SELECT id, article_num FROM articles WHERE doc_id=? AND order_idx<? ORDER BY order_idx DESC LIMIT 1",
              (row["doc_id"], row["order_idx"]))
    prev_r = c.fetchone()
    c.execute("SELECT id, article_num FROM articles WHERE doc_id=? AND order_idx>? ORDER BY order_idx LIMIT 1",
              (row["doc_id"], row["order_idx"]))
    next_r = c.fetchone()

    conn.close()
    return jsonify({
        "id": row["id"],
        "article_num": row["article_num"],
        "content": row["content"],
        "doc_id": row["doc_id"],
        "doc_title": row["doc_title"],
        "chapter_heading": row["chapter_heading"] or "",
        "prev_id": prev_r["id"] if prev_r else None,
        "prev_num": prev_r["article_num"] if prev_r else None,
        "next_id": next_r["id"] if next_r else None,
        "next_num": next_r["article_num"] if next_r else None,
    })


# ============================================================
# API: 关联法条（交叉引用）
# ============================================================

@app.route('/api/articles/<int:article_id>/references')
def api_article_references(article_id):
    conn = get_db()
    c = conn.cursor()

    # 获取本条信息
    c.execute("SELECT content, doc_id FROM articles WHERE id=?", (article_id,))
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify([])

    content = r["content"]
    doc_id = r["doc_id"]

    # 提取本条中的法律引用（《XXX法》）
    refs = re.findall(r'《([^》]+)》', content)
    results = []
    for ref in refs[:10]:
        c.execute("""
            SELECT a.id, a.article_num, a.content, d.title AS doc_title
            FROM articles a
            JOIN documents d ON a.doc_id = d.id
            WHERE d.title LIKE ? AND a.doc_id != ?
            LIMIT 3
        """, (f'%{ref}%', doc_id))
        for ref_r in c.fetchall():
            results.append({
                "id": ref_r["id"],
                "article_num": ref_r["article_num"],
                "doc_title": ref_r["doc_title"],
                "snippet": ref_r["content"][:100],
            })

    conn.close()
    return jsonify(results)


# ============================================================
# API: 收藏
# ============================================================

@app.route('/api/bookmarks', methods=['GET', 'POST'])
def api_bookmarks():
    conn = get_db()
    c = conn.cursor()

    if request.method == 'GET':
        tag = request.args.get('tag', '')
        if tag:
            c.execute("""
                SELECT ab.id, ab.article_id, ab.tags, ab.note, ab.created_at,
                       a.article_num, a.doc_id, d.title AS doc_title
                FROM article_bookmarks ab
                JOIN articles a ON ab.article_id = a.id
                JOIN documents d ON a.doc_id = d.id
                WHERE ab.tags LIKE ?
                ORDER BY ab.created_at DESC
            """, (f'%{tag}%',))
        else:
            c.execute("""
                SELECT ab.id, ab.article_id, ab.tags, ab.note, ab.created_at,
                       a.article_num, a.doc_id, d.title AS doc_title
                FROM article_bookmarks ab
                JOIN articles a ON ab.article_id = a.id
                JOIN documents d ON a.doc_id = d.id
                ORDER BY ab.created_at DESC
            """)
        bookmarks = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify(bookmarks)

    if request.method == 'POST':
        data = request.get_json()
        article_id = data['article_id']
        tags = data.get('tags', '')
        note = data.get('note', '')
        # 检查是否已收藏
        c.execute("SELECT id FROM article_bookmarks WHERE article_id=?", (article_id,))
        if c.fetchone():
            conn.close()
            return jsonify({"status": "exists"})
        c.execute(
            "INSERT INTO article_bookmarks (article_id, tags, note) VALUES (?, ?, ?)",
            (article_id, tags, note),
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "id": c.lastrowid})

    if request.method == 'DELETE':
        bookmark_id = request.args.get('id', type=int)
        if bookmark_id:
            c.execute("DELETE FROM article_bookmarks WHERE id=?", (bookmark_id,))
            conn.commit()
        conn.close()
        return jsonify({"status": "ok"})


@app.route('/api/bookmarks/<int:bookmark_id>', methods=['DELETE'])
def api_delete_bookmark(bookmark_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM article_bookmarks WHERE id=?", (bookmark_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ============================================================
# API: 高亮
# ============================================================

@app.route('/api/highlights', methods=['GET', 'POST', 'DELETE'])
def api_highlights():
    conn = get_db()
    c = conn.cursor()

    if request.method == 'GET':
        article_id = request.args.get('article_id', type=int)
        if article_id:
            c.execute("SELECT * FROM highlights WHERE article_id=? ORDER BY created_at", (article_id,))
        else:
            c.execute("""
                SELECT h.*, a.article_num, d.title AS doc_title
                FROM highlights h
                JOIN articles a ON h.article_id = a.id
                JOIN documents d ON a.doc_id = d.id
                ORDER BY h.created_at DESC LIMIT 50
            """)
        highlights = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify(highlights)

    if request.method == 'POST':
        data = request.get_json()
        c.execute(
            "INSERT INTO highlights (article_id, selected_text, color, note) VALUES (?, ?, ?, ?)",
            (data['article_id'], data['selected_text'], data.get('color', '#f5ebe0'), data.get('note', '')),
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "id": c.lastrowid})

    if request.method == 'DELETE':
        hl_id = request.args.get('id', type=int)
        if hl_id:
            c.execute("DELETE FROM highlights WHERE id=?", (hl_id,))
            conn.commit()
        conn.close()
        return jsonify({"status": "ok"})


# ============================================================
# API: 浏览记录
# ============================================================

@app.route('/api/history')
def api_history():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT bh.id, bh.article_id, bh.created_at,
               a.article_num, d.title AS doc_title, d.id AS doc_id
        FROM browse_history bh
        JOIN articles a ON bh.article_id = a.id
        JOIN documents d ON a.doc_id = d.id
        GROUP BY bh.article_id
        ORDER BY MAX(bh.created_at) DESC
        LIMIT 30
    """)
    history = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(history)


@app.route('/api/history', methods=['POST'])
def api_add_history():
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO browse_history (article_id) VALUES (?)", (data['article_id'],))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ============================================================
# API: AI 问答（SSE 流式）
# ============================================================

@app.route('/api/ai/ask', methods=['POST'])
def api_ai_ask():
    data = request.get_json()
    query = data.get('query', '').strip()
    context = data.get('context', '')

    if not query:
        return jsonify({"error": "empty query"}), 400

    config = load_config()
    api_key = config.get("api_key", "")
    if not api_key:
        return jsonify({"error": "API Key not configured"}), 400

    base_url = config.get("api_base", "https://api.deepseek.com/v1")
    model = config.get("model", "deepseek-chat")
    temperature = config.get("temperature", 0.3)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({
            "role": "user",
            "content": f"以下是我查阅的法律条文内容，请基于这些内容回答我的问题。\n\n【相关法律条文】\n{context}\n\n【我的问题】\n{query}",
        })
    else:
        messages.append({"role": "user", "content": query})

    def generate():
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }).encode("utf-8")

        req = Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
            },
            method="POST",
        )

        try:
            resp = urlopen(req, timeout=120)
            for line in resp:
                line = line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield json.dumps({"text": content}) + "\n"
                    except json.JSONDecodeError:
                        continue
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            yield json.dumps({"error": f"API error (HTTP {e.code}): {body[:200]}"}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# API: 配置
# ============================================================

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'GET':
        cfg = load_config()
        # 不返回 api_key 明文
        cfg.pop('api_key', None)
        return jsonify(cfg)

    if request.method == 'POST':
        data = request.get_json()
        from services.ai_service import save_config
        cfg = load_config()
        cfg.update(data)
        save_config(cfg)
        return jsonify({"status": "ok"})


# ============================================================
# 静态文件：前端 SPA
# ============================================================

@app.route('/')
def index():
    return open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8").read()


@app.route('/assets/<path:path>')
def static_assets(path):
    return open(os.path.join(os.path.dirname(__file__), "assets", path), "rb").read()


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    # 确保数据库已迁移
    print("Checking database migration...")
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM articles")
        count = c.fetchone()[0]
        print(f"  Articles: {count}")
        if count == 0:
            print("  Running migration...")
            conn.close()
            from data.database.migrate_articles import migrate
            migrate()
    except sqlite3.OperationalError:
        conn.close()
        print("  Running migration...")
        from data.database.migrate_articles import migrate
        migrate()

    print("Starting server at http://localhost:5000")
    app.run(debug=True, port=5000)
