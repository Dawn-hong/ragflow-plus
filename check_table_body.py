import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('检查 Table [85] 和 [87] 的 body:')
print('=' * 80)

for idx in [85, 87]:
    item = data[idx]
    print(f'\n[{idx}] type={item.get("type")}, page_idx={item.get("page_idx")}')
    print(f'  table_body length: {len(item.get("table_body", ""))}')
    print(f'  table_body preview: {item.get("table_body", "")[:200]}')
