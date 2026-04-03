# HoyoAssistant

HoYoLAB/MiYoUShe 每日任务自动化助手。

## 功能

- **社区任务**: 米游社签到、阅读、点赞、分享
- **游戏签到**: 国服/国际服游戏每日签到
- **云游戏签到**: 原神、绝区零云游戏签到
- **多账户支持**: 支持多账户配置与运行
- **推送通知**: 支持多种推送渠道（ServerChan、Telegram、Bark等）
- **国际化**: 支持中文和英文界面

## 安装

```bash
pip install hoyo-assistant
```

或从源码安装：

```bash
git clone https://github.com/arisvia/hoyolab.git
cd hoyolab
pip install -e .
```

## 快速开始

### 单账户模式

```bash
hoyo-assistant --config config/config.yaml
```

### 多账户模式

```bash
hoyo-assistant --multi --config config/
```

### 服务器模式

```bash
hoyo-assistant server --config config/config.yaml
```

## 配置

配置文件支持 YAML 格式，可通过文件或环境变量配置。

### 基础配置示例

```yaml
account:
  cookie: "your_cookie_here"
  stoken: "your_stoken_here"

tasks:
  community:
    enable: true
  game_signin:
    chinese:
      enable: true
      genshin: true
      honkai3: false

push:
  enable: false
  # 推送渠道配置
```

### 环境变量

所有配置项均可通过环境变量覆盖，格式为 `HOYO_ASSISTANT_<SECTION>__<KEY>`：

```bash
export HOYO_ASSISTANT_ACCOUNT__COOKIE="your_cookie"
export HOYO_ASSISTANT_PUSH__ENABLE="true"
```

## 运行时环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOYO_ASSISTANT_LOG_DIR` | `logs` | 日志输出目录 |
| `HOYO_ASSISTANT_LOG_ROTATION` | `10 MB` | 日志轮转大小 |
| `HOYO_ASSISTANT_LOG_RETENTION` | `1 week` | 日志保留时间 |
| `HOYO_ASSISTANT_CLI_OUTPUT` | `auto` | 输出模式 (rich/plain/auto) |
| `HOYO_ASSISTANT_LANGUAGE` | - | 强制界面语言 (zh_CN/en_US) |

## 开发

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest
```

### 代码检查

```bash
ruff check .
mypy src/
```

## 许可证

MIT License
