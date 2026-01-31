import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('检查前 30 个元素的顺序:')
print('=' * 80)
for idx, item in enumerate(data[:30]):
    item_type = item.get('type')
    page_idx = item.get('page_idx', 0)
    text = item.get('text', '')[:50] if item_type == 'text' else ''
    table_caption = item.get('table_caption', []) if item_type == 'table' else []
    
    if item_type == 'table':
        print(f'[{idx:2d}] page={page_idx:2d}, type={item_type:10s}, caption={table_caption}')
    else:
        print(f'[{idx:2d}] page={page_idx:2d}, type={item_type:10s}, text={text}')
