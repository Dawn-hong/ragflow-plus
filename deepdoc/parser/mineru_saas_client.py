import hashlib
import json
import logging
import tempfile
from typing import Optional, Dict, Any
import os
import time
import requests

class MinerUSaaSClient:
    def __init__(self, token: str, model_version: str = "vlm"):
        self.token = token
        self.model_version = model_version
        self.base_url = "https://mineru.net/api/v4"
        self.headers = {
            "Authorization": f"Bearer {token}",
            # "Content-Type": "application/json" # Requests handles this for json/files
        }
        self.logger = logging.getLogger("MinerUSaaSClient")
        self.cache_dir = os.path.join(tempfile.gettempdir(), "mineru_upload_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_file_hash(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_cache_path(self, file_hash: str) -> str:
        return os.path.join(self.cache_dir, f"{file_hash}_{self.model_version}.json")

    def upload(self, file_path: str) -> str:
        """
        Uploads a file to MinerU and returns the batch_id. 
        Uses caching to avoid re-uploading identical files.
        """
        file_hash = self._get_file_hash(file_path)
        cache_path = self._get_cache_path(file_hash)
        
        # Check cache
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    cached_data = json.load(f)
                # Verify cache is valid (e.g., expiry?)
                # For now, assume batch_id is valid for some time. 
                # MinerU batch_ids usually expire after some days. 
                # We can check timestamp if needed, but for consecutive task chunks, it's fine.
                if cached_data.get("batch_id") and (time.time() - cached_data.get("timestamp", 0) < 86400): # 1 day cache
                     self.logger.info(f"[MinerU SaaS] Using cached batch_id for {os.path.basename(file_path)}")
                     return cached_data["batch_id"]
            except Exception as e:
                self.logger.warning(f"[MinerU SaaS] Failed to read cache: {e}")

        # Proceed with upload
        url = f"{self.base_url}/file-urls/batch"
        file_name = os.path.basename(file_path)
        
        # Step 1: Get presigned URLs
        data = {
            "files": [
                {"name": file_name, "data_id": "ragflow_upload"} # generic data_id
            ],
            "model_version": self.model_version
        }
        
        self.logger.info(f"[MinerU SaaS] Requesting upload URL for {file_name}...")
        try:
            response = requests.post(url, headers={"Authorization": self.headers["Authorization"], "Content-Type": "application/json"}, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") != 0:
                raise RuntimeError(f"MinerU API error: {result.get('msg')}")
                
            batch_id = result["data"]["batch_id"]
            file_urls = result["data"]["file_urls"]
            
            if not file_urls:
                 raise RuntimeError("MinerU API returned no upload URLs")

            # Step 2: Upload file content to presigned URL
            upload_url = file_urls[0]
            self.logger.info(f"[MinerU SaaS] Uploading file content to {upload_url[:50]}...")
            
            # Read file content once
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Retry logic for upload
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    res_upload = requests.put(upload_url, data=file_data, timeout=300) # 5 min timeout for upload
                    res_upload.raise_for_status()
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    self.logger.warning(f"[MinerU SaaS] Upload attempt {attempt+1} failed ({e}), retrying...")
                    time.sleep(2 * (attempt + 1))
                
            self.logger.info(f"[MinerU SaaS] File {file_name} uploaded successfully. Batch ID: {batch_id}")
            
            # Save to cache
            try:
                with open(cache_path, "w") as f:
                    json.dump({"batch_id": batch_id, "timestamp": time.time(), "file_name": file_name}, f)
            except Exception as e:
                self.logger.warning(f"[MinerU SaaS] Failed to save cache: {e}")
                
            return batch_id

        except Exception as e:
            self.logger.error(f"[MinerU SaaS] Upload failed: {e}")
            raise

    def get_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Checks the status of a batch.
        """
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        try:
            res = requests.get(url, headers=self.headers, timeout=30)
            res.raise_for_status()
            return res.json()
        except Exception as e:
             self.logger.error(f"[MinerU SaaS] Status check failed: {e}")
             raise

    def poll_until_done(self, batch_id: str, interval: int = 5, timeout: int = 600) -> Optional[str]:
        """
        Polls the status until completed or timeout. Returns the download URL for the ZIP or None if failed.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_res = self.get_status(batch_id)
            if status_res.get("code") != 0:
                 self.logger.warning(f"[MinerU SaaS] API non-zero code: {status_res.get('msg')}")
                 time.sleep(interval)
                 continue

            data = status_res.get("data", {})
            # According to docs/obs, we need to check the extract_result
            # The structure might vary slightly, but let's assume it matches the provided example logic
            # However, the provided example code just prints the json.
            # Usually batch status returns a list of files.
            
            extract_results = data.get("extract_result", [])
            if not extract_results:
                 self.logger.info(f"[MinerU SaaS] Processing... (No results yet)")
                 time.sleep(interval)
                 continue
            
            # Assuming single file batch for now as per our usage
            item = extract_results[0]
            state = item.get("state")
            
            if state == "done":
                full_zip_url = item.get("full_zip_url")
                if full_zip_url:
                    return full_zip_url
                else:
                    raise RuntimeError("MinerU SaaS completed but no full_zip_url found.")
            elif state in ["error", "failed"]:
                 raise RuntimeError(f"MinerU SaaS processing failed: {item.get('err_msg')}")
            else:
                 self.logger.info(f"[MinerU SaaS] Processing... State: {state}")

            time.sleep(interval)
            
        raise TimeoutError(f"MinerU SaaS processing timed out after {timeout} seconds")
