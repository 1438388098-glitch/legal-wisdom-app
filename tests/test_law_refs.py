"""law_refs 模块单测：引用抽取（纯函数）+ 关联索引构建（临时库）。

运行：python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.database.schema import get_connection, init_db
from services.law_refs import (
    LAW_SHORT_NAMES,
    build_reference_index,
    extract_references,
    get_references,
)


class ExtractReferencesTest(unittest.TestCase):
    def test_short_name_ref(self):
        refs = extract_references("根据《民法典》的规定处理。", LAW_SHORT_NAMES)
        self.assertTrue(any(r["short_name"] == "民法典" for r in refs))

    def test_full_name_ref(self):
        refs = extract_references("依照《中华人民共和国刑法》第二百六十四条", LAW_SHORT_NAMES)
        self.assertTrue(any(r["short_name"] == "刑法" for r in refs))

    def test_repealed_law_maps_to_civil_code(self):
        # 已废止单行法应映射到民法典对应编
        refs = extract_references("原《合同法》关于违约的规定。", LAW_SHORT_NAMES)
        self.assertTrue(refs)
        self.assertEqual(refs[0]["full_title"], "中华人民共和国民法典")

    def test_no_ref_returns_empty(self):
        self.assertEqual(extract_references("本条没有任何外部引用。", LAW_SHORT_NAMES), [])

    def test_context_keeps_window(self):
        content = "甲" * 200 + "《刑法》" + "乙" * 200
        refs = extract_references(content, LAW_SHORT_NAMES)
        self.assertEqual(len(refs), 1)
        self.assertLessEqual(len(refs[0]["context"]), len(content))
        self.assertIn("《刑法》", refs[0]["context"])

    def test_position_recorded(self):
        content = "前缀文字《民法典》后缀"
        refs = extract_references(content, LAW_SHORT_NAMES)
        self.assertEqual(refs[0]["position"], content.index("《民法典》"))


class ReferenceIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = os.path.join(cls.tmp.name, "refs.db")
        init_db(cls.db)
        conn = get_connection(cls.db)
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE name='law'")
        law_id = cur.fetchone()[0]
        for title, content in [
            ("中华人民共和国民法典", "第一条 为了保护民事主体的合法权益…"),
            ("中华人民共和国刑法", "第一条 根据《民法典》等有关法律的规定…"),
        ]:
            cur.execute(
                "INSERT INTO documents(title, category_id, content) VALUES (?, ?, ?)",
                (title, law_id, content),
            )
        conn.commit()
        conn.close()
        cls.found = build_reference_index(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _doc_id(self, title):
        conn = get_connection(self.db)
        cur = conn.cursor()
        cur.execute("SELECT id FROM documents WHERE title=?", (title,))
        row = cur.fetchone()
        conn.close()
        return row[0]

    def test_index_found_reference(self):
        self.assertGreaterEqual(self.found, 1)

    def test_cited_by_direction(self):
        refs = get_references(self._doc_id("中华人民共和国民法典"), db_path=self.db)
        self.assertTrue(any("刑法" in r["title"] for r in refs["cited_by"]))
        self.assertEqual(refs["cites"], [])

    def test_cites_direction(self):
        refs = get_references(self._doc_id("中华人民共和国刑法"), db_path=self.db)
        self.assertTrue(any("民法典" in r["title"] for r in refs["cites"]))

    def test_no_self_reference(self):
        refs = get_references(self._doc_id("中华人民共和国刑法"), db_path=self.db)
        self.assertFalse(any("刑法" in r["title"] for r in refs["cites"]))


if __name__ == "__main__":
    unittest.main()
