# 法律智库 Web 版 · 设计文档

## 架构概览

Flask 单页应用 + SQLite 后端。浏览器通过 AJAX 请求与 Flask API 交互。
HTML/CSS/JS 纯手写，不引入框架。

```
Browser (HTML+CSS+JS)
     ↕  AJAX / JSON
Flask (Python)
     ↕
SQLite (按条拆分)
     ↕
现有 legal.db → 迁移脚本 → 新表结构
```

## 数据层

### 新表结构

```sql
-- 法律文件（保留原表不动）
documents (id, title, category_id, publish_date)

-- 章
chapters (
  id INTEGER PRIMARY KEY,
  doc_id INTEGER REFERENCES documents(id),
  title TEXT,          -- "总则"
  heading TEXT,        -- "第一章 总则"
  order_idx INTEGER    -- 排序
)

-- 条
articles (
  id INTEGER PRIMARY KEY,
  doc_id INTEGER REFERENCES documents(id),
  chapter_id INTEGER REFERENCES chapters(id),
  article_num TEXT,    -- "第一条", "第四十八条"
  heading TEXT,        -- 条标题（如有）
  content TEXT NOT NULL,
  order_idx INTEGER
)

-- FTS5 全文搜索
CREATE VIRTUAL TABLE articles_fts USING fts5(
  article_num, content, content=articles, content_rowid=id
);

-- 收藏（标签+备注）
bookmarks (
  id, article_id, tags TEXT, note TEXT, created_at
)

-- 高亮笔记
highlights (
  id, article_id, selected_text, note TEXT, color TEXT, created_at
)

-- 浏览记录
browse_history (
  id, article_id, created_at
)
```

### 章条解析算法

从 `documents.content` 中通过正则提取：

1. 匹配 `第[一二三四五六七八九十百零]+章\s*[^（\n]+` → chapters
2. 匹配 `第[一二三四五六七八九十百零]+条\s*` → articles
3. 每个 article 的 content 从本条开头截取到下一条/下一章开头

现存 257 部法律，约 15000-20000 条条文。一次性迁移。

## API 设计

```
GET  /api/search?q=关键词&doc_id=可选&page=1
       → {results: [{id, doc_title, chapter, article_num, snippet, ...}], total}

GET  /api/documents
       → [{id, title, category, count}]

GET  /api/documents/:id/tree
       → {id, title, chapters: [{id, heading, articles: [{id, article_num, heading}]}]}

GET  /api/articles/:id
       → {id, article_num, content, doc_title, chapter_title, prev_id, next_id}

GET  /api/articles/:id/references
       → [{id, article_num, doc_title, snippet}]

POST /api/bookmarks
       {"article_id": 123, "tags": ["常考"], "note": "..."}
GET  /api/bookmarks?tag=常考

POST /api/highlights
       {"article_id": 123, "selected_text": "...", "color": "#ffd", "note": "..."}

POST /api/ai/ask
       {"query": "...", "context": "..."}
       → stream SSE response
```

## 前端页面结构

### 三栏布局

```
┌──────────────────────────────────────────────────────────────────┐
│   ⚖️ 法律智库                        🔍 [搜索框]   [全部法律 ▼] │
├──────────┬───────────────────────────────────┬──────────────────┤
│ 目录树   │  搜索结果 / 法条阅读              │  对比面板        │
│          │                                   │                  │
│ 行政许可 │  第四十八条 听证按照下列程       │  第六十三条      │
│ 法       │  序进行：                        │  行政处罚法      │
│  ├ 第一章 │  （一）当事人要求听证的，应当    │  听证依照以下    │
│  │ 第一条 │  在行政机关告知后五日内提出…    │  程序组织：      │
│  │ 第二条 │                                   │                  │
│  │ 第三条 │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   │  差别：……        │
│  ├ 第二章 │  (高亮部分)                       │                  │
│  │ 第十一条│                                   │   ↩ 移除         │
│  │ 第十二条│  + 加入对比  ⭐ 收藏 💬 笔记     │                  │
│  └ 第三章  │                                   │                  │
│           │  [关联法条]                        │                  │
│           │  行政处罚法第四十二条            │                  │
├──────────┴───────────────────────────────────┴──────────────────┤
│  💬 AI 问答  [输入问题……]  [发送]  [结合当前法条]              │
└──────────────────────────────────────────────────────────────────┘
```

### 交互

- **搜索**：输入关键词 → AJAX 搜索 → 结果列表显示在中间栏
- **结果点击**：左侧目录树切换到该法律并展开到该条
- **阅读**：中间栏显示条文内容，上下条切换
- **拖拽对比**：从中间栏拖到右栏 → 两条并排
- **收藏**：点击 ⭐ → 弹窗选标签+写备注
- **高亮**：选中文字 → 弹出高亮按钮
- **关联法条**：系统自动显示引用该条的其他条文

### 样式

沿用现有 `styles.qss` 的学术极简风格：
- Noto Serif SC / Inter 字体
- #8B4513 暖棕色 accent
- 低饱和、克制、无圆角/浅圆角

## 实现顺序

1. 数据库迁移（章条拆分脚本）
2. Flask 应用框架 + SQLite 查询
3. API 端点（搜索、文档树、文章详情）
4. 前端页面骨架（三栏 HTML + CSS）
5. 搜索功能（输入→AJAX→结果列表→点击跳转）
6. 目录树（动态加载章节→条）
7. 法条阅读（上下条、正文显示）
8. 对比面板（拖拽）
9. 收藏体系（标签+备注+筛选）
10. AI 问答（SSE 流式）
11. 高亮笔记
12. 交叉引用
