import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找 "1、员工计划" table 的详细信息:')
print('=' * 80)
for idx, item in enumerate(data):
    if item.get('type') == 'table':
        table_caption = item.get('table_caption', [])
        if table_caption and '员工计划' in str(table_caption):
            print(f'\nFound at index {idx}:')
            print(f'  page_idx: {item.get("page_idx")}')
            print(f'  caption: {table_caption}')
            print(f'  table_body length: {len(item.get("table_body", ""))}')
            print(f'  bbox: {item.get("bbox")}')
            print(f'  img_path: {item.get("img_path")}')
