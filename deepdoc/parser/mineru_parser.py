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
import re
import shutil
import sys
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from io import BytesIO
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pdfplumber
import requests
from PIL import Image
from strenum import StrEnum

from deepdoc.parser.pdf_parser import RAGFlowPdfParser
from deepdoc.parser.mineru_saas_client import MinerUSaaSClient

LOCK_KEY_pdfplumber = "global_shared_lock_pdfplumber"
if LOCK_KEY_pdfplumber not in sys.modules:
    sys.modules[LOCK_KEY_pdfplumber] = threading.Lock()


class MinerUContentType(StrEnum):
    IMAGE = "image"
    TABLE = "table"
    TEXT = "text"
    EQUATION = "equation"
    CODE = "code"
    LIST = "list"
    DISCARDED = "discarded"


# Mapping from language names to MinerU language codes
LANGUAGE_TO_MINERU_MAP = {
    'English': 'en',
    'Chinese': 'ch',
    'Traditional Chinese': 'chinese_cht',
    'Russian': 'east_slavic',
    'Ukrainian': 'east_slavic',
    'Indonesian': 'latin',
    'Spanish': 'latin',
    'Vietnamese': 'latin',
    'Japanese': 'japan',
    'Korean': 'korean',
    'Portuguese BR': 'latin',
    'German': 'latin',
    'French': 'latin',
    'Italian': 'latin',
    'Tamil': 'ta',
    'Telugu': 'te',
    'Kannada': 'ka',
    'Thai': 'th',
    'Greek': 'el',
    'Hindi': 'devanagari',
}


class MinerUBackend(StrEnum):
    """MinerU processing backend options."""

    PIPELINE = "pipeline"  # Traditional multimodel pipeline (default)
    VLM_TRANSFORMERS = "vlm-transformers"  # Vision-language model using HuggingFace Transformers
    VLM_MLX_ENGINE = "vlm-mlx-engine"  # Faster, requires Apple Silicon and macOS 13.5+
    VLM_VLLM_ENGINE = "vlm-vllm-engine"  # Local vLLM engine, requires local GPU
    VLM_VLLM_ASYNC_ENGINE = "vlm-vllm-async-engine"  # Asynchronous vLLM engine, new in MinerU API
    VLM_LMDEPLOY_ENGINE = "vlm-lmdeploy-engine"  # LMDeploy engine
    VLM_HTTP_CLIENT = "vlm-http-client"  # HTTP client for remote vLLM server (CPU only)


class MinerULanguage(StrEnum):
    """MinerU supported languages for OCR (pipeline backend only)."""

    CH = "ch"  # Chinese
    CH_SERVER = "ch_server"  # Chinese (server)
    CH_LITE = "ch_lite"  # Chinese (lite)
    EN = "en"  # English
    KOREAN = "korean"  # Korean
    JAPAN = "japan"  # Japanese
    CHINESE_CHT = "chinese_cht"  # Chinese Traditional
    TA = "ta"  # Tamil
    TE = "te"  # Telugu
    KA = "ka"  # Kannada
    TH = "th"  # Thai
    EL = "el"  # Greek
    LATIN = "latin"  # Latin
    ARABIC = "arabic"  # Arabic
    EAST_SLAVIC = "east_slavic"  # East Slavic
    CYRILLIC = "cyrillic"  # Cyrillic
    DEVANAGARI = "devanagari"  # Devanagari


class MinerUParseMethod(StrEnum):
    """MinerU PDF parsing methods (pipeline backend only)."""

    AUTO = "auto"  # Automatically determine the method based on the file type
    TXT = "txt"  # Use text extraction method
    OCR = "ocr"  # Use OCR method for image-based PDFs


@dataclass
class MinerUParseOptions:
    """Options for MinerU PDF parsing."""

    backend: MinerUBackend = MinerUBackend.PIPELINE
    lang: Optional[MinerULanguage] = None  # language for OCR (pipeline backend only)
    method: MinerUParseMethod = MinerUParseMethod.AUTO
    server_url: Optional[str] = None
    delete_output: bool = True
    parse_method: str = "raw"
    formula_enable: bool = True
    table_enable: bool = True


