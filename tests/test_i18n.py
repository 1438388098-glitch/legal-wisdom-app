"""i18n 模块与主窗口双语自检：字典键完整、占位符一致、语言切换无 KeyError。

运行：python -m unittest discover -s tests -v
GUI 用例在本机装有 PySide6 时运行：临时库上实例化主窗口但不进入事件循环，
语言偏好读写被重定向到临时文件，不触碰仓库 ui_config.json / ai_config.json。
"""
import os
import string
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import i18n

_FMT = string.Formatter()


def _placeholders(template):
    return {field for _, field, _, _ in _FMT.parse(template) if field is not None}


class I18nDictTest(unittest.TestCase):
    def test_key_parity(self):
        self.assertEqual(set(i18n.ZH), set(i18n.EN))

    def test_values_nonempty(self):
        for lang, table in i18n.STRINGS.items():
            for key, value in table.items():
                self.assertIsInstance(value, str, f"{lang}.{key} 应为字符串")
                self.assertTrue(value.strip(), f"{lang}.{key} 不应为空")

    def test_placeholder_parity(self):
        for key in i18n.ZH:
            self.assertEqual(
                _placeholders(i18n.ZH[key]),
                _placeholders(i18n.EN[key]),
                f"中英占位符不一致: {key}",
            )

    def test_lang_constants(self):
        self.assertEqual(i18n.DEFAULT_LANG, "zh")
        self.assertEqual(set(i18n.STRINGS), {"zh", "en"})

    def test_load_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ui_config.json")
            self.assertEqual(i18n.load_lang(path), "zh")  # 无配置文件回退中文
            i18n.save_lang("en", path=path)
            self.assertEqual(i18n.load_lang(path), "en")

    def test_load_invalid_falls_back_to_zh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ui_config.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{broken json")
            self.assertEqual(i18n.load_lang(path), "zh")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"language": "fr"}')
            self.assertEqual(i18n.load_lang(path), "zh")  # 非法语言值回退中文


def _pyside_available():
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


class MainWindowI18nTest(unittest.TestCase):
    """离线 GUI 自检：临时库上实例化主窗口（不进入事件循环），验证双语切换。"""

    @classmethod
    def setUpClass(cls):
        if not _pyside_available():
            raise unittest.SkipTest("未安装 PySide6，跳过 GUI 自检")
        from data.database.schema import get_connection, init_db
        import data.database.schema as schema_mod

        cls.tmp = tempfile.TemporaryDirectory()
        db_path = os.path.join(cls.tmp.name, "test.db")
        init_db(db_path)
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE name='law'")
        law_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO documents(title, category_id, content) VALUES (?, ?, ?)",
            ("测试法之一", law_id, "第一条 为了测试而设立。"),
        )
        conn.commit()
        conn.close()
        # 主窗口的 get_connection()/search() 默认都回落到 schema.DB_PATH，指向临时库
        cls._orig_db_path = schema_mod.DB_PATH
        schema_mod.DB_PATH = db_path

        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    @classmethod
    def tearDownClass(cls):
        import data.database.schema as schema_mod
        schema_mod.DB_PATH = cls._orig_db_path
        cls.tmp.cleanup()

    def setUp(self):
        # 语言偏好读写重定向到临时文件，不触碰仓库 ui_config.json
        self._cfg_dir = tempfile.TemporaryDirectory()
        self._cfg_path = os.path.join(self._cfg_dir.name, "ui_config.json")
        self._orig_load, self._orig_save = i18n.load_lang, i18n.save_lang
        i18n.load_lang = lambda: self._orig_load(self._cfg_path)
        i18n.save_lang = lambda lang: self._orig_save(lang, path=self._cfg_path)

    def tearDown(self):
        i18n.load_lang, i18n.save_lang = self._orig_load, self._orig_save
        self._cfg_dir.cleanup()

    def test_default_zh_and_switch_to_en_and_back(self):
        from app.main_window import MainWindow

        w = MainWindow()
        try:
            self.assertEqual(w.lang, "zh")
            self.assertEqual(w.windowTitle(), i18n.ZH["window_title"])
            self.assertEqual(w.bookmark_btn.text(), i18n.ZH["bookmark_btn"])
            self.assertEqual(w.category_combo.itemText(0), i18n.ZH["cat_all"])
            self.assertTrue(w._act_zh.isChecked())
            self.assertFalse(w._act_en.isChecked())

            w._switch_language("en")
            self.assertEqual(w.lang, "en")
            self.assertEqual(w.windowTitle(), i18n.EN["window_title"])
            self.assertEqual(w.sub_label.text(), i18n.EN["app_sub"])
            self.assertEqual(w.search_btn.text(), i18n.EN["search_btn"])
            self.assertEqual(w.search_input.placeholderText(), i18n.EN["search_placeholder"])
            self.assertEqual(w.side_title.text(), i18n.EN["sidebar_title"])
            self.assertEqual(w.content_tabs.tabText(0), i18n.EN["tab_results"])
            self.assertEqual(w.content_tabs.tabText(1), i18n.EN["tab_reader"])
            self.assertEqual(w.ai_title_label.text(), i18n.EN["ai_title"])
            self.assertEqual(w.ai_input.placeholderText(), i18n.EN["ai_placeholder"])
            self.assertEqual(w.send_with_context_btn.text(), i18n.EN["send_ctx_btn"])
            self.assertEqual(w.settings_btn.text(), i18n.EN["settings_btn"])
            self.assertEqual(w.bookmark_btn.text(), i18n.EN["bookmark_btn"])
            self.assertEqual(w.category_combo.itemText(0), i18n.EN["cat_all"])
            self.assertTrue(w._act_en.isChecked())
            self.assertFalse(w._act_zh.isChecked())

            w._switch_language("zh")
            self.assertEqual(w.windowTitle(), i18n.ZH["window_title"])
            self.assertEqual(w.category_combo.itemText(0), i18n.ZH["cat_all"])
        finally:
            w.close()

    def test_apply_texts_both_langs_no_keyerror(self):
        from app.main_window import MainWindow

        w = MainWindow()
        try:
            for lang in ("en", "zh"):
                w.lang = lang
                w._apply_texts()  # 任一键缺失会在此抛 KeyError
                for key in i18n.STRINGS[lang]:
                    self.assertIn(key, i18n.STRINGS["zh"])
                    self.assertIn(key, i18n.STRINGS["en"])
        finally:
            w.close()

    def test_switch_language_persists_to_temp_config(self):
        from app.main_window import MainWindow

        w = MainWindow()
        try:
            w._switch_language("en")
            self.assertEqual(self._orig_load(self._cfg_path), "en")
        finally:
            w.close()

    def test_settings_dialog_translated(self):
        from app.main_window import SettingsDialog, MainWindow

        w = MainWindow()
        try:
            dlg_en = SettingsDialog(w, lang="en")
            self.assertEqual(dlg_en.windowTitle(), i18n.EN["dlg_settings_title"])
            dlg_zh = SettingsDialog(w, lang="zh")
            self.assertEqual(dlg_zh.windowTitle(), i18n.ZH["dlg_settings_title"])
        finally:
            w.close()


if __name__ == "__main__":
    unittest.main()
