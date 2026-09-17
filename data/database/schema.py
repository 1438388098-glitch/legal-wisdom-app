"""数据库 Schema：SQLite + FTS5 全文搜索"""
import sqlite3
import os
import sys

def _get_db_path():
    """获取数据库路径：开发环境使用项目目录，打包后使用用户数据目录"""
    # 打包后，数据库应在用户可写目录（书签/历史记录需要持久化）
    if getattr(sys, 'frozen', False):
        app_data = os.environ.get(
            "LEGAL_WISDOM_DATA",
            os.path.join(os.path.expanduser("~"), ".法律智库")
        )
        os.makedirs(app_data, exist_ok=True)
        user_db = os.path.join(app_data, "legal.db")
        # 首次运行：从包内复制默认数据库
        try:
            bundled_db = os.path.join(sys._MEIPASS, "data", "database", "legal.db")
        except AttributeError:
            bundled_db = ""
        if not os.path.exists(user_db) and os.path.exists(bundled_db):
            import shutil
            shutil.copy2(bundled_db, user_db)
        return user_db
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "legal.db")

DB_PATH = _get_db_path()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    publish_date TEXT,
    file_name TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category_id);
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title, content, content=documents, content_rowid=id, tokenize='unicode61'
    -- 注意：unicode61 把连续的中文字符视为同一个 token（不做词级切分），
    -- 中文子串查询通常无法命中 FTS 短语匹配；中文搜索实际依赖
    -- search.py 的 LIKE 模糊匹配降级路径，FTS 主要对英文/数字 token 生效。
);

-- 法条关联表
CREATE TABLE IF NOT EXISTS law_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_doc_id INTEGER NOT NULL,
    target_doc_id INTEGER,
    reference_text TEXT,
    ref_type TEXT DEFAULT 'cross_ref',
    FOREIGN KEY (source_doc_id) REFERENCES documents(id),
    FOREIGN KEY (target_doc_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_ref_source ON law_references(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_ref_target ON law_references(target_doc_id);

-- 收藏夹
CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    snippet TEXT,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES documents(id)
);

-- 搜索历史
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 聊天历史
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 章（从原始文本解析）
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    title TEXT NOT NULL,
    heading TEXT NOT NULL,
    order_idx INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_chapters_doc ON chapters(doc_id);

-- 条
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    chapter_id INTEGER REFERENCES chapters(id),
    article_num TEXT NOT NULL,
    content TEXT NOT NULL,
    order_idx INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_articles_doc ON articles(doc_id);
CREATE INDEX IF NOT EXISTS idx_articles_chapter ON articles(chapter_id);

-- 条 FTS5 全文搜索
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    article_num, content, content=articles, content_rowid=id, tokenize='unicode61'
);

-- 收藏（新：每条收藏可打标签+备注）
CREATE TABLE IF NOT EXISTS article_bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id),
    tags TEXT DEFAULT '',           -- 逗号分隔: "常考,易混"
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ab_article ON article_bookmarks(article_id);

-- 高亮笔记
CREATE TABLE IF NOT EXISTS highlights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id),
    selected_text TEXT NOT NULL,
    color TEXT DEFAULT '#f5ebe0',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_highlights_article ON highlights(article_id);

-- 浏览记录
CREATE TABLE IF NOT EXISTS browse_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# FTS5 内容同步触发器
TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
    INSERT INTO documents_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
END;
"""


def get_connection(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
    return conn


def init_db(db_path=None):
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.executescript(TRIGGERS_SQL)

    # 插入默认分类
    categories = [
        ("law", "法律"),
        ("admin_regulation", "行政法规"),
        ("judicial_interpretation", "司法解释"),
        ("supervision_regulation", "监察法规"),
    ]
    for key, name in categories:
        conn.execute(
            "INSERT OR IGNORE INTO categories(name, display_name) VALUES (?, ?)",
            (key, name),
        )
    conn.commit()
    conn.close()
    return DB_PATH
