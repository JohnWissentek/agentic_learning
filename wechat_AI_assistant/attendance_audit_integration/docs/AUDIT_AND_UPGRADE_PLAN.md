# 企业微信考勤审计系统：现网实盘审计报告与两阶段升级方案

> **审计日期**：2026-11-29  
> **审计范围**：历史项目目录合并去重 + 源码静态核查 + 维恩科仪企业微信管理后台（Chrome DevTools 严格只读实盘盘点）  
> **关联基准**：[PRD.md](PRD.md)（v0.7）、[wecom_live_inventory.md](reference/wecom_live_inventory.md)、[wecom_openapi.md](reference/wecom_openapi.md)、[DEPLOYMENT.md](DEPLOYMENT.md)

---

## 一、战略边界：两阶段清晰拆分

| 阶段 | 定位与数据源 | 金蝶差旅报销交叉审计（F15） | 状态 |
|---|---|---|---|
| **一阶段（当前执行）** | **依靠企业微信独立完成考勤分析**：打卡流水 + 5 类假勤审批 + 假期余额与逾期台账 + 6 类工作日报/现场工作报告/晨会简报 | 暂由**财务人工核对**（保留代码内 F15 只读骨架，不作为一阶段交付阻塞） | 🚀 本轮实施 |
| **二阶段（后续联动）** | 待金蝶侧实现 **Agent 自动化报销与数据分析** 后，与企业微信考勤合并执行**双向自动化交叉审计**（企微出差审批 + 现场工作报告 ↔ 金蝶报销单/补助减半/餐补） | 自动化双向交叉审计 | ⏸️ 待金蝶 Agent 落地 |

---

## 二、企业微信现网考勤相关 5 大数据支柱

通过 Chrome DevTools 严格只读巡检维恩科仪企业微信管理后台，已确认与考勤直接相关的 5 大模块及精确标识：

### 2.1 打卡（考勤）（`AgentId: 3010011`）
- **唯一规则组**：`考勤打卡规则20260829`（`groupid: 4`，14 人打卡 + 徐宏玮/杨丽丽 2 人免打卡）。
- **班次与弹性**：`08:30–17:00`（午休 `12:00–12:30`，标准 8h），弹性晚到 ≤90 分钟（最晚 `10:00` 上班对应 `18:30` 下班），可打卡窗 `08:29–19:00`；半天/按小时请假无需离返打卡；法定节假日免打卡。
- **方式与硬件**：手机 GPS（`纪家庙双创产业园` 100m + 活体人脸 + 拍照 + 禁相册，未配 Wi-Fi）+ **3 台在线得力云门禁 AL600CX**（`301南门`/`301北门`/`503南门`，人脸+指纹自动汇入打卡）。
- **外勤**：已开启「外勤需审批」且「自动同步外勤打卡至上下班打卡」。
- **加班转调休**：企微后台已配「工作日/休息日加班按审批+打卡 **1:1 自动计入调休假**；节假日计加班费」。
- **API 授权**：✅ `Hermes Agent`（`1000016`）已授权。

### 2.2 审批（5 个启用假勤模板，`AgentId: 3010040`）
| 模板名称 | `template_id` | 关键控件特点 |
|---|---|---|
| 请假 | `Bs8114rcQrU1NHmkaEctMKKRDqSCo9YEdCeLAfjmv` | `*Vacation`、事由、附件 |
| 打卡补卡 | `Bs7zz7rsMzoj5roRdLbs2anYNgm3L1ifMq442xHMZ` | `*PunchCorrection`、`*事由`、附件 |
| 加班申请 | `C4NvrtgmDKznbXFJCKEw5XGNyrw6dhLquQuNkq8Ze` | `*Attendance(type=5, 按小时)`、`*事由` |
| 外出申请 | `3WK7K6pXKXzaUwzDh9KmqtjXGUvMThtDGwHAKzHo` | `*外出地点(纯文本 Text，非 GPS)`、`*Attendance(type=4, 按小时)` |
| 出差申请 | `ZvVcpYA7cWdCjM3hr8aDhde5CXcYfGw2pVhiDP` | `*出差地点(纯文本 Text)`、`*Attendance(type=3, 按半天)` |

- **API 授权**：⚠️ `Hermes Agent` 有权限，但 **46 个模板均未勾选回调通知（0 个开启回调）**。

### 2.3 假期管理与余额/逾期
- **真实 `vacation_id` 映射（纠偏旧文档）**：`1=年假`、`2=事假`、`3=病假`、**`4=调休假`**（旧文档误写为 2）、`5–11=婚/产/陪产/其他/产检/育儿/哺乳`。
- **逾期与清零规则现状**：**全部 11 种假期均为「手动导入余额 + 永久有效 + 无自动清零/结转」**。
- **现网余额突出异常**：
  - 调休严重堆积：王旭 **`219.5h`（≈27.4天）**、石志同 `64.7h`、李文颖 `40h`、牛海庆 `38.5h`；
  - 年假堆积/未配工龄：陈晞 `74.1h`、吕旭东 `88h`、王旭 `58h`；16 人中 15 人未填「首次参加工作时间」；
  - 离职人员残留：刘页（离职）仍挂 `61.5h` 调休 + `24h` 病假，于艳丽（离职）挂 `2h` 年假；
  - 病假/婚产假卡死：在职全员余额为 `0` 且开启限额。

