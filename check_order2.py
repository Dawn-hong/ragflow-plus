import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找 "1、员工计划" 附近的顺序:')
print('=' * 80)
for idx, item in enumerate(data):
    item_type = item.get('type')
    page_idx = item.get('page_idx', 0)
    
    if item_type == 'text':
        text = item.get('text', '')
        if '员工计划' in text or '保险期间' in text:
            print(f'[{idx:2d}] page={page_idx:2d}, type={item_type:10s}, text={text[:60]}')
    elif item_type == 'table':
        table_caption = item.get('table_caption', [])
        if table_caption and '员工计划' in str(table_caption):
            print(f'[{idx:2d}] page={page_idx:2d}, type={item_type:10s}, caption={table_caption}')

print('\n\n查看 page 6-7 的所有元素:')
print('=' * 80)
for idx, item in enumerate(data):
    item_type = item.get('type')
    page_idx = item.get('page_idx', 0)
    
    if 6 <= page_idx <= 7:
        if item_type == 'text':
            text = item.get('text', '')[:50]
            print(f'[{idx:2d}] page={page_idx:2d}, type={item_type:10s}, text={text}')
        elif item_type == 'table':
            table_caption = item.get('table_caption', [])
            table_body = item.get('table_body', '')[:50]
            print(f'[{idx:2d}] page={page_idx:2d}, type={item_type:10s}, caption={table_caption}')
            print(f'     body={table_body}')
