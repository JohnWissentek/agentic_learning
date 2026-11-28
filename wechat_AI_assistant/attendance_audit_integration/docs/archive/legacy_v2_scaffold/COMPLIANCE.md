# 开发过程与标准对齐说明（交付客户用，一页纸）

> 本文件随安装包交付，说明本软件的开发过程质量保证——写给客户技术负责人看，只写事实，每条可出示证据。

---

## 项目信息

| 项 | 内容 |
|---|---|
| 软件名称 / 版本 | attendance_audit_integration（企业微信考勤与请假审计系统）一期 / v0.4 |
| 交付范围 | 一期（Stage One）：企微考勤打卡对账 + 请假/外出/出差审批勾稽 + 调休入账 + 异常告警 + 日/周/月审计报表 |
| 制度依据 | 《企业微信打卡及请假说明》2025-04-01；《考勤管理制度》2025-03-12；《差旅管理制度》2025-03-12 |
| PRD 版本 | v0.4（2026-07-14） |
| 部署环境 | 阿里云 ECS（Docker Compose + Cron CLI） |
| 运行时 | Python ≥3.9 / PostgreSQL / Docker |
| 交付方 / 联系方式 | 深圳慧联达科技有限公司（Wissentek） |

---

## 开发过程对齐

本软件按对齐 **ISO/IEC 29110（超小型组织软件工程剖面）** 的六阶段流程开发：需求定义 → 架构设计 → 开发 → 测试 → 验收 → 运维支持。每阶段有书面出口条件并留有记录。

| 质量保证项 | 采用的机制 | 证据（随附/可查验） |
|---|---|---|
| 需求可追溯 | 14 条功能编号（F1–F14）贯穿 PRD → ARCHITECTURE → 伪代码 → 代码 → 测试；26 条异常场景（E1–E26）逐条登记 | `docs/PRD.md` 功能清单 §2 + 异常清单 §6.6 + `docs/STATUS.md` 功能追踪矩阵 |
| 设计与实现一致 | 架构图（Mermaid）与代码 import 关系自动对账（66 条边 1:1），不一致禁止合入 | `tools/check_traceability.py`（pytest 门禁）+ `tools/git-hooks/` 提交钩子 |
| 图文档齐备 | 5 类架构图（系统上下文 / 模块结构 / 核心流程+审计规则 / 函数调用 / 参数路径），按 `code_dev_audit_framework_v2` 复杂度红线（单图 ≤12 节点/≤15 边/单节点度 ≤6）拆为 23 张 Mermaid 小图，均附中文图解（📖） | `docs/ARCHITECTURE.md`（Mermaid）+ `docs/canvas/`（21 个 Obsidian Canvas，一图一文件） |
| 伪代码先行 | 每个代码文件先写伪代码（含异常与边界），通过人审后再编码 | `docs/pseudocode/*.md`（9 个模块） |
| 异常与边界覆盖 | 26 条异常场景逐条登记（E1–E26），各有期望行为与对应测试（ISO/IEC/IEEE 29119 风险驱动） | `docs/PRD.md` §6.6 + 测试报告 |
| 自动化测试 | 单元测试 53 项（含 F11 收件人合规、GPS 围栏阈值、工时常量、瞬移检测、图-代码对账） | `tests/unit/` — `pytest` 全绿 |
| 长时运行稳定性 | 交付前 ≥72 小时连续运行 + 故障注入演练（断网/断电重启/磁盘满） | `docs/soak_report.md`（交付时附） |
| 无人值守自愈 | Docker restart 策略；CLI exit code 供 Cron 感知；幂等设计（重复跑不重复扣薪/发邮件）；诊断命令一键导出 | `docs/ARCHITECTURE.md` §10 |
| 安全 | 凭证独立存放（`.env`），代码零硬编码；Webhook 验签；日志脱敏（禁止打印 secret/token）；不存储人脸特征 | 代码审查 + 日志样本 + PRD §7.3 |
| 个人信息保护 | 不自建生物识别库；不存人脸特征；考勤数据仅用于考勤审计；二期硬件监测须单独知情同意 | `docs/PRD.md` 附录 A §5 |
| 可移植性 | Python ≥3.9；依赖见 `pyproject.toml`；配置全环境变量化（`config.py` + `.env`） | PRD §7.6 + 最低版本测试记录 |
| 远程可支持 | 一键诊断包（`python -m attendance_audit_integration.diagnostics`：日志+脱敏配置+自检），密钥不出客户服务器 | 现场演示 |

---

## 外部依赖清单

| 外部系统 | 用途 | 凭证位置 | 失败策略 |
|---|---|---|---|
| 企业微信 OpenAPI | 打卡/审批/成员/日报 | `.env` WECOM_* | 指数退避重试（1s→2s→4s，最多 3 次）；失败记日志，不静默成功 |
| 企微 Webhook 回调 | 事件推送（可选） | WECOM_TOKEN / AES_KEY | 验签失败直接拒绝 |
| PostgreSQL | 持久化 | DATABASE_URL | 快速失败；事务回滚 |
| SMTP 邮件 | 告警/报表 | SMTP_* | 有限重试 + 管理员告警；TEST_MODE 可拦截收件人 |
| 本地花名册 JSON | 员工姓名/邮箱映射 | `data/employee_roster.json` | 匹配失败入待处理队列；缺文件启动失败 |
| Cron + Docker | 定时与部署 | 宿主机配置 | 进程崩溃依赖编排重启；任务须幂等 |

---

## 已知限制与明确不做的事

以下事项在一期（Stage One）范围内**明确不实施**，如实列出：

