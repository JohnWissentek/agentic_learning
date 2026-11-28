# mail_sender.py 伪代码

## 本文件职责（一句话）
经 SMTP 发送 HTML 邮件；TEST_MODE 拦截改写收件人；提供日/周/月/个人异常/调休超期等模板渲染。

## 对应PRD功能
F1、F7（异常与汇总邮件）、F11 预留（调休催用模板已存在于超期警告）；异常场景 E22

## 依赖
- 调用：config.settings、logger、smtplib、email.mime
- 被调用：audit_engine、main（测试发信）

## 伪代码

函数 send_html_email(subject, html_content, to_email, cc_list=None) -> bool:
    若 TEST_MODE:
        原收件人写入 subject 前缀说明
        to_email 改为 TEST_RECIPIENT_EMAIL
        cc_list 清空
        记 INFO「已拦截」
    组装 MIMEMultipart（From 用 SENDER_NAME <SENDER>，To/Cc/Subject）
    附件 HTML 正文
    尝试:
        按 USE_SSL / USE_TLS 连接 SMTP，timeout=10
        login(USERNAME) → sendmail(SENDER, To+Cc, 报文)
        记 INFO 成功；返回 True
    捕获异常:
        记 ERROR；将 To/Cc/Subject/正文长度写入 WARNING 兜底日志
        返回 False（不抛，调用方可继续）

函数 render_individual_anomaly_email(...):
    渲染「个人昨日异常确认」HTML（含 T+2 指引）

函数 render_daily_summary_email(...):
    渲染公司日汇总（应到/正常/请假出差/异常人数 + 明细表）

函数 render_weekly_summary_email(...):
    渲染上周异常残留周报 + 周期累计预警

函数 render_overdue_warning_email(...):
    渲染调休超 7 天未休警告
    # F11（PRD v0.4）：此邮件仅发 PM_EMAILS（孔紫初、王楠）；禁止发/抄送被催员工

函数 render_monthly_preliminary_email(...):
    渲染月度草稿快报（25 日）：待申诉/待审批/缺日报等

函数 render_monthly_finalized_email(...):
    渲染月度终审报表（26 日）：扣薪天数、拦截加班、调休结转

## 异常与边界（必填）
- 本文件处理：SMTP 失败返回 False + 日志兜底，不抛给引擎（引擎仍可提交 DB）
- 故意往上抛：无；与 ARCHITECTURE「重试后告警」相比，当前实现为单次尝试+日志（技术债：应补有限重试）
- 边界：TEST_MODE 必须剥抄送，防测试骚扰；空 cc_list 合法；超时 10s

## 注意事项 / 坑
- SMTP 认证账号与发件人 From 可以不同（USERNAME vs SENDER），Office365 常见坑
- 模板用 str.format，正文里若出现未转义的 `{` `}` 会炸——动态行应先拼好再塞入占位符
- 生产关闭 TEST_MODE 前做一次真实收件人抽测
