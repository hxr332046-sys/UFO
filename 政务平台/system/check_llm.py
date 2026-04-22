import requests, json
r = requests.post('http://localhost:7860/v1/chat/completions',
    headers={'Authorization': 'Bearer sk-aistudio-2026', 'Content-Type': 'application/json'},
    json={
        'model': 'gemini-flash-latest',
        'messages': [
            {'role': 'system', 'content': 'Return JSON: {"status":"ok"}'},
            {'role': 'user', 'content': 'test'}
        ],
        'max_tokens': 100,
        'temperature': 0.1
    }, timeout=30)
print(r.status_code)
d = r.json()
print(json.dumps(d, ensure_ascii=False)[:500])
