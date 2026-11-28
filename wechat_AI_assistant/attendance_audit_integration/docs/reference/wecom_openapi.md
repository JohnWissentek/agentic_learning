# 企业微信 OpenAPI 考勤与假勤接口参考（wecom_openapi.md）

> **定位**：纯接口契约与工程现状对照表（不重复定义考勤业务制度；业务规则以 `../PRD.md` 为唯一事实来源）。  
> **最后校准**：2026-11-29  
> **红线**：严禁自动同意/驳回审批单；严禁未经确认静默扣减员工假期余额；所有密钥仅放 `.env`。

---

## 一、接口实现现状总览

| 业务域 | 官方接口路径 | 用途 | 当前代码状态（`wecom_api.py` / `main.py`） |
|---|---|---|---|
| 鉴权 | `GET /cgi-bin/gettoken` | 获取并缓存 `access_token`（有效期 7200s） | ✅ 已实现（内存缓存 + 提前 200s 刷新） |
| 通讯录 | `GET /cgi-bin/user/list` | 拉取部门成员花名册 | ✅ 已实现（`fetch_users`） |
| 打卡流水 | `POST /cgi-bin/checkin/getcheckindata` | 拉取原始上下班/外出打卡流水（单批 ≤100 人，跨度 ≤30 天） | ✅ 已实现（`fetch_punches` 自动分批） |
| 打卡日报/月报 | `POST /cgi-bin/checkin/getcheckin_daydata`<br>`POST /cgi-bin/checkin/getcheckin_monthdata` | 拉取企微后台统计的考勤日报/月报基准 | ⬜ 未实现（后续一阶段升级按需接入） |
| 打卡规则 | `POST /cgi-bin/checkin/getcheckinoption` | 拉取员工所属打卡规则组、围栏与班次配置 | ⬜ 未实现 |
| 审批单号列表 | `POST /cgi-bin/oa/getapprovalinfo` | 按时间窗批量拉取审批单号（兜底补齐历史/漏回调单据） | ✅ 已实现（`fetch_approval_ids` + `sync_real_approvals` 自动遍历 5 类假勤模板） |
| 审批单详情 | `POST /cgi-bin/oa/getapprovaldetail` | 根据 `sp_no` 拉取完整审批表单控件与审批节点 | ✅ 已实现（`fetch_approval_detail` + `parse_approval_detail` 全控件解析） |
| 审批事件回调 | Webhook `sys_approval_change` | 审批单提交/通过/驳回/撤销实时推送 | ✅ 已升级（`main.py` 回调触发 `sync_single_approval` 回查完整详情落库） |
| **工作汇报/日报** | **两步官方接口**：<br>1. `POST /cgi-bin/oa/journal/get_record_list`<br>2. `POST /cgi-bin/oa/journal/get_record_detail` | 拉取工作日报、售后现场工作报告等汇报单据 | ✅ **已修复并上线代码**（支持全部 6 个启用模板，自动提取《现场技术支持工作报告》客户手写签名写入 `service_reports`；⚠️ 需人工在企微后台为 `Hermes Agent` 勾选汇报 API 权限） |
| 假期规则/余额 | `POST /cgi-bin/oa/vacation/getcorpconf`<br>`POST /cgi-bin/oa/vacation/getuservacationquota` | 查询企业假期类型 ID 及员工余额/已用/总额度 | ✅ 已实现只读同步与堆积/离职/逾期风险审计（`services/vacation_audit.py` + `cli vacation-audit`） |
| 假期余额写回 | `POST /cgi-bin/oa/vacation/setoneuserquota` | 经员工/HR 确认后写回调休余额（设定绝对值，单位秒） | ⬜ 未实现（对应 `docs/proposals/F16_vacation_ledger_rebuild.md`） |
| 消息通知 | `POST /cgi-bin/message/send`<br>`POST /cgi-bin/webhook/send` | 推送企微应用通知卡片或群机器人告警 | ⬜ 未实现（当前通知走邮件 SMTP） |

---

## 二、关键接口参数与换算约定

### 2.1 鉴权与公网 IP 白名单
- `GET https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=ID&corpsecret=SECRET`
- 自建应用须在企微后台配置「企业可信 IP」（生产 ECS 公网出口 IP），否则报错 `60020`。
- 全局频控参考：常规读接口约 **600 次/分钟**；遇到 `42001` / `40014` 需清空本地缓存并重新拉取 Token 重试；网络抖动或 `5xx` 采用指数退避（1s → 2s → 4s，最多 3 次）。

