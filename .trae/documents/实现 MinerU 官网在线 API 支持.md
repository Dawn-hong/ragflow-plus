## 目标
实现 MinerU 官网在线 API 支持，与本地 MinerU 行为保持一致，完整解析 PDF 后返回 ZIP 包。

## 实现步骤

### 步骤 1: 创建 MinerU 在线解析器类
**文件**: `deepdoc/parser/mineru_online_parser.py`

- 创建 `MinerUOnlineParser` 类，继承 `RAGFlowPdfParser`
- 实现以下核心方法：
  - `__init__()`: 初始化配置（token、model_version、poll_interval、poll_timeout、temp_dir）
  - `check_available()`: 检查在线 API 可用性
  - `_get_presigned_urls()`: 获取预签名上传 URL
  - `_upload_file()`: 上传 PDF 到预签名 URL
  - `_poll_result()`: 轮询获取解析结果
  - `_download_zip()`: 下载 ZIP 包
  - `_extract_zip()`: 解压 ZIP 获取 `_content_list.json`
  - `parse_pdf()`: 主解析方法，整合以上流程
  - `_transfer_to_sections()`: 复用现有逻辑，转换 JSON 为 sections
  - `_line_tag()`: 生成位置标签

### 步骤 2: 更新配置常量
**文件**: `common/constants.py`

- 添加 MinerU 在线 API 相关配置常量
- 包括：MINERU_ONLINE_ENABLED、MINERU_ONLINE_TOKEN、MINERU_ONLINE_TEMP_DIR 等

### 步骤 3: 更新 service_conf.yaml
**文件**: `conf/service_conf.yaml`

- 在现有 mineru 配置下添加：
  - `temp_dir`: 指定 ZIP 解压目录（如 `D:/Agent_Projcet/ragflow/mineru_temp`）
  - 其他在线 API 相关配置

### 步骤 4: 修改 OCR 模型类
**文件**: `rag/llm/ocr_model.py`

- 修改 `MinerUOcrModel` 类：
  - 在 `__init__()` 中读取在线 API 配置
  - 根据 `online_enabled` 决定使用 `MinerUOnlineParser` 还是 `MinerUParser`
  - 保持 `parse_pdf()` 接口不变

### 步骤 5: 添加完整日志追踪
- 在关键步骤添加日志：
  - 获取预签名 URL
  - 上传文件进度
  - 轮询状态
  - 下载 ZIP
  - 解压结果
  - 解析完成

## API 调用流程
```
parse_pdf()
  ├── _get_presigned_urls() → POST https://mineru.net/api/v4/file-urls/batch
  ├── _upload_file() → PUT 预签名URL
  ├── _poll_result() → GET https://mineru.net/api/v4/extract-results/batch/{batch_id}
  ├── _download_zip() → 下载 ZIP 到 temp_dir
  ├── _extract_zip() → 解压获取 _content_list.json
  ├── _read_content_list() → 读取 JSON
  └── _transfer_to_sections() → 转换为 sections
```

## 输出格式
与现有 `MinerUParser` 保持一致：
```python
# Manual 模式
sections = [(text, type, position_tag), ...]
tables = []
```

## 文件变更清单
1. **新增**: `deepdoc/parser/mineru_online_parser.py`
2. **修改**: `common/constants.py` - 添加配置常量
3. **修改**: `conf/service_conf.yaml` - 添加 temp_dir 配置
4. **修改**: `rag/llm/ocr_model.py` - 集成在线解析器

## 兼容性保证
- 在线/本地模式通过配置切换
- 输出格式与现有代码完全一致
- 支持 `parse_method="manual"` 等参数
- 完整日志便于调试

请确认此计划后，我将开始编写代码。