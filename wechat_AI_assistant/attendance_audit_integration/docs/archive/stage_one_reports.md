# 阶段一（过渡期）考勤审计报告与邮件通知规范 (HTML 模板版)
## 目录: `attendance_audit_integration/stage_one/stage_one_reports.md`

---

## 1. 邮件通知与考勤报表发送规则 (Recipients & Schedule)

在第一阶段（过渡期），所有报表均不再使用 Excel 电子表格附件，而是直接在邮件正文中以高颜值的 HTML 格式渲染，方便管理人员直接在手机/电脑邮件客户端中阅读。

### 1.1 发送范围与周期

| 报告类型 | 发送周期与触发时间 | 目标收件人 | 抄送人 (CC) |
| :--- | :--- | :--- | :--- |
| **个人考勤异常预警邮件** | 每日上午 09:00 (自动执行昨日审计后) | 异常员工本人邮箱 | **徐宏玮、薛蕾、王晓**、部门主管 |
| **每日全公司考勤日报** | 每日上午 09:30 (昨日汇总数据) | **徐宏玮、薛蕾、王晓** | 无 |
| **每周全公司考勤周报** | 每周一上午 10:00 (上周一至日汇总) | **徐宏玮、薛蕾、王晓** | 无 |
| **每月考勤预估/临时月报** | 每月 1 日上午 09:00 (上月考勤初审) | **徐宏玮、薛蕾、王晓** | 无 |
| **每月考勤终审/最终月报** | 每月 5 日上午 09:00 (上月数据最终封账) | **徐宏玮、薛蕾、王晓** | 无 |

---

## 2. HTML 邮件模版规格说明 (HTML Templates)

### 2.1 每日个人考勤异常预警邮件 (Daily Individual Anomaly Alert)
* **设计风格**：采用红色警告条和重点卡片布局，提醒员工尽快处理，减少争议。
* **HTML 源码模版**：
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 2px solid #b91c1c; padding-bottom: 5px; margin-bottom: 15px; color: #b91c1c; font-size: 16px;">公司考勤集成审计层 - 昨日考勤异常预警</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        对账日期：${anomaly_date} &nbsp;|&nbsp; 生成时间：${generation_time}
    </p>
    
    <p style="margin-top: 15px; font-weight: bold; color: #111111;">尊敬的 ${employee_name}：</p>
    <p style="margin-top: 5px; color: #333333;">系统在对昨日您的考勤进行自动勾稽对账时发现以下异常。请尽快核对并于 2 个工作日内完成申诉或假单补办：</p>
    
    <div style="border: 1px solid #fca5a5; background-color: #fef2f2; padding: 12px 15px; margin: 15px 0; border-radius: 4px; color: #991b1b;">
        <strong>昨日异常明细：</strong><br>
        - **异常状态**：<span style="font-weight: bold; text-decoration: underline;">${anomaly_type_desc}</span><br>
        - **详细原因**：${anomaly_reason_detail}<br>
        - **打卡记录**：上班打卡：${first_clock_in_time} | 下午打卡：${last_clock_out_time}<br>
        - **当前异常安全标记**：${security_status_desc}
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #111111;">[ 处理申诉指南 ]</h3>
    <ol style="padding-left: 20px; margin-top: 5px; color: #555555;">
        <li style="margin-bottom: 4px;">**确属漏打卡**：请立即在企业微信中提交“补卡申请（漏打卡补登）”等待主管及HR审批。</li>
        <li style="margin-bottom: 4px;">**请假/出差折抵**：请发起请假审批，使用“年假”或“调休”折抵异常时段。</li>
        <li style="margin-bottom: 4px;">**转为事假扣发**：若余额不足，您必须申请“事假”，系统将按缺勤核扣当日基础日薪。</li>
        <li style="margin-bottom: 4px;">**逾期处罚**：若超出 **T+2 宽限期**未提交相关流程，系统将最终判定为 **无故旷工**，计入惩戒档案。</li>
    </</ol>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此邮件由系统考勤集成审计层自动发出，请勿直接回复。
    </p>
