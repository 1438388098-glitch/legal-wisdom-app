# 数据重建指南（repro）

说明 `legal.db` 的来源、构建流程与运行时位置。数据库文件因体积（约 87 MB）与再分发边界**不入库**，按本文档可从原始语料完整重建。

## 1. 数据来源

- 263 部法律法规的公开文本，按四类组织（详见 README「数据来源」）：
  - `法律` (70) · `行政法规` (132) · `司法解释` (59) · `监察法规` (2)
- 目录约定：项目根目录下 `中国法律/{法律,行政法规,司法解释,监察法规}/*.pdf|*.docx`
- 来源为官方公开渠道；本库仅用于本地检索与学习，不用于原文再分发。

## 2. 构建流程

```bash
# 1) 全量导入：建 schema → 扫描目录 → 解析 PDF/DOCX → 写入 documents（FTS 触发器自动同步索引）
python data/database/import_data.py

# 2) 条级结构：从正文解析「章/条」写入 chapters / articles（articles_fts 支持条级检索）
python data/database/migrate_articles.py

# 3) 交叉引用：扫描《XX法》引用，构建 law_references 关联索引
python services/law_refs.py
```

流水线对应关系：

| 步骤 | 入口 | 产物 |
|------|------|------|
| 建库 | `data/database/schema.py::init_db` | 全部表 + `documents_fts`/`articles_fts` + 同步触发器 |
| 解析 | `data/parsers/pdf_parser.py`、`docx_parser.py` | 纯文本 content |
| 导入 | `data/database/import_data.py::import_all` | documents 全量数据（打印 imported/errors 统计） |
| 条级化 | `data/database/migrate_articles.py::migrate` | chapters / articles（解析参数见脚本内注释） |
| 关联 | `services/law_refs.py::build_reference_index` | law_references（简称→全称映射见 `LAW_SHORT_NAMES`） |

## 3. 运行时数据库位置

- **开发环境**：`data/database/legal.db`（已被 .gitignore 排除）
- **打包环境**：首次运行时从包内复制到 `%USERPROFILE%\.法律智库\legal.db`，可用环境变量 `LEGAL_WISDOM_DATA` 重定向数据目录（见 `schema._get_db_path`）

## 5. 已知数据缺口（待补数）

当前库内实际为 **257 部**（法律 70 / 行政法规 132 / 司法解释 53 / 监察法规 2），且存在以下缺口：

- **核心法典缺失**：宪法、民法典、刑法、行政诉讼法、劳动法等常用大法不在库内（标题精确/模糊匹配均无命中），推测为原始语料阶段即缺失或导入失败
- **司法解释数量**：README 历史口径为 59 部，库内实际 53 部

补数步骤：恢复 `中国法律/` 四分类目录（含缺失法典的官方公开文本）后，按第 2 节流程重跑全量导入并重建 `law_references` 索引（`LAW_SHORT_NAMES` 已含核心法典的简称映射，入库后交叉引用会自动接通）。

## 6. 检索口径说明

- `documents_fts` / `articles_fts` 使用 **unicode61** 分词：连续的中文字符被视为**同一个 token**（不做词级切分），因此中文子串查询通常无法命中 FTS 短语匹配；中文搜索实际由 `data/database/search.py` 的 **LIKE 模糊匹配降级路径**承担，FTS 主要对英文/数字 token 生效（tests 中有针对两条路径的实证用例）
- 因此当前检索为**关键词精确检索**，不是语义 / 向量检索；带引用溯源的混合检索 RAG 在演进计划中（见 README「正在探索」）
- 已知改进方向：FTS5 `trigram` tokenizer（SQLite ≥3.34）可让中文子串直接命中 FTS，需要重建 FTS 表，尚未实施
- 相关测试：`python -m unittest discover -s tests -v`（含临时库单测与本机真实库冒烟用例）
