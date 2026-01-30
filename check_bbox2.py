import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('检查前 10 个 bbox 坐标:')
print('=' * 80)
for idx, item in enumerate(data[:10]):
    bbox = item.get('bbox')
    text = item.get('text', '')[:50]
    print(f'[{idx}] type={item.get("type")}, text={text}')
    print(f'    bbox={bbox}')
    if bbox:
        print(f'    left={bbox[0]}, top={bbox[1]}, right={bbox[2]}, bottom={bbox[3]}')
    print()

# 检查坐标范围
print('=' * 80)
print('检查所有 bbox 坐标范围:')
all_left = [item['bbox'][0] for item in data if item.get('bbox')]
all_top = [item['bbox'][1] for item in data if item.get('bbox')]
all_right = [item['bbox'][2] for item in data if item.get('bbox')]
all_bottom = [item['bbox'][3] for item in data if item.get('bbox')]

print(f'left: min={min(all_left)}, max={max(all_left)}')
print(f'top: min={min(all_top)}, max={max(all_top)}')
print(f'right: min={min(all_right)}, max={max(all_right)}')
print(f'bottom: min={min(all_bottom)}, max={max(all_bottom)}')
