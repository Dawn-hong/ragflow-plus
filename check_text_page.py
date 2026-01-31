import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找 "3、连带子女被保险人自选计划" 的详细信息:')
print('=' * 80)
for idx, item in enumerate(data):
    if item.get('type') == 'text':
        text = item.get('text', '')
        if '连带子女被保险人自选计划' in text:
            print(f'\nFound at index {idx}:')
            print(f'  page_idx (0-indexed): {item.get("page_idx")}')
            print(f'  actual page (1-indexed): {item.get("page_idx") + 1}')
            print(f'  text: {text[:100]}')
            print(f'  bbox: {item.get("bbox")}')
