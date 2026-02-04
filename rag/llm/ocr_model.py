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
from typing import Any, Optional

from deepdoc.parser.mineru_parser import MinerUParser
from deepdoc.parser.mineru_online_parser import MinerUOnlineParser
from deepdoc.parser.paddleocr_parser import PaddleOCRParser
from common.config_utils import get_base_config


class Base:
    def __init__(self, key: str | dict, model_name: str, **kwargs):
        self.model_name = model_name

    def parse_pdf(self, filepath: str, binary=None, **kwargs) -> tuple[Any, Any]:
        raise NotImplementedError("Please implement parse_pdf!")


class MinerUOcrModel(Base, MinerUParser):
    _FACTORY_NAME = "MinerU"

    def __init__(self, key: str | dict, model_name: str, **kwargs):
        Base.__init__(self, key, model_name, **kwargs)
        # Initialize outlines attribute (required by RAGFlowPdfParser)
        self.outlines = []
        # Initialize logger attribute (required by MinerUParser)
        self.logger = logging.getLogger(self.__class__.__name__)
        raw_config = {}
        if key:
            try:
                raw_config = json.loads(key)
            except Exception:
                raw_config = {}

        # nested {"api_key": {...}} from UI
        # flat {"MINERU_*": "..."} payload auto-provisioned from env vars
        config = raw_config.get("api_key", raw_config)
        if not isinstance(config, dict):
            config = {}

        def _resolve_config(key: str, env_key: str, default=""):
            # lower-case keys (UI), upper-case MINERU_* (env auto-provision), env vars
            return config.get(key, config.get(env_key, os.environ.get(env_key, default)))

        # Check if online mode is enabled from service_conf.yaml
        mineru_service_config = get_base_config("mineru", {})
        self.online_enabled = mineru_service_config.get("online_enabled", False)

        if self.online_enabled:
            # Online API mode configuration
            self.online_token = mineru_service_config.get("token", "")
            self.online_model_version = mineru_service_config.get("model_version", "vlm")
            self.online_poll_interval = mineru_service_config.get("poll_interval", 5)
            self.online_poll_timeout = mineru_service_config.get("poll_timeout", 300)
            self.online_temp_dir = mineru_service_config.get("temp_dir", "")

            # Override with environment variables if provided
            self.online_token = _resolve_config("mineru_online_token", "MINERU_ONLINE_TOKEN", self.online_token)
            self.online_model_version = _resolve_config("mineru_online_model_version", "MINERU_ONLINE_MODEL_VERSION", self.online_model_version)
            self.online_poll_interval = int(_resolve_config("mineru_online_poll_interval", "MINERU_ONLINE_POLL_INTERVAL", str(self.online_poll_interval)))
            self.online_poll_timeout = int(_resolve_config("mineru_online_poll_timeout", "MINERU_ONLINE_POLL_TIMEOUT", str(self.online_poll_timeout)))
            self.online_temp_dir = _resolve_config("mineru_online_temp_dir", "MINERU_ONLINE_TEMP_DIR", self.online_temp_dir)

            # Initialize online parser
            self._online_parser = MinerUOnlineParser(
                token=self.online_token,
                model_version=self.online_model_version,
                poll_interval=self.online_poll_interval,
                poll_timeout=self.online_poll_timeout,
                temp_dir=self.online_temp_dir,
            )

            logging.info(f"MinerU Online API mode enabled, temp_dir: {self.online_temp_dir or 'system default'}")
        else:
            # Local API mode configuration
            self.mineru_api = _resolve_config("mineru_apiserver", "MINERU_APISERVER", "")
            self.mineru_output_dir = _resolve_config("mineru_output_dir", "MINERU_OUTPUT_DIR", "")
            self.mineru_backend = _resolve_config("mineru_backend", "MINERU_BACKEND", "pipeline")
            self.mineru_server_url = _resolve_config("mineru_server_url", "MINERU_SERVER_URL", "")
            self.mineru_delete_output = bool(int(_resolve_config("mineru_delete_output", "MINERU_DELETE_OUTPUT", 1)))

            MinerUParser.__init__(self, mineru_api=self.mineru_api, mineru_server_url=self.mineru_server_url)

        # Redact sensitive config keys before logging
        redacted_config = {}
        for k, v in config.items():
            if any(sensitive_word in k.lower() for sensitive_word in ("key", "password", "token", "secret")):
                redacted_config[k] = "[REDACTED]"
            else:
                redacted_config[k] = v
        logging.info(f"Parsed MinerU config (sensitive fields redacted): {redacted_config}")

    def check_available(self, backend: Optional[str] = None, server_url: Optional[str] = None) -> tuple[bool, str]:
        if self.online_enabled:
            return self._online_parser.check_available()
        else:
            backend = backend or self.mineru_backend
            server_url = server_url or self.mineru_server_url
            return self.check_installation(backend=backend, server_url=server_url)

    def parse_pdf(self, filepath: str, binary=None, callback=None, parse_method: str = "raw", **kwargs):
        if self.online_enabled:
            # Use online parser
            ok, reason = self._online_parser.check_available()
            if not ok:
                raise RuntimeError(f"MinerU Online API not accessible: {reason}")

            sections, tables = self._online_parser.parse_pdf(
                filepath=filepath,
                binary=binary,
                callback=callback,
                parse_method=parse_method,
                **kwargs,
            )
        else:
            # Use local parser
            ok, reason = self.check_available()
            if not ok:
                raise RuntimeError(f"MinerU server not accessible: {reason}")

            sections, tables = MinerUParser.parse_pdf(
                self,
                filepath=filepath,
                binary=binary,
                callback=callback,
                output_dir=self.mineru_output_dir,
                backend=self.mineru_backend,
                server_url=self.mineru_server_url,
                delete_output=self.mineru_delete_output,
                parse_method=parse_method,
                **kwargs,
            )
        return sections, tables


