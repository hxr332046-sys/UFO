"""按关键词探测 chunk JS：找"中共党员"等业务关键词，分析其周围 200 字符的数据结构。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, 'system')

# 业务关键词分组：每组的关键词如果出现在同一文件 200 字符内，几乎肯定是该枚举的字面量定义
KEYWORD_GROUPS = {
    "politicalStatus": ["中共党员", "中共预备党员", "群众", "民盟盟员", "无党派"],
    "education": ["博士", "硕士", "本科", "大专", "高中"],
    "cerType": ["居民身份证", "护照", "军官证", "港澳居民", "台湾居民"],
    "sex": ["男", "女"],  # 太宽，可能噪音多
    "investWay": ["货币", "实物", "知识产权", "土地使用权"],
    "houseUseMode": ["自有", "租赁", "无偿使用"],
    "yesNo": ["是", "否"],
    "yesOrNo": ["需要", "不需要"],
    "marriageStatus": ["未婚", "已婚", "离异", "丧偶"],
    "natural_corp": ["自然人", "法人", "非法人组织"],
    "industryCategory": ["工业", "商业", "服务业"],
}


def main():
    js_dir = Path("dashboard/data/records/core_assets")
    js_files = sorted(js_dir.glob("*.js"))

    findings = {}  # group_name → list of (file, position, snippet)

    for kw_group, kws in KEYWORD_GROUPS.items():
        for f in js_files:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except:
                continue
            # 找出所有关键词位置
            positions = []
            for kw in kws:
                idx = 0
                while True:
                    p = text.find(kw, idx)
                    if p < 0:
                        break
                    positions.append((p, kw))
                    idx = p + 1
            if not positions:
                continue
            positions.sort()
            # 看是否有 ≥ 2 个不同关键词在 500 字符窗口内（同一字典）
            unique_kws = set()
            cluster_start = None
            cluster_end = None
            for p, kw in positions:
                if cluster_start is None:
                    cluster_start = p
                    cluster_end = p
                    unique_kws.add(kw)
                elif p - cluster_end < 500:
                    cluster_end = p
                    unique_kws.add(kw)
                else:
                    # 处理上一个 cluster
                    if len(unique_kws) >= 2:
                        snippet = text[max(0,cluster_start-100):cluster_end+50]
                        findings.setdefault(kw_group, []).append((f.name, cluster_start, snippet))
                    cluster_start = p
                    cluster_end = p
                    unique_kws = {kw}
            if len(unique_kws) >= 2:
                snippet = text[max(0,cluster_start-100):cluster_end+50]
                findings.setdefault(kw_group, []).append((f.name, cluster_start, snippet))

    # 输出结果
    print(f"=== 关键词扫描结果 ===\n")
    for grp, hits in findings.items():
        print(f"\n【{grp}】 {len(hits)} 处命中:")
        for fname, pos, snippet in hits[:2]:
            print(f"  {fname}:{pos}")
            # 截短 snippet
            print(f"    ...{snippet[:300]}...")

    if not findings:
        print("(无任何关键词组找到 ≥ 2 个关键词聚集)")


if __name__ == "__main__":
    main()
