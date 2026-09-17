"""search 模块单测：临时库上验证 FTS 主路径、LIKE 降级、snippet 提取。

运行：python -m unittest discover -s tests -v
真实库集成用例在本机存在 data/database/legal.db 时自动启用。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.database.schema import get_connection, init_db
from data.database import search as search_mod


def _make_db(path):
    """建一个最小临时库：1 个分类 + 2 部测试法律"""
    init_db(path)
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM categories WHERE name='law'")
    law_id = cur.fetchone()[0]
    docs = [
        ("测试法之一", "第一条 为了测试独角兽关键词而设立。第二条 本法自发布之日起施行。"),
        ("测试法之二", "第一条 本法引用《测试法之一》的规定。"),
    ]
    for title, content in docs:
        cur.execute(
            "INSERT INTO documents(title, category_id, content) VALUES (?, ?, ?)",
            (title, law_id, content),
        )
    conn.commit()
    conn.close()
    return path


class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = _make_db(os.path.join(cls.tmp.name, "test.db"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_search_finds_cjk_substring(self):
        # unicode61 下连续中文为单一 token，中文子串查询走 LIKE 降级路径
        results, total = search_mod.search("独角兽关键词", db_path=self.db)
        self.assertGreaterEqual(total, 1)
        self.assertIn("测试法之一", results[0]["title"])
        self.assertIn("独角兽关键词", results[0]["snippet"])

    def test_fts_path_highlights_ascii_token(self):
        # FTS 主路径对英文/数字 token 生效，且 snippet 带 <b> 高亮、得高分
        conn = get_connection(self.db)
        conn.execute(
            "INSERT INTO documents(title, category_id, content) "
            "VALUES ('ASCII Act', (SELECT id FROM categories WHERE name='law'), "
            "'This act mentions unicornland explicitly in section one.')"
        )
        conn.commit()
        conn.close()
        results, total = search_mod.search("unicornland", db_path=self.db)
        self.assertGreaterEqual(total, 1)
        self.assertEqual(results[0]["score"], 10)
        self.assertIn("<b>", results[0]["snippet"])

    def test_no_result_returns_empty(self):
        results, total = search_mod.search("不存在的词组xyz", db_path=self.db)
        self.assertEqual(total, 0)
        self.assertEqual(results, [])

    def test_fts_syntax_injection_does_not_crash(self):
        # FTS 语法字符不应让搜索崩溃（异常被捕获后走 LIKE 降级）
        results, total = search_mod.search('NEAR(a b) NOT', db_path=self.db)
        self.assertIsInstance(results, list)
        self.assertIsInstance(total, int)

    def test_category_filter(self):
        results, _ = search_mod.search("独角兽关键词", category="law", db_path=self.db)
        self.assertGreaterEqual(len(results), 1)
        results, total = search_mod.search("独角兽关键词", category="judicial_interpretation", db_path=self.db)
        self.assertEqual(total, 0)

    def test_snippet_exact_match(self):
        content = "前" * 100 + "目标词" + "后" * 200
        s = search_mod._extract_snippet_from_content(content, "目标词")
        self.assertIn("目标词", s)
        self.assertTrue(s.startswith("..."))
        self.assertTrue(s.endswith("..."))

    def test_snippet_compact_fallback(self):
        # PDF 提取文本常带空格：原文「目标 词」应能通过去空格匹配定位
        content = "前" * 100 + "目标 词" + "后" * 100
        s = search_mod._extract_snippet_from_content(content, "目标词")
        self.assertIn("目标", s)

    def test_snippet_no_match_returns_head(self):
        s = search_mod._extract_snippet_from_content("字" * 300, "目标词")
        self.assertTrue(s.endswith("..."))

    def test_get_document_roundtrip(self):
        results, _ = search_mod.search("独角兽关键词", db_path=self.db)
        doc = search_mod.get_document(results[0]["id"], db_path=self.db)
        self.assertEqual(doc["title"], "测试法之一")
        self.assertIn("独角兽", doc["content"])
        self.assertIsNone(search_mod.get_document(99999, db_path=self.db))

    def test_get_categories(self):
        cats = search_mod.get_categories(db_path=self.db)
        self.assertTrue(any(c["name"] == "law" for c in cats))


class RealDbIntegrationTest(unittest.TestCase):
    """真实库固定 query 冒烟：仅在本机存在 legal.db 时运行"""

    DB = os.path.join(os.path.dirname(__file__), "..", "data", "database", "legal.db")

    def setUp(self):
        if not os.path.exists(self.DB):
            self.skipTest("本地无 legal.db，跳过集成用例")

    def test_search_common_law_name(self):
        results, total = search_mod.search("民法典", db_path=self.DB)
        self.assertGreater(total, 0)

    def test_full_title_hit(self):
        # 全称查询：FTS 精确 token 或 LIKE 标题匹配，都应把本尊排进结果
        # （选用库内真实存在的法律；宪法/民法典/刑法等核心法典暂缺，见 docs/repro.md）
        results, total = search_mod.search("中华人民共和国外商投资法", db_path=self.DB)
        self.assertGreater(total, 0)
        self.assertTrue(any(r["title"] == "中华人民共和国外商投资法" for r in results))

    def test_fixed_query_set_no_crash(self):
        for q in ["行政诉讼", "劳动合同", "侵权责任", "无固定搭配词组qqq"]:
            results, total = search_mod.search(q, db_path=self.DB)
            self.assertIsInstance(results, list)
            self.assertGreaterEqual(total, 0)


if __name__ == "__main__":
    unittest.main()
