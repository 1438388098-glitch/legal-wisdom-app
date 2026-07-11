"""法条关联分析：提取法律间的交叉引用关系"""
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data.database.schema import get_connection


# 常用法律简称映射
LAW_SHORT_NAMES = {
    "民法典": "中华人民共和国民法典",
    "刑法": "中华人民共和国刑法",
    "行政诉讼法": "中华人民共和国行政诉讼法",
    "民事诉讼法": "中华人民共和国民事诉讼法",
    "刑事诉讼法": "中华人民共和国刑事诉讼法",
    "公司法": "中华人民共和国公司法",
    "合同法": "中华人民共和国民法典",  # 合同编已并入民法典
    "行政许可法": "中华人民共和国行政许可法",
    "行政处罚法": "中华人民共和国行政处罚法",
    "行政复议法": "中华人民共和国行政复议法",
    "宪法": "中华人民共和国宪法",
    "劳动法": "中华人民共和国劳动法",
    "劳动合同法": "中华人民共和国劳动合同法",
    "婚姻法": "中华人民共和国民法典",  # 婚姻编已并入
    "继承法": "中华人民共和国民法典",
    "侵权责任法": "中华人民共和国民法典",
    "物权法": "中华人民共和国民法典",
    "担保法": "中华人民共和国民法典",
    "食品安全法": "中华人民共和国食品安全法",
    "药品管理法": "中华人民共和国药品管理法",
    "产品质量法": "中华人民共和国产品质量法",
    "消费者权益保护法": "中华人民共和国消费者权益保护法",
    "反不正当竞争法": "中华人民共和国反不正当竞争法",
    "反垄断法": "中华人民共和国反垄断法",
    "专利法": "中华人民共和国专利法",
    "商标法": "中华人民共和国商标法",
    "著作权法": "中华人民共和国著作权法",
    "税收征收管理法": "中华人民共和国税收征收管理法",
    "环境保护法": "中华人民共和国环境保护法",
    "未成年人保护法": "中华人民共和国未成年人保护法",
    "预防未成年人犯罪法": "中华人民共和国预防未成年人犯罪法",
    "国家赔偿法": "中华人民共和国国家赔偿法",
    "保险法": "中华人民共和国保险法",
    "证券法": "中华人民共和国证券法",
    "企业破产法": "中华人民共和国企业破产法",
    "合伙企业法": "中华人民共和国合伙企业法",
    "个人独资企业法": "中华人民共和国个人独资企业法",
    "外商投资法": "中华人民共和国外商投资法",
    "招标投标法": "中华人民共和国招标投标法",
    "政府采购法": "中华人民共和国政府采购法",
    "拍卖法": "中华人民共和国拍卖法",
    "土地管理法": "中华人民共和国土地管理法",
    "城市房地产管理法": "中华人民共和国城市房地产管理法",
    "农村土地承包法": "中华人民共和国农村土地承包法",
    "建筑法": "中华人民共和国建筑法",
    "安全生产法": "中华人民共和国安全生产法",
    "消防法": "中华人民共和国消防法",
    "道路交通安全法": "中华人民共和国道路交通安全法",
    "海商法": "中华人民共和国海商法",
    "审计法": "中华人民共和国审计法",
}


def extract_references(doc_content, known_titles):
    """从文档内容中提取对其他法律的引用"""
    refs = []
    for short_name, full_title in known_titles.items():
        # 搜索 "根据《XXX法》"、"依照《XXX法》"、"《XXX法》规定" 等模式
        patterns = [
            rf"《{re.escape(short_name)}》",
            rf"《{re.escape(full_title)}》",
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, doc_content))
            if matches:
                context_window = 100
                for m in matches:
                    start = max(0, m.start() - context_window)
                    end = min(len(doc_content), m.end() + context_window)
                    context = doc_content[start:end].strip()
                    refs.append({
                        "short_name": short_name,
                        "full_title": full_title,
                        "context": context,
                        "position": m.start(),
                    })
                break  # 找到一个模式即可
    return refs


def build_reference_index(db_path=None):
    """构建法条关联索引"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 获取所有文档
    cursor.execute("SELECT id, title, content FROM documents")
    docs = cursor.fetchall()

    # 构建标题查找表
    title_map = {row[1]: row[0] for row in docs}

    refs_found = 0
    for doc_id, title, content in docs:
        if not content:
            continue

        refs = extract_references(content, LAW_SHORT_NAMES)
        doc_refs = set()  # 去重

        for ref in refs:
            target_full = ref["full_title"]
            if target_full in title_map:
                target_id = title_map[target_full]
                if target_id != doc_id:
                    key = (doc_id, target_id)
                    if key not in doc_refs:
                        doc_refs.add(key)
                        cursor.execute(
                            "INSERT OR IGNORE INTO law_references "
                            "(source_doc_id, target_doc_id, reference_text, ref_type) "
                            "VALUES (?, ?, ?, ?)",
                            (doc_id, target_id,
                             ref["context"][:200],
                             "statutory_ref"),
                        )
                        refs_found += 1

        if refs_found % 50 == 0 and refs_found > 0:
            conn.commit()

    conn.commit()
    conn.close()
    return refs_found


def get_references(doc_id, db_path=None):
    """获取某文档的关联法条"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 被引用的法条（其他法条引用本法）
    cursor.execute("""
        SELECT d.id, d.title, lr.reference_text
        FROM law_references lr
        JOIN documents d ON lr.source_doc_id = d.id
        WHERE lr.target_doc_id = ?
        LIMIT 20
    """, (doc_id,))
    cited_by = [{"id": r[0], "title": r[1], "context": r[2][:100] if r[2] else ""}
                for r in cursor.fetchall()]

    # 本法引用的其他法条
    cursor.execute("""
        SELECT d.id, d.title, lr.reference_text
        FROM law_references lr
        JOIN documents d ON lr.target_doc_id = d.id
        WHERE lr.source_doc_id = ?
        LIMIT 20
    """, (doc_id,))
    cites = [{"id": r[0], "title": r[1], "context": r[2][:100] if r[2] else ""}
             for r in cursor.fetchall()]

    conn.close()
    return {"cited_by": cited_by, "cites": cites}


if __name__ == "__main__":
    count = build_reference_index()
    print(f"已构建 {count} 条法条关联")
