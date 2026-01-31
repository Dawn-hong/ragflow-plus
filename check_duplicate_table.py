import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找所有包含 "员工计划" 的 table:')
print('=' * 80)
table_count = 0
for idx, item in enumerate(data):
    if item.get('type') == 'table':
        table_count += 1
        table_caption = item.get('table_caption', [])
        table_body = item.get('table_body', '')
        page_idx = item.get('page_idx', 0)
        
        if table_caption and '员工计划' in str(table_caption):
            print(f'\n[Table {table_count}] idx={idx}, page={page_idx}')
            print(f'  caption={table_caption}')
            print(f'  body_length={len(table_body)}')
            print(f'  body_preview={table_body[:100]}')
