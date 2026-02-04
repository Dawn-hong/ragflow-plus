## 方案概述
在后端添加 MinerU 配置状态接口，前端在 MinerU 选项区域显示当前模式。

## 实现步骤

### 步骤 1: 后端添加 MinerU 状态接口
**文件**: `api/apps/system_app.py`

在 `/system/config` 接口中添加 MinerU 配置状态：
```python
@manager.route("/config", methods=["GET"])
def get_config():
    from common.config_utils import get_base_config
    mineru_config = get_base_config("mineru", {})
    return get_json_result(data={
        "registerEnabled": settings.REGISTER_ENABLED,
        "mineru": {
            "online_enabled": mineru_config.get("online_enabled", False),
        }
    })
```

### 步骤 2: 前端添加 Hook 获取 MinerU 状态
**文件**: `web/src/hooks/use-mineru-status.ts` (新建)

创建 hook 获取 MinerU 配置状态。

### 步骤 3: 修改 MinerU 选项组件
**文件**: `web/src/components/mineru-options-form-field.tsx`

添加模式提示标签：
- 在线模式：显示绿色标签 "Online API"
- 本地模式：显示蓝色标签 "Local API"

### 步骤 4: 添加国际化翻译
**文件**: 
- `web/src/locales/en.ts`
- `web/src/locales/zh.ts`

添加翻译键：
- `knowledgeConfiguration.mineruOnlineMode` - 在线模式
- `knowledgeConfiguration.mineruLocalMode` - 本地模式

## 显示效果

在知识库配置页面，当选择 MinerU 时显示：

```
MinerU Options
[Online API]  ← 绿色标签表示在线模式
Parse Method: [auto ▼]
Language: [English ▼]
...
```

或

```
MinerU Options
[Local API]   ← 蓝色标签表示本地模式
Parse Method: [auto ▼]
...
```

## 优势
- 用户清楚知道当前使用的模式
- 无需手动配置，自动读取后端设置
- 不影响现有功能

请确认此方案后，我将开始实现代码。