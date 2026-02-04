## 问题
`MinerUOcrModel` 在在线模式下没有初始化 `outlines` 属性，导致报错：
`'MinerUOcrModel' object has no attribute 'outlines'`

## 原因
- 在线模式下只调用了 `Base.__init__` 和创建了 `MinerUOnlineParser`
- 没有调用 `MinerUParser.__init__`，所以缺少 `self.outlines = []`

## 解决方案
在 `MinerUOcrModel.__init__` 中，无论在线模式还是本地模式，都初始化 `self.outlines = []`

## 修改文件
- `rag/llm/ocr_model.py` - 在 `__init__` 中添加 `self.outlines = []`

请确认后我将立即修复。