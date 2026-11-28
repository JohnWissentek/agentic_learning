# main.py 伪代码

## 本文件职责（一句话）
启动 FastAPI Web 服务端，暴露企业微信 Webhook 实时回调接口、审计任务手动触发端点、国家法定节假日管理接口以及调试辅助工具。

## 对应PRD功能
- Webhook 审批流变动通知接收与解密入库（PRD §3.1）
- 每日/每周/每周超期调休/每月预决算审计任务的 Web 触发接口（PRD §3.3）
- 节假日日历增删改查管理端点（PRD §3.7）

## 依赖
- 调用：config, db.init_db, audit_engine, wxbiz_msg_crypt.WXBizMsgCrypt, mail_sender.send_html_email
- 被调用：Gunicorn/Uvicorn 容器，企业微信服务器 Webhook 回调推送

## 伪代码
```python
实例化 FastAPI 应用对象 app
实例化 消息加解密器 wxcrypt = WXBizMsgCrypt(settings.WECOM_TOKEN, settings.WECOM_ENCODING_AES_KEY, settings.WECOM_CORPID)

事件处理器: 当 app 启动时 (startup):
    尝试:
        调用 config.validate()  # 检查 .env
        调用 db.init_db()       # 初始化建表
    捕获 异常 并记 CRITICAL 日志

# ＝＝＝＝＝ 1. 企业微信 Webhook 审批变动接口 ＝＝＝＝＝

路由 GET "/webhooks/approval" (msg_signature, timestamp, nonce, echostr):
    # 企业微信首次配置回调 URL 校验
    尝试:
        解密明文 = wxcrypt.verify_url(msg_signature, timestamp, nonce, echostr)
        返回 文本响应(解密明文)
    捕获 异常 并抛出 HTTP 400 错误

路由 POST "/webhooks/approval" (request, msg_signature, timestamp, nonce):
    # 处理企业微信推送的加密 XML 审批变动事件
    尝试:
        加密正文 = 获取请求体 request.body()
        解密XML = wxcrypt.decrypt_xml_msg(msg_signature, timestamp, nonce, 加密正文)
        数据字典 = 将 XML 解析为 dict (xmltodict.parse)
        
        如果 数据字典["xml"]["Event"] == "sys_approval_change":
            审批信息 = 数据字典["xml"]["ApprovalInfo"]
            审批单号 = 审批信息["SpNo"]
            审批状态 = 审批信息["SpStatus"]  # 2 表示审批通过已生效
            
            如果 审批状态 == 2:
                连接 = get_db_connection()
                游标 = 连接.游标()
                尝试:
                    # 将通过的审批单入库，保存至 approvals 表中，便于审计引擎勾稽
                    游标.执行 """
                    INSERT INTO approvals (approval_no, wecom_userid, approval_type, status)
                    VALUES (审批单号, 申请人UserId, 审批单名称, 'approved')
                    ON CONFLICT (approval_no) DO UPDATE SET status = 'approved';
                    """
                    提交事务
                最后:
                    关闭连接
        
        返回 文本响应("success")
    捕获 异常 并记录日志:
        # 即使失败也必须返回 "success"，防止企业微信重复发起推送
        返回 文本响应("success")


# ＝＝＝＝＝ 2. 考勤审计任务手动/定时触发端点 ＝＝＝＝＝

路由 POST "/audit/run" (AuditRequest, background_tasks):
    # 手动触发每日对账或月度决算
    解析日期 target_date = 从请求参数转换, 默认为昨日
    如果 请求要求最终决算 (req.is_final == True):
        background_tasks 异步执行：audit_engine.run_monthly_audit(target_date, is_final=True)
        返回 {"status": "success", "message": "月度终审对账任务已加入后台队列"}
    否则:
        background_tasks 异步执行：audit_engine.run_daily_audit(target_date)
        返回 {"status": "success", "message": "每日对账任务已加入后台队列"}

路由 POST "/audit/monthly" (MonthlyAuditRequest, background_tasks):
    # 手动触发月度预估 (草稿) 或终审
    解析日期 target_date = 从请求参数转换, 默认为今天
    background_tasks 异步执行：audit_engine.run_monthly_audit(target_date, is_final=req.is_final)
    返回 {"status": "success", "message": "月度对账任务已加入后台队列"}

路由 POST "/audit/weekly" (background_tasks):
    # 手动触发周报生成
    background_tasks 异步执行：audit_engine.run_weekly_audit()
    返回 {"status": "success", "message": "周报生成任务已加入后台队列"}

路由 POST "/audit/check_expiry" (background_tasks):
    # 手动触发 7 天超期调休预警扫描
    background_tasks 异步执行：audit_engine.check_compensatory_leave_expiry()
    返回 {"status": "success", "message": "调休超期预警扫描已加入后台队列"}


# ＝＝＝＝＝ 3. 国家法定节假日管理接口 ＝＝＝＝＝

路由 GET "/holidays" (year):
    连接数据库查询 national_holidays 中属于指定年份的所有节假日及调班工作日记录
    返回 序列化列表

路由 POST "/holidays" (HolidayEntry):
    插入或更新单条节假日/调班工作日记录 (holiday_date, day_type, description) 到 national_holidays 表

路由 DELETE "/holidays/{holiday_id}":
    从 national_holidays 表中物理删除指定的节假日记录 ID

路由 POST "/holidays/seed/{year}":
    # 自动初始化调用
    结果 = 调用 audit_engine.seed_national_holidays(year)
    返回 结果

路由 POST "/holidays/annual_reminder" (background_tasks):
    # 手动触发给总经理的年末补录通知邮件任务
    background_tasks 异步执行：send_annual_holiday_reminder()
    返回 {"status": "success"}


# ＝＝＝＝＝ 4. 测试与运维工具 ＝＝＝＝＝

路由 POST "/test/send_email" (TestEmailRequest):
    # 测试 SMTP 配置是否通畅
    调用 mail_sender.send_html_email 发送一封测试邮件
    如果 发送成功 返回 200，否则抛出 HTTP 500

路由 GET "/":
    返回 {"status": "running"}
```

## 注意事项 / 坑
- 企业微信服务器在收到回调事件后，如果我们的 Webhook 接口没有在 **3 秒**内返回字符串 `"success"`，它就会认为推送失败并尝试重试多次。因此，所有耗时较长、包含大量数据库计算或网络拉取的对账动作（如 `/audit/run`），必须全部通过 FastAPI 的 `BackgroundTasks` 放到**后台异步执行**，Web 接口当场无条件返回 `"success"` 或状态包。
- Webhook 接口在捕获解密异常或数据库异常时，最终也要向企业微信回复 `"success"` 字符串。如果不这么做，会导致企业微信由于多次重试失败而封禁回调服务。
