import json

with open(r'D:\Agent_Projcet\mineru_download\广东2025年员工保险服务手册_400171da-00c9-452f-825b-f7ed7edbdcc8\0eb854a0-5292-4176-a07b-be042c728dfe_content_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('查找 "2、实习生计划" 的详细信息:')
print('=' * 80)
for idx, item in enumerate(data):
    if item.get('type') == 'table':
        caption = item.get('table_caption', [])
        if caption and '实习生计划' in str(caption):
            print(f'\nFound at index {idx}:')
            print(f'  page_idx: {item.get("page_idx")}')
            print(f'  caption: {caption}')
            print(f'  bbox: {item.get("bbox")}')
            # 查看前后的元素
            print('\n  Previous elements:')
            for i in range(max(0, idx-3), idx):
                prev = data[i]
                print(f'    [{i}] page={prev.get("page_idx")}, type={prev.get("type")}, text={prev.get("text", "")[:50]}')
            print(f'    [{idx}] page={item.get("page_idx")}, type={item.get("type")}, caption={caption}')
            print('  Next elements:')
            for i in range(idx+1, min(len(data), idx+4)):
                nxt = data[i]
                print(f'    [{i}] page={nxt.get("page_idx")}, type={nxt.get("type")}, text={nxt.get("text", "")[:50]}')
