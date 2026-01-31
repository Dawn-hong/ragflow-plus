# MinerU 解析与 Manual 切分流程

本文档详细说明了 RAGFlow 如何使用 **MinerU** 解析器处理 PDF，并随后使用 **Manual** 方法 (`rag/app/manual.py`) 对内容进行切分。

## 流程总览

```mermaid
graph TD
    A[用户上传 PDF] --> B(rag/app/manual.py: chunk)
    B --> C{解析器选择}
    C -- "检查配置/环境变量" --> D[选择 MinerU 解析器]
    D --> E(deepdoc/parser/mineru_parser.py: MinerUParser)
    E --> F[调用 MinerU API / SDK]
    F --> G[接收 ZIP 并解压]
    G --> H[读取 _content_list.json]
    H --> I[转换为 Sections]
    I -- "按 text_level 分组" --> J[Section 列表 (文本, 层级, bbox)]
    J --> K(返回 manual.py)
    K --> L[检测 MinerU 格式]
    L --> M[创建文本块 (保留分组)]
    L --> N[单独处理表格]
    M --> O[最终合并与排序]
    N --> O
    O --> P[最终切分结果]
```

## 详细步骤

### 1. 初始化 (`rag/app/manual.py`)

流程始于 `manual.py` 中的 `chunk` 函数。

*   **逻辑**: 确定使用的解析器。
*   **自动选择**: 检查环境变量 `MINERU_TOKEN` 或 `service_conf.yaml`。如果存在，将 `layout_recognizer` 设置为 "MinerU"。
*   **调用**: 初始化 `MinerUParser` 并调用，参数为 `parse_method="manual"`。

### 2. MinerU 解析 (`deepdoc/parser/mineru_parser.py`)

`MinerUParser` 类处理与 MinerU 引擎的交互。

*   **API 调用**: 将文件上传到 MinerU API（或使用本地 SDK）。
*   **响应处理**: 下载生成的 ZIP 文件并解压到临时目录。
*   **数据读取 (`_read_output`)**: 在解压后的输出中查找 `*_content_list.json`。该 JSON 包含从 PDF 解析出的结构化数据，包括文本、表格、图片及其边界框 (`bbox`) 和层级 (`text_level`)。

### 3. 段落分组逻辑 (`_transfer_to_sections`)

这是准备切分数据的核心逻辑。当 `parse_method="manual"` 时，`mineru_parser.py` 在将数据返回给 `manual.py` 之前会进行智能分组。

*   **遍历输出**: 循环处理 `content_list.json` 中的项。
*   **分组规则**:
    *   维护一个 `current_section_text` 缓冲区。
    *   **文本**: 追加到当前缓冲区。
    *   **表格**: 作为“硬中断”。如果遇到表格，当前文本段落将结束并添加到结果列表中。表格本身在此处被跳过（稍后通过 `_extract_table_figure` 处理）。
    *   **文本层级**: 虽然此函数不显式分割*每个*层级，但 `text_level` 属性被保留并传递下去。
    *   **结果**: 一个元组列表：`(merged_text, level, position_list)`。

### 4. Manual 切分 (`rag/app/manual.py`)

回到 `manual.py`，代码处理 MinerU 返回的 sections。

*   **格式检测**: 检查 sections 是否遵循 MinerU 格式（3 元素元组，其中第二个元素为整数层级）。
    *   `is_mineru_format = True`
*   **Section ID 分配**:
    *   使用 `text_level` 分配 section ID。
    *   **关键点**: 对于 MinerU 格式，它通常将 sections 视为独立的，或使用提供的层级来确定边界。
*   **切分生成**:
    *   如果 `is_mineru_format` 为真，则**保留原始顺序**。在此阶段*不*根据位置重新排序文本段落。
    *   直接根据步骤 3 提供的分组 sections 创建 chunk。
    *   这确保了 MinerU 完成的“语义分组”（例如，标题保留在其正文中）得到尊重。

### 5. 最终合并与排序

*   **表格**: 通过 `vision_figure_parser_pdf_wrapper` 和 `tokenize_table` 单独处理。
*   **合并**: 文本块和表格块合并为一个列表。
*   **全局排序**:
    *   合并后的列表按 **页码** 和 **垂直位置 (Top)** 排序。
    *   `all_chunks_with_index.sort(key=get_chunk_position)`
    *   这确保了即使表格是单独处理的，它们也能相对于文本块插回到正确的阅读顺序中。

## 关键数据结构

*   **MinerU JSON 项**:
    ```json
    {
        "type": "text",
        "text": "Chapter 1...",
        "text_level": 1,
        "bbox": [x0, top, x1, bottom],
        "page_idx": 0
    }
    ```
*   **Section 元组 (内部)**: `(text_content, text_level, [list_of_bboxes])`
*   **最终 Chunk**: 包含 `content_with_weight` 和 `position_int` 的字典。

## 职责总结

| 组件 | 职责 |
| :--- | :--- |
| **MinerU 引擎** | 版面分析、OCR、结构检测（标题、段落、表格）。 |
| **`mineru_parser.py`** | 管理 API，读取 JSON，**根据结构将文本分组为逻辑段落**。 |
| **`manual.py`** | 编排流程，**根据位置进行最终排序**，将表格和文本合并为可引用的 chunk。 |