### 二期硬件与交叉审计（不做）
- 不部署 BLT1 蓝牙打卡器、联网门禁及 Wi-Fi/蓝牙/门禁三合一交叉审计
- 外勤 GPS 围栏强校验（F13）不接入日审主流程——一期仅消费企微已有打卡字段

### 自动处分（不做）
- 不自动执行旷工扣薪/辞退处分——惩戒须 HR 人工流转（民主五步法为前提）
- 严重违纪门槛（连续/累计旷工自动处分）属二期制度启用范畴

### 功能边界（不做）
- 不自建人脸/生物识别库或人脸特征存储（一期只消费企微现网打卡结果）
- 不调用法定节假日外部 API（全年手动维护 `national_holidays` 表）
- 不做完整 HR Web 门户看板（MVP 以 CLI/API + 邮件为主）
- 不改造企微审批表单本体（只拉取现有数据）
- 已封账月份不自动重算（须 HR 正式追溯调整）

### 已知技术限制
- 日审规模设计按 ≤30 人预留，不支持百人以上高并发场景
- 法定假数据需年初手动录入，无自动同步
- 外勤 GPS 距离 >200m 判定一期仅记录日志，不自动触发打卡无效（留二期 F13）

---

## 合规要点摘要

来源：`docs/PRD.md` 附录 A（并入自 `docs/archive/law_regulation_consulting/legal_opinion_and_procedures.md`）。

| 合规项 | 要点 | PRD 落点 |
|---|---|---|
| 缺卡闭环 | 催告 → 年假/调休 → 事假 → 逾期记旷工；禁止罚款式扣款与强制扣年假 | 附录 A §1、E15–E17 |
| 扣薪公式 | 事假/旷工：`基本工资 ÷ 21.75 × 缺勤天数`；本系统仅计算并导出，不自动执行扣薪 | 附录 A §2 |
| 旷工定量 | 单次缺一侧卡 0.5 天；全日双缺 1 天 | 附录 A §3、E1 |
| 民主五步法 | 为自动惩戒前提；无全员送达签字则制度对该员工无效——本系统一期不自动处分 | 附录 A §4 |
| 个人信息保护 | 不自建生物识别库、不存人脸特征；企微侧人脸/定位由其平台告知同意约束；二期硬件监测须单独知情同意 | 附录 A §5、附录 B |

---

## 质量闸门清单

开发过程中强制执行以下自动化闸门：

| 闸门 | 工具 | 触发时机 | 通过标准 |
|---|---|---|---|
| 图-代码溯源对账 | `tools/check_traceability.py` | `pytest` + pre-commit | 声明边 = 真实边（当前 66/66） |
| 模块循环依赖检测 | 同上（`find_cycle`） | `pytest` + pre-commit | 无环 |
| 跨模块私有接口调用检测 | 同上（`private_violations`） | `pytest` + pre-commit | 0 违规 |
| F11 收件人合规 | `test_phase4_remediation.py` | `pytest` | TO=PM_EMAILS（孔/王），CC=F11_CC_EMAILS（徐/薛），禁发被催员工 |
| 工时硬参数存在性 | `test_phase4_remediation.py` | `pytest` | 11 个常量值与 PRD v0.4 一致 |
| GPS 围栏阈值 | `test_phase4_remediation.py` | `pytest` | ≤200m 有效、>200m 无效 |
| 瞬移检测 | `test_phase4_remediation.py` | `pytest` | >350km/h 标记虚拟定位 |
| 提交信息分级 | `tools/git-hooks/prepare-commit-msg` 与 `github_push` 生成的 `commit-msg` | git commit | 标题为 `<类型>(L1–L4\|init[/范围]): <中文摘要>`；`Device`/`Hardware` 由钩子写入 |

---

## 证据文件索引

| 证据文件 | 路径 | 内容 |
|---|---|---|
| 产品需求文档 | `docs/PRD.md` | v0.4，含功能清单、业务规则、异常场景、合规附录 |
| 架构文档 | `docs/ARCHITECTURE.md` | 23 张 Mermaid 小图（按复杂度红线拆分）+ 图解 + 速查表 |
| 架构图 Canvas（人审） | `docs/canvas/*.canvas` | 21 个 Obsidian Canvas，一图一文件，与 Mermaid 一一对应 |
| 伪代码 | `docs/pseudocode/*.md` | 9 个模块的伪代码（含异常分支） |
| 开发状态 | `docs/STATUS.md` | 功能追踪矩阵 + 开发日志 |
| 开发检查清单 | `docs/CHECKLIST.md` | 六阶段出口条件 |
| 测试报告 | `tests/` | 53 项自动化测试 |
| 溯源对账工具 | `tools/check_traceability.py` | 图-代码自动 diff |
| Canvas 生成工具 | `tools/generate_canvas.py` | Mermaid → Obsidian Canvas 自动转换 |
| 归档文件（只读） | `docs/archive/` | 历史 PRD、法务意见、WiFi/蓝牙专题 |
| 长时运行报告 | `docs/soak_report.md` | 交付时附（≥72h 连续运行记录） |

---

## 支持约定

| 项 | 约定 |
|---|---|
| 问题反馈方式 | 客户执行 `python -m attendance_audit_integration.diagnostics` 导出诊断包（日志+脱敏配置），发送至技术支持邮箱 |
| 响应时限 | 收到诊断包后 2 个工作日内响应 |
| 升级方式 | Docker 镜像 + `docker-compose pull && docker-compose up -d`；支持回滚到前一版本 |
| 日志保留 | 运行日志默认保留 90 天；审计日志（`audit_logs` 表）永久保留 |
| 远程支持 | 诊断包机制确保密钥不出客户服务器；如需远程接入须客户授权 |

> 说明：本软件开发过程对齐上述标准的实质要求，未申请第三方认证。各证据文件可应要求提供查验。
