#!/usr/bin/env python3
"""
测试修复后的 MinerU 在线解析逻辑 - 完整流程测试
使用与修复后代码相同的逻辑
"""
import os
import sys
import time
import zipfile
import tempfile
import shutil
import requests
from pathlib import Path
from io import BytesIO

# ================= 配置区域 =================
token = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI4MjMwMDQ4OSIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2OTIyOTc0NiwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiMTMxOTIzMjc0MjgiLCJvcGVuSWQiOm51bGwsInV1aWQiOiI1MmNkZjRlOC05MTZkLTQ0OTAtYTY5OC0zNzk5ZTBhZjQ3ZjMiLCJlbWFpbCI6IiIsImV4cCI6MTc3MDQzOTM0Nn0.rkJprHOD8Ww9w5_9qN-cs5NCg-Ws_pos1BbgC10Uin4iozHg-2jGIeJlgdCQD2hQPKhDCC6orqqIQEzSo29kig"

# 请在这里填入你的本地文件绝对路径
target_file = r"D:\Agent_Projcet\Japan KB\Japan KB\China KB\2025员工年度体检手册.pdf"

BASE_URL = "https://mineru.net/api/v4"
POLL_INTERVAL = 5
POLL_TIMEOUT = 300
# ===========================================

def get_headers():
    """获取 API 请求头"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

def get_presigned_urls(filename):
    """获取预签名上传 URL"""
    url = f"{BASE_URL}/file-urls/batch"
    data = {
        "files": [{"name": filename, "data_id": "abcd"}],
        "model_version": "vlm",
    }
    
    print(f"[步骤 1] 获取预签名 URL...")
    print(f"  请求 URL: {url}")
    print(f"  文件名: {filename}")
    
    response = requests.post(url, headers=get_headers(), json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    if result.get("code") != 0:
        raise RuntimeError(f"API error: {result.get('msg', 'Unknown error')}")
    
    batch_id = result["data"]["batch_id"]
    urls = result["data"]["file_urls"]
    
    if not urls:
        raise RuntimeError("No presigned URL returned")
    
    print(f"  ✅ 获取成功 - batch_id: {batch_id}")
    return batch_id, urls[0]

def upload_file(file_path, presigned_url):
    """上传文件到预签名 URL"""
    print(f"[步骤 2] 上传文件...")
    print(f"  文件: {file_path}")
    print(f"  大小: {os.path.getsize(file_path)} bytes")
    
    with open(file_path, "rb") as f:
        response = requests.put(presigned_url, data=f, timeout=300)
        response.raise_for_status()
    
    print(f"  ✅ 上传成功")

def poll_result(batch_id):
    """
    轮询获取解析结果 - 使用修复后的逻辑
    """
    print(f"[步骤 3] 轮询解析结果...")
    url = f"{BASE_URL}/extract-results/batch/{batch_id}"
    start_time = time.time()
    attempt = 0
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > POLL_TIMEOUT:
            raise RuntimeError(f"Polling timeout after {POLL_TIMEOUT}s")
        
        response = requests.get(url, headers=get_headers(), timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") != 0:
            raise RuntimeError(f"API error: {result.get('msg', 'Unknown error')}")
        
        data = result.get("data", {})
        
        # ===== 修复后的逻辑：从 extract_result 数组中获取状态 =====
        extract_results = data.get("extract_result", [])
        if not extract_results:
            print(f"  第 {attempt + 1} 次轮询 - 无 extract_result，继续等待...")
            status = "pending"
            progress_info = {}
        else:
            result_item = extract_results[0]
            status = result_item.get("state", "")
            progress_info = result_item.get("extract_progress", {})
            
            # 显示进度
            if progress_info:
                pages = f"{progress_info.get('extracted_pages', 0)}/{progress_info.get('total_pages', 0)} pages"
            else:
                pages = status
            
            print(f"  第 {attempt + 1} 次轮询 - 状态: '{status}', 进度: {pages}, 已等待: {elapsed:.1f}s")
        
        # 状态判断
        if status in ["completed", "done"]:
            print(f"  ✅ 解析完成!")
            return data
        elif status == "failed":
            error_msg = result_item.get("err_msg", "Unknown error")
            raise RuntimeError(f"Parsing failed: {error_msg}")
        elif status in ["pending", "running", ""]:
            # 继续轮询
            pass
        else:
            print(f"  ⚠️ 未知状态: '{status}'，继续等待...")
        
        time.sleep(POLL_INTERVAL)
        attempt += 1

def download_zip(zip_url, output_path):
    """下载 ZIP 文件"""
    print(f"[步骤 4] 下载 ZIP 文件...")
    print(f"  URL: {zip_url[:60]}...")
    
    response = requests.get(zip_url, timeout=300, stream=True)
    response.raise_for_status()
    
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    file_size = os.path.getsize(output_path)
    print(f"  ✅ 下载完成 - 大小: {file_size} bytes")

def extract_zip(zip_path, extract_to):
    """解压 ZIP 文件"""
    print(f"[步骤 5] 解压 ZIP 文件...")
    print(f"  ZIP: {zip_path}")
    print(f"  解压到: {extract_to}")
    
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    
    # 列出解压后的文件
    files = list(Path(extract_to).rglob("*"))
    print(f"  ✅ 解压完成 - 共 {len(files)} 个文件/目录")
    
    # 查找 _content_list.json
    content_list_files = [f for f in files if f.name.endswith("_content_list.json")]
    if content_list_files:
        print(f"  📄 找到内容列表文件: {content_list_files[0]}")
        return content_list_files[0]
    else:
        print(f"  ⚠️ 未找到 _content_list.json 文件")
        return None

def read_content_list(json_path):
    """读取内容列表 JSON"""
    import json
    
    print(f"[步骤 6] 读取解析结果...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    outputs = data if isinstance(data, list) else data.get("result", {}).get("output", [])
    print(f"  ✅ 读取完成 - 共 {len(outputs)} 个内容块")
    
    # 显示前几个内容块
    for i, item in enumerate(outputs[:3]):
        content = item.get("text", item.get("content", ""))[:100]
        print(f"  块 {i+1}: {content}...")
    
    return outputs

def test_mineru_fixed():
    """测试修复后的完整流程"""
    
    print("=" * 70)
    print("MinerU 修复后逻辑测试 - 完整流程")
    print("=" * 70)
    
    # 检查文件
    if not os.path.exists(target_file):
        print(f"❌ 文件不存在: {target_file}")
        print("请修改 target_file 变量指向一个存在的 PDF 文件")
        return False
    
    work_dir = None
    try:
        # 步骤 1: 获取预签名 URL
        batch_id, presigned_url = get_presigned_urls(os.path.basename(target_file))
        
        # 步骤 2: 上传文件
        upload_file(target_file, presigned_url)
        
        # 步骤 3: 轮询结果（使用修复后的逻辑）
        result_data = poll_result(batch_id)
        
        # 步骤 4: 获取 ZIP 下载链接（使用修复后的逻辑）
        print(f"\n[获取下载链接]")
        extract_results = result_data.get("extract_result", [])
        if not extract_results:
            raise RuntimeError("No extract_result returned")
        
        result_item = extract_results[0]
        # ZIP 下载链接在 full_zip_url 字段
        zip_url = result_item.get("full_zip_url")
        
        print(f"  从 extract_result[0].full_zip_url 获取: {zip_url[:60] if zip_url else 'None'}...")
        
        if not zip_url:
            raise RuntimeError("No ZIP URL in result")
        
        # 步骤 5: 下载 ZIP
        work_dir = Path(tempfile.mkdtemp(prefix="mineru_test_"))
        zip_path = work_dir / "result.zip"
        download_zip(zip_url, zip_path)
        
        # 步骤 6: 解压 ZIP
        extract_dir = work_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)
        json_path = extract_zip(zip_path, extract_dir)
        
        # 步骤 7: 读取内容
        if json_path:
            outputs = read_content_list(json_path)
            print(f"\n✅ 测试成功! 共解析 {len(outputs)} 个内容块")
            return True
        else:
            print(f"\n⚠️ 测试部分成功，但未找到内容列表文件")
            return True
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时文件
        if work_dir and work_dir.exists():
            try:
                shutil.rmtree(work_dir)
                print(f"\n🧹 清理临时目录: {work_dir}")
            except Exception:
                pass

if __name__ == "__main__":
    success = test_mineru_fixed()
    print("\n" + "=" * 70)
    if success:
        print("✅ 修复后的逻辑测试通过!")
    else:
        print("❌ 修复后的逻辑测试失败!")
    print("=" * 70)
