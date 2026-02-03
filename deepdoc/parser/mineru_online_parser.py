#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import json
import logging
import os
import shutil
import tempfile
import time
import zipfile
from io import BytesIO
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from PIL import Image

from deepdoc.parser.mineru_parser import MinerUContentType, LANGUAGE_TO_MINERU_MAP
from deepdoc.parser.pdf_parser import RAGFlowPdfParser


class MinerUOnlineParser(RAGFlowPdfParser):
    """MinerU Online API Parser - 支持 MinerU 官网在线 API 解析 PDF"""

    # MinerU 在线 API 端点
    BASE_URL = "https://mineru.net/api/v4"
    BATCH_URL = f"{BASE_URL}/file-urls/batch"

    def __init__(
        self,
        token: str = "",
        model_version: str = "vlm",
        poll_interval: int = 5,
        poll_timeout: int = 300,
        temp_dir: Optional[str] = None,
    ):
        """
        初始化 MinerU 在线解析器

        Args:
            token: MinerU API Token
            model_version: 模型版本，默认 "vlm"
            poll_interval: 轮询间隔（秒），默认 5
            poll_timeout: 轮询超时时间（秒），默认 300
            temp_dir: 临时目录路径，用于存储 ZIP 文件和解压内容
        """
        self.token = token
        self.model_version = model_version
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.temp_dir = temp_dir
        self.outlines = []
        self.logger = logging.getLogger(self.__class__.__name__)

        # 确保临时目录存在
        if self.temp_dir:
            os.makedirs(self.temp_dir, exist_ok=True)
            self.logger.info(f"[MinerU Online] Using configured temp dir: {self.temp_dir}")

    def _get_headers(self) -> dict:
        """获取 API 请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def check_available(self) -> tuple[bool, str]:
        """检查在线 API 是否可用"""
        if not self.token:
            return False, "[MinerU Online] Token not configured"

        try:
            # 尝试调用 batch API 检查可用性（不实际创建任务）
            response = requests.get(
                f"{self.BASE_URL}/extract-results/batch/test",
                headers=self._get_headers(),
                timeout=10,
            )
            # 404 表示端点存在但 batch_id 不存在，说明服务正常
            if response.status_code in [200, 404]:
                return True, ""
            else:
                return False, f"[MinerU Online] API check failed: {response.status_code}"
        except Exception as e:
            return False, f"[MinerU Online] API check exception: {e}"

    def _get_presigned_urls(self, filename: str, callback: Optional[Callable] = None) -> tuple[str, str]:
        """
        获取预签名上传 URL

        Args:
            filename: 文件名
            callback: 进度回调函数

        Returns:
            (batch_id, presigned_url)
        """
        data = {
            "files": [
                {"name": filename, "data_id": "ragflow_upload"}
            ],
            "model_version": self.model_version,
        }

        self.logger.info(f"[MinerU Online] Getting presigned URL for: {filename}")
        if callback:
            callback(0.10, f"[MinerU Online] Getting presigned URL...")

        try:
            response = requests.post(
                self.BATCH_URL,
                headers=self._get_headers(),
                json=data,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("code") != 0:
                raise RuntimeError(f"API error: {result.get('msg', 'Unknown error')}")

            batch_id = result["data"]["batch_id"]
            urls = result["data"]["file_urls"]

            if not urls:
                raise RuntimeError("No presigned URL returned")

            self.logger.info(f"[MinerU Online] Got batch_id: {batch_id}")
            return batch_id, urls[0]

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"[MinerU Online] Failed to get presigned URL: {e}")

    def _upload_file(
        self, file_path: str, presigned_url: str, callback: Optional[Callable] = None
    ) -> None:
        """
        上传文件到预签名 URL

        Args:
            file_path: 本地文件路径
            presigned_url: 预签名 URL
            callback: 进度回调函数
        """
        self.logger.info(f"[MinerU Online] Uploading file to presigned URL...")
        if callback:
            callback(0.20, f"[MinerU Online] Uploading PDF file...")

        try:
            with open(file_path, "rb") as f:
                response = requests.put(
                    presigned_url,
                    data=f,
                    timeout=300,
                )
                response.raise_for_status()

            self.logger.info("[MinerU Online] File uploaded successfully")
            if callback:
                callback(0.30, f"[MinerU Online] File uploaded, waiting for parsing...")

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"[MinerU Online] Failed to upload file: {e}")

    def _poll_result(
        self, batch_id: str, callback: Optional[Callable] = None
    ) -> dict:
        """
        轮询获取解析结果

        Args:
            batch_id: 任务批次 ID
            callback: 进度回调函数

        Returns:
            解析结果字典
        """
        url = f"{self.BASE_URL}/extract-results/batch/{batch_id}"
        start_time = time.time()
        attempt = 0

        self.logger.info(f"[MinerU Online] Polling result for batch_id: {batch_id}")

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.poll_timeout:
                raise RuntimeError(
                    f"[MinerU Online] Polling timeout after {self.poll_timeout}s"
                )

            try:
                response = requests.get(
                    url,
                    headers=self._get_headers(),
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") != 0:
                    raise RuntimeError(
                        f"[MinerU Online] API error: {result.get('msg', 'Unknown error')}"
                    )

                data = result.get("data", {})
                status = data.get("status", "")

                # 计算进度（30% - 70%）
                progress = min(0.30 + (attempt * 0.02), 0.70)
                attempt += 1

                if status == "completed":
                    self.logger.info("[MinerU Online] Parsing completed")
                    if callback:
                        callback(0.70, f"[MinerU Online] Parsing completed")
                    return data
                elif status == "failed":
                    error_msg = data.get("error", "Unknown error")
                    raise RuntimeError(f"[MinerU Online] Parsing failed: {error_msg}")
                elif status in ["pending", "processing"]:
                    self.logger.debug(f"[MinerU Online] Status: {status}, elapsed: {elapsed:.1f}s")
                    if callback:
                        callback(progress, f"[MinerU Online] Parsing {status}... ({elapsed:.0f}s)")
                else:
                    self.logger.warning(f"[MinerU Online] Unknown status: {status}")

                time.sleep(self.poll_interval)

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"[MinerU Online] Polling request failed: {e}, retrying...")
                time.sleep(self.poll_interval)

    def _download_zip(self, zip_url: str, output_path: Path, callback: Optional[Callable] = None) -> Path:
        """
        下载 ZIP 文件

        Args:
            zip_url: ZIP 文件下载 URL
            output_path: 输出文件路径
            callback: 进度回调函数

        Returns:
            ZIP 文件路径
        """
        self.logger.info(f"[MinerU Online] Downloading ZIP from: {zip_url[:50]}...")
        if callback:
            callback(0.75, f"[MinerU Online] Downloading result ZIP...")

        try:
            response = requests.get(zip_url, timeout=300, stream=True)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            self.logger.info(f"[MinerU Online] ZIP downloaded to: {output_path}")
            return output_path

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"[MinerU Online] Failed to download ZIP: {e}")

    def _extract_zip(self, zip_path: Path, extract_to: Path, callback: Optional[Callable] = None) -> Path:
        """
        解压 ZIP 文件

        Args:
            zip_path: ZIP 文件路径
            extract_to: 解压目标目录
            callback: 进度回调函数

        Returns:
            解压后的目录路径
        """
        self.logger.info(f"[MinerU Online] Extracting ZIP: {zip_path}")
        if callback:
            callback(0.85, f"[MinerU Online] Extracting ZIP...")

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_to)

            self.logger.info(f"[MinerU Online] ZIP extracted to: {extract_to}")
            return extract_to

        except zipfile.BadZipFile as e:
            raise RuntimeError(f"[MinerU Online] Invalid ZIP file: {e}")

    def _find_content_list_json(self, extract_dir: Path) -> Path:
        """
        在解压目录中查找 _content_list.json 文件

        Args:
            extract_dir: 解压目录

        Returns:
            JSON 文件路径
        """
        # 查找所有 _content_list.json 文件
        json_files = list(extract_dir.rglob("*_content_list.json"))

        if not json_files:
            raise FileNotFoundError(
                f"[MinerU Online] No _content_list.json found in {extract_dir}"
            )

        # 通常只有一个，取第一个
        json_path = json_files[0]
        self.logger.info(f"[MinerU Online] Found content list: {json_path}")
        return json_path

    def _read_content_list(self, json_path: Path) -> list[dict[str, Any]]:
        """
        读取内容列表 JSON 文件

        Args:
            json_path: JSON 文件路径

        Returns:
            内容列表
        """
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 处理图片路径，转换为绝对路径
            base_dir = json_path.parent
            for item in data:
                for key in ("img_path", "table_img_path", "equation_img_path"):
                    if key in item and item[key]:
                        img_path = base_dir / item[key]
                        if img_path.exists():
                            item[key] = str(img_path.resolve())

            return data

        except json.JSONDecodeError as e:
            raise RuntimeError(f"[MinerU Online] Failed to parse JSON: {e}")

    def _transfer_to_sections(
        self, outputs: list[dict[str, Any]], parse_method: str = None
    ) -> list:
        """
        将 MinerU 输出转换为 sections 格式
        与本地 MinerUParser 保持一致的输出格式

        Args:
            outputs: MinerU 解析输出列表
            parse_method: 解析方法 ("manual", "paper", "raw")

        Returns:
            sections 列表
        """
        sections = []
        for output in outputs:
            content_type = output.get("type", "")

            # 根据类型提取内容
            match content_type:
                case MinerUContentType.TEXT:
                    section = output.get("text", "")
                case MinerUContentType.TABLE:
                    section = output.get("table_body", "")
                    if output.get("table_caption"):
                        section += "\n".join(output["table_caption"])
                    if output.get("table_footnote"):
                        section += "\n".join(output["table_footnote"])
                    if not section.strip():
                        section = "FAILED TO PARSE TABLE"
                case MinerUContentType.IMAGE:
                    section = ""
                    if output.get("image_caption"):
                        section += "".join(output["image_caption"])
                    if output.get("image_footnote"):
                        section += "\n" + "".join(output["image_footnote"])
                case MinerUContentType.EQUATION:
                    section = output.get("text", "")
                case MinerUContentType.CODE:
                    section = output.get("code_body", "")
                    if output.get("code_caption"):
                        section += "\n".join(output["code_caption"])
                case MinerUContentType.LIST:
                    section = "\n".join(output.get("list_items", []))
                case MinerUContentType.DISCARDED:
                    continue  # 跳过丢弃的内容
                case _:
                    section = output.get("text", "")

            # 根据 parse_method 返回不同格式
            if section and parse_method == "manual":
                sections.append((section, content_type, self._line_tag(output)))
            elif section and parse_method == "paper":
                sections.append((section + self._line_tag(output), content_type))
            else:
                sections.append((section, self._line_tag(output)))

        return sections

    def _line_tag(self, output: dict) -> str:
        """
        生成位置标签
        格式: @@page	x0	x1	y0	y1##
        """
        page_idx = output.get("page_idx", 0)
        bbox = output.get("bbox", [0, 0, 0, 0])

        # bbox 格式: [x0, y0, x1, y1] (相对于页面宽高的千分比)
        x0, y0, x1, y1 = bbox

        # 转换为像素坐标（假设 72 DPI）
        if hasattr(self, "page_images") and self.page_images and page_idx < len(self.page_images):
            page_width, page_height = self.page_images[page_idx].size
            x0 = (x0 / 1000.0) * page_width
            x1 = (x1 / 1000.0) * page_width
            y0 = (y0 / 1000.0) * page_height
            y1 = (y1 / 1000.0) * page_height

        return "@@{}\t{:.1f}\t{:.1f}\t{:.1f}\t{:.1f}##".format(
            page_idx + 1, x0, x1, y0, y1
        )

    def __images__(
        self, fnm, zoomin: int = 1, page_from: int = 0, page_to: int = 600, callback=None
    ):
        """加载 PDF 页面图像（用于位置计算）"""
        import pdfplumber

        self.page_from = page_from
        self.page_to = page_to
        try:
            with pdfplumber.open(fnm) if isinstance(fnm, (str, PathLike)) else pdfplumber.open(BytesIO(fnm)) as pdf:
                self.pdf = pdf
                self.page_images = [
                    p.to_image(resolution=72 * zoomin, antialias=True).original
                    for _, p in enumerate(pdf.pages[page_from:page_to])
                ]
                self.total_page = len(pdf.pages)
        except Exception as e:
            self.logger.warning(f"[MinerU Online] Failed to load PDF images: {e}")
            self.page_images = None
            self.total_page = 0

    def parse_pdf(
        self,
        filepath: str | PathLike[str],
        binary: Optional[BytesIO | bytes] = None,
        callback: Optional[Callable] = None,
        parse_method: str = "raw",
        **kwargs,
    ) -> tuple:
        """
        解析 PDF 文件

        Args:
            filepath: PDF 文件路径
            binary: PDF 二进制数据（可选）
            callback: 进度回调函数
            parse_method: 解析方法 ("manual", "paper", "raw")
            **kwargs: 其他参数

        Returns:
            (sections, tables) 元组
        """
        temp_pdf_path = None
        work_dir = None
        zip_path = None

        try:
            # 1. 准备 PDF 文件
            if binary:
                # 使用临时文件保存二进制数据
                temp_dir = Path(tempfile.mkdtemp(prefix="mineru_online_"))
                temp_pdf_path = temp_dir / "input.pdf"
                with open(temp_pdf_path, "wb") as f:
                    if isinstance(binary, BytesIO):
                        f.write(binary.read())
                    else:
                        f.write(binary)
                pdf_path = str(temp_pdf_path)
                self.logger.info(f"[MinerU Online] Using binary PDF: {pdf_path}")
            else:
                pdf_path = str(filepath)
                self.logger.info(f"[MinerU Online] Using file: {pdf_path}")

            # 2. 加载 PDF 图像（用于位置计算）
            self.__images__(pdf_path, zoomin=1)

            # 3. 获取文件名
            filename = Path(pdf_path).name

            # 4. 获取预签名 URL
            batch_id, presigned_url = self._get_presigned_urls(filename, callback)

            # 5. 上传文件
            self._upload_file(pdf_path, presigned_url, callback)

            # 6. 轮询获取结果
            result_data = self._poll_result(batch_id, callback)

            # 7. 获取 ZIP 下载链接
            files = result_data.get("files", [])
            if not files:
                raise RuntimeError("[MinerU Online] No result files returned")

            zip_url = files[0].get("url")
            if not zip_url:
                raise RuntimeError("[MinerU Online] No ZIP URL in result")

            # 8. 创建工作目录
            if self.temp_dir:
                work_dir = Path(self.temp_dir) / f"mineru_online_{batch_id}"
            else:
                work_dir = Path(tempfile.mkdtemp(prefix="mineru_online_"))
            work_dir.mkdir(parents=True, exist_ok=True)

            # 9. 下载 ZIP
            zip_path = work_dir / "result.zip"
            self._download_zip(zip_url, zip_path, callback)

            # 10. 解压 ZIP
            extract_dir = work_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            self._extract_zip(zip_path, extract_dir, callback)

            # 11. 查找并读取 _content_list.json
            json_path = self._find_content_list_json(extract_dir)
            outputs = self._read_content_list(json_path)

            self.logger.info(f"[MinerU Online] Parsed {len(outputs)} blocks from PDF")
            if callback:
                callback(0.95, f"[MinerU Online] Parsed {len(outputs)} blocks")

            # 12. 转换为 sections
            sections = self._transfer_to_sections(outputs, parse_method)
            tables = []  # MinerU 的表格已包含在 sections 中

            return sections, tables

        finally:
            # 清理临时文件
            if temp_pdf_path and temp_pdf_path.exists():
                try:
                    shutil.rmtree(temp_pdf_path.parent)
                except Exception:
                    pass

            # 根据配置决定是否保留工作目录
            delete_output = kwargs.get("delete_output", True)
            if delete_output and work_dir and work_dir.exists():
                try:
                    shutil.rmtree(work_dir)
                    self.logger.info(f"[MinerU Online] Cleaned up work dir: {work_dir}")
                except Exception:
                    pass

    @staticmethod
    def extract_positions(txt: str):
        """从文本中提取位置信息"""
        import re

        poss = []
        for tag in re.findall(r"@@[0-9-]+\t[0-9.\t]+##", txt):
            pn, left, right, top, bottom = tag.strip("#").strip("@").split("\t")
            left, right, top, bottom = float(left), float(right), float(top), float(bottom)
            poss.append(([int(p) - 1 for p in pn.split("-")], left, right, top, bottom))
        return poss


if __name__ == "__main__":
    # 测试代码
    parser = MinerUOnlineParser(
        token="your-token-here",
        temp_dir="D:/temp/mineru_online",
    )

    ok, reason = parser.check_available()
    print(f"Available: {ok}, Reason: {reason}")
