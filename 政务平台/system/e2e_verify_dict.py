#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证SPA提取的行业分类数据与GB/T 4754-2017字典匹配度"""
import json

# 加载
with open(r'g:\UFO\政务平台\data\industry_spa_extracted.json', encoding='utf-8') as f:
    spa = json.load(f)
with open(r'g:\UFO\政务平台\data\industry_gb4754_2017.json', encoding='utf-8') as f:
    dic = json.load(f)

spa_data = spa.get('data', [])
dict_data = dic.get('categories', [])

print("="*60)
print("验证1: 门类级匹配 (A~T)")
print("="*60)

spa_map = {}
for c in spa_data:
    code = c.get('code','').replace('[','').replace(']','')
    name = c.get('name','').replace(f'[{code}]','').strip()
    spa_map[code] = name

dict_map = {}
for c in dict_data:
    dict_map[c['code']] = c['name']

match = 0
for code in sorted(dict_map.keys()):
    spa_name = spa_map.get(code, '')
    dict_name = dict_map.get(code, '')
    if spa_name and dict_name and (spa_name[:4] == dict_name[:4] or spa_name == dict_name):
        match += 1
        status = '✅'
    elif spa_name:
        status = '⚠️ 名称不同'
    else:
        status = '❌ SPA无'
    print(f"  [{code}] SPA={spa_name[:20]:20s} 字典={dict_name[:20]:20s} {status}")

print(f"\n门类匹配: {match}/{len(dict_map)}")

print("\n" + "="*60)
print("验证2: [I]门类子节点深度匹配")
print("="*60)

# 找SPA的[I]
spa_I = None
for c in spa_data:
    if c.get('code','') == 'I' or '[I]' in c.get('code',''):
        spa_I = c; break

dict_I = None
for c in dict_data:
    if c['code'] == 'I':
        dict_I = c; break

def count_nodes(node, depth=0):
    """递归统计节点数"""
    count = 1
    for child in node.get('children', []):
        count += count_nodes(child, depth+1)
    return count

def print_tree(node, depth=0, max_depth=3):
    """打印树"""
    if depth > max_depth: return
    code = node.get('code','')
    name = node.get('name','')
    # 清理name中的[code]前缀
    clean_name = name.replace(f'[{code}]','').strip() if name else ''
    prefix = '  ' * depth
    child_count = len(node.get('children', []))
    print(f"{prefix}[{code}] {clean_name[:25]} ({child_count}子)")
    for child in node.get('children', []):
        print_tree(child, depth+1, max_depth)

if spa_I:
    print(f"SPA [I] 总节点数: {count_nodes(spa_I)}")
    print_tree(spa_I, max_depth=3)
else:
    print("SPA无[I]数据")

print()
if dict_I:
    print(f"字典 [I] 总节点数: {count_nodes(dict_I)}")
    print_tree(dict_I, max_depth=3)
else:
    print("字典无[I]数据")

# 逐级对比
print("\n" + "="*60)
print("验证3: [I]大类逐个对比")
print("="*60)

if spa_I and dict_I:
    spa_big = {c.get('code','').replace('[','').replace(']',''): c.get('name','').replace(f"[{c.get('code','')}]",'').strip() for c in spa_I.get('children',[])}
    dict_big = {c['code']: c['name'] for c in dict_I.get('children',[])}
    
    for code in sorted(dict_big.keys()):
        spa_name = spa_big.get(code, '(无)')
        dict_name = dict_big.get(code, '')
        status = '✅' if spa_name[:4] == dict_name[:4] or spa_name == dict_name else '❌'
        spa_children = 0
        dict_children = len(dict_I.get('children',[])[list(dict_big.keys()).index(code)].get('children',[])) if code in dict_big else 0
        for c in spa_I.get('children',[]):
            if c.get('code','') == code or f'[{code}]' in c.get('code',''):
                spa_children = len(c.get('children',[]))
        print(f"  [{code}] SPA={spa_name[:25]:25s} 字典={dict_name[:25]:25s} {status} 子: SPA={spa_children} 字典={dict_children}")

print("\n" + "="*60)
print("验证4: 统计摘要")
print("="*60)

total_spa = sum(count_nodes(c) for c in spa_data)
total_dict = sum(count_nodes(c) for c in dict_data)
print(f"SPA总节点数: {total_spa}")
print(f"字典总节点数: {total_dict}")
print(f"SPA门类数: {len(spa_data)}")
print(f"字典门类数: {len(dict_data)}")

# 检查SPA数据是否包含小类(4位代码)
leaf_4digit = 0
leaf_3digit = 0
def count_leaves(node):
    global leaf_4digit, leaf_3digit
    children = node.get('children', [])
    if not children:
        code = node.get('code','').replace('[','').replace(']','')
        if len(code) == 4: leaf_4digit += 1
        elif len(code) == 3: leaf_3digit += 1
    else:
        for c in children: count_leaves(c)

for c in spa_data: count_leaves(c)
print(f"SPA叶子节点: 4位代码={leaf_4digit} 3位代码={leaf_3digit}")

print("\n✅ 验证完成")
