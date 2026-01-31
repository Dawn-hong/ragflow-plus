import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找关键元素的 page_idx:')
print('=' * 80)

# 查找 "2、实习生计划" table
for idx, item in enumerate(data):
    if item.get('type') == 'table':
        caption = item.get('table_caption', [])
        if caption and '实习生计划' in str(caption):
            print(f'\n[2、实习生计划 table]')
            print(f'  JSON index: {idx}')
            print(f'  page_idx (0-indexed): {item.get("page_idx")}')
            print(f'  Actual page (1-indexed): {item.get("page_idx") + 1}')

# 查找 "3、连带子女被保险人自选计划" text
for idx, item in enumerate(data):
    if item.get('type') == 'text':
        text = item.get('text', '')
        if '连带子女被保险人自选计划' in text:
            print(f'\n[3、连带子女被保险人自选计划 text]')
            print(f'  JSON index: {idx}')
            print(f'  page_idx (0-indexed): {item.get("page_idx")}')
            print(f'  Actual page (1-indexed): {item.get("page_idx") + 1}')
