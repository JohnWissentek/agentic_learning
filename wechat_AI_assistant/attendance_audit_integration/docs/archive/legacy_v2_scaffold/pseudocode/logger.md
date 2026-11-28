# logger.py 伪代码

## 本文件职责（一句话）
统一初始化根日志（控制台 INFO+、文件 DEBUG+ 轮转），并提供敏感串脱敏 `mask()`。

## 对应PRD功能
非功能可观测性（支撑 F1–F14 全流程排障）；异常场景 E20/E22/E23 的失败日志落盘

## 依赖
- 调用：标准库 logging / RotatingFileHandler / pathlib
- 被调用：几乎所有业务模块（audit_engine、wecom_api、mail_sender、db、main、diagnostics、config、mock_data_populator）

## 伪代码

日志目录 = 项目根 / logs
_INITIALIZED 标志防止重复挂载 handler

函数 _init_root(log_file="app.log"):
    若已初始化则返回
    创建 logs 目录（exist_ok）
    根 logger 级别 = DEBUG
    控制台 Handler：级别取自 LOG_LEVEL（默认 INFO），简洁格式
    文件 Handler：RotatingFileHandler(5MB × 5 份)，DEBUG，完整格式含模块:函数:行号
    置 _INITIALIZED = True

函数 get_logger(name, log_file="app.log"):
    调用 _init_root
    返回 logging.getLogger(name)

函数 mask(secret, keep=4):
    空串返回 ""
    否则返回 secret 前 keep 位 + "****"

## 异常与边界（必填）
- 本文件处理：目录创建失败会向上抛 OSError（少见）；mask 对空输入安全
- 故意往上抛：磁盘不可写时由调用方/进程感知；本文件不做吞异常
- 边界：多进程各写同一 app.log 可能交错（MVP 单进程可接受）；禁止业务里用 print 调试

## 注意事项 / 坑
- 首次 get_logger 才建目录；纯 import logger 模块不写盘
- 脱敏只提供 mask，诊断包应对全部 .env 值统一 mask，不要自行判断「是否敏感」
- 控制台与文件级别分离：线上排障以 logs/app.log 为准
