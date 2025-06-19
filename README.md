# 高德天气查询插件

一个基于高德开放平台 API 的天气查询插件，支持查询天气预报和天气订阅功能，并使用 LLM 进行结果优化展示。

## 功能特点

- 支持查询天气预报
- 支持天气订阅功能（定时推送）
- 支持文本和图片两种展示模式
- 支持自定义默认城市
- 支持 LLM 优化天气描述，让天气播报更生动有趣

## 安装说明

1. 安装依赖包：
```bash
pip install aiohttp>=3.8.0
pip install APScheduler>=3.10.1
pip install python-dateutil>=2.8.2
pip install "zoneinfo;python_version<'3.9'"
```

2. 确保你的 Python 环境中有以下模块：
- re (Python 内置模块，用于正则表达式处理)
- json (Python 内置模块，用于处理JSON数据)
- datetime (Python 内置模块，用于处理日期和时间)
- uuid (Python 内置模块，用于生成唯一标识符)

## 配置说明

在 `_conf_schema.json` 中配置以下参数：

```json
{
    "amap_api_key": {
        "description": "高德开放平台 API Key",
        "type": "string",
        "hint": "请前往 https://lbs.amap.com/ 注册并获取 API Key",
        "obvious_hint": true
    },
    "default_city": {
        "description": "默认城市",
        "type": "string",
        "hint": "当用户没有输入城市时，将使用此配置查询天气",
        "default": "上海"
    },
    "send_mode": {
        "description": "发送模式",
        "type": "string",
        "options": ["text", "image"],
        "default": "text",
        "hint": "选择以纯文本还是图片形式发送天气信息"
    },
    "LLM_prompt": {
        "description": "自定义 Prompt",
        "type": "string",
        "hint": "自定义Prompt"
    }
}
```

## 使用方法

### 天气查询命令

```
/weather [城市名]
```

示例：
- `/weather 杭州` - 查询杭州的天气预报
- `/weather` - 查询默认城市的天气预报

### 天气订阅命令

```
/weather_subscribe <子命令> [参数]
```

支持的子命令：
- `subscribe [描述]`: 订阅天气预报
  - 示例：`/weather_subscribe subscribe 每天早上9点发送上海天气`
- `ls`: 查看当前订阅列表
  - 示例：`/weather_subscribe ls`
- `rm <序号>`: 删除指定序号的订阅
  - 示例：`/weather_subscribe rm 1`

### 天气信息展示格式

#### 基础文本格式
```
[当前时间] 地点:[城市] [日期] 周[星期] 天气预报：
白天[天气]，气温[高温]°C ~ [低温]°C, [风向]风[风力]级；
夜间[天气]，[风向]风[风力]级。
```

#### LLM 优化格式
LLM 会将基础天气信息转化为更生动、友好的格式，包括：
- 更自然的语言描述
- 适当的表情符号
- 贴心的天气建议
- 温暖活力的语气

示例：
```
2024-03-19 周二 天气小播报（杭州） 预报时间：09:00:00
大家早安哦~ 今天白天是超美的晴天☀️呢！气温在25°C~15°C之间波动，晚上转为多云，今天风蛮大的，早上东南风3级，晚上西北风2级，记得多穿件外套哦~

小贴士：
- 今天温差有点大，记得带件外套呀~
- 白天阳光超好，防晒霜别忘记涂哦！
- 晚上多云很舒服，适合和朋友出去走走

这么好的天气，心情都会变得超棒的！记得好好享受这个美丽的春日～
```

## 依赖要求

- Python 3.7+
- aiohttp>=3.8.0 (外部依赖，用于HTTP请求)
- APScheduler>=3.10.1 (外部依赖，用于定时任务)
- python-dateutil>=2.8.2 (外部依赖，用于日期处理)
- zoneinfo (Python 3.9+ 内置，3.9以下需要安装)
- AstrBot 框架

## 作者信息

- 作者：Guan
- 版本：1.1.0
- 项目地址：https://github.com/guanhuhao/astrbot_plugin_daily_weather
