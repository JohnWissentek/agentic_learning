# config.py 伪代码

## 本文件职责（一句话）
从项目根目录的 `.env` 文件加载环境变量配置，并在此阶段执行必填配置项的静态校验，如有缺失则强制退出程序。

## 对应PRD功能
系统公共基础配置与测试拦截模式配置（TEST_MODE）

## 依赖
- 调用：logger.get_logger
- 被调用：项目内的所有服务和入口模块 (main.py, db.py, mail_sender.py, wecom_api.py 等)

## 伪代码
```python
# 声明根路径并加载环境变量
ROOT_DIR = 当前文件上两级目录的绝对路径
加载环境变量自 (ROOT_DIR / ".env")

# 必填项清单
REQUIRED_KEYS = ["WECOM_CORPID", "WECOM_SECRET", "DATABASE_URL"]

类 Settings:
    属性 WECOM_CORPID = 读取环境变量 "WECOM_CORPID", 默认值为 "ww9238966755b26e48"
    属性 WECOM_SECRET = 读取环境变量 "WECOM_SECRET", 默认值为 "4v0O2zfAJmy1NvP7JCa-m6gUVgn1anccYHwbNWi2jRo"
    属性 WECOM_AGENT_ID = 读取环境变量 "WECOM_AGENT_ID", 默认值为 1000002
    
    属性 WECOM_TOKEN = 读取环境变量 "WECOM_TOKEN", 默认值 "uY7hN8mK2pL5vX4zQ9wR1tB6yC3dE0fG"
    属性 WECOM_ENCODING_AES_KEY = 读取环境变量 "WECOM_ENCODING_AES_KEY", 默认值 "n8mK2pL5vX4zQ9wR1tB6yC3dE0fGuY7hN8mK2pL5vX4"
    
    属性 DATABASE_URL = 读取环境变量 "DATABASE_URL"
    
    # 邮件服务器配置 (SMTP 基础参数)
    属性 SMTP_SERVER = 读取环境变量 "SMTP_SERVER", 默认 "smtp.office365.com"
    属性 SMTP_PORT = 读取环境变量 "SMTP_PORT", 默认 587
    属性 SMTP_USERNAME = 读取环境变量 "SMTP_USERNAME", 默认 "info@palmarytech.com"
    属性 SMTP_PASSWORD = 读取环境变量 "SMTP_PASSWORD", 默认 "AgenticRich@2026$$"
    属性 SMTP_SENDER = 读取环境变量 "SMTP_SENDER", 默认 "cyber.griffin@palmarytech.com"
    属性 SMTP_SENDER_NAME = 读取环境变量 "SMTP_SENDER_NAME", 默认 "Cyber Griffin (Chief AI Agent)"
    属性 SMTP_USE_TLS = 读取环境变量 "SMTP_USE_TLS", 默认 True
    属性 SMTP_USE_SSL = 读取环境变量 "SMTP_USE_SSL", 默认 False
    
    # 测试拦截配置
    属性 TEST_MODE = 读取环境变量 "TEST_MODE", 默认 True
    属性 TEST_RECIPIENT_EMAIL = 读取环境变量 "TEST_RECIPIENT_EMAIL", 默认 "john.xu@palmarytech.com" (徐宏玮邮箱)
    
    # 管理员与项目经理邮箱清单 (用于抄送)
    属性 ADMIN_EMAILS = ["john.xu@palmarytech.com", "xuelei@palmarytech.com", "wangxiao@palmarytech.com"]
    属性 PM_EMAILS = ["winni-zichu.kong@wissentek.com", "wangnan@palmarytech.com"]

实例化 settings = Settings()

函数 get(键, 默认值=None):
    返回 读取环境变量(键, 默认值)

函数 validate():
    缺失配置列表 = 过滤 REQUIRED_KEYS 中在环境变量中不存在或为空的键
    如果 缺失配置列表 不为空:
        记 CRITICAL 日志 "缺少必填配置项: 缺失配置列表"
        系统强行退出(状态码=1)
    否则:
        记 DEBUG 日志 "配置校验通过"
```

## 注意事项 / 坑
- 部署新环境时必须首先配置 `.env`，若缺失必填项（如 `WECOM_CORPID` 等）则服务启动即会挂掉。
- `TEST_MODE` 默认为 `True`。在开发或测试阶段，所有邮件发送动作都将被拦截，强制投递到 `TEST_RECIPIENT_EMAIL`，防止因逻辑漏洞给公司高层和员工发送测试骚扰邮件。
