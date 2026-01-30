import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('检查 bbox 坐标 (left, top, right, bottom):')
print('=' * 80)
invalid_count = 0
for idx, item in enumerate(data):
    bbox = item.get('bbox')
    if bbox and len(bbox) == 4:
        left, top, right, bottom = bbox
        issues = []
        if right <= left:
            issues.append(f'right({right}) <= left({left})')
        if bottom <= top:
            issues.append(f'bottom({bottom}) <= top({top})')
        if issues:
            invalid_count += 1
            print(f'[{idx}] type={item.get("type")}, text={item.get("text", "")[:50]}')
            print(f'    bbox={bbox}')
            print(f'    问题: {", ".join(issues)}')
            print()

print('=' * 80)
print(f'总共 {len(data)} 个 blocks, 发现 {invalid_count} 个无效 bbox')
