# mock_data_populator.py 伪代码

## 本文件职责（一句话）
清空数据库并模拟生成最近 30 天的高仿真员工考勤与审批数据，包含各种打卡缺失、异地代打卡、设备异常、加班单与服务单缺失等异常数据，用于全链条系统测试。

## 对应PRD功能
沙箱数据模拟及框架审计异常链条的功能验证。

## 依赖
- 调用：db.get_db_connection, audit_engine.is_workday_db, config.settings
- 被调用：tests 单元/集成测试、开发自测脚本

## 伪代码
```python
函数 populate_mock_data():
    连接 = get_db_connection()
    游标 = 连接.游标()
    
    # 1. 强力清空本地所有考勤相关表，保证数据纯净
    游标.执行 TRUNCATE 清空：attendance_logs, approvals, field_work_reports, service_reports, daily_attendance, compensatory_leave_details, vacation_balances, audit_logs 等表
    
    # 2. 查询系统中的所有员工
    查询所有员工 SELECT wecom_userid, name FROM employees
    如果 员工列表为空:
        记日志 ERROR "没有找到员工，请先执行 sync-roster 或检查员工名册导入。"
        关闭连接并退出
        
    起始日期 = 今天 - 30天
    办公IP地址 = "125.33.9.60"
    常备客户地址 = ["北京朝阳区朝阳北路研发中心", "客户现场-北京海淀区腾讯大厦", "客户现场-上海张江高科技园"]
    
    对于 每一个员工 emp:
        用户ID = emp.wecom_userid
        姓名 = emp.name
        
        # 3. 初始化默认调休假期余额
        游标.执行 INSERT 写入该用户的调休假初始值：发放16小时，已用4小时，剩余12小时 (vacation_balances)
        
        # 4. 对 30 天周期内的每一天进行循环模拟
        当前日期 = 起始日期
        当 当前日期 <= 今天 时循环:
            是工作日 = 调用 is_workday_db(当前日期)
            
            如果 是工作日:
                随机概率 = [0, 1] 之间的浮点数
                
                # 情况 A：75% 概率为完美出勤日
                如果 随机概率 < 0.75:
                    上午打卡时间 = 8点45分 到 8点59分 随机
                    下午打卡时间 = 18点00分 到 18点15分 随机
                    游标.执行 INSERT 写入 attendance_logs，类型分别为 'start_shift', 'end_shift'
                
                # 情况 B：10% 概率为休假或出差申请
                否则如果 随机概率 < 0.85:
                    假勤类型 = 'leave' 或 'business_trip' 随机
                    游标.执行 INSERT 写入 approvals 表，状态标记为 'approved' (已通过)
                    如果 假勤类型 == 'business_trip' 且 随机概率 < 0.5:
                        # 50% 概率员工提交了带水印的出差工作现场照日报
                        游标.执行 INSERT 写入 field_work_reports 表
                
                # 情况 C：5% 概率为漏打卡 (即只有上班卡，没有下班卡)
                否则如果 随机概率 < 0.90:
                    上午打卡时间 = 8点45分 到 8点59分 随机
                    游标.执行 INSERT 写入 attendance_logs (start_shift)
                    
                # 情况 D：5% 概率为设备异常打卡 (触发 WeCom 物理环境报警)
                否则如果 随机概率 < 0.95:
                    打卡时间 = 上午9点和下午18点左右
                    游标.执行 INSERT 写入 attendance_logs，包含设备异常编码 "device_anomaly" 或 "location_anomaly"
                
                # 情况 E：5% 概率为严重作弊超速 (同一天极短时间内异地多地打卡)
                否则:
                    上午9:00 写入北京打卡记录 (start_shift)
                    上午10:00 写入上海打卡记录 (outdoor)，两地相距 1060 公里，时速 1060 km/h 触发瞬移报警
            
            如果 不是工作日 (周末):
                # 5. 15% 概率模拟周末申请了加班
                如果 随机概率 < 0.15:
                    游标.执行 INSERT 写入 approvals (overtime) 加班 8 小时
                    游标.执行 INSERT 写入 attendance_logs 上下班打卡流水
                    
                    # 60% 概率员工上传了客户手写签字现场服务单，40% 漏交 (触发月决算加班驳回)
                    如果 随机概率 < 0.6:
                        游标.执行 INSERT 写入 service_reports 且 is_customer_signed = TRUE
            
            当前日期 += 1天
            
        # 6. 额外注入一笔 10 天前产生但尚未消费的调休记录，以便测试 Day 8 过期预警警报
        游标.执行 INSERT 写入 compensatory_leave_details，产生日期 = 今天 - 10天，时长=8小时，状态='released'
        
    提交事务并关闭连接
    记日志 INFO "仿真沙箱测试数据生成完毕。"
```

## 注意事项 / 坑
- 每次运行 `populate_mock_data` 都会**物理级清空 (TRUNCATE)** 所有的业务流水和关联报表数据，千万不要在生产数据库上执行该方法。
- 生成的异地代打卡（北京-上海）以及加班单服务单缺失数据是为了测试 `audit_engine.py` 中的防作弊算法和月度对账扣款逻辑。