### 2.2 打卡原始记录（`/cgi-bin/checkin/getcheckindata`）
- `opencheckindatatype`: `1`=上下班，`2`=外出，`3`=全部（推荐填 `3`）。
- 单次请求：`useridlist` ≤ 100 人，`endtime - starttime` ≤ 30 天。
- 核心返回字段：`userid`、`groupname`、`checkin_type`、`exception_type`（`未打卡`/`地点异常`/`时间异常`/`wifi异常`/`非常规打卡`）、`checkin_time`（秒级时间戳）、`location_title`、`location_detail`、`lat`/`lng`（整数，除以 $10^6$ 得经纬度）、`wifiname`、`wifimac`、`notes`、`mediaids`、`deviceid`。

### 2.3 审批单批量拉取与详情（`/cgi-bin/oa/getapprovalinfo` + `getapprovaldetail`）
- **重要补缺**：不能只依赖 Webhook 推送（服务重启或配置缺失时会丢单），生产一阶段升级应补齐 `getapprovalinfo` 每日定时兜底拉取 + `getapprovaldetail` 解析完整控件。
- `sp_status` 枚举：`1`=审批中，`2`=已通过，`3`=已驳回，`4`=已撤销。
- 核心表单控件：`Vacation`（假期类型/起止/时长）、`DateRange`（出差/外出/加班区间）、`Location`（外出位置）、`Table`（多行程明细）、`File`（病假证明/现场服务报告附件）。

### 2.4 汇报/工作日报（官方两步接口，修正旧版错误路径）
> 旧代码 `wecom_api.py:184` 及旧方案文档误写了 `/cgi-bin/oa/getreportdata`，实际企微官方汇报 API 为两步调用：
1. **拉取汇报记录单号列表**：`POST https://qyapi.weixin.qq.com/cgi-bin/oa/journal/get_record_list?access_token=ACCESS_TOKEN`
   - 参数：`starttime`、`endtime`（跨度 ≤ 1 个月）、`cursor`、`limit`（最大 100）、`filters`（可按 `template_id`、`creator`、`department` 过滤）。
2. **拉取汇报详情**：`POST https://qyapi.weixin.qq.com/cgi-bin/oa/journal/get_record_detail?access_token=ACCESS_TOKEN`
   - 参数：`journaluuid`。
   - 返回：`info.apply_data.contents[]`（按模板内各控件 `id` 与 `control` 类型提取文本、日期、附件/图片等）。
3. **权限前提**：在企微后台「应用管理 → 汇报 → API → 可调用接口的应用」中，必须将本系统使用的自建应用加入白名单。

### 2.5 假期规则与余额（`/cgi-bin/oa/vacation/*`）
- 查询假期类型配置：`POST /cgi-bin/oa/vacation/getcorpconf`（获取年假、调休假等 `vacation_id` 与计价单位 `time_attr`）。
- 查询个人余额：`POST /cgi-bin/oa/vacation/getuservacationquota`（返回 `quota`、`used`、`balance`）。
- 修改剩余余额：`POST /cgi-bin/oa/vacation/setoneuserquota`（传入 `leftquota` 为**设定后的绝对剩余秒数**，写回前必须先读后写并留审计流水；仅限经员工/HR 确认后执行）。
- **单位换算**：企微内部统一按秒计，1 小时 = `3600` 秒，1 天 = `8` 小时 = `28800` 秒。
- **现网真实 `vacation_id`**（2026-11-29 后台实测，纠正旧文档误写的 `2=调休`）：`1`=年假、`2`=事假、`3`=病假、**`4`=调休假**、`5`–`11`=婚假/产假/陪产假/其他/产检假/育儿假/哺乳时间。

---

## 三、核心错误码速查

| `errcode` | 含义 | 处理策略 |
|---|---|---|
| `0` | 成功 | 正常处理 |
| `40014` / `42001` | Token 无效 / 过期 | 清空缓存，重新 `gettoken` 后重试 1 次 |
| `60020` | IP 不在可信白名单 | 打 CRITICAL 日志并告警运维检查 ECS 公网 IP |
| `301005` | 打卡规则 ID 无效 | 刷新本地规则缓存 |
| `301011` | 员工未分配假期规则 | 记录待办并提醒 HR 补配 |
| `-1` | 企微服务端繁忙 | 指数退避重试 |

---

## 四、官方文档索引

- [企业微信服务端 API 首页](https://developer.work.weixin.qq.com/document/path/90213)
- [获取打卡数据](https://developer.work.weixin.qq.com/document/path/90262)
- [获取审批数据](https://developer.work.weixin.qq.com/document/path/90269)
- [汇报（工作日报）API](https://developer.work.weixin.qq.com/document/path/93393)
- [假期管理 API](https://developer.work.weixin.qq.com/document/path/93376)
- [全局错误码](https://developer.work.weixin.qq.com/document/path/90313)