### 2.4 汇报（6 个启用模板，`AgentId: 3010041`）
| 模板名称 | `template_id` | 考勤审计核心作用 |
|---|---|---|
| **`现场技术支持工作报告`** | `C4ZW7hqyqemoDeSFqoGAyEoGMB1HdvfE78qzTv58B` | **含必填「客户现场确认签名（手机手写）」** → **F5 签字服务报告真身** |
| **`现场每日10分钟工作报告`** | `3WPHEvoCeoDFheRgDUVsyjpSUpfFr2WimsxeXGQ3` | 含日期、客户地点、图文明细 → **F4 出差日报真身** |
| **`研发性能测试/返厂维护日报`** | `3WN63QNme5LesazCsN6TrsJsF4G5ZGW6wNt5ryB8` | **唯一含必填「投入工时（小时）」** |
| **`每日10分钟工作日报`** | `C4c9RoeekLMSRRcqyurjgee3x7c6MUgPqN96rLmFr` | 14 人全员日常工作留痕（17:00 提醒） |
| **`财务每日10分钟工作简报`** | `3WPHEvnos5s9srSXWAqcs5hUgib4WwJYkb8yxAsZ` | 财务人员日常留痕 |
| **`晨会简报`** | `3WNhb5shbwE39YGY3xP8Uds7zUQCF8kNxKkYyWaP` | **含必填「当日请假/倒休/出差人员记录」**，天然人工交叉基准源 |

- **API 授权**：❌ **`Hermes Agent`（`1000016`）未获授权**（当前仅 `Project Kanban` `1000014` 在白名单内）。

### 2.5 周边关联模块
- 已启用 `得力云设备`、`考勤确认`、`人事助手`、`工资条`；二阶段金蝶侧已装 `星空应用管家`、`掌上报销`、`金蝶业务审批`。

---

## 三、本次审计揪出的 6 大根因缺陷（现网 vs 现代码/制度）

1. **审批数据完全断流**：企微 0 个模板开回调，而现代码只依赖 Webhook、**未实现 `oa/getapprovalinfo` 定时拉取**，导致 `approvals` 表在生产上无法自动获取请假/出差/外出/加班/补卡单。
2. **汇报接口路径写错 + 应用未授权 + 单模板局限**：
   - `wecom_api.py:184` 调用了不存在的 `/cgi-bin/oa/getreportdata`，实际官方接口是两步 `oa/journal/get_record_list` + `oa/journal/get_record_detail`；
   - `Hermes Agent` 无汇报权限；
   - 原先把《客户签字服务报告》误当成“企微无接口只能 mock”，实则就是汇报模板 `现场技术支持工作报告`（含必填手写签名）。
3. **假期 `vacation_id` 映射错误且无余额/逾期拉取**：旧文档误写调休 `id=2`（实际为 `4`），且现代码未接入 `oa/vacation/getcorpconf` 与 `getuservacationquota`，无法发现王旭 `219.5h` 堆积与离职人员残留余额。
4. **企微加班自动入池与 F5 签字把关存在口径冲突**：企微已配置加班审批+打卡 1:1 自动计入调休，系统应侧重「缺签字服务报告 → 标异常/通知 HR 复核核减」，避免与企微重复充值。
5. **企微现网补卡规则滞后于 8/21 制度**：制度取消坐班遗忘补卡，但企微仍允许每月 3 次全异常类型补卡。
6. **请假审批流存在配置瑕疵**：残留离职审批人、王楠分支顺序错位自审、杨震漏配部门分支。

---

## 四、一阶段（纯企微独立考勤分析）垂直薄切片实施清单

严格遵守《生产级工程宪章》：按 **Slice 1 → Slice 2 → Slice 3** 逐片以**黑盒 TDD（先红灯后绿灯）**交付，每片同步维护 `docs/ARCHITECTURE.md` 以确保 `check_traceability.py` 1:1 全绿：

### Slice 1：打通断流的「审批批量拉取」与「汇报官方两步接口」
- **配置与常量（`config.py`）**：
  - 内置 5 类核心假勤审批模板 ID 映射、6 类启用汇报模板 ID（含默认配置与 `.env` 覆盖项）、真实 `WECOM_VACATION_ID_ANNUAL = 1` / `WECOM_VACATION_ID_COMPENSATORY = 4`。
- **企微客户端升级（`wecom_api.py`）**：
  - 新增 `fetch_approval_ids(start_ts, end_ts, template_id=None)`（分页调用 `POST /cgi-bin/oa/getapprovalinfo`，单页 `size=100`，防死循环页数硬上限）；
  - 重写 `fetch_daily_reports` / 新增 `fetch_journal_record_list` + `fetch_journal_record_detail`（改用官方两步 `POST /cgi-bin/oa/journal/get_record_list` + `get_record_detail`，支持多模板 ID 批量拉取并兼容旧调用签名）。
