"""界面文案中英双语字典 + 界面语言偏好持久化。

翻译字典只覆盖界面框架文案（菜单/标题栏/按钮/标签页/占位符/状态栏/对话框），
不涉及法条库数据内容。语言偏好写入仓库根目录 ui_config.json——与 ai_config.json
同一模式：运行时生成、含本机用户偏好、绝不入库（.gitignore 已排除）。
"""
import json
import os

_LANG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "ui_config.json"
)

DEFAULT_LANG = "zh"
LANGUAGES = ("zh", "en")

ZH = {
    # --- 窗口 / 标题栏 ---
    "window_title": "法律智库 · 个人法条库",
    "app_name": "法律智库",
    "app_sub": "个人法条库",
    "bookmark_btn": "收藏",
    "bookmarked_btn": "已收藏",
    "settings_btn": "设置",
    # --- 搜索栏 / 侧栏 ---
    "search_placeholder": "搜索法条，如「行政处罚」「正当防卫」「合同效力」……",
    "search_btn": "搜索",
    "searching_btn": "搜索中",
    "sidebar_title": "  分类浏览",
    "cat_all": "全部",
    "cat_bookmarks": "收藏夹",
    "cat_law": "法律",
    "cat_admin_regulation": "行政法规",
    "cat_judicial_interpretation": "司法解释",
    "cat_supervision_regulation": "监察法规",
    # --- 标签页 / 结果列表 ---
    "tab_results": "搜索结果",
    "tab_reader": "文档阅读",
    "searching_title": "搜索中: 「{query}」",
    "search_error": "搜索出错: {error}",
    "results_title": "搜索结果 ({total} 条，显示 {shown})",
    "no_results_title": "未找到结果",
    "no_results_hint": "   未找到相关法条，请尝试其他关键词",
    "empty_category": "   该分类暂无数据",
    # --- 阅读器 ---
    "publish_date_label": "{date} 发布",
    "truncated_notice": "……（内容过长，已截断前 50KB）……",
    "show_full_link": "显示全文",
    "related_heading": "关联法条",
    "reading_status": "正在阅读: {title}",
    "reading_related_status": "正在阅读: {title}（{count} 条关联法条）",
    "reading_full_status": "正在阅读: {title}（全文）",
    # --- 收藏 ---
    "bookmark_added": "已添加到收藏夹",
    "bookmark_removed": "已取消收藏",
    "bookmarks_title": "收藏夹",
    "bookmarks_empty": "   收藏夹为空，浏览法条时点击「收藏」按钮",
    "bookmarked_on": "  (收藏于 {date})",
    # --- AI 面板 ---
    "ai_title": "AI 法律问答",
    "ai_placeholder": "输入法律问题，如「行政处罚有哪几种？」……",
    "send_btn": "发送",
    "send_ctx_btn": "结合当前法条",
    "ai_thinking": "AI 思考中……",
    "ai_error_status": "出错",
    "ai_you": "\n你：{query}\n",
    "ai_error_msg": "\n错误：{error}\n",
    "open_doc_first": "请先打开一个法条文档",
    "doc_not_found": "文档不存在",
    "config_warn_title": "配置提醒",
    "config_warn_body": "请先在设置中配置 API Key。\n\n推荐：DeepSeek (api.deepseek.com)",
    "expand_btn": "展开",
    "collapse_btn": "收起",
    # --- 状态栏 / 首页 ---
    "status_ready": "就绪 · 已收录 263 部法律法规",
    "status_home": "首页 · 257 部法律法规",
    "welcome_sub": "个人法条库 · 全文检索 · AI 问答",
    "welcome_line1": "收录 263 部中国法律法规",
    "welcome_line2": "涵盖法律、行政法规、司法解释、监察法规",
    "welcome_line3": "支持全文搜索、分类浏览、法条关联与 AI 问答",
    "welcome_hint": "在上方搜索框输入关键词，或从左侧分类浏览",
    "home_sub": "个人法条库 · 257 部法律法规",
    "home_count": "（{count} 部）",
    "home_footer": "PDF 文档解析可能存在格式偏差 · 内容仅供参考",
    # --- 设置对话框 ---
    "dlg_settings_title": "设置",
    "dlg_ai_title": "AI 服务配置",
    "dlg_provider": "提供商",
    "dlg_api_key": "API Key",
    "dlg_api_base": "接口地址",
    "dlg_model": "模型名称",
    "dlg_temperature": "温度 (0-2)",
    "dlg_save": "保存",
    "dlg_cancel": "取消",
}

