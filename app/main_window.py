"""法律智库 - 主窗口"""
import os
import re
import sys
import html

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
    QTextBrowser, QTabWidget, QSplitter, QListWidget, QListWidgetItem,
    QFrame, QStatusBar, QDialog, QFormLayout, QMessageBox, QMenu,
)
from PySide6.QtCore import Qt, Signal, QObject, QThread, QUrl, QTimer
from PySide6.QtGui import QFont, QTextCursor, QColor

from data.database.schema import DB_PATH, get_connection
from data.database.search import (
    search, get_document, get_documents_by_category, get_categories,
)
from services.ai_service import ask_ai, load_config, save_config
from app import i18n


class SearchThread(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, query, category=None, limit=100):
        super().__init__()
        self.query = query
        self.category = category
        self.limit = limit

    def run(self):
        try:
            results, total = search(self.query, self.category, self.limit)
            self.finished.emit((results, total))
        except Exception as e:
            self.error.emit(str(e))


class AIThread(QThread):
    chunk = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, query, context=None):
        super().__init__()
        self.query = query
        self.context = context
        self._result = ""

    def run(self):
        try:
            def on_chunk(text):
                self._result += text
                self.chunk.emit(text)
            result = ask_ai(self.query, self.context, on_stream=on_chunk)
            self.finished.emit(result or self._result)
        except Exception as e:
            self.error.emit(str(e))


