import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找 page 6-8 的所有元素顺序:')
print('=' * 80)
for idx, item in enumerate(data):
    page_idx = item.get('page_idx', 0)
    if 6 <= page_idx <= 8:
        item_type = item.get('type')
        if item_type == 'text':
            text = item.get('text', '')[:60]
            print(f'[{idx:3d}] page={page_idx}, type={item_type:10s}, text={text}')
        elif item_type == 'table':
            caption = item.get('table_caption', [])
            print(f'[{idx:3d}] page={page_idx}, type={item_type:10s}, caption={caption}')
