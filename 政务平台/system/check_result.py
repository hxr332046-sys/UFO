import requests, json, time

# 等待后台审核完成
time.sleep(10)

r = requests.get("http://localhost:9090/api/dashboard", timeout=10)
d = r.json()
print(f"Total: {d['stats']['total']}, CDP: {d.get('cdp_status',{}).get('cdp_connected')}")
for t in d['recent_tasks']:
    print(f"\n  Task: {t['task_id']} | {t['client_name']} | {t['status_label']}")
    if t.get('review_result'):
        rr = t['review_result']
        print(f"  Review: approved={rr.get('approved')} risk={rr.get('risk_level','')}")
        print(f"  Summary: {rr.get('summary','')[:120]}")
        if rr.get('issues'):
            for i in rr['issues'][:3]:
                print(f"  Issue: {i[:80]}")
    if t.get('form_data', {}).get('fields'):
        print(f"  Form fields: {len(t['form_data']['fields'])} mapped")
        for k, v in list(t['form_data']['fields'].items())[:5]:
            val = v.get('value', '') if isinstance(v, dict) else str(v)
            print(f"    {k}: {val[:50]}")
    if t.get('needs_client_action'):
        print(f"  ⚠️ Needs client: {t.get('client_action_message','')}")
