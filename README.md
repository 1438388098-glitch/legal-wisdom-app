# ⚖️ 法律智库 · 个人法条库

**收录 263 部中国法律法规的本地桌面应用，支持全文搜索、AI 问答、法条关联浏览。**

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 **全文搜索** | 基于 SQLite FTS5 的全文搜索引擎，支持关键词高亮 |
| 📂 **分类浏览** | 按法律/行政法规/司法解释/监察法规分类浏览 |
| 📄 **文档阅读** | 内置文档阅读器，章标题/法条编号自动高亮 |
| 🔗 **法条关联** | 阅读时自动推荐相关法条，一键跳转 |
| 💬 **AI 问答** | 接入大模型 API，支持结合当前法条提问 |
| ⭐ **收藏夹** | 收藏常用法条，方便快速查找 |

## 数据来源

- **法律** (70 部) — 宪法、民法典、刑法等
- **行政法规** (132 部) — 各领域实施条例、管理办法
- **司法解释** (59 部) — 最高人民法院、最高人民检察院解释
- **监察法规** (2 部) — 监察法相关法规
- 数据更新至 **2026 年**

## 使用

### 下载运行

解压后运行 `法律智库.exe` 即可，无需安装。

首次启动时会在 `%USERPROFILE%\\.法律智库\\` 下创建数据目录。

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

### 运行

```bash
python3 main.py
```

### 打包 EXE

```bash
python3 build.py
```

## 项目结构

```
legal-wisdom-app/
├── main.py                    # 入口
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
├── build.py                  # 打包脚本
└── requirements.txt
```
