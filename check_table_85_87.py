import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('检查 Table [85] 和 [87] 的详细信息:')
print('=' * 80)

for idx in [85, 87]:
    item = data[idx]
    print(f'\n[{idx}] type={item.get("type")}, page_idx={item.get("page_idx")}')
    print(f'  caption: {item.get("table_caption", [])}')
    print(f'  bbox: {item.get("bbox")}')
    # 检查前一个和后一个元素
    if idx > 0:
        prev = data[idx-1]
        print(f'  prev [{idx-1}]: type={prev.get("type")}, text={prev.get("text", "")[:50]}')
    if idx < len(data) - 1:
        next_item = data[idx+1]
        print(f'  next [{idx+1}]: type={next_item.get("type")}, text={next_item.get("text", "")[:50]}')
