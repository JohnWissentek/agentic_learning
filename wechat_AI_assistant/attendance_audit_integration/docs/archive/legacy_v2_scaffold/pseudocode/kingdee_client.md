# kingdee_client.py 伪代码（F15，v0.5 新增）

## 本文件职责（一句话）
金蝶云星空 Web API 只读客户端：仅封装 LoginByAppSecret（登录）与 ExecuteBillQuery（单据查询），供 F15 交叉审计拉取差旅报销单——严禁写接口。

## 对应PRD功能
F15；异常场景 E32（登录/查询失败由调用方降级处理）

## 依赖
- 调用：httpx（与 wecom_api 同栈）、config（KINGDEE_*）、logger
- 被调用：services.expense_cross_audit

## 伪代码

常量 _LOGIN_PATH / _QUERY_PATH = 金蝶 WebApi 标准路径；_LCID_ZH_CN=2052；超时 30s

异常类 KingdeeAuthError / KingdeeQueryError

类 KingdeeClient:
    __init__: httpx.Client(base_url=KINGDEE_BASE_URL)，未登录态
    静态 is_configured() -> bool: 五个 KINGDEE_* 环境变量齐全才 True
    login():
        POST LoginByAppSecret(acctID/username/appid/appsecret/lcid)
        HTTP 错误 → raise_for_status 上抛
        LoginResultType != 1 → 抛 KingdeeAuthError（含 Message）
        成功 → 标记已登录，INFO 日志
    query_expense_bills(filter_string, field_keys, limit=2000) -> 行列表:
        未登录 → 抛 KingdeeAuthError
        POST ExecuteBillQuery(FormId=KINGDEE_EXPENSE_FORM_ID, FieldKeys, FilterString, TopRowCount)
        返回 dict（而非行数组）说明查询失败 → 抛 KingdeeQueryError
    close(): 关闭 http 会话

## 异常与边界（必填）
- 本文件处理：登录结果码校验、查询返回类型校验（dict=错误对象）
- 故意往上抛：KingdeeAuthError / KingdeeQueryError / httpx.HTTPStatusError——由 expense_cross_audit 统一重试+降级（E32），本层不吞
- 边界条件：凭证缺失时 is_configured()=False，调用方不应实例化后直接 login；TopRowCount 上限 2000（编制 <20 人月度单据远低于此）

## 注意事项 / 坑
- FormId 默认 ER_ExpenseRequest，须按企业真实账套确认（可经 .env KINGDEE_EXPENSE_FORM_ID 覆盖）
- 金蝶账号申请只读查询权限即可（最小权限）；严禁在本文件添加 Save/Audit/Delete 封装
