#!/usr/bin/env python3
"""
检查 MinerU 完成状态的完整数据结构
"""
import os
import time
import requests

# ================= 配置区域 =================
token = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI4MjMwMDQ4OSIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2OTIyOTc0NiwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiMTMxOTIzMjc0MjgiLCJvcGVuSWQiOm51bGwsInV1aWQiOiI1MmNkZjRlOC05MTZkLTQ0OTAtYTY5OC0zNzk5ZTBhZjQ3ZjMiLCJlbWFpbCI6IiIsImV4cCI6MTc3MDQzOTM0Nn0.rkJprHOD8Ww9w5_9qN-cs5NCg-Ws_pos1BbgC10Uin4iozHg-2jGIeJlgdCQD2hQPKhDCC6orqqIQEzSo29kig"

target_file = r"D:\Agent_Projcet\Japan KB\Japan KB\China KB\2025员工年度体检手册.pdf"
BASE_URL = "https://mineru.net/api/v4"
# ===========================================

def get_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

def main():
    # 1. 获取预签名 URL
    url = f"{BASE_URL}/file-urls/batch"
    data = {
        "files": [{"name": os.path.basename(target_file), "data_id": "abcd"}],
        "model_version": "vlm",
    }
    
    print("[1] 获取预签名 URL...")
    response = requests.post(url, headers=get_headers(), json=data, timeout=30)
    result = response.json()
    batch_id = result["data"]["batch_id"]
    presigned_url = result["data"]["file_urls"][0]
    print(f"  batch_id: {batch_id}")
    
    # 2. 上传文件
    print("[2] 上传文件...")
    with open(target_file, "rb") as f:
        requests.put(presigned_url, data=f, timeout=300)
    print("  上传成功")
    
    # 3. 轮询直到完成
    print("[3] 轮询直到完成...")
    poll_url = f"{BASE_URL}/extract-results/batch/{batch_id}"
    
    while True:
        response = requests.get(poll_url, headers=get_headers(), timeout=30)
        result = response.json()
        data = result.get("data", {})
        extract_results = data.get("extract_result", [])
        
        if extract_results:
            result_item = extract_results[0]
            status = result_item.get("state", "")
            print(f"  状态: {status}")
            
            if status in ["completed", "done"]:
                print("\n[4] 完成状态完整数据结构:")
                import json
                print(json.dumps(result_item, indent=2, ensure_ascii=False))
                break
        
        time.sleep(5)

if __name__ == "__main__":
    main()
