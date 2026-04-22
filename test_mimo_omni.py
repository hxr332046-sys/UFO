#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test MiMo v2-omni vision model capability"""

import requests
import json
import base64
import io
from PIL import ImageGrab

# Take a screenshot and encode as base64
print("Taking screenshot...")
img = ImageGrab.grab()
buf = io.BytesIO()
img.save(buf, format='PNG', compress_level=1)
b64 = base64.b64encode(buf.getvalue()).decode()
print(f"Screenshot size: {img.size}, base64 length: {len(b64)}")

# Test mimo-v2-omni with image
print("\nTesting mimo-v2-omni with image...")
resp = requests.post('http://localhost:5678/v1/chat/completions', json={
    'model': 'mimo-v2-omni',
    'messages': [
        {'role': 'user', 'content': [
            {'type': 'text', 'text': '请简要描述这张截图中你看到的内容'},
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}}
        ]}
    ],
    'stream': False
}, timeout=120)

print(f"Status: {resp.status_code}")
data = resp.json()
if 'choices' in data:
    content = data['choices'][0]['message']['content']
    print(f"Omni Response: {content[:500]}")
    print(f"\nVision model WORKS!" if len(content) > 50 else "\nVision model may NOT work properly")
else:
    print(f"Error response: {json.dumps(data, ensure_ascii=False)[:500]}")

# Also test mimo-v2-pro text-only for comparison
print("\n\nTesting mimo-v2-pro text-only...")
resp2 = requests.post('http://localhost:5678/v1/chat/completions', json={
    'model': 'mimo-v2-pro',
    'messages': [
        {'role': 'user', 'content': '请用一句话描述Windows桌面的常见元素'}
    ],
    'stream': False
}, timeout=120)
data2 = resp2.json()
if 'choices' in data2:
    print(f"Pro Response: {data2['choices'][0]['message']['content'][:300]}")
