"""Smoke test governance modules."""
import sys
sys.path.insert(0, 'system')
from governance import IndustryMatcher, OptionDict

m = IndustryMatcher.load()
total = len(m._flat)
leaf = sum(1 for r in m._flat if r["level"] == 4)
print(f"Industry tree: total nodes={total}, leaf(4-digit)={leaf}")
print(f"Index size: {len(m._index_by_code)}")

print("\n=== lookup_by_code ===")
for c in ["6513", "5710", "9999"]:
    r = m.lookup_by_code(c)
    print(f"  {c}: {r.name if r else 'NOT FOUND'}")

print("\n=== search tests ===")
for q in ["软件开发", "应用软件开发", "餐饮", "咨询服务", "信息技术", "不存在的行业xxx"]:
    res = m.search(q, top_n=3)
    decisive = m.is_decisive(res)
    print(f"\nQuery: {q!r}  decisive={decisive}")
    for c in res:
        print(f"   -> [{c.code}] {c.name} ({c.match_type}, score={c.score})")

print("\n=== OptionDict (empty) ===")
od = OptionDict.load()
print(f"fields: {len(od.fields)}")
print(f"summary: {od.summary()}")

# 测试 upsert + validate
od.upsert_options("politicalStatus",
    [{"code":"01","name":"中共党员"},{"code":"13","name":"群众"}],
    label="政治面貌", source="MemberInfo.politicalStatus")
print(f"\nAfter upsert: validate('politicalStatus','01') = {od.validate_value('politicalStatus','01')[0]}")
print(f"validate('politicalStatus','99') = {od.validate_value('politicalStatus','99')[0]}")
print(f"validate('politicalStatus','中共党员') = {od.validate_value('politicalStatus','中共党员')[0]}")
print(f"validate('politicalStatus','党员') = {od.validate_value('politicalStatus','党员')}")
