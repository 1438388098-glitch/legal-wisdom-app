[English](./README.md) · 简体中文

# ⚖️ 法律智库 · 个人法条库

> **简介** — 本地个人法条库桌面应用：收录 257 部中国法律法规，基于 SQLite FTS5 全文搜索，支持法条间关联推荐，以及以当前阅读法条为上下文的 LLM 问答。因体积与再分发边界，语料不入库——**完全可复现**：按 [docs/repro.md](docs/repro.md) 的一条文档化流水线即可从公开来源重建全部 87MB 数据库。带引用溯源的混合检索在 [statute-rag](https://github.com/1438388098-glitch/statute-rag) 中持续演进。

**收录 257 部中国法律法规的本地桌面应用，支持全文搜索、AI 问答、法条关联浏览。**

> ℹ️ **数据可复现**：宪法、民法典、刑法等核心法典暂未入库（原始语料缺失）。数据库不入库是体积与再分发边界的主动取舍，全部 87MB 数据可按 [docs/repro.md](docs/repro.md) 从官方公开渠道一键重建。

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 **全文搜索** | 基于 SQLite FTS5 的全文搜索引擎，支持关键词高亮 |
| 📂 **分类浏览** | 按法律/行政法规/司法解释/监察法规分类浏览 |
| 📄 **文档阅读** | 内置文档阅读器，章标题/法条编号自动高亮 |
| 🔗 **法条关联** | 阅读时自动推荐相关法条，一键跳转 |
| 💬 **AI 问答** | 接入大模型 API，支持结合当前法条提问 |
| ⭐ **收藏夹** | 收藏常用法条，方便快速查找 |
| 🌐 **双语界面** | 标题栏语言菜单一键切换 中文 / English，选择自动记忆 |

> **检索口径说明**：全文搜索为 SQLite FTS5 + LIKE 混合检索——unicode61 分词下连续中文视为单一词元，中文子串查询主要由 LIKE 模糊匹配承担（英文/数字 token 可命中 FTS 并高亮），**不是**语义/向量检索；带引用溯源的混合检索 RAG 在演进计划中。数据库因体积与再分发边界不入库，从零重建见 [docs/repro.md](docs/repro.md)。

## 界面速览

| 中文界面 | English 界面 |
|----------|------------|
| ![中文界面](docs/screenshots/main-zh.png) | ![English 界面](docs/screenshots/main-en.png) |

> 截图为桌面应用真实离屏渲染，图中为搜索「正当防卫」的结果。截图使用仅含 7 部公开法条摘录的**演示库**（非完整 87MB 语料）；双语切换只作用于界面框架文案，法条数据内容不翻译。

## 数据来源

- **法律** (70 部) — 外商投资法、消防法、建筑法等单行法律
- **行政法规** (132 部) — 各领域实施条例、管理办法
- **司法解释** (53 部) — 最高人民法院、最高人民检察院解释
- **监察法规** (2 部) — 监察法相关法规
- 以上为当前库内实际数量（合计 257 部）；数据更新至 **2026 年**

## 使用

### 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

### 构建 exe（可选）

仓库不直接分发可执行文件，需要 exe 请用 PyInstaller 自行构建：

```bash
python build.py   # 或 pyinstaller 法律智库.spec
```

首次启动时会在 `%USERPROFILE%\.法律智库\` 下创建数据目录（可用环境变量 `LEGAL_WISDOM_DATA` 重定向）。

### AI 配置

1. 点击右上角 **设置**
2. 选择 AI 提供商（DeepSeek / OpenAI / SiliconFlow / 智谱）
3. 填入 API Key
4. 在底部 AI 面板输入法律问题

**推荐:** [DeepSeek](https://platform.deepseek.com/)（国内访问快、性价比高）

### 搜索技巧

- 输入关键词如 **"行政处罚"**、"正当防卫"、"合同效力"
- 可在搜索结果中点击打开全文
- 阅读时点击 **"结合当前法条"** 让 AI 基于当前法条回答问题

## 开发

### 环境要求

- Python 3.13+
- PySide6
- pdfminer.six
- python-docx

### 安装依赖

```bash
pip install PySide6 pdfminer.six python-docx pyinstaller
```

### 导入数据

```bash
python3 data/database/import_data.py
```

### 打包

```bash
python3 build.py
```

## 项目结构

```
legal-wisdom-app/
├── main.py                    # 桌面端入口（PySide6）
├── webapp.py                  # Flask Web 后端（可选）
├── app/
│   └── main_window.py        # 主窗口
├── assets/
│   └── styles.qss            # 样式表
├── data/
│   ├── parsers/              # PDF/DOCX 解析器
│   └── database/             # 数据库 & 搜索
├── services/
│   ├── ai_service.py         # AI API 调用
│   └── law_refs.py           # 法条关联
├── static/                   # Web 端静态资源
├── tests/                    # 单元测试（检索主路径 + 法条关联）
├── build.py                  # 打包脚本
├── run.bat                   # 一键启动
└── requirements.txt
```
