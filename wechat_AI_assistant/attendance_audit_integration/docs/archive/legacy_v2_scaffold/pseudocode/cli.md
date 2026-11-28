# cli.py 伪代码

## 本文件职责（一句话）
命令行入口：初始化库、同步花名册、触发日/周/月审与调休超期扫描（供 Cron 调用）。

## 对应PRD功能
F1、F7、F8、F6/F11（check-expiry）；异常场景 E20/E22/E23（任务失败非 0 退出供 Cron 感知）

## 依赖
- 调用：db.init_db、audit_engine、argparse/sys/datetime
- 被调用：无（`python -m attendance_audit_integration.cli` 或脚本入口）；架构图：cli → audit_engine、cli → config（经引擎间接）

## 伪代码

函数 main():
    定义子命令:
        init-db
        sync-roster
        daily [--date YYYY-MM-DD]     # 默认昨天 T-1
        weekly
        check-expiry
        monthly [--date YYYY-MM-DD] [--final]  # 默认今天；--final=终审否则草稿
        expense-cross [--date YYYY-MM-DD]      # F15 金蝶补助交叉审计（只读；周期=26~25）

    若无子命令: 打印帮助并 exit 0

    尝试:
        非 init-db 时先 config.validate()
        init-db → init_db()
        sync-roster → audit_engine.sync_employee_roster()
        daily → 解析日期后 run_daily_audit；logger 输出统计
        weekly → run_weekly_audit()
        check-expiry → check_compensatory_leave_expiry()
        monthly → run_monthly_audit(target_date, is_final=--final)
        expense-cross → get_monthly_cycle_range(参考日) 算周期 → run_expense_cross_audit(start, end)
            # F15 编排在 cli 层（Services 互不调用）；金蝶失败在 service 内降级跳过，不使 cli 退非 0
    捕获任意异常:
        logger.error；sys.exit(1)

## 异常与边界（必填）
- 本文件处理：顶层 catch-all → 非 0 退出；日期非法落入同一分支；validate 缺失配置 exit 1
- 故意往上抛：无，全部在 main 兜底
- 边界：无命令不算失败（exit 0）；daily 默认昨天、monthly 默认今天且无 --final 为草稿

## 注意事项 / 坑
- 进度输出已改为 logger（禁止 print 调试）
- Cron：每月 25 日 `monthly`（随后 `expense-cross`）；每月 26 日 `monthly --final`；每日 `daily`
- sync-roster：企微成员 + `data/employee_roster.json` 合并邮箱（禁止 xlsx）
