import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('检查 TABLE 类型的 caption:')
print('=' * 80)
table_count = 0
for idx, item in enumerate(data):
    if item.get('type') == 'table':
        table_count += 1
        table_body = item.get('table_body', '')
        table_caption = item.get('table_caption', [])
        table_footnote = item.get('table_footnote', [])
        
        print(f'\n[Table {table_count}] page_idx={item.get("page_idx")}')
        print(f'  table_caption: {table_caption}')
        print(f'  table_body length: {len(table_body)}')
        print(f'  table_footnote: {table_footnote}')
        
        # 检查前一个元素是否是 caption
        if idx > 0:
            prev = data[idx - 1]
            print(f'  前一个元素: type={prev.get("type")}, text={prev.get("text", "")[:50]}')

print(f'\n总共发现 {table_count} 个 table')
