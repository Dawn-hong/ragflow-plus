import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找所有 table 的 page_idx:')
print('=' * 80)
table_count = 0
for idx, item in enumerate(data):
    if item.get('type') == 'table':
        table_count += 1
        page_idx = item.get('page_idx')
        caption = item.get('table_caption', [])
        body_len = len(item.get('table_body', ''))
        print(f'[{table_count:2d}] idx={idx:3d}, page_idx={page_idx}, caption={caption}, body_len={body_len}')
