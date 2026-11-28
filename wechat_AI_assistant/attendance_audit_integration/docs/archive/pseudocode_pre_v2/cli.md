# cli.py 伪代码

## 本文件职责（一句话）
提供命令行交互入口（CLI），封装了数据库初始化、同步通讯录、每日对账、周报生成、超期调休扫描及月度预估与终审结账等任务命令。

## 对应PRD功能
后台任务运维调度接口，供系统运维或 Cron 定时任务执行脚本调用。

## 依赖
- 调用：db.init_db, audit_engine.audit_engine
- 被调用：命令行终端（通过 python cli.py 命令）

## 伪代码
```python
函数 main():
    创建 命令行解析器 parser, 描述 = "企业微信考勤审计集成 CLI 工具"
    创建 子命令解析器 subparsers
    
    # 注册子命令 init-db
    注册子命令 "init-db", 描述 = "初始化创建 PostgreSQL 数据库表"
    
    # 注册子命令 sync-roster
    注册子命令 "sync-roster", 描述 = "同步企业微信员工花名册"
    
    # 注册子命令 daily
    注册子命令 "daily", 描述 = "运行每日考勤对账"
    为 "daily" 添加可选参数 "--date", 默认=None, 描述 = "指定对账业务日期 YYYY-MM-DD，若为空默认为昨日"
    
    # 注册子命令 weekly
    注册子命令 "weekly", 描述 = "运行考勤对账汇总周报"
    
    # 注册子命令 check-expiry
    注册子命令 "check-expiry", 描述 = "扫描未消费的过期调休假并发送预警"
    
    # 注册子命令 monthly
    注册子命令 "monthly", 描述 = "运行月度考勤对账决算"
    为 "monthly" 添加可选参数 "--date", 默认=None, 描述 = "指定对账基准日期 YYYY-MM-DD，默认为今天"
    为 "monthly" 添加开关参数 "--final", 动作=store_true, 描述 = "是否执行最终封账锁定对账 (若无此参数则默认执行预估草稿版)"

    解析命令行输入参数 args = parser.parse_args()

    如果 args.command 为空:
        打印命令行帮助信息并退出

    尝试:
        如果 args.command == "init-db":
            调用 init_db()
            
        否则如果 args.command == "sync-roster":
            调用 audit_engine.sync_employee_roster()
            
        否则如果 args.command == "daily":
            如果 args.date 存在:
                计算日期 target_date = 从字符串转换(args.date)
            否则:
                计算日期 target_date = 当前日期 - 1天
            输出 "正在执行每日考勤审计，日期: target_date"
            结果 = 调用 audit_engine.run_daily_audit(target_date)
            输出 "每日审计已完成: 结果"
            
        否则如果 args.command == "weekly":
            输出 "正在执行周度考勤审计..."
            调用 audit_engine.run_weekly_audit()
            输出 "周度审计已完成。"
            
        否则如果 args.command == "check-expiry":
            输出 "正在扫描即将过期的调休余额并发送预警..."
            预警次数 = 调用 audit_engine.check_compensatory_leave_expiry()
            输出 "扫描完成，共向 预警次数 名员工发送了超期调休预警。"
            
        否则如果 args.command == "monthly":
            如果 args.date 存在:
                计算日期 target_date = 从字符串转换(args.date)
            否则:
                计算日期 target_date = 当前日期
            是否终审 is_final = args.final
            输出 "正在执行月度审计，基准日期: target_date, 是否终审: is_final"
            调用 audit_engine.run_monthly_audit(target_date, is_final=is_final)
            输出 "月度审计已完成。"

    捕获 异常 并输出错误:
        打印 "执行命令 args.command 失败: 异常详情" 到标准错误流
        系统退出(状态码=1)
```

## 注意事项 / 坑
- 执行 `init-db` 之前确保本地环境变量中的 `DATABASE_URL` 正确且数据库服务已启动，否则程序会直抛连接错误挂掉。
- 定时任务推荐配置：
  - `python cli.py daily` 每天凌晨 01:00 运行一次。
  - `python cli.py weekly` 每周一早上 09:30 运行一次。
  - `python cli.py check-expiry` 每天上午 10:00 运行一次。
  - `python cli.py monthly` 每月 25 日 17:00 运行一次预估。
  - `python cli.py monthly --final` 每月 26 日 10:00 运行一次终审。
