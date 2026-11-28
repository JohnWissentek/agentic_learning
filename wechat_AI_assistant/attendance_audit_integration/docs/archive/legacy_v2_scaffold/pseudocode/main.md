# main.py 伪代码

## 本文件职责（一句话）
FastAPI 入口：企微 Webhook 验签入库、后台触发日/周/月审与调休超期扫描、法定节假日 CRUD/种子、SMTP 联调。

## 对应PRD功能
F1、F7、F9、F14（Webhook 审批与审计触发）；异常场景 E18（封账语义由月审承担）、E20、E22

## 依赖
- 调用：config、db、audit_engine、mail_sender、logger、wxbiz_msg_crypt、xmltodict、fastapi
- 被调用：无（进程入口 uvicorn / `python -m` 托管）

## 伪代码

启动时 startup_event:
    尝试 config.validate() 与 init_db()
    捕获异常: 记 CRITICAL（服务可起来但库不可用须人工介入）

全局 wxcrypt = 尝试 WXBizMsgCrypt(TOKEN, AES_KEY, CORPID)
    若 TOKEN/AES_KEY 未配置或格式非法(ValueError，如 AES_KEY 非 43 位):
        记 WARNING，wxcrypt = None（不得让此可选功能拖垮整个服务的启动——
        日/周/月审、催办等核心接口不依赖 wxcrypt）

GET /webhooks/approval:
    若 wxcrypt is None → HTTP 503（未配置）
    尝试 wxcrypt.verify_url → 明文 echostr
    失败 → HTTP 400

POST /webhooks/approval:
    若 wxcrypt is None → 记 ERROR，仍返回 "success"（避免企微重试；功能性禁用不等于故障）
    读 body → decrypt_xml_msg → xmltodict
    若 Event == sys_approval_change 且 SpStatus == 2(已通过):
        UPSERT approvals(approval_no, userid, type, status=approved)
    任意异常: 记 ERROR，仍返回 "success"（避免企微疯狂重试）
    正常返回 "success"

POST /audit/run:
    解析 audit_date（默认昨天）；非法日期 → 400
    若 is_final: 后台 run_monthly_audit(..., is_final=True)
    否则: 后台 run_daily_audit(target_date)
    立即返回 queued

POST /audit/monthly:
    后台 run_monthly_audit(date 默认今天, is_final)
    返回 draft/final queued

POST /audit/weekly → 后台 run_weekly_audit
POST /audit/check_expiry → 后台 check_compensatory_leave_expiry

节假日 API（F9）:
    GET /holidays?year → 列表
    POST /holidays → day_type 仅 holiday|workday，UPSERT
    DELETE /holidays/{id} → 404 若不存在
    POST /holidays/seed/{year} → seed_national_holidays；缺库则 500
    POST /holidays/annual_reminder → 后台 send_annual_holiday_reminder

POST /test/send_email → send_html_email；失败 500
GET / → {status: running}

## 异常与边界（必填）
- 本文件处理：日期格式、day_type 非法 → 400；Webhook 解密失败 GET 拒绝、POST 记日志仍 success
- 故意往上抛：后台任务内异常由引擎自己记日志；HTTP 层不吞 500（除 Webhook POST 策略）
- 边界：审计接口异步排队，调用方拿到 success 不代表审计已跑完；审批 Webhook 当前字段映射粗粒度（SpName→approval_type），完整明细需后续拉 getapprovaldetail

## 注意事项 / 坑
- 依赖方向与架构图一致：main → audit_engine、wxbiz、config；另直接用 db/mail_sender 做 Webhook 与测信
- `@app.on_event("startup")` 在新版 FastAPI 可能弃用，迁移 lifespan 时保持 validate+init_db
- 月审「封账」当前靠 is_final 业务语义，尚无独立 lock 表——E18 完整落地需后续加固
- 2026-07-14 生产事故复盘：`.env` 未配置 `WECOM_ENCODING_AES_KEY` 时旧代码在模块加载期直接崩溃，导致整个 uvicorn 进程无法启动（日审/周审/月审全部遭殃）；已改为 try/except 降级为 wxcrypt=None + 503，回调功能与核心审计功能解耦