class PaddleOCROcrModel(Base, PaddleOCRParser):
    _FACTORY_NAME = "PaddleOCR"

    def __init__(self, key: str | dict, model_name: str, **kwargs):
        Base.__init__(self, key, model_name, **kwargs)
        raw_config = {}
        if key:
            try:
                raw_config = json.loads(key)
            except Exception:
                raw_config = {}

        # nested {"api_key": {...}} from UI
        # flat {"PADDLEOCR_*": "..."} payload auto-provisioned from env vars
        config = raw_config.get("api_key", raw_config)
        if not isinstance(config, dict):
            config = {}

        def _resolve_config(key: str, env_key: str, default=""):
            # lower-case keys (UI), upper-case PADDLEOCR_* (env auto-provision), env vars
            return config.get(key, config.get(env_key, os.environ.get(env_key, default)))

        self.paddleocr_api_url = _resolve_config("paddleocr_api_url", "PADDLEOCR_API_URL", "")
        self.paddleocr_algorithm = _resolve_config("paddleocr_algorithm", "PADDLEOCR_ALGORITHM", "PaddleOCR-VL")
        self.paddleocr_access_token = _resolve_config("paddleocr_access_token", "PADDLEOCR_ACCESS_TOKEN", None)

        # Redact sensitive config keys before logging
        redacted_config = {}
        for k, v in config.items():
            if any(sensitive_word in k.lower() for sensitive_word in ("key", "password", "token", "secret")):
                redacted_config[k] = "[REDACTED]"
            else:
                redacted_config[k] = v
        logging.info(f"Parsed PaddleOCR config (sensitive fields redacted): {redacted_config}")

        PaddleOCRParser.__init__(
            self,
            api_url=self.paddleocr_api_url,
            access_token=self.paddleocr_access_token,
            algorithm=self.paddleocr_algorithm,
        )

    def check_available(self) -> tuple[bool, str]:
        return self.check_installation()

    def parse_pdf(self, filepath: str, binary=None, callback=None, parse_method: str = "raw", **kwargs):
        ok, reason = self.check_available()
        if not ok:
            raise RuntimeError(f"PaddleOCR server not accessible: {reason}")

        sections, tables = PaddleOCRParser.parse_pdf(self, filepath=filepath, binary=binary, callback=callback, parse_method=parse_method, **kwargs)
        return sections, tables
