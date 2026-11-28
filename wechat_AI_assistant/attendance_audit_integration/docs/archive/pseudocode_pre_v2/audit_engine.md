# audit_engine.py 伪代码

## 本文件职责（一句话）
企业微信考勤对账系统的核心逻辑引擎，承担拉取数据、执行每日考勤核算与 3D 防作弊校验、扫描调休超期、出具周报明细，以及每月对账决算扣款计薪核定的核心业务规则。

## 对应PRD功能
- 考勤打卡原始数据拉取及对账（PRD §3.1）
- 对账周期自动计算规则（PRD §3.2）
- 每日考勤勾稽与 3D 防代打卡过滤校验（PRD §3.3）
- 出差工作日志完整性月核查勾稽（PRD §3.4）
- 周末加班工时与手写客户服务单月勾稽（PRD §3.5）
- 调休假期 7 天超期预警（PRD §3.6）
- 财务月度计薪扣款公式自动核算（PRD §3.7）

## 依赖
- 调用：time, datetime, db, wecom_client, mail_sender, config.settings, logger
- 被调用：cli.py, main.py

## 伪代码

### 1. 基础辅助函数

#### 1.1 哈弗辛大圆距离计算 (calculate_haversine_distance)
```python
函数 calculate_haversine_distance(纬度1, 经度1, 纬度2, 经度2) -> 浮点数 (公里):
    基于地球赤道半径（6371.0 公里），运用三角函数公式计算地球球面上两点之间的最短地理连线距离。
    返回 距离值
```

#### 1.2 工作日与休假日检测 (is_workday_db / is_statutory_holiday)
```python
函数 is_workday_db(日期, 游标=None):
    如果 传入游标 为空:
        连接 = get_db_connection()
        游标 = 连接.游标()
        
    查询 national_holidays 表中是否存在该日期的记录
    如果 记录存在:
        如果 day_type == 'workday' (补班工作日) 返回 True
        如果 day_type == 'holiday' (法定节假日) 返回 False
        
    # 如果数据库中无维护记录，降级到默认的周末休假规则
    如果 日期是周六(5) 或 周日(6):
        返回 False (非工作日)
    否则:
        返回 True (工作日)
```

#### 1.3 计薪对账周期计算 (get_monthly_cycle_range)
```python
函数 get_monthly_cycle_range(基准日期):
    # 考勤账期固定为：上月 26 号至本月 25 号
    如果 基准日期.day <= 25:
        账期截止日 = 当前月的 25 号
        账期起始日 = 上个月的 26 号
    否则:
        账期截止日 = 下个月的 25 号
        账期起始日 = 当前月的 26 号
        
    返回 (账期起始日, 账期截止日, "YYYY年MM月" 描述)
```

---

### 2. 核心业务方法 (Class AuditEngine)

#### 2.1 同步在岗员工花名册 (sync_employee_roster)
```python
函数 sync_employee_roster() -> 列表:
    员工原始列表 = wecom_client.fetch_users()
    如果 列表为空:
        记日志 WARN，返回空
        
    连接 = get_db_connection()
    对于 每一个企业微信员工:
        设定签约公司: 若 department 中首项不等于 2，则为 "北京帕莫瑞科技有限公司"；否则为 "维恩科仪（北京）机械自动化设备有限公司"
        
        执行 INSERT INTO employees 进行同步插入
        如果 wecom_userid 冲突，则 UPDATE 姓名、邮箱、岗位、签约公司
        
    提交事务并返回同步的 UserID 列表
```