class MinerUParser(RAGFlowPdfParser):
    def __init__(self, mineru_path: str = "mineru", mineru_api: str = "", mineru_server_url: str = "", mineru_token: str = "", model_version: str = "vlm"):
        self.mineru_api = mineru_api.rstrip("/")
        self.mineru_server_url = mineru_server_url.rstrip("/")
        self.mineru_token = mineru_token
        self.model_version = model_version
        self.outlines = []
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _is_zipinfo_symlink(member: zipfile.ZipInfo) -> bool:
        return (member.external_attr >> 16) & 0o170000 == 0o120000

    def _extract_zip_no_root(self, zip_path, extract_to, root_dir):
        self.logger.info(f"[MinerU] Extract zip: zip_path={zip_path}, extract_to={extract_to}, root_hint={root_dir}")
        base_dir = Path(extract_to).resolve()
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            members = zip_ref.infolist()
            if not root_dir:
                if members and members[0].filename.endswith("/"):
                    root_dir = members[0].filename
                else:
                    root_dir = None
            if root_dir:
                root_dir = root_dir.replace("\\", "/")
                if not root_dir.endswith("/"):
                    root_dir += "/"

            for member in members:
                if member.flag_bits & 0x1:
                    raise RuntimeError(f"[MinerU] Encrypted zip entry not supported: {member.filename}")
                if self._is_zipinfo_symlink(member):
                    raise RuntimeError(f"[MinerU] Symlink zip entry not supported: {member.filename}")

                name = member.filename.replace("\\", "/")
                if root_dir and name == root_dir:
                    self.logger.info("[MinerU] Ignore root folder...")
                    continue
                if root_dir and name.startswith(root_dir):
                    name = name[len(root_dir) :]
                if not name:
                    continue
                if name.startswith("/") or name.startswith("//") or re.match(r"^[A-Za-z]:", name):
                    raise RuntimeError(f"[MinerU] Unsafe zip path (absolute): {member.filename}")

                parts = [p for p in name.split("/") if p not in ("", ".")]
                if any(p == ".." for p in parts):
                    raise RuntimeError(f"[MinerU] Unsafe zip path (traversal): {member.filename}")

                rel_path = os.path.join(*parts) if parts else ""
                dest_path = (Path(extract_to) / rel_path).resolve(strict=False)
                if dest_path != base_dir and base_dir not in dest_path.parents:
                    raise RuntimeError(f"[MinerU] Unsafe zip path (escape): {member.filename}")

                if member.is_dir():
                    os.makedirs(dest_path, exist_ok=True)
                    continue

                os.makedirs(dest_path.parent, exist_ok=True)
                with zip_ref.open(member) as src, open(dest_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    @staticmethod
    def _is_http_endpoint_valid(url, timeout=5):
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code in [200, 301, 302, 307, 308]
        except Exception:
            return False

    def check_installation(self, backend: str = "pipeline", server_url: Optional[str] = None) -> tuple[bool, str]:
        # If token is provided, we assume SaaS mode and skip local/self-hosted checks
        if self.mineru_token:
             return True, ""

        reason = ""

        valid_backends = ["pipeline", "vlm-http-client", "vlm-transformers", "vlm-vllm-engine", "vlm-mlx-engine", "vlm-vllm-async-engine", "vlm-lmdeploy-engine"]
        if backend not in valid_backends:
            reason = f"[MinerU] Invalid backend '{backend}'. Valid backends are: {valid_backends}"
            self.logger.warning(reason)
            return False, reason

        if not self.mineru_api:
            reason = "[MinerU] MINERU_APISERVER not configured."
            self.logger.warning(reason)
            return False, reason

        api_openapi = f"{self.mineru_api}/openapi.json"
        try:
            api_ok = self._is_http_endpoint_valid(api_openapi)
            self.logger.info(f"[MinerU] API openapi.json reachable={api_ok} url={api_openapi}")
            if not api_ok:
                reason = f"[MinerU] MinerU API not accessible: {api_openapi}"
                return False, reason
        except Exception as exc:
            reason = f"[MinerU] MinerU API check failed: {exc}"
            self.logger.warning(reason)
            return False, reason

        if backend == "vlm-http-client":
            resolved_server = server_url or self.mineru_server_url
            if not resolved_server:
                reason = "[MinerU] MINERU_SERVER_URL required for vlm-http-client backend."
                self.logger.warning(reason)
                return False, reason
            try:
                server_ok = self._is_http_endpoint_valid(resolved_server)
                self.logger.info(f"[MinerU] vlm-http-client server check reachable={server_ok} url={resolved_server}")
            except Exception as exc:
                self.logger.warning(f"[MinerU] vlm-http-client server probe failed: {resolved_server}: {exc}")

        return True, reason

    def _run_mineru(
        self, input_path: Path, output_dir: Path, options: MinerUParseOptions, callback: Optional[Callable] = None
    ) -> Path:
        return self._run_mineru_api(input_path, output_dir, options, callback)

    def _run_mineru_api(
        self, input_path: Path, output_dir: Path, options: MinerUParseOptions, callback: Optional[Callable] = None
    ) -> Path:
        if self.mineru_token:
            return self._run_mineru_saas(input_path, output_dir, options, callback)

        pdf_file_path = str(input_path)

        if not os.path.exists(pdf_file_path):
            raise RuntimeError(f"[MinerU] PDF file not exists: {pdf_file_path}")

        pdf_file_name = Path(pdf_file_path).stem.strip()
        output_path = tempfile.mkdtemp(prefix=f"{pdf_file_name}_{options.method}_", dir=str(output_dir))
        output_zip_path = os.path.join(str(output_dir), f"{Path(output_path).name}.zip")

        data = {
            "output_dir": "./output",
            "lang_list": options.lang,
            "backend": options.backend,
            "parse_method": options.method,
            "formula_enable": options.formula_enable,
            "table_enable": options.table_enable,
            "server_url": None,
            "return_md": True,
            "return_middle_json": True,
            "return_model_output": True,
            "return_content_list": True,
            "return_images": True,
            "response_format_zip": True,
            "start_page_id": 0,
            "end_page_id": 99999,
        }

        if options.server_url:
            data["server_url"] = options.server_url
        elif self.mineru_server_url:
            data["server_url"] = self.mineru_server_url

        self.logger.info(f"[MinerU] request {data=}")
        self.logger.info(f"[MinerU] request {options=}")

        headers = {"Accept": "application/json"}
        try:
            self.logger.info(f"[MinerU] invoke api: {self.mineru_api}/file_parse backend={options.backend} server_url={data.get('server_url')}")
            if callback:
                callback(0.20, f"[MinerU] invoke api: {self.mineru_api}/file_parse")
            with open(pdf_file_path, "rb") as pdf_file:
                files = {"files": (pdf_file_name + ".pdf", pdf_file, "application/pdf")}
                with requests.post(
                    url=f"{self.mineru_api}/file_parse",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=1800,
                    stream=True,
                ) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "")
                    if content_type.startswith("application/zip"):
                        self.logger.info(f"[MinerU] zip file returned, saving to {output_zip_path}...")

                        if callback:
                            callback(0.30, f"[MinerU] zip file returned, saving to {output_zip_path}...")

                        with open(output_zip_path, "wb") as f:
                            response.raw.decode_content = True
                            shutil.copyfileobj(response.raw, f)

                        self.logger.info(f"[MinerU] Unzip to {output_path}...")
                        self._extract_zip_no_root(output_zip_path, output_path, pdf_file_name + "/")

                        if callback:
                            callback(0.40, f"[MinerU] Unzip to {output_path}...")
                    else:
                        self.logger.warning(f"[MinerU] not zip returned from api: {content_type}")
        except Exception as e:
            raise RuntimeError(f"[MinerU] api failed with exception {e}")
        self.logger.info("[MinerU] Api completed successfully.")
        return Path(output_path)

    def _run_mineru_saas(
        self, input_path: Path, output_dir: Path, options: MinerUParseOptions, callback: Optional[Callable] = None
    ) -> Path:
        pdf_file_path = str(input_path)
        if not os.path.exists(pdf_file_path):
            raise RuntimeError(f"[MinerU SaaS] PDF file not exists: {pdf_file_path}")

        pdf_file_name = Path(pdf_file_path).stem.strip()
        
        self.logger.info(f"[MinerU SaaS] Starting SaaS processing for {pdf_file_path}")
        if callback:
            callback(0.20, f"[MinerU SaaS] Starting upload...")

        try:
            client = MinerUSaaSClient(self.mineru_token, self.model_version)
            batch_id = client.upload(pdf_file_path)
            
            if callback:
                 callback(0.40, f"[MinerU SaaS] Uploaded. Batch ID: {batch_id}. Waiting for result...")
            
            # Use batch_id to create a stable, reusable output directory
            # Sanitize filename for path safety
            safe_name = "".join([c for c in pdf_file_name if c.isalnum() or c in (' ', '.', '-', '_')]).strip()
            final_output_path = output_dir / f"{safe_name}_{batch_id}"
            marker_file = final_output_path / "_completed"
            lock_file = final_output_path / "_lock"

            # Always verify status with server first, as requested
            self.logger.info(f"[MinerU SaaS] Polling for results (batch_id={batch_id})...")
            download_url = client.poll_until_done(batch_id)
            self.logger.info(f"[MinerU SaaS] Download URL obtained: {download_url}")

            # Check if already processed LOCALLY after server confirms it's DONE
            if final_output_path.exists() and marker_file.exists():
                self.logger.info(f"[MinerU SaaS] Found cached result in {final_output_path}, reusing.")
                if callback:
                    callback(0.90, f"[MinerU SaaS] Using cached result.")
                return final_output_path

            # Ensure directory exists
            os.makedirs(final_output_path, exist_ok=True)

            # Simple file lock mechanism to prevent race conditions among parallel workers
            import time
            lock_acquired = False
            try:
                # Try to acquire lock
                start_lock_wait = time.time()
                while time.time() - start_lock_wait < 600: # Wait up to 10 mins for other task to finish download
                    try:
                        # Open for exclusive creation
                        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        os.close(fd)
                        lock_acquired = True
                        break
                    except FileExistsError:
                        # Check recursively if done while waiting
                        if marker_file.exists():
                            self.logger.info(f"[MinerU SaaS] Another task completed download in {final_output_path}, reusing.")
                            return final_output_path
                        time.sleep(1)
                
                if not lock_acquired:
                    self.logger.warning(f"[MinerU SaaS] Could not acquire lock for {final_output_path}, proceeding potentially unsafe.")

                # Proceed with download (Critical Section)
                if callback:
                    callback(0.80, f"[MinerU SaaS] Downloading result...")

                output_zip_path = final_output_path / f"output.zip"

                # Download ZIP
                with requests.get(download_url, stream=True) as r:
                    r.raise_for_status()
                    with open(output_zip_path, 'wb') as f:
                        shutil.copyfileobj(r.raw, f)

                self.logger.info(f"[MinerU SaaS] Unzip to {final_output_path}...")
                self._extract_zip_no_root(output_zip_path, final_output_path, pdf_file_name + "/")
                
                # Create marker file
                with open(marker_file, 'w') as f:
                    f.write("done")

            finally:
                if lock_acquired and lock_file.exists():
                    try:
                        os.remove(lock_file)
                    except Exception:
                        pass


        except Exception as e:
             self.logger.error(f"[MinerU SaaS] processing failed: {e}")
             raise RuntimeError(f"[MinerU SaaS] processing failed: {e}")

        return Path(final_output_path)

    def __images__(self, fnm, zoomin: int = 1, page_from=0, page_to=600, callback=None):
        self.page_from = page_from
        self.page_to = page_to
        try:
            with pdfplumber.open(fnm) if isinstance(fnm, (str, PathLike)) else pdfplumber.open(BytesIO(fnm)) as pdf:
                self.pdf = pdf
                self.page_images = [p.to_image(resolution=72 * zoomin, antialias=True).original for _, p in
                                    enumerate(self.pdf.pages[page_from:page_to])]
        except Exception as e:
            self.page_images = None
            self.total_page = 0
            self.logger.exception(e)

    def _line_tag(self, bx):
        pn = [bx["page_idx"] + 1]
        positions = bx.get("bbox", (0, 0, 0, 0))
        x0, top, x1, bott = positions

        if hasattr(self, "page_images") and self.page_images:
            idx = bx["page_idx"] - getattr(self, "page_from", 0)
            if 0 <= idx < len(self.page_images):
                page_width, page_height = self.page_images[idx].size
                x0 = (x0 / 1000.0) * page_width
                x1 = (x1 / 1000.0) * page_width
                top = (top / 1000.0) * page_height
                bott = (bott / 1000.0) * page_height

        return "@@{}\t{:.1f}\t{:.1f}\t{:.1f}\t{:.1f}##".format("-".join([str(p) for p in pn]), x0, x1, top, bott)

    def crop(self, text, ZM=1, need_position=False):
        imgs = []
        poss = self.extract_positions(text)
        if not poss:
            if need_position:
                return None, None
            return

        if not getattr(self, "page_images", None):
            self.logger.warning("[MinerU] crop called without page images; skipping image generation.")
            if need_position:
                return None, None
            return

        page_from = getattr(self, "page_from", 0)
        page_count = len(self.page_images)

        filtered_poss = []
        for pns, left, right, top, bottom in poss:
            if not pns:
                self.logger.warning("[MinerU] Empty page index list in crop; skipping this position.")
                continue
            # Convert absolute page numbers to relative indices
            rel_pns = [p - page_from for p in pns]
            valid_rel_pns = [p for p in rel_pns if 0 <= p < page_count]
            if not valid_rel_pns:
                # self.logger.warning(f"[MinerU] All page indices {pns} (rel {rel_pns}) out of range for {page_count} images (offset {page_from}); skipping.")
                continue
            
            # Use original pns for checking if they are contiguous? No, we just need valid relative indices to crop from images.
            # But the logic uses pns to check continuity? 
            # Logic below uses pns[0] etc.
            # We strictly need to use relative indices for image access.
            filtered_poss.append((valid_rel_pns, left, right, top, bottom))

        poss = filtered_poss
        if not poss:
            # self.logger.warning("[MinerU] No valid positions after filtering; skip cropping.")
            if need_position:
                return None, None
            return

        max_width = max(np.max([right - left for (_, left, right, _, _) in poss]), 6)
        GAP = 6
        pos = poss[0]
        # pos[0] is valid_rel_pns
        first_page_idx = pos[0][0]
        poss.insert(0, ([first_page_idx], pos[1], pos[2], max(0, pos[3] - 120), max(pos[3] - GAP, 0)))
        pos = poss[-1]
        last_page_idx = pos[0][-1]
        if not (0 <= last_page_idx < page_count):
            self.logger.warning(
                f"[MinerU] Last page index {last_page_idx} out of range for {page_count} pages; skipping crop.")
            if need_position:
                return None, None
            return
        last_page_height = self.page_images[last_page_idx].size[1]
        poss.append(
            (
                [last_page_idx],
                pos[1],
                pos[2],
                min(last_page_height, pos[4] + GAP),
                min(last_page_height, pos[4] + 120),
            )
        )

        positions = []
        for ii, (pns, left, right, top, bottom) in enumerate(poss):
            right = left + max_width

            # Ensure bottom > top
            if bottom <= top:
                self.logger.warning(f"[MinerU][crop] Position {ii}: bottom({bottom}) <= top({top}), adjusting bottom to top + 2")
                bottom = top + 2

            for pn in pns[1:]:
                # pn is relative
                if 0 <= pn - 1 < page_count:
                    bottom += self.page_images[pn - 1].size[1]
                else:
                    self.logger.warning(
                        f"[MinerU] Page index {pn}-1 out of range for {page_count} pages during crop; skipping height accumulation.")

            if not (0 <= pns[0] < page_count):
                self.logger.warning(
                    f"[MinerU] Base page index {pns[0]} out of range for {page_count} pages during crop; skipping this segment.")
                continue

            img0 = self.page_images[pns[0]]
            
            # Ensure coordinates are valid for cropping
            x0, y0, x1, y1 = int(left), int(top), int(right), int(min(bottom, img0.size[1]))
            
            # Double-check coordinates before cropping
            if y1 <= y0:
                self.logger.warning(f"[MinerU][crop] Position {ii}: y1({y1}) <= y0({y0}), adjusting y1 to y0 + 2")
                y1 = y0 + 2
            if x1 <= x0:
                self.logger.warning(f"[MinerU][crop] Position {ii}: x1({x1}) <= x0({x0}), adjusting x1 to x0 + 2")
                x1 = x0 + 2
            
            # Ensure coordinates are within image bounds
            y1 = min(y1, img0.size[1])
            x1 = min(x1, img0.size[0])
            
            self.logger.info(f"[MinerU][crop] Position {ii}: cropping with coords ({x0}, {y0}, {x1}, {y1}), img_size={img0.size}")
            
            try:
                crop0 = img0.crop((x0, y0, x1, y1))
                imgs.append(crop0)
                if 0 < ii < len(poss) - 1:
                    positions.append((pns[0] + page_from, x0, x1, y0, y1))
            except ValueError as e:
                self.logger.error(f"[MinerU][crop] Position {ii}: crop failed with coords ({x0}, {y0}, {x1}, {y1}): {e}")
                continue

            bottom -= img0.size[1]
            for pn in pns[1:]:
                if not (0 <= pn < page_count):
                    self.logger.warning(
                        f"[MinerU] Page index {pn} out of range for {page_count} pages during crop; skipping this page.")
                    continue
                page = self.page_images[pn]
                
                # Ensure coordinates are valid
                x0, y0, x1, y1 = int(left), 0, int(right), int(min(bottom, page.size[1]))
                if y1 <= y0:
                    y1 = y0 + 2
                if x1 <= x0:
                    x1 = x0 + 2
                y1 = min(y1, page.size[1])
                x1 = min(x1, page.size[0])
                
                try:
                    cimgp = page.crop((x0, y0, x1, y1))
                    imgs.append(cimgp)
                    if 0 < ii < len(poss) - 1:
                        positions.append((pn + page_from, x0, x1, y0, y1))
                except ValueError as e:
                    self.logger.error(f"[MinerU][crop] Page {pn}: crop failed with coords ({x0}, {y0}, {x1}, {y1}): {e}")
                    continue
                bottom -= page.size[1]

        if not imgs:
            if need_position:
                return None, None
            return

        height = 0
        for img in imgs:
            height += img.size[1] + GAP
        height = int(height)
        width = int(np.max([i.size[0] for i in imgs]))
        pic = Image.new("RGB", (width, height), (245, 245, 245))
        height = 0
        for ii, img in enumerate(imgs):
            if ii == 0 or ii + 1 == len(imgs):
                img = img.convert("RGBA")
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                overlay.putalpha(128)
                img = Image.alpha_composite(img, overlay).convert("RGB")
            pic.paste(img, (0, int(height)))
            height += img.size[1] + GAP

        if need_position:
            return pic, positions
        return pic

    @staticmethod
    def extract_positions(txt: str):
        poss = []
        for tag in re.findall(r"@@[0-9-]+\t[0-9.\t]+##", txt):
            pn, left, right, top, bottom = tag.strip("#").strip("@").split("\t")
            left, right, top, bottom = float(left), float(right), float(top), float(bottom)
            poss.append(([int(p) - 1 for p in pn.split("-")], left, right, top, bottom))
        return poss

    def _read_output(self, output_dir: Path, file_stem: str, method: str = "auto", backend: str = "pipeline") -> list[
        dict[str, Any]]:
        json_file = None
        subdir = None
        attempted = []

        # mirror MinerU's sanitize_filename to align ZIP naming
        def _sanitize_filename(name: str) -> str:
            sanitized = re.sub(r"[/\\\.]{2,}|[/\\]", "", name)
            sanitized = re.sub(r"[^\w.-]", "_", sanitized, flags=re.UNICODE)
            if sanitized.startswith("."):
                sanitized = "_" + sanitized[1:]
            return sanitized or "unnamed"

        safe_stem = _sanitize_filename(file_stem)
        allowed_names = {f"{file_stem}_content_list.json", f"{safe_stem}_content_list.json"}
        self.logger.info(f"[MinerU] Expected output files: {', '.join(sorted(allowed_names))}")
        self.logger.info(f"[MinerU] Searching output in: {output_dir}")

        jf = output_dir / f"{file_stem}_content_list.json"
        self.logger.info(f"[MinerU] Trying original path: {jf}")
        attempted.append(jf)
        if jf.exists():
            subdir = output_dir
            json_file = jf
        else:
            alt = output_dir / f"{safe_stem}_content_list.json"
            self.logger.info(f"[MinerU] Trying sanitized filename: {alt}")
            attempted.append(alt)
            if alt.exists():
                subdir = output_dir
                json_file = alt
            else:
                nested_alt = output_dir / safe_stem / f"{safe_stem}_content_list.json"
                self.logger.info(f"[MinerU] Trying sanitized nested path: {nested_alt}")
                attempted.append(nested_alt)
                if nested_alt.exists():
                    subdir = nested_alt.parent
                    json_file = nested_alt

        if not json_file:
            self.logger.info(f"[MinerU] Specific file not found. Searching recursively in {output_dir}...")
            found_files = []
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    full_path = Path(root) / file
                    found_files.append(str(full_path))
                    if file.endswith("_content_list.json"):
                        # Use the first one found if we haven't found one yet
                        # We prefer the one that might match the stem, but if we are here, we failed to find exact matches.
                        # So just taking the first valid content list is a reasonable fallback.
                        if not json_file:
                             json_file = full_path
                             subdir = Path(root)
                             self.logger.info(f"[MinerU] Found fallback JSON: {json_file}")
            
            self.logger.info(f"[MinerU] All files found in output: {found_files}")

        if not json_file:
            raise FileNotFoundError(f"[MinerU] Missing output file, tried: {', '.join(str(p) for p in attempted)}. All files found: {found_files}")

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            # Compatibility fix: ensure 'bbox' exists, map from 'layout_bbox' if needed
            if "bbox" not in item and "layout_bbox" in item:
                item["bbox"] = item["layout_bbox"]
            
            # Ensure page_idx is present (some older versions might use 'page_id'?)
            if "page_idx" not in item and "page_id" in item:
                item["page_idx"] = item["page_id"]

            for key in ("img_path", "table_img_path", "equation_img_path"):
                if key in item and item[key]:
                    item[key] = str((subdir / item[key]).resolve())
        return data

    def _transfer_to_sections(self, outputs: list[dict[str, Any]], parse_method: str = None):
        """
        Transfer MinerU outputs to sections.
        
        For 'manual' parse_method:
        - Groups content by text_level, using level 1 as section boundaries
        - Returns list of (text, level, poss) tuples where level is the text_level
        
        For 'paper' parse_method:
        - Returns list of (text + position_tag, type) tuples
        
        For other parse_methods:
        - Returns list of (text, position_tag) tuples
        """
        sections = []
        
        if parse_method == "manual":
            # Group content by text_level, using level 1 as section boundaries
            current_section_text = []
            current_section_level = 0
            current_section_poss = []
            section_count = 0
            
            self.logger.info(f"[MinerU][_transfer_to_sections] Starting with {len(outputs)} outputs for manual parsing")
            
            for idx, output in enumerate(outputs):
                output_type = output.get("type")
                text_level = output.get("text_level", 0)
                
                # Skip discarded blocks
                if output_type == MinerUContentType.DISCARDED:
                    continue
                
                # Extract text content based on type
                match output_type:
                    case MinerUContentType.TEXT:
                        text = output.get("text", "")
                    case MinerUContentType.TABLE:
                        text = output.get("table_body", "") + "\n".join(output.get("table_caption", [])) + "\n".join(
                            output.get("table_footnote", []))
                        if not text.strip():
                            text = "FAILED TO PARSE TABLE"
                    case MinerUContentType.IMAGE:
                        text = "".join(output.get("image_caption", [])) + "\n" + "".join(
                            output.get("image_footnote", []))
                    case MinerUContentType.EQUATION:
                        text = output.get("text", "")
                    case MinerUContentType.CODE:
                        text = output.get("code_body", "") + "\n".join(output.get("code_caption", []))
                    case MinerUContentType.LIST:
                        text = "\n".join(output.get("list_items", []))
                    case _:
                        text = ""
                
                if not text.strip():
                    continue
                
                # Get position info
                page_idx = output.get("page_idx", 0)
                positions = output.get("bbox", (0, 0, 0, 0))
                x0, top, x1, bott = positions
                
                # Convert coordinates from normalized (0-1000) to actual pixel coordinates
                # Similar to _line_tag method
                if hasattr(self, "page_images") and self.page_images:
                    idx = page_idx - getattr(self, "page_from", 0)
                    if 0 <= idx < len(self.page_images):
                        page_width, page_height = self.page_images[idx].size
                        x0 = (x0 / 1000.0) * page_width
                        x1 = (x1 / 1000.0) * page_width
                        top = (top / 1000.0) * page_height
                        bott = (bott / 1000.0) * page_height
                        self.logger.info(f"[MinerU][_transfer_to_sections] Converted coords for page {page_idx}: ({x0:.1f}, {top:.1f}, {x1:.1f}, {bott:.1f}), page_size=({page_width}, {page_height})")
                    else:
                        self.logger.warning(f"[MinerU][_transfer_to_sections] Page index {page_idx} out of range for {len(self.page_images)} images, using raw coords")
                else:
                    self.logger.warning(f"[MinerU][_transfer_to_sections] No page images available, using raw coords")
                
                poss = ([page_idx], float(x0), float(x1), float(top), float(bott))
                
                # If this is a level 1 text (title/heading), start a new section
                if text_level == 1:
                    # Save previous section if exists
                    if current_section_text:
                        section_text = "\n".join(current_section_text)
                        sections.append((section_text, current_section_level, current_section_poss))
                        section_count += 1
                        self.logger.info(f"[MinerU] Section {section_count}: level={current_section_level}, text_length={len(section_text)}, blocks={len(current_section_text)}")
                    
                    # Start new section with this level 1 text
                    current_section_text = [text]
                    current_section_level = text_level
                    current_section_poss = [poss]
                else:
                    # Add to current section
                    current_section_text.append(text)
                    current_section_poss.append(poss)
                    # Keep the highest level (lowest number) as the section level
                    if text_level > 0 and (current_section_level == 0 or text_level < current_section_level):
                        current_section_level = text_level
            
            # Don't forget the last section
            if current_section_text:
                section_text = "\n".join(current_section_text)
                sections.append((section_text, current_section_level, current_section_poss))
                section_count += 1
                self.logger.info(f"[MinerU] Section {section_count}: level={current_section_level}, text_length={len(section_text)}, blocks={len(current_section_text)}")
            
            self.logger.info(f"[MinerU][_transfer_to_sections] Created {len(sections)} sections from {len(outputs)} outputs")
            
        elif parse_method == "paper":
            # Original paper parsing logic
            for output in outputs:
                match output["type"]:
                    case MinerUContentType.TEXT:
                        section = output.get("text", "")
                    case MinerUContentType.TABLE:
                        section = output.get("table_body", "") + "\n".join(output.get("table_caption", [])) + "\n".join(
                            output.get("table_footnote", []))
                        if not section.strip():
                            section = "FAILED TO PARSE TABLE"
                    case MinerUContentType.IMAGE:
                        section = "".join(output.get("image_caption", [])) + "\n" + "".join(
                            output.get("image_footnote", []))
                    case MinerUContentType.EQUATION:
                        section = output.get("text", "")
                    case MinerUContentType.CODE:
                        section = output.get("code_body", "") + "\n".join(output.get("code_caption", []))
                    case MinerUContentType.LIST:
                        section = "\n".join(output.get("list_items", []))
                    case MinerUContentType.DISCARDED:
                        continue
                
                if section:
                    sections.append((section + self._line_tag(output), output["type"]))
        else:
            # Original default parsing logic
            for output in outputs:
                match output["type"]:
                    case MinerUContentType.TEXT:
                        section = output.get("text", "")
                    case MinerUContentType.TABLE:
                        section = output.get("table_body", "") + "\n".join(output.get("table_caption", [])) + "\n".join(
                            output.get("table_footnote", []))
                        if not section.strip():
                            section = "FAILED TO PARSE TABLE"
                    case MinerUContentType.IMAGE:
                        section = "".join(output.get("image_caption", [])) + "\n" + "".join(
                            output.get("image_footnote", []))
                    case MinerUContentType.EQUATION:
                        section = output.get("text", "")
                    case MinerUContentType.CODE:
                        section = output.get("code_body", "") + "\n".join(output.get("code_caption", []))
                    case MinerUContentType.LIST:
                        section = "\n".join(output.get("list_items", []))
                    case MinerUContentType.DISCARDED:
                        continue
                
                if section:
                    sections.append((section, self._line_tag(output)))
        
        return sections

    def _transfer_to_tables(self, outputs: list[dict[str, Any]]):
        tables = []
        table_count = 0
        self.logger.info(f"[MinerU][_transfer_to_tables] Starting with {len(outputs)} outputs")
        for output in outputs:
            if output.get("type") == MinerUContentType.TABLE:
                table_count += 1
                table_body = output.get("table_body", "")
                table_caption = "\n".join(output.get("table_caption", []))
                table_footnote = "\n".join(output.get("table_footnote", []))
                
                if not table_body.strip():
                    table_body = "FAILED TO PARSE TABLE"
                
                full_table = table_body
                if table_caption:
                    full_table = table_caption + "\n" + full_table
                if table_footnote:
                    full_table = full_table + "\n" + table_footnote
                
                img_path = output.get("img_path", "")
                
                # Build position tuple directly (pn_list, left, right, top, bottom)
                positions = output.get("bbox", (0, 0, 0, 0))
                x0, top, x1, bott = positions
                page_idx = output.get("page_idx", 0)
                
                # Convert to the format expected by manual.py: [(pn_list, left, right, top, bottom), ...]
                # where pn_list is [page_idx] (0-indexed)
                poss = [([page_idx], float(x0), float(x1), float(top), float(bott))]
                
                tables.append(((img_path, full_table), poss))
                self.logger.info(f"[MinerU] Extracted table {table_count}: caption='{table_caption[:50] if table_caption else 'N/A'}', body_length={len(table_body)}, img_path={img_path}")
                self.logger.info(f"[MinerU] Table {table_count} poss format: {poss}")
        self.logger.info(f"[MinerU] Total tables extracted: {table_count}, returning {len(tables)} tables")
        return tables

    def parse_pdf(
            self,
            filepath: str | PathLike[str],
            binary: BytesIO | bytes,
            callback: Optional[Callable] = None,
            *,
            output_dir: Optional[str] = None,
            backend: str = "pipeline",
            server_url: Optional[str] = None,
            delete_output: bool = True,
            parse_method: str = "raw",
            **kwargs,
    ) -> tuple:
        import shutil

        temp_pdf = None
        created_tmp_dir = False

        parser_cfg = kwargs.get('parser_config', {})
        lang = parser_cfg.get('mineru_lang') or kwargs.get('lang', 'English')
        mineru_lang_code = LANGUAGE_TO_MINERU_MAP.get(lang, 'ch')  # Defaults to Chinese if not matched
        mineru_method_raw_str = parser_cfg.get('mineru_parse_method', 'auto')
        enable_formula = parser_cfg.get('mineru_formula_enable', True)
        enable_table = parser_cfg.get('mineru_table_enable', True)

        # remove spaces, or mineru crash, and _read_output fail too
        file_path = Path(filepath)
        pdf_file_name = file_path.stem.replace(" ", "") + ".pdf"
        pdf_file_path_valid = os.path.join(file_path.parent, pdf_file_name)

        if binary:
            temp_dir = Path(tempfile.mkdtemp(prefix="mineru_bin_pdf_"))
            temp_pdf = temp_dir / pdf_file_name
            with open(temp_pdf, "wb") as f:
                f.write(binary)
            pdf = temp_pdf
            self.logger.info(f"[MinerU] Received binary PDF -> {temp_pdf}")
            if callback:
                callback(0.15, f"[MinerU] Received binary PDF -> {temp_pdf}")
        else:
            if pdf_file_path_valid != filepath:
                self.logger.info(f"[MinerU] Remove all space in file name: {pdf_file_path_valid}")
                shutil.move(filepath, pdf_file_path_valid)
            pdf = Path(pdf_file_path_valid)
            if not pdf.exists():
                if callback:
                    callback(-1, f"[MinerU] PDF not found: {pdf}")
                raise FileNotFoundError(f"[MinerU] PDF not found: {pdf}")

        if output_dir:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = Path(tempfile.mkdtemp(prefix="mineru_pdf_"))
            created_tmp_dir = True

        from_page = kwargs.get("from_page", 0)
        to_page = kwargs.get("to_page", 100000)

        self.logger.info(f"[MinerU] Output directory: {out_dir} backend={backend} api={self.mineru_api} server_url={server_url or self.mineru_server_url}")
        if callback:
            callback(0.15, f"[MinerU] Output directory: {out_dir}")

        self.__images__(pdf, zoomin=1, page_from=from_page, page_to=to_page)

        try:
            options = MinerUParseOptions(
                backend=MinerUBackend(backend),
                lang=MinerULanguage(mineru_lang_code),
                method=MinerUParseMethod(mineru_method_raw_str),
                server_url=server_url,
                delete_output=delete_output,
                parse_method=parse_method,
                formula_enable=enable_formula,
                table_enable=enable_table,
            )
            final_out_dir = self._run_mineru(pdf, out_dir, options, callback=callback)
            outputs = self._read_output(final_out_dir, pdf.stem, method=mineru_method_raw_str, backend=backend)
            
            # Filter outputs based on page range
            filtered_outputs = [o for o in outputs if from_page <= o.get("page_idx", 0) < to_page]
            self.logger.info(f"[MinerU] Parsed {len(outputs)} blocks from PDF (filtered to {len(filtered_outputs)} in range {from_page}-{to_page}).")
            
            if callback:
                callback(0.75, f"[MinerU] Parsed {len(filtered_outputs)} blocks from PDF.")

            return self._transfer_to_sections(filtered_outputs, parse_method), self._transfer_to_tables(filtered_outputs)
        finally:
            if temp_pdf and temp_pdf.exists():
                try:
                    temp_pdf.unlink()
                    temp_pdf.parent.rmdir()
                except Exception:
                    pass
            if delete_output and created_tmp_dir and out_dir.exists():
                try:
                    shutil.rmtree(out_dir)
                except Exception:
                    pass


if __name__ == "__main__":
    parser = MinerUParser("mineru")
    ok, reason = parser.check_installation()
    print("MinerU available:", ok)

    filepath = ""
    with open(filepath, "rb") as file:
        outputs = parser.parse_pdf(filepath=filepath, binary=file.read())
        for output in outputs:
            print(output)
