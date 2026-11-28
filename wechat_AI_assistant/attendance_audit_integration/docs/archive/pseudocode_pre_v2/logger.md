# logger.py 伪代码

## 本文件职责（一句话）
初始化系统的日志配置（包含控制台输出和带文件轮转的多备份本地日志文件），并提供敏感数据脱敏辅助工具。

## 对应PRD功能
系统日志输出标准规范与敏感信息保护机制。

## 依赖
- 调用：无 (标准库 logging, os, sys)
- 被调用：项目内的几乎所有模块，用于记写业务/系统行为日志。

## 伪代码
```python
# 初始化静态配置
日志目录 _LOG_DIR = 项目根目录 / "logs"
是否已初始化标识 _INITIALIZED = False

# 日志格式规范
文件日志格式 _FILE_FMT = "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
控制台格式 _CONSOLE_FMT = "%(asctime)s | %(levelname)-8s | %(message)s"

函数 _init_root(日志文件名 = "app.log"):
    全局变量 _INITIALIZED
    如果 _INITIALIZED 是 True:
        直接返回
        
    创建 _LOG_DIR 目录 (若不存在)
    获取全局根 logger，设置最低过滤级别为 DEBUG
    
    # 1. 创建控制台输出 Handler
    控制台 Handler = 绑定 stdout 视频流
    控制台 Handler 级别 = 环境变量 "LOG_LEVEL", 默认为 "INFO"
    设置 控制台格式 为 _CONSOLE_FMT
    将 控制台 Handler 附加到根 logger
    
    # 2. 创建文件轮转输出 Handler
    文件 Handler = 实例化 RotatingFileHandler(文件路径=_LOG_DIR / 日志文件名, 最大单文件5MB, 最多保留5份, 字符集='utf-8')
    文件 Handler 级别 = DEBUG
    设置 文件格式 为 _FILE_FMT
    将 文件 Handler 附加到根 logger
    
    _INITIALIZED = True

函数 get_logger(名称, 日志文件名 = "app.log"):
    调用 _init_root(日志文件名)
    返回 logging.getLogger(名称)

函数 mask(敏感字符串, 保留前缀位数 = 4):
    如果 敏感字符串 为空:
        返回 空字符串
    返回 敏感字符串[前0到保留前缀位数] + "****"
```

## 注意事项 / 坑
- 部署在服务器上时，如需切换控制台的过滤精度，可以在外部定义 `LOG_LEVEL` 环境变量（如：`LOG_LEVEL=DEBUG`）。
- 使用 `mask` 函数对企业微信 `secret` 或数据库连接密码进行日志脱敏输出，防止调试日志中泄漏核心安全凭证。
- 本地日志文件最多只占用 5MB * 5 = 25MB 磁盘空间，超过会被自动覆盖，不必担心撑爆磁盘。