</body>
</html>
```

---

### 2.2 每日全公司考勤汇总日报 (Daily Company Attendance Summary)
* **设计风格**：采用淡灰色边框汇总栏，清晰呈现前一日全公司异常与假期抵扣情况。
* **HTML 源码模版**：
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 1px solid #111111; padding-bottom: 5px; margin-bottom: 15px; color: #111111; font-size: 16px;">公司考勤异常汇总日报</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        业务日期：${audit_date} &nbsp;|&nbsp; 生成时间：${generation_time}
    </p>
    <p style="margin: 5px 0 15px 0; color: #888888; font-style: italic; font-size: 12px;">
        Oh, my money money come!
    </p>
    
    <div style="border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; padding: 12px 0; margin-top: 15px; margin-bottom: 20px; color: #333333; background-color: #f8fafc; padding-left: 10px; border-radius: 4px;">
        <strong>当日考勤统计：</strong><br>
        - 在岗应到人数：${total_expected} 人<br>
        - 正常打卡出勤：${total_normal} 人<br>
        - 请假/出差/调休：${total_on_leave} 人<br>
        <strong>- 异常缺卡人数：<span style="color: #b91c1c; font-weight: bold;">${total_anomalies} 人</span></strong>
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #b91c1c;">[ ⚠️ 当日考勤异常人员清单 ]</h3>
    <table style="width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 12px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #f1f5f9; text-align: left;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">岗位</th>
                <th style="padding: 6px;">异常理由</th>
                <th style="padding: 6px;">防作弊状态</th>
                <th style="padding: 6px;">补假截止</th>
            </tr>
        </thead>
        <tbody>
            <!-- 循环开始 -->
            ${anomaly_rows}
            <!-- 循环结束 -->
        </tbody>
    </table>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #111111;">[ 历史假期抵扣/核销流水变动 ]</h3>
    <div style="font-size: 12px; color: #555555; line-height: 1.8;">
        ${deduction_history_rows}
    </div>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此日报由系统自动发出，请勿回复。
    </p>
</body>
</html>
```

*表单循环行模版示例*：
```html
<tr style="border-bottom: 1px dashed #e2e8f0;">
    <td style="padding: 6px; font-weight: bold; color: #111111;">员工B</td>
    <td style="padding: 6px; color: #555555;">软件工程师</td>
    <td style="padding: 6px; color: #b91c1c;">下午缺卡</td>
    <td style="padding: 6px; color: #b91c1c;">企微提示“设备/位置异常作弊”</td>
    <td style="padding: 6px; color: #555555;">05-07 18:00</td>
</tr>
```

---

### 2.3 每周全公司考勤汇总周报 (Weekly Company Attendance Summary)
* **设计风格**：采用加粗表格布局，重点突出逾期未处理并最终转化为“旷工惩戒”的人员清单。
* **HTML 源码模版**：
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 1px solid #111111; padding-bottom: 5px; margin-bottom: 15px; color: #111111; font-size: 16px;">公司上周考勤异常残留与旷工周报</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        业务周期：${week_range_desc} &nbsp;|&nbsp; 生成时间：${generation_time}
    </p>
    <p style="margin: 5px 0 15px 0; color: #888888; font-style: italic; font-size: 12px;">
        Oh, my money money come!
    </p>
    
    <div style="border: 1px solid #e2e8f0; padding: 12px; margin-bottom: 20px; border-radius: 4px; background-color: #f8fafc; font-size: 12px; color: #333333;">
        <strong>周报重点摘要：</strong><br>
        上周累计产生异常缺卡 ${total_week_anomalies} 次，截至今日上午 10:00，已通过审批核销 ${total_resolved} 次，仍有 **<span style="color: #b91c1c;">${total_unresolved} 次逾期未处理</span>**，已由系统锁定记入旷工或事假账目。
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #b91c1c;">[ ⚠️ 异常残留最终惩戒扣发清单 ]</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #f1f5f9; text-align: left;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">部门</th>
                <th style="padding: 6px;">异常次数</th>
                <th style="padding: 6px;">判定旷工天数</th>
                <th style="padding: 6px;">判定扣薪事假工时</th>
            </tr>
        </thead>
        <tbody>
            ${weekly_anomaly_rows}
        </tbody>
    </table>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #111111;">[ 员工考勤纪律高危名单（月度累计） ]</h3>
    <div style="font-size: 12px; color: #555555; line-height: 1.8;">
        ${weekly_warning_list_rows}
    </div>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此周报由系统自动发出，请勿回复。
    </p>
