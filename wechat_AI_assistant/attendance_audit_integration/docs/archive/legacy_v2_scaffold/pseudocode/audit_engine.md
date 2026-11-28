# audit_engine.py 伪代码

## 本文件职责（一句话）
考勤审计门面（Facade）：不含业务逻辑，仅 re-export 各子模块公开 API，保持旧 import 路径向后兼容。

> v0.4 起：原 1113 行已拆分为 geo.py / holiday.py / payroll_cycle.py / compensatory.py + services/{daily_audit,weekly_audit,monthly_audit,expiry_checker,roster_sync}.py。本文件保留门面约 70 行。

## 对应PRD功能
F1、F2、F4、F5、F6、F7、F8、F9、F14、F15；异常场景 E1–E8、E11–E13、E15–E20、E22–E33；F13 GPS 围栏强校验归**二期**（一期不接日审）

## 依赖
- re-export: geo, holiday, payroll_cycle, compensatory, work_hours（v0.5 新增：动态工时判定）, services.daily_audit（含 run_daily_audit / sync_real_punches / sync_real_daily_reports）, services.weekly_audit, services.monthly_audit, services.expiry_checker, services.roster_sync, services.expense_cross_audit（F15）
- 被调用：cli.py、main.py、mock_data_populator.py（复用 is_workday_db / sync_real_punches / sync_real_daily_reports，走门面而不直接 import services，保持"外部只碰门面"的约定）

## 伪代码

### 地理与日历助手

函数 calculate_haversine_distance(lat1, lon1, lat2, lon2) -> 公里:
    地球半径 6371km，Haversine 大圆距离

函数 is_workday_db(target_date, cursor=None) -> bool:
    查 national_holidays:
        day_type=workday → True（调班补班）
        day_type=holiday → False（法定假）
        无记录 → 默认周一至周五 True，周末 False
    无游标时自开连接并在 finally 关闭

函数 is_statutory_holiday(target_date, cursor=None) -> bool:
    仅当库中存在 day_type=holiday 的当日记录 → True

函数 seed_national_holidays(year) -> dict:
    一次性用 chinese_calendar 种子写入（运行时审计不依赖该库）
    法定假写入 holiday；周末且需上班写入 workday
    ON CONFLICT DO NOTHING；返回 inserted/skipped；缺库返回 error

函数 send_annual_holiday_reminder():
    邮件提醒总经理录入下一年法定假（F9 年底维护）

### 薪资周期（关键业务规则）

函数 get_payroll_cycle_start(reference_date) -> date:
    若日 ≥ 26: 本月 26 日；否则上月 26 日

函数 get_monthly_cycle_range(target_date) -> (start, end, audit_month标签):
    # 周期：上月 26 日 – 本月 25 日
    若 target_date.day ≥ 25:
        end = 本月 25 日
        start = 上月 26 日
    否则:
        end = 上月 25 日
        start = 再上月 26 日
    audit_month = end 的「YYYY年MM月」
    返回三元组

### AuditEngine

#### sync_employee_roster（F8）
    users = wecom_client.fetch_users()
    若空: WARNING 返回 []
    对每个企微返回的 (userid, name):
        先按 name 查 employees 是否已有记录
        若有且 wecom_userid 不同: UPDATE 该行的 wecom_userid/email/role/company（企微 userid
            并非稳定不变——2026-07-14 生产实测出现大小写变化及历史合并遗留的
            "userid@corp别名" 后缀，若仍按 wecom_userid 做 UPSERT 主键会插出重复行、
            造成同一人收到两封审计邮件，其中一封还带着已废弃的错误邮箱域名）
        否则: 按 wecom_userid UPSERT 插入/更新（真正新员工的路径）
    对每用户 UPSERT employees（userid/name/email/role/company）
    部门粗分签约公司；入职日暂用占位
    提交；失败 rollback 上抛

#### sync_real_punches(cursor, employee_ids, start_ts, end_ts) -> 写入条数（新抽出的公共函数）
    拉取企微指定窗口打卡 → 写入 attendance_logs（类型映射上班/下班/外勤；经纬度 /1e6；
    exception_type 忽略「未打卡」；UNIQUE(userid,clock_time,clock_type) 幂等去重 E23）
    供 run_daily_audit 与 mock_data_populator.populate_test_data 复用，避免两处字段映射各写一份

#### sync_real_daily_reports(cursor, start_ts, end_ts) -> 写入条数（新增，修复生产缺口）
    拉取企微指定窗口外勤/出差日报 → 写入 field_work_reports
    自建应用表单 control_list 无固定 schema，字段抽取为最佳努力递归扫描（非精确解析，raw_payload 落全量兜底）
    ⚠️ 此前 wecom_api.fetch_daily_reports 已实现但从未被调用，field_work_reports 在生产环境
       实际从未被真实数据填充过——F4 出差日报核查此前只能看见 mock 数据，本次补上生产接线

