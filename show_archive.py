import json

with open('D:/UFO/desktop_control_archive.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== 快速直达索引 ===\n')

for app_key, app in data['applications'].items():
    if app.get('error'):
        continue
    qi = app.get('quick_index', {})
    auto_ids = qi.get('by_auto_id', {})
    static_names = qi.get('by_static_name', {})
    
    if not auto_ids and not static_names:
        continue
    
    exe = app.get('exe', '?')
    title = app.get('title', '')[:40]
    print('--- %s (%s) ---' % (exe, title))
    
    if auto_ids:
        print('  🎯 Automation IDs (%d):' % len(auto_ids))
        for aid, info in list(auto_ids.items())[:12]:
            print('     %s → %s [%s]' % (aid, info['control_type'], info.get('class_name','')[:30]))
    
    if static_names:
        print('  📌 Static Names (%d):' % len(static_names))
        for key, info in list(static_names.items())[:12]:
            aid = info.get('automation_id', '') or '-'
            print('     %s → id=%s [%s]' % (key, aid, info.get('class_name','')[:30]))
    print()