</body>
</html>
```

---

### 2.4 每月考勤预估/临时月报邮件 (Monthly Company Preliminary Report)
* **触发时间**：每月 1 日上午 09:00 (自动统计上月考勤初稿)
* **收件人**：**徐宏玮、薛蕾、王晓**
* **设计风格**：黄色底色，提示此表为“预估初稿”，主要用于提醒 HR 和主管及时督促员工补卡与清理待办审批流。
* **HTML 源码模版**：
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 2px solid #d97706; padding-bottom: 5px; margin-bottom: 15px; color: #d97706; font-size: 16px;">公司上月考勤数据预估快报（月初对账版）</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        对账月份：${audit_month} &nbsp;|&nbsp; 生成时间：${generation_time}
    </p>
    <p style="margin: 5px 0 15px 0; color: #888888; font-style: italic; font-size: 12px;">
        Oh, my money money come!
    </p>
    
    <div style="border: 1px solid #fcd34d; background-color: #fffbeb; padding: 12px 15px; margin: 15px 0; border-radius: 4px; color: #b45309; font-size: 12px;">
        <strong>⚠️ 注意：</strong><br>
        本报表为 **月初预估初稿**。由于上月末期发生的打卡异常仍在 T+2 申诉宽限期内，且部分主管待办审批、服务报告尚未清仓，数据并非最终锁定数据。**最终终审对账月报将于每月 5 日正式下发**，届时数据将锁定并直接用于算薪。
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #111111;">[ 待办事务与清仓进度 ]</h3>
    <ul style="padding-left: 20px; margin-top: 5px; color: #555555;">
        <li style="margin-bottom: 4px;">员工处于 T+2 宽限期内的待办申诉：**${pending_employee_appeals}** 笔</li>
        <li style="margin-bottom: 4px;">主管审批列表中待处理考勤审批：**${pending_manager_approvals}** 笔</li>
        <li style="margin-bottom: 4px;">出差未按期提交《现场工作日报》：**${missing_daily_reports}** 天</li>
    </ul>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #111111;">[ 考勤异常预估扣发预览 ]</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #f1f5f9; text-align: left;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">签约公司</th>
                <th style="padding: 6px;">预估事假天数</th>
                <th style="padding: 6px;">预估旷工天数</th>
                <th style="padding: 6px;">未完成对账警告</th>
            </tr>
        </thead>
        <tbody>
            ${monthly_preliminary_rows}
        </tbody>
    </table>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此邮件由系统自动发出，请勿回复。
    </p>
</body>
</html>
```

---

### 2.5 每月考勤终审/最终月报邮件 (Monthly Company Finalized Report)
* **触发时间**：每月 5 日上午 09:00 (结转结余后正式下发)
* **收件人**：**徐宏玮、薛蕾、王晓**
* **设计风格**：经典深黑色底线，清晰直观的表格排版，完美对齐财务扣薪及调休账目，代替 Excel 附件供直接核薪。
* **HTML 源码模版**：
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 2px solid #111111; padding-bottom: 5px; margin-bottom: 15px; color: #111111; font-size: 16px;">公司上月考勤终审与财务扣薪对账报表 (最终锁定版)</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        结算月份：${audit_month} &nbsp;|&nbsp; 封账时间：${generation_time}
    </p>
    <p style="margin: 5px 0 15px 0; color: #888888; font-style: italic; font-size: 12px;">
        Oh, my money money come!
    </p>
    
    <div style="border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; padding: 12px 0; margin-top: 15px; margin-bottom: 20px; color: #111111; background-color: #f8fafc; padding-left: 10px; border-radius: 4px;">
        <strong>上月全司考勤决算：</strong><br>
        - 应计薪满勤天数：${standard_workdays} 天<br>
        - 发生无故旷工总量：${total_absent_days} 天<br>
        - 发生扣薪事假总量：${total_unpaid_leave_days} 天<br>
        - 新增产生调休工时：${total_accrued_comp} 小时<br>
        <strong>- 月度异常警报封账数：<span style="color: #b91c1c; font-weight: bold;">0 笔 (全部完成处理)</span></strong>
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px solid #111111; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #111111;">[ 💵 财务实发工资扣减执行清单 ]</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 5px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #e2e8f0; text-align: left; font-weight: bold;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">签约公司</th>
                <th style="padding: 6px;">标准计薪天</th>
                <th style="padding: 6px;">事假扣发天</th>
                <th style="padding: 6px;">旷工扣发天</th>
                <th style="padding: 6px; text-align: right;">应折日薪系数</th>
            </tr>
        </thead>
        <tbody>
            ${monthly_final_rows}
        </tbody>
    </table>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #b91c1c;">[ ⚠️ 异常凭证拦截与惩戒流水记录 ]</h3>
    <div style="font-size: 12px; color: #555555; line-height: 1.8;">
        ${intercepted_logs_rows}
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #111111;">[ 员工个人调休假余额库变结存 ]</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #f1f5f9; text-align: left;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">上月结转(H)</th>
                <th style="padding: 6px;">本月新增(H)</th>
                <th style="padding: 6px;">本月抵扣/消耗(H)</th>
                <th style="padding: 6px; text-align: right;">本期结余余额(H)</th>
            </tr>
        </thead>
        <tbody>
            ${monthly_comp_balance_rows}
        </tbody>
    </table>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此报表已归档至考勤中间件数据库，并已正式封账，不可擅自更改。
    </p>
</body>
</html>
```

*扣薪列表数据渲染模版示例*：
```html
<tr style="border-bottom: 1px dashed #cbd5e1;">
    <td style="padding: 6px; font-weight: bold; color: #111111;">员工A</td>
    <td style="padding: 6px; color: #555555;">帕莫瑞科技</td>
    <td style="padding: 6px; color: #555555;">21.75</td>
    <td style="padding: 6px; color: #b91c1c;">1.0</td>
    <td style="padding: 6px; color: #b91c1c;">1.0</td>
    <td style="padding: 6px; text-align: right; font-weight: bold; color: #b91c1c;">-2.0 天 (扣发)</td>
</tr>
```
