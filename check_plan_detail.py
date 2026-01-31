import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找 "计划一" 和 "计划二" 的完整内容:')
print('=' * 80)

for idx, item in enumerate(data[80:115]):
    actual_idx = 80 + idx
    if item.get('type') == 'text':
        text = item.get('text', '')
        print(f'\n[{actual_idx}] type={item.get("type")}, page_idx={item.get("page_idx")}')
        print(f'  text: {text[:150]}')
    elif item.get('type') == 'table':
        caption = item.get('table_caption', [])
        print(f'\n[{actual_idx}] type={item.get("type")}, page_idx={item.get("page_idx")}')
        print(f'  caption: {caption}')
