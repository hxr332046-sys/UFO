import requests, json
r = requests.get('http://localhost:9090/api/dashboard', timeout=5)
d = r.json()
print(f"Stats: {d['stats']['total']} tasks, {d['stats']['needs_client_action']} need action")
for t in d['recent_tasks']:
    print(f"  {t['task_id']} | {t['client_name']} | {t['status_label']}")
