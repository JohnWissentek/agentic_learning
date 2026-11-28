# mail_sender.py 伪代码

## 本文件职责（一句话）
封装 SMTP 协议发送 HTML 邮件，内含防测试骚扰的测试模式拦截器（TEST_MODE Interceptor），并提供 6 个定制化的高保真 HTML 邮件模板渲染函数。

## 对应PRD功能
- 考勤异常每日邮件预警提醒（PRD §3.3）
- 每日考勤对账汇总日报（PRD §3.3）
- 考勤待确认项汇总周报（PRD §3.3）
- 月度考勤预估快报草稿（PRD §3.5）
- 月度考勤封账财务决算终审月报（PRD §3.5）
- 7 天超期调休假预警提醒（PRD §3.6）

## 依赖
- 调用：smtplib, config.settings, logger, email.mime.multipart.MIMEMultipart, email.mime.text.MIMEText
- 被调用：audit_engine.py, main.py

## 伪代码
```python
函数 send_html_email(主题 subject, 网页内容 html_content, 收件人 to_email, 抄送列表 cc_list = None) -> 布尔值:
    如果 抄送列表 为空:
        抄送列表 = []
        
    原始收件人 = 收件人
    原始抄送列表 = 抄送列表
    
    # 1. 拦截器：安全防护机制 (TEST_MODE)
    如果 settings.TEST_MODE 是 True:
        收件人 = settings.TEST_RECIPIENT_EMAIL (强制改写为徐宏玮邮箱)
        抄送列表 = []  # 清空真实抄送列表，防止对员工及HR发送测试邮件
        主题 = f"[TEST MODE] 主题 (原本发给: 原始收件人, 抄送: 原始抄送列表)"
        记日志 INFO "[TEST MODE] 拦截邮件发送，强制重定向至测试接收端"
        
    # 2. 组装邮件报头对象
    消息 = 实例化 MIMEMultipart()
    消息['From'] = f"settings.SMTP_SENDER_NAME <settings.SMTP_SENDER>"
    消息['To'] = 收件人
    如果 抄送列表 不为空:
        消息['Cc'] = 拼接(抄送列表)
    消息['Subject'] = 主题
    
    将 html_content 包装为 MIMEText('html', 'utf-8')，附加到 消息 对象中
    
    实际全部收件人列表 = [收件人] + 抄送列表
    
    # 3. 发送邮件与安全防崩回滚
    尝试:
        如果 settings.SMTP_USE_SSL 是 True:
            # 建立加密 SSL 物理连接
            服务器 = smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT, 超时=10秒)
        否则:
            # 建立明文连接并通过 TLS 升级安全
            服务器 = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, 超时=10秒)
            如果 settings.SMTP_USE_TLS 是 True:
                服务器.starttls()
                
        # 登录 SMTP 授权账号
        服务器.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        # 用发送者身份发送给所有收件人
        服务器.sendmail(settings.SMTP_SENDER, 实际全部收件人列表, 消息.as_string())
        记日志 INFO "邮件发送成功，收件人: 收件人, 主题: 主题"
        服务器.quit()
        返回 True
    捕获 异常:
        记日志 ERROR "SMTP 邮件服务器网络连接或验证失败: 异常详情"
        # 回滚保障：在终端打印出一份 Fallback 伪邮件头部输出，防崩溃并利于控制台排查
        返回 False

# ＝＝＝＝＝ HTML 模板渲染器 ＝＝＝＝＝

函数 render_individual_anomaly_email(员工姓名, 异常日期, 异常描述, 异常详情, 上班卡时间, 下班卡时间, 设备状态):
    将参数代入并在后台动态拼接生成昨日个人考勤异常处理的 HTML 正文。
    主要包含：缺卡报警、T+2 补正宽限期声明、操作处理流程指南。
    返回 渲染后的 HTML 字符串

函数 render_daily_summary_email(对账日期, 应到人数, 正常人数, 请假天数, 异常人数, 异常表格行HTML, 历史核销变动HTML):
    渲染每日考勤对账汇总日报 HTML 正文，带有帕莫瑞经典财务警语 "Oh, my money money come!"。
    返回 渲染后的 HTML 字符串

函数 render_weekly_summary_email(周范围描述, 异常次数, 已核销数, 待处理数, 周异常表格HTML, 月累计警告警告列表HTML):
    渲染每周一发布的考勤异常未处理残留汇总周报 HTML 正文。
    返回 渲染后的 HTML 字符串

函数 render_monthly_preliminary_email(对账月份, 待审核申诉数, 待审核假单数, 缺失出差日报天数, 数据表格HTML):
    渲染每月 25 日下发的工作日考勤草稿预估月报 HTML 正文，主要是提示员工抓紧在 25 号下班前补齐假单、日报。
    返回 渲染后的 HTML 字符串

函数 render_monthly_finalized_email(对账月份, 计薪满勤天数, 旷工天数, 事假天数, 记增调休小时, 未处理异常笔数, 表格明细HTML, 拦截明细HTML, 调休假期变动明细HTML):
    渲染每月 26 日下发的封账财务扣薪对账决算 HTML 正文，并根据未结清事项数量动态标注报表状态。
    返回 渲染后的 HTML 字符串

函数 render_overdue_warning_email(员工姓名, 加班产生日期, 可休假时长, 超期天数):
    渲染当员工调休假超出 7 天后，发给该员工并抄送总经理、财务及项目经理孔紫初、王楠的假期清理督促警告 HTML 正文。
    返回 渲染后的 HTML 字符串
```

## 注意事项 / 坑
- `settings.TEST_MODE` 变量在日常开发和 staging 调试中应开启（设置为 `True`），这样所有的考勤周报、月报均会被自动发到徐宏玮的个人邮箱，避免对外打扰，也便于单独验证各层渲染样式是否完全正常。
- 进行邮件发送时，`sendmail` 的第二形参需要接收一个包含了 `To` 和 `Cc` 所有邮箱地址在内的扁平数组 `[to_email] + cc_list`，否则那些在 `Cc` 列表里的收件人虽然能收到这封邮件，但其实是在垃圾信箱或者无法在 SMTP 传输层正确接收。
- 渲染模板中的占位符字符串必须使用安全的 `format()`，防范因输入中存在特殊字符导致的渲染失败崩溃。
