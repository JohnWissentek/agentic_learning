# mock_data_populator.py 伪代码

## 本文件职责（一句话）
填充 `[start_date, end_date]` 窗口的测试数据：优先调企微真实接口拉取打卡/日报（不清空已有真实历史），仅当 PRD 6.6 某异常场景在真实窗口里完全没出现时，才补 1 条 mock 记录，并把每条 mock 行登记进 `test_data_provenance`（未登记 = 真实）。

## 对应PRD功能
测试支撑 F1、F2、F4、F5、F6、F7（造数触发异常场景 E1/E6/E7/E11/E12）；非生产功能

## 依赖
- 调用：db.get_db_connection、audit_engine.{is_workday_db, sync_real_punches, sync_real_daily_reports}、logger
- 被调用：无（独立脚本，`scripts/run_demo_tests.py` 手工调用）；架构图：mock → db / mock → audit_engine / mock → logger（3.0，未变）

## 伪代码

```
函数 populate_test_data(start_date, end_date) -> 汇总dict:
    连接数据库（普通 tuple 游标，非 RealDictCursor）
    _purge_previous_mock_rows(游标)   # 只删上一轮 provenance 登记过的 mock 行，真实数据不碰
    提交

    读取 employees(status=active)；若空:
        记 ERROR「先 sync-roster」，返回 {"error": "no_employees"}

    # —— 1. 真实优先：打卡 + 出差/外勤日报 ——
    real_punches   = sync_real_punches(游标, employee_ids, start_ts, end_ts)      # 复用 daily_audit，不清空历史
    real_reports   = sync_real_daily_reports(游标, start_ts, end_ts)              # 同上；修复此前从未接线的生产缺口
    提交

    # —— 2. 调休余额基线（幂等 ON CONFLICT DO NOTHING，真实数据优先不覆盖） ——
    对每员工: 若无 vacation_balances 记录则建 16H/已用4H 基线；新建行登记 provenance(baseline_seed)
    提交

    # —— 3. 审批 + 客户签字服务报告：无真实批量拉取渠道，本轮固定按分布造数 ——
    对 start_date..end_date 每天 × 每员工:
        若工作日: ~10% 请假/出差审批（出差 50% 配一条 mock 日报→覆盖 E7 有日报分支；
                                        另 50% 不配→天然覆盖 E7 出差无日报分支，不用额外造假）
        否则(休息日): ~15% 周末加班审批（60% 配签字服务报告→覆盖 E6 released 分支；
                                          40% 不配→天然覆盖 E6 拒绝调休分支）
        每条造的 approvals/field_work_reports/service_reports 行都登记 provenance
    提交

    # —— 4. 场景缺口检测：仅当真实打卡窗口完全没出现该场景才补 1 条 ——
    汇总真实窗口内 attendance_logs 按 (userid, 日期) 分组的条数/异常码/经纬度序列
    e1_found  = 存在 某(userid,日) 未被 leave/trip 审批覆盖 且 当日打卡条数 < 2
    e11_found = 存在 任意打卡行 exception_type 非空
    e12_found = 存在 同日相邻两次打卡经纬度差>1.0度 且 间隔<4小时（粗粒度瞬移探测，复用现有字段不引新依赖）

    若 not e1_found:  为 1 名员工挑 1 个「无覆盖数据的工作日」补 1 条仅上班卡记录 → 登记 provenance(E1)
    若 not e11_found: 同理补 1 条 exception_type='location_anomaly' 打卡 → 登记 provenance(E11)
    若 not e12_found 且员工数≥2: 同理补 2 条北京→上海瞬移打卡 → 登记 provenance(E12)
    提交

    # —— 5. 调休到期催告测试夹具（前瞻性场景，无法从过去真实数据反推，固定造数） ——
    对每员工: 造 1 条 accrual_date=今天-10天、status=released 的调休流水 → 登记 provenance(expiry_seed)
    提交

    返回 {window, real_punches, real_daily_reports,
          mock_approvals, mock_field_work_reports, mock_service_reports,
          mock_scenario_backfill:{E1,E11,E12}, mock_expiry_fixtures}

函数 populate_mock_data():  # 向后兼容旧调用名
    返回 populate_test_data(今天-30天, 今天)
```

## 异常与边界（必填）
- 本文件处理：无员工则安全返回 `{"error": "no_employees"}`；单条 approvals/reports 造数用 `ON CONFLICT DO NOTHING` 幂等，重跑不重复
- 故意往上抛：数据库错误、真实接口调用异常（`sync_real_punches`/`sync_real_daily_reports` 内部已捕获降级为空列表，不会在这里抛）
- 边界：
  - `_purge_previous_mock_rows` 只按 `test_data_provenance` 里登记过的 (table_name, record_pk) 精确删除，绝不 TRUNCATE 任何业务表——避免删掉真实历史（此前版本的教训）
  - E1/E11/E12 的「真实覆盖」判定是启发式（尤其 E12 瞬移用经纬度差值+时间差的粗粒度阈值，非精确速度计算），只用于决定「要不要补一条」，不作为审计结论
  - approvals / service_reports 本仓库无真实批量拉取渠道（前者靠 Webhook 实时推送，后者无任何接口），本轮**固定**造数且**全部**登记 provenance，不参与「真实优先」判定
  - is_workday_db 调用不传游标（本文件用普通 tuple 游标，is_workday_db 内部按 dict 游标取列，混用会报错）；代价是循环调用时会各自开一次短连接，仅测试脚本路径，可接受

## 注意事项 / 坑
- 必须先有 employees（sync-roster 或手工导入）
- 随机种子未固定，回归断言应针对「provenance 里有没有登记某 scenario_id」而非精确条数
- `populate_test_data` 是幂等的：重跑只会清理并重建自己登记过的 mock 行，真实数据（含上一轮 sync_real_* 拉到的历史）原样保留
- 若某测试库长期没有真实企微凭证/没有真实历史打卡，`sync_real_punches`/`sync_real_daily_reports` 会返回 0，届时 E1/E11/E12 会持续走 mock 补齐分支——这是预期行为，不是 bug