class SettingsDialog(QDialog):
    def __init__(self, parent=None, lang=i18n.DEFAULT_LANG):
        super().__init__(parent)
        self.config = load_config()
        self.S = i18n.STRINGS[lang]
        self.setWindowTitle(self.S["dlg_settings_title"])
        self.setMinimumSize(450, 350)
        self.setModal(True)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        S = self.S
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel(S["dlg_ai_title"])
        title.setStyleSheet(
            "font-family: 'Noto Serif SC', serif; font-size: 18px; font-weight: 600; color: #1a1a1a;"
        )
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(14)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["deepseek", "openai", "siliconflow", "zhipu", "custom"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow(S["dlg_provider"], self.provider_combo)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        form.addRow(S["dlg_api_key"], self.api_key_input)

        self.api_base_input = QLineEdit()
        self.api_base_input.setPlaceholderText("https://api.deepseek.com/v1")
        form.addRow(S["dlg_api_base"], self.api_base_input)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("deepseek-chat")
        form.addRow(S["dlg_model"], self.model_input)

        self.temp_input = QLineEdit()
        self.temp_input.setPlaceholderText("0.3")
        form.addRow(S["dlg_temperature"], self.temp_input)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        save_btn = QPushButton(S["dlg_save"])
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton(S["dlg_cancel"])
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def _on_provider_changed(self, provider):
        presets = {
            "deepseek": {"api_base": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
            "openai": {"api_base": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
            "siliconflow": {"api_base": "https://api.siliconflow.cn/v1", "model": "Qwen/Qwen2.5-14B-Instruct"},
            "zhipu": {"api_base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-plus"},
            "custom": {"api_base": "", "model": ""},
        }
        if provider in presets and provider != "custom":
            preset = presets[provider]
            self.api_base_input.setText(preset["api_base"])
            self.model_input.setText(preset["model"])

    def _load_config(self):
        self.provider_combo.setCurrentText(self.config.get("provider", "deepseek"))
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.api_base_input.setText(self.config.get("api_base", ""))
        self.model_input.setText(self.config.get("model", ""))
        self.temp_input.setText(str(self.config.get("temperature", 0.3)))

    def _save(self):
        try:
            temp = float(self.temp_input.text() or "0.3")
        except ValueError:
            temp = 0.3
        self.config.update({
            "provider": self.provider_combo.currentText(),
            "api_key": self.api_key_input.text().strip(),
            "api_base": self.api_base_input.text().strip(),
            "model": self.model_input.text().strip(),
            "temperature": temp,
        })
        save_config(self.config)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(1280, 800)
        self.resize(1400, 900)

        style_path = os.path.join(os.path.dirname(__file__), "..", "assets", "styles.qss")
        with open(style_path, "r", encoding="utf-8") as f:
            self._style = f.read()
        self.setStyleSheet(self._style)

        self.current_doc_id = None
        self._search_seq = 0
        self._ai_seq = 0
        self._cat_cache = None
        self._current_content = ""
        self._current_related = None
        self.lang = i18n.load_lang()
        self._view = "welcome"
        self._ai_expanded = True

        self._setup_ui()
        self._load_categories()
        self._show_welcome()

    # --- UI Setup ---

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Title bar
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 8, 20, 8)

        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        title_layout.addWidget(self.title_label)

        self.sub_label = QLabel()
        self.sub_label.setObjectName("titleSubLabel")
        title_layout.addWidget(self.sub_label)

        title_layout.addStretch()

        self.bookmark_btn = QPushButton()
        self.bookmark_btn.setObjectName("bookmarkBtn")
        self.bookmark_btn.clicked.connect(self._toggle_bookmark)
        title_layout.addWidget(self.bookmark_btn)

        # 界面语言切换菜单（选择持久化到 ui_config.json，不入库）
        self.lang_btn = QPushButton("语言 Language")
        self.lang_btn.setObjectName("settingsBtn")
        self.lang_btn.setToolTip("切换界面语言 / Switch UI language")
        lang_menu = QMenu(self.lang_btn)
        self._act_zh = lang_menu.addAction("中文")
        self._act_en = lang_menu.addAction("English")
        self._act_zh.setCheckable(True)
        self._act_en.setCheckable(True)
        self._act_zh.triggered.connect(lambda: self._switch_language("zh"))
        self._act_en.triggered.connect(lambda: self._switch_language("en"))
        self.lang_btn.setMenu(lang_menu)
        title_layout.addWidget(self.lang_btn)

        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.clicked.connect(self._open_settings)
        title_layout.addWidget(self.settings_btn)

        main_layout.addWidget(title_bar)

        # Search bar
        search_bar = QWidget()
        search_bar.setStyleSheet(
            "background: #ffffff; padding: 10px 20px; border-bottom: 1px solid #e8e8e8;"
        )
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(8, 4, 8, 4)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.returnPressed.connect(self._do_search)
        search_layout.addWidget(self.search_input, 1)

        self.category_combo = QComboBox()
        self.category_combo.setObjectName("categoryCombo")
        search_layout.addWidget(self.category_combo)

        self.search_btn = QPushButton()
        self.search_btn.setObjectName("searchButton")
        self.search_btn.clicked.connect(self._do_search)
        search_layout.addWidget(self.search_btn)

        main_layout.addWidget(search_bar)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(320)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)

        self.side_title = QLabel()
        self.side_title.setObjectName("sidebarTitle")
        side_layout.addWidget(self.side_title)

        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderHidden(True)
        self.category_tree.setIndentation(18)  # TODO: apply DPI scaling factor
        self.category_tree.itemClicked.connect(self._on_category_clicked)
        side_layout.addWidget(self.category_tree)

        splitter.addWidget(sidebar)

        # Content area
        content_area = QWidget()
        content_area.setObjectName("contentArea")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.content_tabs = QTabWidget()
        self.content_tabs.setDocumentMode(True)

        # Tab: Results
        self.result_widget = QWidget()
        result_layout = QVBoxLayout(self.result_widget)
        result_layout.setContentsMargins(0, 0, 0, 0)

        self.result_title = QLabel("")
        self.result_title.setObjectName("resultTitle")
        result_layout.addWidget(self.result_title)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self._on_result_clicked)
        result_layout.addWidget(self.result_list)

        self.content_tabs.addTab(self.result_widget, "")

        # Tab: Reader
        self.reader_widget = QWidget()
        reader_layout = QVBoxLayout(self.reader_widget)
        reader_layout.setContentsMargins(0, 0, 0, 0)

        self.doc_title = QLabel("")
        self.doc_title.setObjectName("docTitle")
        reader_layout.addWidget(self.doc_title)

        self.doc_meta = QLabel("")
        self.doc_meta.setObjectName("docMeta")
        reader_layout.addWidget(self.doc_meta)

        self.doc_viewer = QTextBrowser()
        self.doc_viewer.setObjectName("docViewer")
        self.doc_viewer.setOpenExternalLinks(False)
        self.doc_viewer.anchorClicked.connect(self._on_doc_link)
        reader_layout.addWidget(self.doc_viewer)

        self.content_tabs.addTab(self.reader_widget, "")

        content_layout.addWidget(self.content_tabs)
        splitter.addWidget(content_area)
        splitter.setSizes([240, 760])

        main_layout.addWidget(splitter, 1)

        # AI panel (bottom)
        self._ai_container = QWidget()
        self._ai_container.setObjectName("aiContainer")
        ai_container_layout = QVBoxLayout(self._ai_container)
        ai_container_layout.setContentsMargins(0, 0, 0, 0)
        ai_container_layout.setSpacing(0)

        # Thin always-visible bar with the toggle button
        ai_control_bar = QWidget()
        ai_control_bar.setObjectName("aiControlBar")
        ai_control_bar.setStyleSheet(
            "background: #ffffff; border-top: 1px solid #e8e8e8;"
        )
        ai_control_layout = QHBoxLayout(ai_control_bar)
        ai_control_layout.setContentsMargins(8, 2, 8, 2)
        ai_control_layout.addStretch()
        self.ai_expand_btn = QPushButton()
        self.ai_expand_btn.setObjectName("expandButton")
        self.ai_expand_btn.clicked.connect(self._toggle_ai_panel)
        ai_control_layout.addWidget(self.ai_expand_btn)
        ai_container_layout.addWidget(ai_control_bar)

        ai_panel = QWidget()
        ai_panel.setObjectName("aiPanel")
        ai_layout = QVBoxLayout(ai_panel)
        ai_layout.setContentsMargins(20, 10, 20, 14)
        ai_layout.setSpacing(8)

        ai_header = QHBoxLayout()
        self.ai_title_label = QLabel()
        self.ai_title_label.setStyleSheet(
            "font-family: 'Noto Serif SC', serif; font-size: 14px; font-weight: 600; color: #1a1a1a;"
        )
        ai_header.addWidget(self.ai_title_label)

        self.ai_status = QLabel("")
        self.ai_status.setStyleSheet("font-size: 11px; color: #aaa;")
        ai_header.addWidget(self.ai_status)
        ai_header.addStretch()

        ai_header.addStretch()
        ai_layout.addLayout(ai_header)

        ai_input_layout = QHBoxLayout()
        self.ai_input = QLineEdit()
        self.ai_input.setObjectName("aiInput")
        self.ai_input.returnPressed.connect(self._do_ai_query)
        ai_input_layout.addWidget(self.ai_input)

        self.send_btn = QPushButton()
        self.send_btn.setObjectName("sendButton")
        self.send_btn.clicked.connect(self._do_ai_query)
        ai_input_layout.addWidget(self.send_btn)

        self.send_with_context_btn = QPushButton()
        self.send_with_context_btn.setObjectName("contextButton")
        self.send_with_context_btn.clicked.connect(self._do_ai_query_with_context)
        ai_input_layout.addWidget(self.send_with_context_btn)

        ai_layout.addLayout(ai_input_layout)

        self.ai_output = QTextBrowser()
        self.ai_output.setObjectName("aiOutput")
        self.ai_output.setMinimumHeight(140)
        self.ai_output.setMaximumHeight(280)
        ai_layout.addWidget(self.ai_output)

        ai_container_layout.addWidget(ai_panel)

        main_layout.addWidget(self._ai_container)

        self._apply_texts()
        self.statusBar().showMessage(self._S()["status_ready"])

    # --- i18n ---

    def _S(self):
        """当前界面语言的文案字典"""
        return i18n.STRINGS[self.lang]

    def _cat_display(self, cat_key, fallback):
        """分类显示名：按界面语言翻译（cat_* 键），未知分类回退库内名称"""
        return self._S().get("cat_" + cat_key, fallback)

    def _apply_texts(self):
        """按当前语言刷新全部界面框架文案（法条库数据内容不翻译）"""
        S = self._S()

        self.setWindowTitle(S["window_title"])
        self.title_label.setText(S["app_name"])
        self.sub_label.setText(S["app_sub"])
        self.settings_btn.setText(S["settings_btn"])
        self._act_zh.setChecked(self.lang == "zh")
        self._act_en.setChecked(self.lang == "en")

        self.search_input.setPlaceholderText(S["search_placeholder"])
        self.search_btn.setText(S["search_btn"] if self.search_btn.isEnabled() else S["searching_btn"])
        self.side_title.setText(S["sidebar_title"])

        self.content_tabs.setTabText(0, S["tab_results"])
        self.content_tabs.setTabText(1, S["tab_reader"])

        self.ai_title_label.setText(S["ai_title"])
        self.ai_input.setPlaceholderText(S["ai_placeholder"])
        self.send_btn.setText(S["send_btn"])
        self.send_with_context_btn.setText(S["send_ctx_btn"])
        self.ai_expand_btn.setText(S["collapse_btn"] if self._ai_expanded else S["expand_btn"])

        if self.current_doc_id:
            self._update_bookmark_btn(self.current_doc_id)
        else:
            self.bookmark_btn.setText(S["bookmark_btn"])

        self._load_categories()

    def _switch_language(self, lang):
        """切换界面语言并持久化（写入 ui_config.json，已被 .gitignore 排除）"""
        if lang not in i18n.STRINGS or lang == self.lang:
            return
        self.lang = lang
        i18n.save_lang(lang)
        self._apply_texts()
        # 无文档打开时刷新欢迎页/首页，让框架文案即时生效；文档正文属数据内容不重译
        if self.current_doc_id is None:
            if self._view == "home":
                self._show_home()
            else:
                self._show_welcome()
                self.statusBar().showMessage(self._S()["status_ready"])

    # --- Categories ---

    def _get_categories(self):
        if self._cat_cache is None:
            self._cat_cache = get_categories()
        return self._cat_cache

    def _load_categories(self):
        self.category_tree.clear()
        S = self._S()
        root = QTreeWidgetItem(self.category_tree, [S["cat_all"]])
        root.setData(0, Qt.UserRole, "all")
        root.setExpanded(True)

        count_map = {}
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.name, c.display_name, COUNT(d.id) as cnt
            FROM categories c LEFT JOIN documents d ON c.id = d.category_id
            GROUP BY c.id ORDER BY c.id
        """)
        for name, display_name, cnt in cursor.fetchall():
            count_map[name] = (display_name, cnt)
        conn.close()

        for cat in self._get_categories():
            name = cat["name"]
            display_name = cat["display_name"]
            cnt = count_map.get(name, (display_name, 0))[1]
            item = QTreeWidgetItem(root, [f"{self._cat_display(name, display_name)}  ({cnt})"])
            item.setData(0, Qt.UserRole, name)

        fav_item = QTreeWidgetItem(self.category_tree, [S["cat_bookmarks"]])
        fav_item.setData(0, Qt.UserRole, "bookmarks")

        self.category_combo.clear()
        self.category_combo.addItem(S["cat_all"], "all")
        for cat in self._get_categories():
            self.category_combo.addItem(
                self._cat_display(cat["name"], cat["display_name"]), cat["name"]
            )

    # --- Welcome ---

    def _show_welcome(self):
        S = self._S()
        self._view = "welcome"
        self.doc_viewer.setHtml(f"""
        <div style="text-align: center; padding: 80px 40px;">
            <h2 style="font-family: 'Noto Serif SC', serif; color: #1a1a1a;
                       font-size: 28px; font-weight: 600; margin-bottom: 8px;
                       letter-spacing: 2px;">
                {S['app_name']}
            </h2>
            <p style="font-family: 'Inter', 'Segoe UI', sans-serif;
                      color: #999; font-size: 15px; margin-bottom: 32px;">
                {S['welcome_sub']}
            </p>
            <div style="width: 48px; height: 1px; background: #8B4513; margin: 0 auto 32px;"></div>
            <p style="font-family: 'Noto Serif SC', serif;
                      color: #aaa; font-size: 14px; line-height: 2.2;">
                {S['welcome_line1']}<br>
                {S['welcome_line2']}<br>
                {S['welcome_line3']}
            </p>
            <p style="font-family: 'Inter', 'Segoe UI', sans-serif;
                      color: #ccc; font-size: 12px; margin-top: 48px;">
                {S['welcome_hint']}
            </p>
        </div>
        """)

    def _show_home(self):
        """显示首页：分类入口 + 最新法条速览"""
        S = self._S()
        self._view = "home"
        conn = get_connection()
        cursor = conn.cursor()

        # 构建分类区块
        cat_blocks = ""
        for cat in self._get_categories():
            display_name = self._cat_display(cat["name"], cat["display_name"])
            cat_key = cat["name"]
            cursor.execute("SELECT COUNT(*) FROM documents WHERE category_id=?", (cat["id"],))
            cnt = cursor.fetchone()[0]
            # 最近 5 条
            cursor.execute(
                "SELECT id, title FROM documents WHERE category_id=? ORDER BY publish_date DESC LIMIT 5",
                (cat["id"],),
            )
            items = "".join(
                f'<div style="margin:2px 0;font-size:13px;">'
                f'<a href="doc://{r[0]}" style="color:#666;text-decoration:none;">{html.escape(r[1])}</a></div>'
                for r in cursor.fetchall()
            )
            cat_blocks += f"""
            <div style="margin:0 0 20px 0;">
                <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">
                    <a href="cat://{cat_key}" style="font-size:15px;font-weight:600;color:#8B4513;
                           text-decoration:none;">{display_name}</a>
                    <span style="font-size:11px;color:#aaa;">{S['home_count'].format(count=cnt)}</span>
                </div>
                {items}
            </div>
            """

        conn.close()

        html_out = f"""
        <div style="padding:0 16px;">
            <div style="text-align:center;padding:24px 0 28px 0;
                        border-bottom:1px solid #e8e8e8;margin-bottom:24px;">
                <div style="font-size:22px;font-weight:600;color:#1a1a1a;letter-spacing:2px;
                            font-family:'Noto Serif SC',serif;">{S['app_name']}</div>
                <div style="font-size:12px;color:#aaa;margin-top:4px;">{S['home_sub']}</div>
            </div>
            {cat_blocks}
            <div style="text-align:center;padding:16px 0;color:#ccc;font-size:12px;
                        border-top:1px solid #e8e8e8;margin-top:8px;">
                {S['home_footer']}
            </div>
        </div>
        """

        self.doc_viewer.setHtml(html_out)
        self.content_tabs.setCurrentIndex(1)  # 切换到 Reader tab
        self.statusBar().showMessage(S["status_home"])

    # --- Search ---

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        cat = self.category_combo.currentData()
        if cat == "all":
            cat = None

        self._search_seq += 1
        my_seq = self._search_seq

        # 清理旧线程（quit() 不中断同步 run()，断开信号避免过期回调）
        if hasattr(self, '_search_thread') and self._search_thread.isRunning():
            self._search_thread.finished.disconnect()
            self._search_thread.error.disconnect()
            self._search_thread.quit()
            self._search_thread.wait(500)

        self.search_btn.setEnabled(False)
        self.search_btn.setText(self._S()["searching_btn"])
        self.result_list.clear()
        self.result_title.setText(self._S()["searching_title"].format(query=query))

        thread = SearchThread(query, cat)
        thread.finished.connect(lambda data, seq=my_seq: self._on_search_results(data, seq))
        thread.error.connect(lambda e: self.statusBar().showMessage(self._S()["search_error"].format(error=e)))
        thread.start()
        self._search_thread = thread

    def _on_search_results(self, data, seq):
        if seq != self._search_seq:
            return
        results, total = data
        S = self._S()

        self.search_btn.setEnabled(True)
        self.search_btn.setText(S["search_btn"])

        self.result_list.clear()

        if not results:
            self.result_title.setText(S["no_results_title"])
            no_item = QListWidgetItem(S["no_results_hint"])
            no_item.setFlags(no_item.flags() & ~Qt.ItemIsSelectable)
            no_item.setForeground(QColor("#aaa"))
            self.result_list.addItem(no_item)
            return

        self.result_title.setText(S["results_title"].format(total=total, shown=len(results)))
        for r in results:
            cat_name = r.get("category", "")
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            clean_snippet = snippet.replace('<b>', '*').replace('</b>', '*')
            clean_snippet = re.sub(r'<[^>]+>', '', clean_snippet)
            display_text = f"[{cat_name}] {title}\n{clean_snippet[:120]}"  # Python slicing is Unicode-safe
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, r["id"])
            self.result_list.addItem(item)

        self.content_tabs.setCurrentIndex(0)

    def _on_category_clicked(self, item, col):
        cat_key = item.data(0, Qt.UserRole)
        if not cat_key:
            return

        self.result_list.clear()

        if cat_key == "all":
            self._show_home()
            return

        if cat_key == "bookmarks":
            self._show_bookmarks()
            return

        # cat_key is internal name ("law"), need display name
        cat_display = cat_key
        for c in self._get_categories():
            if c["name"] == cat_key:
                cat_display = self._cat_display(cat_key, c["display_name"])
                break
        self.result_title.setText(cat_display)

        docs = get_documents_by_category(cat_key)
        if not docs:
            self.result_list.addItem(self._S()["empty_category"])
            return

        for d in docs:
            prefix = f"[{d.get('date', '')}] " if d.get('date') else ""
            item = QListWidgetItem(f"{prefix}{d['title']}")
            item.setData(Qt.UserRole, d["id"])
            self.result_list.addItem(item)

    def _on_result_clicked(self, item):
        doc_id = item.data(Qt.UserRole)
        if not doc_id:
            return
        self._show_document(doc_id)

    # --- Document Reader ---

    def _show_document(self, doc_id):
        doc = get_document(doc_id)
        if not doc:
            return

        self._view = "doc"
        self.current_doc_id = doc_id
        self.doc_title.setText(doc["title"])

        meta_parts = []
        if doc.get("date"):
            meta_parts.append(self._S()["publish_date_label"].format(date=doc["date"]))
        if doc.get("category"):
            meta_parts.append(doc["category"])
        self.doc_meta.setText(" · ".join(meta_parts))

        content = doc.get("content", "")
        # 大文档：只渲染前 50KB 避免卡死 UI，其余可滚动查看
        content_preview = content[:50000]
        self._current_content = content_preview
        if len(content) > 50000:
            content_preview += "\n\n" + self._S()["truncated_notice"]
            content_preview += ('\n\n<a href="expand:full" style="color:#8B4513;">'
                                + self._S()["show_full_link"] + "</a>")

        html_out = self._format_doc_content(content_preview, None)
        self.doc_viewer.setHtml(html_out)

        self.content_tabs.setCurrentIndex(1)
        self.statusBar().showMessage(self._S()["reading_status"].format(title=doc["title"]))
        self._update_bookmark_btn(doc_id)

        # 关联法条后台加载（仍在 UI 线程中执行 SQL，TODO: 移至 QThread）
        original_doc_id = doc_id
        saved_content = self._current_content

        def load_related():
            related = self._get_related_documents(doc["title"], doc_id)
            if related and self.current_doc_id == original_doc_id:
                self._current_related = related
                html_out = self._format_doc_content(saved_content, related)
                self.doc_viewer.setHtml(html_out)
                self.statusBar().showMessage(
                    self._S()["reading_related_status"].format(title=doc["title"], count=len(related))
                )
        QTimer.singleShot(100, load_related)

    def _on_doc_link(self, url):
        if url.scheme() == "doc":
            doc_id = int(url.path())
            self._show_document(doc_id)
        elif url.scheme() == "cat":
            # 模拟点击侧栏分类
            cat_key = url.path()
            for i in range(self.category_tree.topLevelItemCount()):
                item = self.category_tree.topLevelItem(i)
                if item.data(0, Qt.UserRole) == cat_key:
                    self._on_category_clicked(item, 0)
                    return
            # 如果在子节点中（"全部"的子节点）
            root = self.category_tree.topLevelItem(0)
            if root:
                for i in range(root.childCount()):
                    child = root.child(i)
                    if child.data(0, Qt.UserRole) == cat_key:
                        self._on_category_clicked(child, 0)
                        return
        elif url.scheme() == "expand" and url.path() == "full":
            self._show_full_content()

    def _show_full_content(self):
        """Reload the current document with full content (no truncation)."""
        doc = get_document(self.current_doc_id)
        if not doc:
            return
        content = doc.get("content", "")
        self._current_content = content
        html_out = self._format_doc_content(content, getattr(self, '_current_related', None))
        self.doc_viewer.setHtml(html_out)
        self.statusBar().showMessage(self._S()["reading_full_status"].format(title=doc["title"]))

    def _get_related_documents(self, title, doc_id, limit=8):
        working_title = title
        keywords = []
        for kw in ["中华人民共和国", "暂行", "条例", "实施", "管理"]:
            working_title = working_title.replace(kw, "")
        parts = re.split(r'[的、与和及]', working_title)
        for p in parts:
            p = p.strip()
            if len(p) >= 2 and p not in keywords:
                keywords.append(p)
                if len(keywords) >= 2:
                    break
        if not keywords:
            keywords = [title[:4]]

        conn = get_connection()
        cursor = conn.cursor()
        seen = set()
        related = []
        for kw in keywords:
            cursor.execute("""
                SELECT id, title, category_id FROM documents
                WHERE id != ? AND title LIKE ? LIMIT ?
            """, (doc_id, f'%{kw}%', limit))
            for row in cursor.fetchall():
                if row[0] not in seen:
                    seen.add(row[0])
                    related.append({"id": row[0], "title": row[1]})
        conn.close()
        return related[:limit]

    def _format_doc_content(self, content, related=None):
        escaped = html.escape(content)
        html_content = escaped.replace("\n", "<br>")

        related_html = ""
        if related:
            links = "".join(
                f'<a href="doc://{r["id"]}" style="color:#8B4513;text-decoration:none;'
                f'display:inline-block;padding:3px 10px;margin:2px;'
                f'border:1px solid rgba(139,69,19,0.2);font-size:12px;">'
                f'{html.escape(r["title"][:30])}</a>'
                for r in related
            )
            related_html = f"""
            <div style="margin:16px 0;padding:12px 16px;
                        border-left:3px solid #8B4513;background:#fafafa;">
                <div style="font-size:11px;font-weight:600;color:#999;margin-bottom:8px;
                            letter-spacing:1px;text-transform:uppercase;
                            font-family:'Inter','Segoe UI',sans-serif;">
                {self._S()["related_heading"]}</div>
                {links}
            </div>
            """

        html_content = re.sub(
            r'(第[一二三四五六七八九十百零]+章\s*[^<]*)',
            r'<b style="font-size: 16px; color: #1a1a1a;">\1</b>',
            html_content
        )
        html_content = re.sub(
            r'(第[一二三四五六七八九十百零]+条)',
            r'<b style="color: #8B4513;">\1</b>',
            html_content
        )

        return f"""
        <div style="line-height: 2; font-size: 15px; padding: 10px;">
            {related_html}
            {html_content}
        </div>
        """

    # --- Bookmarks ---

    def _update_bookmark_btn(self, doc_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bookmarks WHERE doc_id=?", (doc_id,))
        exists = cursor.fetchone()
        conn.close()
        self.bookmark_btn.setText(
            self._S()["bookmarked_btn"] if exists else self._S()["bookmark_btn"]
        )

    def _toggle_bookmark(self):
        if not self.current_doc_id:
            return

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bookmarks WHERE doc_id=?", (self.current_doc_id,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute("DELETE FROM bookmarks WHERE id=?", (exists[0],))
            conn.commit()
            self.bookmark_btn.setText(self._S()["bookmark_btn"])
            self.statusBar().showMessage(self._S()["bookmark_removed"])
        else:
            doc = get_document(self.current_doc_id)
            content_preview = doc["content"][:200] if doc else ""
            cursor.execute(
                "INSERT INTO bookmarks (doc_id, snippet) VALUES (?, ?)",
                (self.current_doc_id, content_preview),
            )
            conn.commit()
            self.bookmark_btn.setText(self._S()["bookmarked_btn"])
            self.statusBar().showMessage(self._S()["bookmark_added"])

        conn.close()

    def _show_bookmarks(self):
        S = self._S()
        self.result_list.clear()
        self.result_title.setText(S["bookmarks_title"])
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, d.id, d.title, b.snippet, b.created_at
            FROM bookmarks b
            JOIN documents d ON b.doc_id = d.id
            ORDER BY b.created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            no_item = QListWidgetItem(S["bookmarks_empty"])
            no_item.setFlags(no_item.flags() & ~Qt.ItemIsSelectable)
            no_item.setForeground(QColor("#aaa"))
            self.result_list.addItem(no_item)
            return

        for row in rows:
            title = row[2]
            date_str = str(row[4] or "")[:10]
            display = f"{title}{S['bookmarked_on'].format(date=date_str)}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, row[1])
            self.result_list.addItem(item)

        self.content_tabs.setCurrentIndex(0)

    # --- AI Panel ---

    def _toggle_ai_panel(self):
        ai_panel = self.findChild(QWidget, "aiPanel")
        if not ai_panel:
            return
        visible = ai_panel.isVisible()
        ai_panel.setVisible(not visible)
        self._ai_expanded = not visible
        S = self._S()
        self.ai_expand_btn.setText(S["expand_btn"] if visible else S["collapse_btn"])

    def _do_ai_query(self):
        self._ai_query(context=None)

    def _do_ai_query_with_context(self):
        if not self.current_doc_id:
            self.statusBar().showMessage(self._S()["open_doc_first"])
            return
        doc = get_document(self.current_doc_id)
        if not doc:
            self.statusBar().showMessage(self._S()["doc_not_found"])
            return
        context = f"[{doc['title']}]\n{doc['content'][:4000]}"
        self._ai_query(context=context)

    def _ai_query(self, context=None):
        query = self.ai_input.text().strip()
        if not query:
            return

        self._ai_seq += 1
        my_seq = self._ai_seq

        config = load_config()
        if not config.get("api_key"):
            QMessageBox.warning(self, self._S()["config_warn_title"],
                                self._S()["config_warn_body"])
            self._open_settings()
            return

        self.ai_running = True
        self.send_btn.setEnabled(False)
        self.send_with_context_btn.setEnabled(False)
        self.ai_status.setText(self._S()["ai_thinking"])

        self.ai_output.append(self._S()["ai_you"].format(query=query))

        def on_chunk(text):
            if not _check_seq():
                return
            self.ai_output.moveCursor(QTextCursor.End)
            self.ai_output.insertPlainText(text)

        def _check_seq():
            return self._ai_seq == my_seq

        def _enable_ai_buttons():
            self.ai_running = False
            self.send_btn.setEnabled(True)
            self.send_with_context_btn.setEnabled(True)

        def on_finished(result):
            if not _check_seq():
                return
            _enable_ai_buttons()
            self.ai_status.setText("")
            if result and not result.startswith("Error") and not result.startswith("API"):
                self.ai_output.append("\n---\n")

        def on_error(err):
            if not _check_seq():
                return
            _enable_ai_buttons()
            self.ai_status.setText(self._S()["ai_error_status"])
            self.ai_output.append(self._S()["ai_error_msg"].format(error=err))

        # 清理旧线程（quit() 不中断同步 run()，断开信号避免过期回调）
        if hasattr(self, '_ai_thread') and self._ai_thread.isRunning():
            self._ai_thread.chunk.disconnect()
            self._ai_thread.finished.disconnect()
            self._ai_thread.error.disconnect()
            self._ai_thread.quit()
            self._ai_thread.wait(500)

        thread = AIThread(query, context)
        self._ai_thread = thread
        thread.chunk.connect(on_chunk)
        thread.finished.connect(on_finished)
        thread.error.connect(on_error)
        thread.start()

        self.ai_input.clear()

    def _open_settings(self):
        dlg = SettingsDialog(self, lang=self.lang)
        dlg.exec()

    def closeEvent(self, event):
        self._search_seq = -1  # 终止所有待处理的搜索
        self._ai_seq = -1
        for t_name in ('_search_thread', '_ai_thread'):
            t = getattr(self, t_name, None)
            if t and t.isRunning():
                # 断开信号连接，防止线程结束后回调已销毁的对象
                for sig_name in ('finished', 'error', 'chunk'):
                    sig = getattr(t, sig_name, None)
                    if sig is not None:
                        try:
                            sig.disconnect()
                        except (TypeError, RuntimeError):
                            pass
                t.quit()
                if not t.wait(2000):
                    # 线程超时未结束（如AI请求仍在进行），作为最后手段强制终止。
                    # 仅在进程退出时调用，操作系统会回收资源，不存在泄漏风险。
                    t.terminate()
                    t.wait()
        event.accept()
