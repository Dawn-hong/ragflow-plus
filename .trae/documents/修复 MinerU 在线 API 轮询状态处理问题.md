## 问题
MinerU 在线 API 返回的状态字段为空，导致轮询逻辑无法识别，最终超时。

## 解决方案
修改 `deepdoc/parser/mineru_online_parser.py` 中的 `_poll_result` 方法：

1. 增加对空状态的处理
2. 当状态为空时，视为仍在处理中（pending）
3. 添加更多调试日志，记录完整的 API 响应

## 修改内容
```python
def _poll_result(self, batch_id: str, callback: Optional[Callable] = None) -> dict:
    # ... 现有代码 ...
    
    while True:
        # ... 现有代码 ...
        
        data = result.get("data", {})
        status = data.get("status", "")
        
        # 处理空状态
        if not status:
            self.logger.warning(f"[MinerU Online] Empty status received, treating as pending")
            status = "pending"
        
        # ... 后续逻辑 ...
```

## 文件变更
- `deepdoc/parser/mineru_online_parser.py` - 修复状态处理逻辑

请确认后我将立即修改代码。