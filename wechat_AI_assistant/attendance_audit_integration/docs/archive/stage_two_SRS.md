# 软件需求规格说明书 (SRS) - 阶段二（目标系统方案）
## 目录: `attendance_audit_integration/stage_two/docs/SRS.md`

---

## 1. 系统数据模型与数据库 Schema（阶段二）

阶段二系统启用完整的关系数据库模型，用于支持多维交叉审计与余额流转：

### 1.1 核心数据表清单

* **`employees` (员工表)**：存储基础人员信息及绑定的企业微信 UserID 与邮箱。
* **`attendance_logs` (打卡日志表)**：增加 `device_id`（存储蓝牙打卡器ID）与 `location_name` 等字段，核对 WiFi MAC 与蓝牙信号。
* **`approvals` (审批表)**：存储请假、出差、补卡、加班单据。新增加班必要性类型（`necessity_type`）与辅证材料链接（`evidence_url`）。
* **`field_work_reports` (现场工作日报表)**：对应企业微信现有的日报数据，存储现场环境水印照片链接 `watermark_image_url`。
* **`service_reports` (现场服务报告表)**：存储有客户签字的正式服务报告照片 `signature_image_url` 和现场水印照。
* **`travel_expense_claims` (报销对账单表)**：与出差审批单号关联，进行月度财务后置交叉核验。
* **`daily_attendance` (日明细结果表)**：逐日计算在岗状态，存储 `is_anomaly` 及具体异常理由。
* **`compensatory_leave_details` (调休流水明细表)**：记录每笔加班产生的调休假，用于计算产生的时长及 7/15/30 天催用时间差。
* **`vacation_balances` (假期余额表)**：管理年假及调休假余额。
* **`national_holidays` (国家节假日日历表)**：用于手动导入法定公休日与调班补班工作日。

---

## 2. 接口集成规范（阶段二）

1. **企业微信 API 对接**：
   - **获取打卡数据** (`/cgi-bin/checkin/getcheckindata`)。
   - **获取审批详情** (`/cgi-bin/oa/getapprovaldetail`)。
   - **获取成员信息** (`/cgi-bin/user/list`)。
   - **获取工作汇报数据** (`/cgi-bin/oa/getreportdata`)。
2. **腾讯地图 WebService API 对接 (出差定位锁)**：
   - 调用地址：`https://apis.map.qq.com/ws/place/v1/suggestion`
   - 控制流：员工点击“搜索/定位”按钮时触发单次 GET 请求，获取经纬度坐标（GCJ-02）。前端配置 500ms 防抖和 1s 节流。

---

## 3. 定时任务与核心审计算法逻辑（阶段二）

### 3.1 日基础考勤审计 (T-1 日对账)
- **触发时间**：每日上午 09:00。
- **对账逻辑**：核对昨日拍照打卡/位置打卡或门禁刷卡时间。无有效打卡且无审批的，标记异常并发送催办邮件。

### 3.2 调休假三阶段催用提醒
- **触发时间**：每日上午 08:00。
- **算法逻辑**：
  - 扫描 `compensatory_leave_details` 中未用完的调休记录，计算天数差 `days_diff = 当前日期 - 产生日期`。
  - 若为 7 天、15 天、30 天，向员工发送催用邮件，并**抄送（CC）至六人监督与项目经理组（王晓、薛蕾、徐宏玮、杨丽丽、孔紫初、王楠）**。

### 3.3 月度终审与复合凭证交叉审计
- **触发时间**：每月 5 日凌晨 01:00。
- **算法逻辑**：
  1. **法定节假日分流**：核对 `national_holidays` 表，将法定节假日加班标记为法定工资支付，禁止计入调休余额。
  2. **加班后置复合凭证核对**：检查加班时段打卡情况、现场服务报告（`is_customer_signed` 必须为真且有签字及现场水印照片）。必要性为“客户要求”的，检查是否上传了聊天/邮件凭证；“自主加班”的，检查主管确认状态。
  3. **出差日报水印照片校验**：针对上月出差日期，检索对应的 `field_work_reports` 记录。若没有提交日报或 `watermark_image_url` 为空，当日 `daily_attendance.is_anomaly` 置为 `TRUE`，异常原由计为 *"出差日缺失现场工作日报或环境水印照片"*。
  4. **月度对账异常汇总**：向未通过终审的员工发送警告，并将全公司考勤报表发送给四位高管邮箱。
