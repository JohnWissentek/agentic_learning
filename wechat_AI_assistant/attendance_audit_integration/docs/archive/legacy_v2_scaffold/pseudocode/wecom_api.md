# wecom_api.py 伪代码

## 本文件职责（一句话）
封装企微 OpenAPI：access_token 缓存续期，拉取通讯录、打卡、审批详情与日报列表。

## 对应PRD功能
F1（打卡）、F8（成员列表）、F4（日报，现由 `services/daily_audit.sync_real_daily_reports` 消费，不再是预留接口）；异常场景 E20

## 依赖
- 调用：config.settings、logger、httpx
- 被调用：audit_engine（wecom_client）

## 伪代码

类 WeComAPIClient:
    初始化:
        保存 corpid、secret
        _access_token = None
        _token_expires_at = 0

    函数 get_access_token():
        若缓存未过期: 返回缓存 token
        GET gettoken(corpid, corpsecret)，超时 10s
        若 errcode == 0:
            缓存 token，过期时间 = now + expires_in - 200 秒
            返回 token
        否则: 抛异常（记 ERROR）
        网络异常: 记 ERROR 后上抛

    函数 fetch_users(department_id=1):
        token = get_access_token()
        GET user/list，fetch_child=1，超时 15s
        成功返回 userlist；业务错误或异常: 记 ERROR，返回 []

    函数 fetch_punches(start_ts, end_ts, user_ids):
        POST checkin/getcheckindata，opencheckindatatype=3（全部打卡）
        成功返回 checkindata；失败返回 []

    函数 fetch_approval_detail(approval_no):
        POST oa/getapprovaldetail
        成功返回 info；失败返回 {}

    函数 fetch_daily_reports(start_ts, end_ts):
        POST oa/getreportdata（模板 ID 为配置占位）
        成功返回 report_list；失败返回 []

wecom_client = WeComAPIClient()  # 模块单例

## 异常与边界（必填）
- 本文件处理：token 获取失败上抛；拉取类接口失败降级为空列表/空字典并打 ERROR（调用方须判断空结果，不可当「全员正常」）
- 故意往上抛：get_access_token 失败 → 日审整体失败（符合 ARCHITECTURE §9 快速失败）
- 边界：userid 列表过长时企微有条数限制（需分批，当前 MVP 未分批）；token 提前 200s 刷新防边界过期；超时固定 10/15s

## 注意事项 / 坑
- fetch_users / fetch_punches 失败返回空：audit_engine 必须区分「真无数据」与「API 失败」，否则会漏告警（E20）
- 经纬度企微常以整数×1e6 返回，转换在 audit_engine 侧完成
- 日报 template_id 来自 `.env` 的 `WECOM_DAILY_REPORT_TEMPLATE_ID`；未配置则跳过拉取
- fetch_punches 已按 100 人一批拆分 useridlist
