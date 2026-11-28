# services/expense_cross_audit.py 伪代码（F15，v0.5 新增）

## 本文件职责（一句话）
只读拉取金蝶差旅/费用报销单，与企微出差打卡/日报判定的单日现场工时交叉核对差旅补助减半规则（制度 4.2.3），输出「补助待核」差异清单——不回写金蝶、不自动扣发。

## 对应PRD功能
F15；规则条文 §4.2-12；异常场景 E31（金额不符）、E32（金蝶 API 失败降级）、E33（客观等待待命只标待核）

## 依赖
- 调用：kingdee_client（LoginByAppSecret / ExecuteBillQuery，只读）、db、mail_sender、logger、config（KINGDEE_*、TRIP_ONSITE_HALF_SUBSIDY_HOURS=4.0）
- 被调用：services.monthly_audit（草稿日随月审跑）、cli（可单独触发 `cli expense-cross`）

## 伪代码

类 KingdeeClient（若复用外部 kingdee_addon_dev 封装则适配为本包薄封装）:
    login():
        POST AuthService.LoginByAppSecret（acctID/username/appid/appsecret/lcid=2052）
        失败 → 抛 KingdeeAuthError
        成功 → 保存 session cookie
    query_travel_expense_bills(start_date, end_date) -> list:
        ExecuteBillQuery（FormId=ER_ExpenseRequest 或企业实际差旅报销 FormId）
        FieldKeys：单据号/员工/出差起止日/补助明细行（日期、差旅补助金额、餐补金额）/单据状态
        只取已审核或已提交单据；分页拉全
        ⚠️ 严禁调用 Save / Audit / Delete 等写接口

函数 run_expense_cross_audit(cycle_start, cycle_end) -> dict:
    若 KINGDEE_* 凭证缺失:
        记 WARNING「F15 未配置金蝶凭证，跳过」；返回 {skipped: true}
    尝试 login，失败重试 2 次（指数退避）:
        仍失败 → 记 ERROR + 告警邮件 ADMIN（E32）；返回 {skipped: true}
        # ❗降级跳过，绝不抛出阻塞月审主流程

    bills = query_travel_expense_bills(cycle_start, cycle_end)
    diffs = []
    对每张单、每个补助明细日 d:
        # —— 企微侧单日现场工时判定 ——
        onsite_hours = 由 attendance_logs 出差打卡里程碑（到达/离开客户现场首末点）
                        + field_work_reports 日报佐证 核定
        transit_hours = 当日在途核定（票据口径一期不可得时取 0 并标注）
        # —— 应发口径（制度 4.2.3）——
        若 onsite_hours ≥ 4.0: 应发 = 全额
        否则若 onsite_hours + transit_hours ≥ 4.0 且当日无请假/年假折抵: 应发 = 全额（合并在岗）
        否则: 应发 = 减半
        # 客观等待待命：主管书面确认单引擎读不到 → 若当日无任何现场/在途记录
        #   但单据备注含待命字样，只标「待核」不判错（E33）
        若 金蝶实发口径 ≠ 应发口径:
            diffs.append(员工, 日期, onsite_hours, transit_hours, 应发口径, 金蝶实发金额, 单据号)（E31）

    若 diffs 非空:
        渲染「差旅补助待核清单」邮件 → 财务 + HR（ADMIN_EMAILS 白名单）
        写 audit_logs(expense_cross_audit, 差异数)
    返回 {bills: N, checked_days: M, diffs: len(diffs)}

## 异常与边界（必填）
- 本文件处理：金蝶认证/查询失败 → 重试 2 次 → 降级跳过 + 告警（E32），返回 skipped 而非抛出
- 故意往上抛：数据库写 audit_logs 失败（属本地故障，须让月审感知）
- 边界条件:
  - 凭证缺失 → 跳过（F15 为可选增强，不得让考勤主流程因财务侧不可用而失败）
  - 报销单跨薪资周期（出差跨 25/26 日）→ 按补助明细行的自然日归属各自周期，只核本周期内的日
  - 同员工同日多张单 → 金额合并后再比对
  - 无补助明细行的单据（纯交通费报销）→ 跳过不比对
  - 判定不了的（无打卡无日报、备注待命、主管确认单场景）→ 一律「待核」，禁止判错（E33）
  - 金蝶返回字段缺失/格式变化 → 该行标「解析失败待核」，raw 落库兜底，不中断整轮

## 注意事项 / 坑
- FormId 与 FieldKeys 须按企业真实金蝶账套元数据确认（参考 kingdee_addon_dev/kingdee_API_docs），首次接入先跑只读 dry-run 打印字段
- 补助标准金额（每日差旅补助、早 20/午 40/晚 40 餐补）以《公司差旅补贴政策》为准，配置化，不散落硬编码
- 一期只做补助减半核对；餐补行程边界（制度 4.5）与在途调休凭证核对为后续批次，PRD §1.1 已标暂缓
- 金蝶账号申请只读查询权限即可，遵循最小权限