#### 2.2 每日考勤对账与 3D 防代打卡校验 (run_daily_audit)
```python
函数 run_daily_audit(核对日期):
    # 排除清单：徐宏玮、杨丽丽不参与考勤勾稽
    连接 = get_db_connection()
    游标 = 连接.游标(RealDictCursor)
    
    工作日标识 = is_workday_db(核对日期, 游标)
    在岗活跃员工列表 = 从 employees 表查询所有 active 员工
    
    对于 每一个员工 emp:
        如果 姓名 是 "徐宏玮" 或 "杨丽丽":
            继续下一位员工 (剔除对账)
            
        # 查询当天内该员工是否已审批通过请假 (leave) 或 出差 (business_trip)
        假勤审批列表 = 从 approvals 查询生效的假单
        有出差 = 假勤审批列表中含有 "business_trip"
        有请假 = 假勤审批列表中含有 "leave"
        
        # 拉取当天的所有原始打卡流水
        打卡流水 = 从 attendance_logs 查询该用户当天的打卡记录 (按时间升序)
        
        考勤状态 = "normal"
        有异常 = False
        异常原因 = ""
        安全预警状态 = "正常"
        
        首次卡时间 = 打卡流水中最早的记录时间
        末次卡时间 = 打卡流水中最晚的记录时间 (若仅打卡一次则为 None)
        
        # ＝＝＝ 3D 防作弊校验逻辑 ＝＝＝
        
        # 维度 1: 企业微信定位异常代码检测 (Root / 模拟器作弊)
        打卡异常代码列表 = [流水中所有 exception_type 不为空的项]
        如果 打卡异常代码列表 不为空:
            有异常 = True
            考勤状态 = "device_anomaly"
            异常原因 = "打卡物理定位偏离（外勤打卡 / 非公司指定设备）"
            安全预警状态 = "设备环境待确认"
            
        # 维度 2: 地理瞬移超速校验
        如果 打卡流水记录数 >= 2:
            对打卡流水进行两两相邻点对比:
                如果 两点经纬度数据完整:
                    距离 = 计算哈弗辛球面距离(点1, 点2)
                    时差 = 点2时间 - 点1时间 (单位：小时)
                    如果 时差 > 0:
                        速度 = 距离 / 时差
                        如果 速度 > 350.0 公里/小时:
                            有异常 = True
                            考勤状态 = "location_anomaly"
                            异常原因 = "打卡位置异常（检测到极短时间内远距离多地打卡，时速超标）"
                            安全预警状态 = "打卡位置待核实"
                            
        # 维度 3: 结合节假日与假单进行最终勾稽
        如果 有请假:
            如果未报设备位置异常: 考勤状态 = "leave"
        否则如果 有出差:
            如果未报设备位置异常: 考勤状态 = "business_trip"
        否则如果 工作日标识 是 True:
            # 工作日必须考核打卡次数
            如果 打卡流水为空:
                有异常 = True
                考勤状态 = "absent" (旷工)
                异常原因 = "正常工作日全天无打卡记录（且未关联请假或出差审批）"
            否则如果 打卡流水仅有 1 次:
                有异常 = True
                考勤状态 = "late" (迟到/半天缺卡)
                异常原因 = "工作日半天缺卡（仅检测到单次打卡记录，另一半天打卡缺失）"
            否则:
                # 迟到宽限校验 (9点00分59秒之后签到算迟到)
                如果 首次卡时间.time() > 09:00:59:
                    有异常 = True
                    考勤状态 = "late"
                    异常原因 = "签到迟到"
        
        # 写入或更新 daily_attendance 考勤表
        写入考勤日表 (wecom_userid, 核对日期, 首次卡时间, 递交卡时间, 考勤状态, 有异常, 异常原因)
        
        如果 有异常 是 True:
            # 渲染个人考勤确认邮件并发给员工
            邮件内容 = 渲染 render_individual_anomaly_email(...)
            调用 mail_sender.send_html_email(收件人=员工邮箱, 抄送=管理员列表)
            
    # 汇总全公司昨日考勤生成日报 HTML，并发送给总经理徐宏玮，抄送财务薛蕾、王晓
    日报内容 = 渲染 render_daily_summary_email(...)
    调用 mail_sender.send_html_email(收件人=徐宏玮邮箱, 抄送=薛蕾与王晓)
```

