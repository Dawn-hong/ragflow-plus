#!/usr/bin/env python3
"""
测试 MinerU 官方示例代码 - 完整流程测试
"""
import os
import sys
import time
import requests
from pathlib import Path

# ================= 配置区域 =================
token = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI4MjMwMDQ4OSIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2OTIyOTc0NiwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiMTMxOTIzMjc0MjgiLCJvcGVuSWQiOm51bGwsInV1aWQiOiI1MmNkZjRlOC05MTZkLTQ0OTAtYTY5OC0zNzk5ZTBhZjQ3ZjMiLCJlbWFpbCI6IiIsImV4cCI6MTc3MDQzOTM0Nn0.rkJprHOD8Ww9w5_9qN-cs5NCg-Ws_pos1BbgC10Uin4iozHg-2jGIeJlgdCQD2hQPKhDCC6orqqIQEzSo29kig"

# 请在这里填入你的本地文件绝对路径
target_file = r"D:\Agent_Projcet\Japan KB\Japan KB\China KB\2025员工年度体检手册.pdf"

# 如果没有指定文件，使用一个测试文件
if not os.path.exists(target_file):
    print(f"文件不存在: {target_file}")
    print("请修改 target_file 变量指向一个存在的 PDF 文件")
    sys.exit(1)

BASE_URL = "https://mineru.net/api/v4"
POLL_INTERVAL = 5
POLL_TIMEOUT = 300
# ===========================================

def test_mineru_api():
    """测试 MinerU API 完整流程"""
    
    print("=" * 60)
    print("MinerU API 测试开始")
    print("=" * 60)
    
    # 步骤 1: 获取预签名 URL
    print("\n[步骤 1] 获取预签名 URL...")
    url = f"{BASE_URL}/file-urls/batch"
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # 自动从路径中提取文件名
    file_name = os.path.basename(target_file)
    
    data = {
        "files": [
            {"name": file_name, "data_id": "abcd"}
        ],
        "model_version": "vlm"
    }
    
    try:
        print(f"请求 URL: {url}")
        print(f"文件名: {file_name}")
        response = requests.post(url, headers=header, json=data, timeout=30)
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ 获取预签名 URL 失败: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
        
        result = response.json()
        print(f"响应内容: {result}")
        
        if result.get("code") != 0:
            print(f"❌ API 错误: {result.get('msg')}")
            return False
        
        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]
        print(f"✅ 获取预签名 URL 成功")
        print(f"   batch_id: {batch_id}")
        print(f"   预签名 URL: {urls[0][:60]}...")
        
    except Exception as err:
        print(f"❌ 获取预签名 URL 异常: {err}")
        return False
    
    # 步骤 2: 上传文件
    print("\n[步骤 2] 上传文件...")
    try:
        with open(target_file, 'rb') as f:
            print(f"正在上传: {target_file}")
            print(f"文件大小: {os.path.getsize(target_file)} bytes")
            res_upload = requests.put(urls[0], data=f, timeout=300)
            print(f"上传响应状态码: {res_upload.status_code}")
            
            if res_upload.status_code != 200:
                print(f"❌ 文件上传失败: HTTP {res_upload.status_code}")
                print(f"响应内容: {res_upload.text}")
                return False
        
        print("✅ 文件上传成功")
        
    except Exception as err:
        print(f"❌ 文件上传异常: {err}")
        return False
    
    # 步骤 3: 轮询结果
    print("\n[步骤 3] 轮询解析结果...")
    poll_url = f"{BASE_URL}/extract-results/batch/{batch_id}"
    start_time = time.time()
    attempt = 0
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > POLL_TIMEOUT:
            print(f"❌ 轮询超时 ({POLL_TIMEOUT}秒)")
            return False
        
        try:
            print(f"\n第 {attempt + 1} 次轮询 (已等待 {elapsed:.1f} 秒)...")
            poll_response = requests.get(poll_url, headers=header, timeout=30)
            print(f"轮询响应状态码: {poll_response.status_code}")
            
            if poll_response.status_code != 200:
                print(f"❌ 轮询请求失败: HTTP {poll_response.status_code}")
                time.sleep(POLL_INTERVAL)
                attempt += 1
                continue
            
            poll_result = poll_response.json()
            print(f"轮询响应: {poll_result}")
            
            if poll_result.get("code") != 0:
                print(f"❌ 轮询 API 错误: {poll_result.get('msg')}")
                time.sleep(POLL_INTERVAL)
                attempt += 1
                continue
            
            data = poll_result.get("data", {})
            status = data.get("status", "")
            
            print(f"解析状态: '{status}'")
            
            if status == "completed":
                print("✅ 解析完成!")
                files = data.get("files", [])
                if files:
                    zip_url = files[0].get("url")
                    print(f"ZIP 下载链接: {zip_url[:60]}...")
                    return True
                else:
                    print("❌ 没有返回文件链接")
                    return False
            
            elif status == "failed":
                error_msg = data.get("error", "Unknown error")
                print(f"❌ 解析失败: {error_msg}")
                return False
            
            elif status in ["pending", "processing", ""]:
                if status == "":
                    print("⚠️ 状态为空，继续等待...")
                else:
                    print(f"⏳ 正在解析中 ({status})，继续等待...")
            else:
                print(f"⚠️ 未知状态: '{status}'，继续等待...")
            
            time.sleep(POLL_INTERVAL)
            attempt += 1
            
        except Exception as err:
            print(f"⚠️ 轮询异常: {err}，继续重试...")
            time.sleep(POLL_INTERVAL)
            attempt += 1

if __name__ == "__main__":
    success = test_mineru_api()
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试通过!")
    else:
        print("❌ 测试失败!")
    print("=" * 60)