#### run_daily_audit(target_date)（F1、F2、F7）
    记日志开始；开连接
    每次都先 sync_employee_roster（2026-07-14 修复：原来只在 employees 为空时才同步，
    导致花名册邮箱域名纠错/新增离职/改名等永远无法在生产库里生效——一旦表非空这条
    同步就再也不会跑；改成每次运行都同步，代价是多一次企微 API 调用，可接受）
    取 status=active 员工
    sync_real_punches(...) + sync_real_daily_reports(...) 写入当日真实打卡与日报
    排除高管徐宏玮、杨丽丽不参与考核
    is_workday = is_workday_db(target_date)

    对每名考核员工:
        查覆盖当日的已通过审批；查当日打卡
        has_leave / has_trip
        # —— 三维防作弊 F2 ——
        若打卡带 exception_type: 标 device_anomaly（E11）
        若相邻打卡均有坐标且时速 > 350km/h: 标 location_anomaly（E12）
        # —— 勾稽 F1（v0.5 动态工时判定，制度 3.1.1/3.1.2/3.2.1） ——
        若全天假: status=leave（有作弊标记则保留异常）
        否则若出差: status=business_trip
        否则若工作日:
            计入应到
            无打卡 → absent 全日缺勤预警（E1；处分走人工）
            仅 1 次打卡 → pending_single_punch（跨度不可算，标待核推人工；
                          ❗不再自动折 0.5 天——旧口径已废，E1）
            ≥2 次且无作弊 → evaluate_work_hours(punches, approved_partial_leaves):
                start_eff = max(首个上班卡, 08:30)                    # 早到从 08:30 起算
                required = 8.5h；若当日午休(用餐+小憩)满 1h → 9.0h     # E29
                cap = 18:30；若 required=9.0h → 19:00
                end_eff = min(末个下班卡, cap)                        # 晚走多坐不计 E24
                required -= 当日已批短假小时数                        # 请假顺延 10:00+N 由此自然成立 E30
                span = end_eff - start_eff
                actual_work = span - 午休扣除(默认 0.5h，满 1h 场景扣 1h)
                若 span ≥ required → normal
                否则若 actual_work ≥ 4h → pending_reconciliation：
                    缺额小时 = required - span
                    勾稽当日已批冲抵/核销审批后仍缺 → 缺额邮件
                    累计当月被动抵扣；>4h 部分按无酬缺勤公式导出（E27）
                    当月被动抵扣 >2 次 → 标主管面谈
                否则（actual_work < 4h 且无审批）→ absent 旷工 1 天预警（E17）
        否则: status=rest

        UPSERT daily_attendance（异常写 is_anomaly 与原因）
        若异常:
            渲染个人异常邮件（含 T+2 截止提示）→ 发本人 + CC ADMIN_EMAILS
            加入日汇总明细行
    渲染公司日汇总邮件 → 发 ADMIN_EMAILS[0]，抄送其余
    提交；返回 {total_expected, total_normal, total_anomalies}
    异常: rollback，记 ERROR，上抛

#### check_compensatory_leave_expiry()（F6 / F11 催用）
    查 status=released 且未用完的调休流水
    若距 accrual_date ≥ 8 天:
        发超期警告邮件（To PM_EMAILS[0]，CC PM_EMAILS[1:] + F11_CC_EMAILS）
        ❗ PRD v0.4：TO 孔紫初、王楠；CC 徐宏玮、薛蕾；禁止发/抄送被催员工
        写 audit_logs(overdue_leave_alert)
    返回通知条数；失败 rollback 上抛
    # 注意：不自动清零余额（只催告）

#### run_weekly_audit()（F7）
    上周周一～周日
    统计异常条数；用补卡审批粗算已核销数
    按人汇总残留异常行
    自 get_payroll_cycle_start(今天) 起累计缺卡 ≥2 次 → 高危名单
    渲染周报邮件 → ADMIN_EMAILS
    失败记 ERROR 上抛