#### 2.3 调休假期 7 天超期预警扫描 (check_compensatory_leave_expiry)
```python
函数 check_compensatory_leave_expiry() -> 整数:
    # 扫描处于 released (已释放) 状态且未使用的调休假期明细
    连接 = get_db_connection()
    游标 = 连接.游标()
    
    查询所有 c.status='released' 且 已用工时 < 总工时 的调休记录
    对于 每一条调休记录:
        天数差 = 今天 - 产生日期
        如果 天数差 >= 8:
            # 触发超期 7 天预警，通过邮件发送催办通知
            预警邮件 = 渲染 render_overdue_warning_email(员工姓名, 产生日期, 剩余小时, 天数差)
            调用 mail_sender.send_html_email(
                收件人=员工邮箱,
                抄送=[总经理徐宏玮, 财务薛蕾, 财务王晓, 项目经理孔紫初, 项目经理王楠]
            )
            登记 audit_logs 日志记录 "调休假超期预警"
            计数器 += 1
            
    提交事务并返回计数器值
```

#### 2.4 月度考勤预对账与财务封账决算审计 (run_monthly_audit)
```python
函数 run_monthly_audit(基准日期, 是否为终审标记 is_final):
    # 1. 确定账期开始和结束日期 (上月 26 号至本月 25 号)
    账期开始, 账期结束, 账期月份 = get_monthly_cycle_range(基准日期)
    
    连接 = get_db_connection()
    游标 = 连接.游标(RealDictCursor)
    
    # 2. 统计周期内国家标准工作天数
    标准工作天数 = 0
    循环当前日期 从 账期开始 到 账期结束:
        如果 is_workday_db(当前日期, 游标):
            标准工作天数 += 1
            
    在职活跃员工列表 = 从 employees 表中获取
    
    # 3. 如果是 26 号终审封账阶段 (is_final == True)，执行强力交叉勾稽校验
    如果 is_final 是 True:
        对于 每一个在岗员工 (排查徐宏玮、杨丽丽):
            用户ID = 员工ID
            
            # 【月勾稽项一】：周末加班审核放行资格验证
            查询此周期内员工所有的 approved 加班单
            对于 每一个加班单:
                加班日期 = 加班单开始日期
                在 service_reports 现场服务单中查询是否存在该加班日期且客户签字 (is_customer_signed = True) 的报告
                如果 现场报告存在:
                    # 勾稽成功：放行加班时长，生成 released 状态调休假并累加至假期库
                    执行 INSERT INTO compensatory_leave_details (status='released')
                    执行 UPDATE vacation_balances 累加总发放调休时数
                否则:
                    # 勾稽失败：标记状态为 invalid 并进行加班工时锁定驳回
                    执行 INSERT INTO compensatory_leave_details (status='invalid')
                    记警告日志 "加班驳回：未找到客户签字服务单"
            
            # 【月勾稽项二】：出差日报与环境照水印复核
            查询此周期内员工所有的 approved 出差单
            对于 出差单覆盖的每一天:
                如果 该天是工作日:
                    查询 field_work_reports 表中是否存在当天出差汇报，且水印图 url 不为空
                    如果 不存在汇报:
                        # 缺失现场工作日志：在 daily_attendance 中强制覆写为异常
                        执行 UPDATE daily_attendance SET is_anomaly = TRUE, 异常原因 = "出差日缺失现场工作日报或环境水印照片"

    # 4. 汇总周期内每一位员工的考勤月度指标
    全员变动表格行 = []
    调休余额变动行 = []
    加班拦截历史行 = []
    
    对于 每一个在岗员工 (排查徐宏玮、杨丽丽):
        用户ID = 员工ID
        
        # 统计异常状态天数 (BUG-09: 旷工按1.0天扣减，半天缺卡late按0.5天扣除事假/旷工)
        旷工天数 = 查询 daily_attendance 中本周期 status='absent' 且 is_anomaly=True 的总天数 * 1.0
        缺卡天数 = 查询 daily_attendance 中本周期 status='late' 且 is_anomaly=True 的总天数 * 0.5
        扣薪累计天数 = 旷工天数 + 缺卡天数
        
        # 统计事假请假小时并折算为天数 (duration_hours / 8.0)
        事假小时 = 查询 approvals 表中请假类型为事假的总时长
        事假天数 = 事假小时 / 8.0
        
        # 查询假期余额
        调休总发放, 调休已用, 调休结余 = 查询 vacation_balances 表的最新值
        # 查询本期产生的有效调休新增时长
        本期新增调休 = 查询 compensatory_leave_details 表中本期 accrual_date 在账期内且 status='released' 的总时长
        # 查询本期已经消耗使用的调休时长
        本期消耗调休 = 查询 approvals 表中本期请假类型为调休的总时长
        # BUG-02: 结转计算公式：上期结转 = 剩余余额 - 本期新增 + 本期消耗
        上期结转 = 调休结余 - 本期新增 + 本期消耗
        
        如果 is_final 是 True:
            # 终审版表格行数据：生成带扣薪变动天数明细 (标准工作日 - 事假扣减 - 旷工扣减 = 应折日薪系数)
            追加 全员变动表格行 HTML
            追加 调休余额变动行 HTML
        否则:
            # 预对账草稿行数据：只展示待确定扣薪指标，不锁定
            追加 全员变动表格行 HTML (状态为待定)
            
    如果 is_final 是 True:
        # 搜集被拦截的周末无效加班明细
        从 compensatory_leave_details 中查询本账期内 status='invalid' 的名单
        追加到 加班拦截历史行
        
        # BUG-08: 统计截止目前数据库中尚未结清的残留异常总数
        未结清异常笔数 = 查询 daily_attendance 中本周期内仍处于 is_anomaly=True 的记录数
        
        月报 HTML = 渲染 render_monthly_finalized_email(...)
        主题 = "公司月度考勤终审与财务扣薪对账报表 (最终锁定版) - 账期月份"
    否则:
        # BUG-07: 从数据库中实时获取各类预对账指标，取代硬编码
        草稿异常未核销量 = 查询 daily_attendance 中 is_anomaly=True 的计数
        草稿待审批单据数 = 查询 approvals 中 status!='approved' 的计数
        出差缺日报总天数 = 查询 daily_attendance 中 status='business_trip' 且 异常原因含"缺失现场工作日报"的计数
        
        月报 HTML = 渲染 render_monthly_preliminary_email(...)
        主题 = "公司月度考勤数据预估快报 (草稿版) - 账期月份"
        
    # 5. 发送月度对账邮件给总经理徐宏玮，抄送财务薛蕾、王晓
    调用 mail_sender.send_html_email(收件人=徐宏玮邮箱, 抄送=薛蕾与王晓)
    提交事务并返回 True
```

## 注意事项 / 坑
- 考勤的扣款计薪计算逻辑必须支持对徐宏玮与杨丽丽进行**全局白名单过滤**。他们在数据同步时可以正常写入，但是在 `run_daily_audit` 和 `run_monthly_audit` 的勾稽核算中会被强制剔除。
- 调休的结余 carryover 核算存在典型的"后向追溯性"，由于员工可能会在月底补录请假或在 Staging 中进行调结。为了保证最终的数据强一致性，公式必须使用 `结余 - 新增 + 消耗` 来实时倒推本账期之前的`上期结转`余额，避免将当前库中已被扣减的数据重复折合到上期。
- 3D 防作弊的地理时速阈值限制在 **350 km/h**。这刚好是国内高铁的极限行驶速度，对于时差极短（例如半小时内）但物理距离很大（如北京朝阳至上海张江）的打卡会被瞬间判定为异地代打卡。