- **审批与多模板汇报同步服务（`services/daily_audit.py`）**：
  - 新增 `parse_approval_detail(detail)` 纯函数（精确解析 `Vacation`/`Attendance`/`PunchCorrection`/`DateRange` 控件 → 统一映射 `approval_type`/`sub_type`/`start_time`/`end_time`/`duration_hours`/`status`）；
  - 新增 `sync_real_approvals(cursor, start_ts, end_ts)` 幂等落库 `approvals`（彻底摆脱仅靠 0 回调的盲区）；
  - 升级 `sync_real_daily_reports(cursor, start_ts, end_ts)`：解析官方 `journal` 详情结构，将《现场每日10分钟工作报告》《每日10分钟工作日报》等写入 `field_work_reports`，并将**《现场技术支持工作报告》**自动识别客户手写签名并幂等写入 `service_reports`（打通 F5 真实数据源！）。

### Slice 2：接入企业微信真实「假期余额与逾期堆积审计」
- **企微客户端扩展（`wecom_api.py`）**：
  - 新增 `fetch_vacation_corp_conf()`（`POST /cgi-bin/oa/vacation/getcorpconf`）与 `fetch_user_vacation_quota(userid)`（`POST /cgi-bin/oa/vacation/getuservacationquota`，秒→小时换算，严禁自动写回扣减）。
- **独立纯逻辑 + 同步分析服务（`services/vacation_audit.py`）**：
  - 新增 `sync_and_audit_vacation_balances(cursor=None)`：拉取企微真实年假(`id=1`)与调休(`id=4`)余额，幂等同步至 `vacation_balances`；
  - 确定性风控规则（只告警、不自动扣减）：
    1. **调休堆积预警**：单人调休余额 ≥ `32h`（4 天，可配置阈值，如王旭 `219.5h` / 石志同 `64.7h`）标记堆积并定向推送 PM（孔紫初、王楠，CC 徐宏玮、薛蕾，严守 F11 不发本人规则）；
    2. **年假跨年/超额核查**：单人年假余额 > `40h`（5 天）或无「首次参加工作时间」提示 HR 核对；
    3. **离职人员残留余额检测**：状态非在职但余额 > 0（如刘页/于艳丽）提醒 HR 清理；
    4. **病假 0 余额限额提示**：检测全员病假限额为 0 风险。
- **门面与 CLI 接线**：在 `audit_engine.py` 暴露 `run_vacation_balance_audit()`，在 `cli.py` 新增 `vacation-audit` 子命令。

### Slice 3：日审/月审闭环融合 + 架构图与全量回归验证
- **日审闭环（`services/daily_audit.py`）**：
  - `run_daily_audit` 自动串联 `sync_employee_roster` → `sync_real_punches` → `sync_real_approvals` → `sync_real_daily_reports`（含 `service_reports` 签字提取），同时保留出差无日报/加班缺签字预警线索；
  - 兼容外勤/请假审批（含外出 `outing`、补卡 `punch_correction` 审批记录识别）。
- **月审与报表（`services/monthly_audit.py`）**：
  - 月审前自动同步当期审批、汇报与真实假期余额，避免因漏回调导致误判旷工或漏算请假/调休。
- **架构图与全量验证**：
  - 同步更新 `docs/ARCHITECTURE.md`（新增 `services/vacation_audit.py` 节点与依赖边），确保 `tools/check_traceability.py` 100% 边对齐；
  - 补全并运行全部单元测试（含 Slice 1/2/3 新增黑盒测试与全部既有 79 项测试）。

---

## 五、企微后台配合事项执行状态（2026-11-29 实时更新）

| 项 | 优先级 | 事项 | 当前状态 |
|---|---|---|---|
| 1 | 🔴 P0 | 给 `Hermes Agent`（`1000016`）开通「汇报」API 权限 | ✅ **已完成并后台二次核验**（当前授权列表：`Project Kanban` + `Hermes Agent`） |
| 2 | 🟡 P1 | 清理离职人员假期余额（刘页/于艳丽）、复核王旭 219.5h 等期初余额、病假 0 限额与 15 人首次工作时间 | ⏳ **待负责人周一与同事核对**（本次未触碰「假期余额」任何数据） |
| 3 | 🟡 P1 | 修复「请假」审批流分支（清理 5 名离职人员、修王楠自审、补入杨震至 `产品开发` 分支） | ✅ **已完成并服务端二次核验生效** |
| 4 | 🟡 P1 | 对齐 `考勤打卡规则20260829` 补卡与加班规则（补卡收紧至 2 次/月且仅限缺卡/旷工；工作日/休息日加班取消自动计入调休、改为仅统计时长；节假日保持加班费） | ✅ **已完成并立即生效、二次核验通过** |