EN = {
    # --- Window / title bar ---
    "window_title": "Legal Wisdom · Personal Statute Library",
    "app_name": "Legal Wisdom",
    "app_sub": "Personal Statute Library",
    "bookmark_btn": "Bookmark",
    "bookmarked_btn": "Bookmarked",
    "settings_btn": "Settings",
    # --- Search bar / sidebar ---
    "search_placeholder": "Search statutes, e.g. “administrative penalty”, “justifiable defense”, “contract validity”…",
    "search_btn": "Search",
    "searching_btn": "Searching…",
    "sidebar_title": "  Categories",
    "cat_all": "All",
    "cat_bookmarks": "Bookmarks",
    "cat_law": "Statutes",
    "cat_admin_regulation": "Administrative Regulations",
    "cat_judicial_interpretation": "Judicial Interpretations",
    "cat_supervision_regulation": "Supervision Regulations",
    # --- Tabs / result list ---
    "tab_results": "Search Results",
    "tab_reader": "Document Reader",
    "searching_title": "Searching: “{query}”",
    "search_error": "Search error: {error}",
    "results_title": "Search results ({total} found, showing {shown})",
    "no_results_title": "No results",
    "no_results_hint": "   No matching statutes found. Try other keywords.",
    "empty_category": "   No documents in this category yet.",
    # --- Reader ---
    "publish_date_label": "Published {date}",
    "truncated_notice": "…… (Content too long, showing first 50 KB) ……",
    "show_full_link": "Show full text",
    "related_heading": "Related Statutes",
    "reading_status": "Reading: {title}",
    "reading_related_status": "Reading: {title} ({count} related statutes)",
    "reading_full_status": "Reading: {title} (full text)",
    # --- Bookmarks ---
    "bookmark_added": "Added to bookmarks",
    "bookmark_removed": "Removed from bookmarks",
    "bookmarks_title": "Bookmarks",
    "bookmarks_empty": "   Your bookmarks are empty. Click “Bookmark” while reading a statute.",
    "bookmarked_on": "  (bookmarked on {date})",
    # --- AI panel ---
    "ai_title": "AI Legal Q&A",
    "ai_placeholder": "Type a legal question, e.g. “What types of administrative penalties exist?”…",
    "send_btn": "Send",
    "send_ctx_btn": "Use current statute",
    "ai_thinking": "AI is thinking…",
    "ai_error_status": "Error",
    "ai_you": "\nYou: {query}\n",
    "ai_error_msg": "\nError: {error}\n",
    "open_doc_first": "Open a statute document first",
    "doc_not_found": "Document not found",
    "config_warn_title": "Configuration Required",
    "config_warn_body": "Please configure an API Key in Settings first.\n\nRecommended: DeepSeek (api.deepseek.com)",
    "expand_btn": "Expand",
    "collapse_btn": "Collapse",
    # --- Status bar / home ---
    "status_ready": "Ready · 263 laws and regulations collected",
    "status_home": "Home · 257 laws and regulations",
    "welcome_sub": "Personal Statute Library · Full-text Search · AI Q&A",
    "welcome_line1": "263 Chinese laws and regulations collected",
    "welcome_line2": "Covering statutes, administrative regulations, judicial interpretations and supervision regulations",
    "welcome_line3": "Full-text search, category browsing, statute cross-references and AI Q&A",
    "welcome_hint": "Type keywords in the search box above, or browse categories on the left",
    "home_sub": "Personal Statute Library · 257 laws and regulations",
    "home_count": "({count})",
    "home_footer": "PDF parsing may introduce formatting deviations · For reference only",
    # --- Settings dialog ---
    "dlg_settings_title": "Settings",
    "dlg_ai_title": "AI Service Configuration",
    "dlg_provider": "Provider",
    "dlg_api_key": "API Key",
    "dlg_api_base": "API Base URL",
    "dlg_model": "Model",
    "dlg_temperature": "Temperature (0-2)",
    "dlg_save": "Save",
    "dlg_cancel": "Cancel",
}

STRINGS = {"zh": ZH, "en": EN}


def load_lang(path=None):
    """读取界面语言偏好，缺省/损坏/非法值一律回退中文。"""
    file_path = path or _LANG_FILE
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                lang = json.load(f).get("language")
            if lang in STRINGS:
                return lang
    except (json.JSONDecodeError, OSError, AttributeError):
        pass
    return DEFAULT_LANG


def save_lang(lang, path=None):
    """保存界面语言偏好（JSON，与 ai_config.json 同模式）。"""
    if lang not in STRINGS:
        return
    file_path = path or _LANG_FILE
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"language": lang}, f, ensure_ascii=False, indent=2)
