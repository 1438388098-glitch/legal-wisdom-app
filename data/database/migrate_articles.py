"""章条拆分迁移：从 documents.content 解析章→条结构"""
import re
import sys
import os
import sqlite3
import html

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data.database.schema import get_connection, DB_PATH

RE_CHAPTER = re.compile(r'第[\s　]*[一二三四五六七八九十百零]+[\s　]*章[\s　]*[^\n]{0,40}')
RE_ARTICLE = re.compile(r'第[\s　]*[一二三四五六七八九十百零]+[\s　]*条')

def clean_pdf_text(text):
    """去除 PDF 提取的字间空格，恢复可读中文"""
    # 中文字符之间的空格
    text = re.sub(r'(?<=[一-鿿]) +(?=[一-鿿])', '', text)
    # 中文字符与中文标点之间的空格
    text = re.sub(r'(?<=[一-鿿]) +(?=[　-〿＀-￯])', '', text)
    text = re.sub(r'(?<=[　-〿＀-￯]) +(?=[一-鿿])', '', text)
    # 去除多余全角空格
    text = text.replace('　', ' ')
    # 合并连续空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

CN_NUM = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'百':100,'零':0}
def cn_to_int(s):
    if not s or s == '': return 0
    if s in CN_NUM: return CN_NUM[s]
    if '十' in s:
        p = s.split('十')
        l = cn_to_int(p[0]) if p[0] else 1
        r = cn_to_int(p[1]) if len(p) > 1 and p[1] else 0
        return l * 10 + r
    return 0

def chapter_to_num(heading):
    m = re.search(r'第([一二三四五六七八九十百零]+)章', heading)
    return cn_to_int(m.group(1)) if m else 0

def normalize_article_num(text):
    return re.sub(r'[\s　]', '', text.strip())[:15]

def migrate(db_path=None):
    conn = get_connection(db_path)
    cursor = conn.cursor()

    from data.database.schema import init_db
    init_db(db_path)

    for table in ['articles_fts', 'articles', 'chapters', 'article_bookmarks', 'highlights', 'browse_history']:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except sqlite3.OperationalError:
            pass

    cursor.execute(
        "SELECT id, title, content FROM documents WHERE content IS NOT NULL AND length(content) > 0 ORDER BY id"
    )
    docs = cursor.fetchall()
    total_docs = len(docs)
    total_chapters = 0
    total_articles = 0
    docs_with_articles = 0

    for doc_idx, (doc_id, title, content) in enumerate(docs):
        try:
            content = clean_pdf_text(content)
        except Exception:
            continue

        full_text = content
        article_positions = []  # [(article_num, pos_in_full_text)]
        seen_articles = set()

        for m in re.finditer(RE_ARTICLE, full_text):
            art_num = normalize_article_num(m.group())
            if art_num not in seen_articles:
                seen_articles.add(art_num)
                article_positions.append((art_num, m.start()))

        if not article_positions:
            continue

        docs_with_articles += 1

        # 第二步：找章节位置和条文顺序（用于分配章节）
        # 跳过目录区：从第一条之后的章标题算
        first_art_pos = article_positions[0][1]

        chapters_map = {}
        for m in re.finditer(RE_CHAPTER, full_text):
            pos = m.start()
            # 只保留第一条之后的章节（跳过目录）
            if pos < first_art_pos:
                continue
            heading = m.group().strip()
            ch_num = chapter_to_num(m.group())
            if ch_num > 0 and ch_num not in chapters_map:
                title_clean = re.sub(r'第[一二三四五六七八九十百零]+章\s*', '', heading).strip()
                chapters_map[ch_num] = {
                    "ch_num": ch_num,
                    "heading": heading,
                    "title": title_clean or heading,
                    "pos": pos,
                }

        # 第三章：写入 chapters
        sorted_ch_nums = sorted(chapters_map.keys())
        db_chapters = {}
        for order, ch_num in enumerate(sorted_ch_nums):
            ch = chapters_map[ch_num]
            cursor.execute(
                "INSERT INTO chapters (doc_id, title, heading, order_idx) VALUES (?, ?, ?, ?)",
                (doc_id, ch["title"], ch["heading"], order),
            )
            db_chapters[ch_num] = {"db_id": cursor.lastrowid, "ch_num": ch_num, "pos": ch["pos"]}
            total_chapters += 1

        # 第四步：写入 articles，从完整文本取内容窗口
        ch_nums_sorted = sorted(db_chapters.keys())

        for i, (art_num, pos) in enumerate(article_positions):
            # 取内容窗口：至少 1500 字符（宁可多取包含邻条）
            # 最多 4000 字符避免单条过大
            if i + 1 < len(article_positions):
                next_pos = article_positions[i + 1][1]
                dist_to_next = next_pos - pos
                if dist_to_next < 1500:
                    content_window = min(1500, len(full_text) - pos)
                else:
                    content_window = min(dist_to_next, 4000)
            else:
                content_window = min(len(full_text) - pos, 4000)

            article_content = full_text[pos:pos + content_window].strip()
            # 去掉开头的"第X条"标记
            article_content = re.sub(r'^第[一二三四五六七八九十百零]+条[\s　]*', '', article_content, count=1)

            # 分配章节
            assigned_ch = 0
            for cn in ch_nums_sorted:
                if db_chapters[cn]["pos"] <= pos:
                    assigned_ch = cn
                else:
                    break
            chapter_id = db_chapters[assigned_ch]["db_id"] if assigned_ch > 0 else None

            cursor.execute(
                "INSERT INTO articles (doc_id, chapter_id, article_num, content, order_idx) VALUES (?, ?, ?, ?, ?)",
                (doc_id, chapter_id, art_num, article_content, i),
            )
            total_articles += 1

        if (doc_idx + 1) % 50 == 0:
            conn.commit()
            print(f"  [{doc_idx+1}/{total_docs}] {title[:25]} -> {total_articles} articles")

    conn.commit()

    # FTS5
    print("  Rebuilding FTS5 index...")
    try:
        cursor.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
    except Exception:
        cursor.execute("DELETE FROM articles_fts")
        cursor.execute("INSERT INTO articles_fts(rowid, article_num, content) SELECT id, article_num, content FROM articles")
    conn.commit()
    conn.close()

    print(f"\n完成：{docs_with_articles}/{total_docs} 部法律 → {total_chapters} 章 + {total_articles} 条")
    return docs_with_articles, total_chapters, total_articles

if __name__ == "__main__":
    docs, ch, art = migrate()
    print(f"迁移结果: {docs} 部法律, {ch} 章, {art} 条")