#### run_monthly_audit(target_date, is_final=False)（F4、F5、F6、F7、F14）
    start, end, audit_month = get_monthly_cycle_range(target_date)
    用 is_workday_db 累计周期标准工作日数

    若 is_final（终审 / 对应 26 日）:
        对每名考核员工:
            # F5：周末加班 vs 客户签字服务报告
            对周期内已通过 overtime:
                若存在当日 is_customer_signed 服务报告:
                    写入 compensatory_leave_details(status=released)
                    累加 vacation_balances.compensatory
                否则:
                    写入 status=invalid（拒绝调休，E6）
            # F4：出差日 vs 带水印日报
            对周期内 business_trip 覆盖的每个工作日:
                若无 watermark_image_url 的 field_work_reports:
                    UPSERT daily_attendance 异常「出差日缺失现场工作日报或环境水印照片」（E7）

    汇总每人:
        缺勤核算（v0.5）：旷工预警日（<4h 无审批）×1 天；缺额小时合计；
            被动抵扣已用小时（月上限 4h）；超限部分按无酬缺勤公式
            （月基本工资÷21.75÷8×缺勤小时）生成导出行——只导出，禁止代扣
        事假 unpaid_leave 小时 /8 → 天
        调休：本期新增 released 小时、本期消耗、结转估算、当前余额

    # F15 金蝶差旅报销交叉审计：独立 CLI 命令 `cli expense-cross`（建议 25 日随
    # 月审草稿的 Cron 顺序触发）。编排在 cli 层——Services 之间互不调用（§3.0a 铁律），
    # 月审不直接 import expense_cross_audit。详见 expense_cross_audit.md

    若 is_final:
        收集 invalid 加班拦截说明
        统计周期内未解消异常数
        渲染终审邮件（扣薪天数 + 调休结转表）
        subject 含「最终锁定版」
        # F14：终审成功写入 payroll_period_locks；重复终审拒绝（E18）
    否则（草稿 / 对应 25 日）:
        统计待申诉异常、未通过审批、缺出差日报数
        渲染草稿快报邮件

    发送月报至 ADMIN_EMAILS；提交；返回 True
    失败 rollback 上抛

模块级单例: audit_engine = AuditEngine()

## 异常与边界（必填）
- 本文件处理：各公开方法内 try/except → rollback + ERROR + 重新抛出；日历助手在自管连接时保证关闭
- 故意往上抛：企微 token 失败、数据库错误、未预期异常 → cli/main 转为非 0 或后台任务失败日志
- 边界条件:
  - 空花名册：日审先同步；仍空则 early return 零统计
  - 重复日审：依赖 daily_attendance UNIQUE UPSERT；新建库 attendance_logs 含 UNIQUE(wecom_userid, clock_time, clock_type)（E23）
  - 非工作日无请假出差：记 rest，不告缺卡
  - 请假/出差期间仍可因 F2 作弊标记保持异常
  - 法定假加班转入调休：decide_compensatory_accrual 强制 invalid（E5 已落地）
  - 封账后重跑终审：payroll_period_locks 已存在则 RuntimeError（E18 已落地）；草稿可重复
  - 邮件失败：mail_sender 返回 False，日审仍提交库（人可能收不到信，须看日志 E22）

## 注意事项 / 坑
- 月审周期切勿写成「自然月 1–月底」或旧稿「每月 5 日」；唯一口径：上月26–本月25；Cron：25 草稿、26 `--final`
- get_monthly_cycle_range：day≥25 用「本月 25」为期末；day<25 回退到「上月 25」为期末——25/26 当天跑才对齐当月薪资周期
- Haversine 单位是公里；阈值阈值是 350 km/h，时间差用小时，time_delta=0 跳过防除零
- 企微 lat/lng 常为整数微度，必须 /1e6
- 徐宏玮、杨丽丽姓名与 UserID 双条件排除，改名单时两处都改
- seed_national_holidays 仅引导数据；生产以手工/API 维护 national_holidays 为准（F9）
- F8 本地 JSON 花名册（data/employee_roster.json）在 sync_employee_roster 中合并邮箱；禁止 xlsx
- sync_employee_roster 按 name 优先匹配再决定 UPDATE/INSERT（见上）；历史 attendance_logs/approvals
  里保存的是旧 wecom_userid 字符串快照，不会被这次 rename 回填——员工 userid 变更前后的历史记录
  按“旧值”分段存在，属已知限制，暂不做跨版本 userid 归并
- P1 未做：F10 大交通、F12 审批重叠；F13 GPS 围栏强校验归**二期**（一期不接日审），判定函数 ≤200m/>200m 已就绪
- 已有库需再跑 `cli init-db` 以创建 `payroll_period_locks` 与 `test_data_provenance`
- sync_real_daily_reports 的字段抽取（work_summary/watermark_image_url）是最佳努力递归扫描，非按企业真实模板 control_id 精确解析；拿到真实模板结构后应改精确抽取（PRD 待定项）
- 一期硬参数（PRD v0.5 §4.1，制度 2026-08-21 版）：打卡大区间 8:30–18:30（顺延日 19:00）；动态工时 = 上班卡+8.5h（午休满 1h → 9.0h）；早到从 08:30 起算；封顶 18:30/19:00；被动抵扣月 4h 上限；坐班取消遗忘补卡；加班无月上限；在途调休 ≤2h/2–4h=0.5天/>4h=1天；无酬缺勤 = 月基本工资÷21.75÷8×小时；调休可延至次年头两月
- ❗判定禁止写死 10:00：全勤到岗截止是 18:30−8.5h 的推导值，请假日为 10:00+N、9.0h 顺延日同为 10:00——一律按公式计算
- F15 金蝶侧只读；失败降级不阻塞；差异只标「待核」，不回写、不扣发
