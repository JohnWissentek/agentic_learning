# work_hours.py 伪代码（v0.5 新增）

## 本文件职责（一句话）
纯函数实现制度 3.1.1/3.1.2/3.1.5.2 的动态工时判定：给定当日首末打卡与已批短假小时，算出截断后跨度、实际工作时长、缺额与状态——不连库、不发邮件。

## 对应PRD功能
F1；规则条文 §4.2-1；异常场景 E24（区间截断）、E29（9.0h 顺延）、E30（请假顺延 10:00+N）

## 依赖
- 调用：config（工时常量）、datetime（标准库）
- 被调用：services.daily_audit（日审判定）、tests

## 伪代码

数据类 WorkHoursVerdict:
    status: "normal" | "pending_reconciliation" | "absent"
    effective_start / effective_end（截断后起止）
    presence_span_hours（截断后跨度）
    actual_work_hours（跨度 − 午休）
    required_presence_hours（当日应出勤跨度）
    shortfall_hours（缺额，≥0）

函数 evaluate_daily_work_hours(workday, first_punch, last_punch,
                               approved_partial_leave_hours=0, lunch_hours_taken=None) -> WorkHoursVerdict:
    lunch = lunch_hours_taken 或默认 0.5h
    extended = lunch ≥ 1.0h                       # 制度 3.1.2.3 顺延触发
    required = 9.0h 若 extended 否则 8.5h          # E29
    required = max(required − 已批短假小时, 0)     # 请假顺延 10:00+N 由此自然成立 E30
    window_start = 当日 08:30
    window_cap   = 当日 19:00 若 extended 否则 18:30
    effective_start = max(首卡, window_start)      # 早到从 08:30 起算
    effective_end   = min(末卡, window_cap)        # 晚走多坐不计 E24
    span = max(end − start, 0) 小时
    actual_work = max(span − lunch, 0)
    shortfall = max(required − span, 0)
    若 span ≥ required            → normal
    否则若 actual_work ≥ 4.0h     → pending_reconciliation（缺额进核销流程）
    否则                          → absent（旷工 1 天预警，制度 3.1.5.2；处分走人工）
    # ❗禁止写死 10:00：全勤到岗截止 = 封顶 − required，是推导值

## 异常与边界（必填）
- 本文件处理：末卡早于起算点（如两卡都在 08:30 前）→ span=0 → absent；短假 ≥ 应出勤 → required=0 → normal
- 故意往上抛：first_punch > last_punch 属调用方排序错误 → ValueError 快速失败
- 边界条件:
  - 恰好 span == required → normal（含边界）
  - actual_work 恰好 4.0h → pending_reconciliation（含边界，制度「已满 4 小时」）
  - lunch_hours_taken=0（外勤日不休）→ actual_work=span
  - 一期引擎观测不到真实午休时长，默认 0.5h；9.0h 顺延须依赖午休外出打卡留痕或人工报备（PRD 待定项，当前保守按 8.5h 判定不误伤）

## 注意事项 / 坑
- 全部阈值从 config 常量读取，禁止在本文件写数字字面量（对账口径唯一）
- 时区：打卡时间已在 sync_real_punches 转为北京时间 naive datetime，本模块不再做时区转换
