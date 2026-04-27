"""Find all 'token': '' occurrences in phase2_protocol_driver.py"""
path = 'system/phase2_protocol_driver.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    if '"token": ""' in line:
        print(f'  Line {i}: {line.strip()[:80]}')
