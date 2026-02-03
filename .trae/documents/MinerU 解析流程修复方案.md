## 问题分析

目前的 MinerU 解析流程存在以下核心问题：

### 1. 图片数据丢失

* `_transfer_to_sections` 只提取 IMAGE 的 caption 文本

* `img_path`（图片路径）被完全丢弃

* 没有 `_transfer_to_figures` 方法提取图片数据

### 2. 表格数据丢失

* `_transfer_to_tables` 直接返回空列表 `[]`

* 表格处理完全未实现

### 3. 数据传递问题

* `by_mineru` 返回 `(sections, tables, pdf_parser)`

* 但 `tables` 始终是空的

* `manual.py` 期望处理 tables 和 figures，但没有数据

## 修复方案

### 阶段 1: 添加图片提取功能

1. 在 `mineru_parser.py` 添加 `_transfer_to_figures` 方法
2. 提取 IMAGE 类型的 `img_path`, `image_caption`, `image_footnote`
3. 返回 `((img_path, caption), poss)` 格式的列表

### 阶段 2: 实现表格提取功能

1. 完善 `_transfer_to_tables` 方法
2. 提取 TABLE 类型的 `table_body`, `table_caption`, `table_footnote`
3. 返回 `((img_path, table_content), poss)` 格式的列表

### 阶段 3: 修改数据返回格式

1. 修改 `parse_pdf` 返回 `(sections, tables, figures)`
2. 修改 `by_mineru` 返回 `(sections, tables, figures, pdf_parser)`
3. 修改 `manual.py` 接收并处理 figures

### 阶段 4: 图片加载和显示

1. 在 `manual.py` 中加载图片路径为 PIL.Image 对象
2. 通过 `tokenize_table` 创建 image chunk
3. 设置 `doc_type_kwd = "image"`

## 预期结果

* PDF 中的图片将被正确提取和显示

* 表格将被正确解析和处理

* 文本、表格、图片按位置排序合并

