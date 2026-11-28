# 项目状态总账（STATUS.md）

> AI 每次会话结束前必须更新。人工签字勾在 `docs/CHECKLIST.md`。【人】项默认不代勾。

---

## 0. 当前状态与待办队列

| 项 | 内容 |
|---|---|
| **当前阶段** | v0.7 一阶段（纯企微独立考勤分析）**Slice 1 / Slice 2 / Slice 3 代码与 TDD 全部完工绿灯**；**F15 金蝶交叉审计划归二阶段** |
| **阻塞事项** | 企微后台 P0（`Hermes Agent` 汇报授权）与 P1（请假审批流修复、补卡 2 次/仅缺卡、加班取消自动入调休）均已完成并二次核验；仅剩「假期余额核对（离职清理/王旭 219.5h/首次工作时间）」待周一与同事核对 |
| 最后更新 | 2026-11-29 |

### 待办队列

| 序 | 待办 | 对应 | 状态 |
|---|---|---|---|
| 1 | ~~L1 v0.5：规则口径对齐 8/21 确认版制度（动态 8.5h/9.0h、被动抵扣 4h、坐班取消补卡、废 16h 上限）+ F15 立项，全链 PRD→图→伪代码→代码→测试~~ | 会话 N | ✅ 79 项测试全绿含对账门禁 |
| 2 | tools/generate_canvas.py 更新图定义 | L2 债 | ⏸️ lightweight 本轮不强制新画 Canvas，已有图保留 |
| 3 | F15 金蝶差旅报销交叉审计 | F15 | ⏸️ 本轮搁置，代码保留，不等金蝶凭证 |
| 3b | F10 大交通在途、F12 审批重叠 | F10 / F12 | ⏸️ 本轮搁置，不作为日审月审出口 |
| 4 | 被动抵扣月 4h 上限的**月度累计核算**（当前日审邮件已提示、月审只列待核条数；累计追踪与超限无酬导出未实现，E27 完整闭环） | F1 | ⬜ |
| 5 | 【人】PRD §8（v0.5）；4 项 HR 裁定见阻塞事项；企微后台按 8:30–19:00 开口重配并公告「迟到标签不作薪资依据」 | 阶段一出口 | ⬜ |
| 6 | F13 GPS 围栏强校验 — **二期，本期不排期** | 二期 | ⏸️ |
| 7 | 安装 ruff + 设置 git hooks（`core.hooksPath`） | 阶段三闸门 | ⬜ |
| 8 | PRD 6.6 异常场景补测（E1–E33；本轮已覆盖 E24/E27 分级/E29/E30/E31/E33 纯函数层） | 阶段四 | ⬜ |
| 9 | sync_real_daily_reports 字段抽取需真实日报模板 control_id 精确映射 | F4 | ⬜ |
| 10 | 补齐阿里云服务器 `.env`：`WECOM_TOKEN`/`WECOM_ENCODING_AES_KEY`、`WECOM_DAILY_REPORT_TEMPLATE_ID` | 会话M | ⬜ |
| 11 | 【人】决定是否需要向误收到假阳性"考勤对账确认"邮件的员工做说明 | 会话M | ⬜ |
| 12 | 生产库历史 daily_attendance 中旧 `late` 记录按新口径属「待核」，月审已兼容读取；封账前【人】确认历史周期是否需要按新规则重跑 | L1 v0.5 | ⬜ |

---

## 1. 阶段门状态表

| 阶段 | 状态 | 通过日期 | 备注 |
|---|---|---|---|
| 一、需求定义 | 🔵 | | PRD v0.4 一期范围已写入；【AI】项全部 ✅；待【人】确认 §8 |
| 二、架构设计 | ⬜ | | 【AI】项全部 ✅（含 5 类图；按框架复杂度红线拆为 23 张 Mermaid 小图 + 21 个 Canvas，一图一文件；对账 66/66）；待【人】架构评审 + scaffold/hooks 收尾 |
| 三、开发 | ⬜ | | 代码拆分+重试+F11 已完成；ruff 未安装、日志打点待查、功能矩阵逐项待刷新 |
| 四、测试 | ⬜ | | unit 53 项全绿（含对账门禁+F11+工时常量）；集成测试/异常场景测试待补 |
| 五、验收与交付 | ⬜ | | COMPLIANCE ✅；浸泡/README/可移植性待做 |
| 六、运维与维护 | ⬜ | | |

---

## 2. 功能追踪矩阵

| 功能ID | 名称 | PRD | 图节点 | 伪代码 | 代码 | 测试 | 对账✓ | 验收 |
|---|---|---|---|---|---|---|---|---|
| F1 | 日基础考勤对账（一期） | ✓ | 🔵 | ✓ | 🔵 | 🔵 | ⬜ | ⬜ |
| F2 | 防作弊-企微字段（一期） | ✓ | 🔵 | ✓ | 🔵 | 🔵 | ⬜ | ⬜ |
| F3 | 强制现场打卡依赖（一期） | ✓ | 🔵 | ✓ | 🔵 | ⬜ | ⬜ | ⬜ |
| F4 | 出差日报审计（一期） | ✓ | 🔵 | ✓ | 🔵 | ⬜ | ⬜ | ⬜ |
| F5 | 服务报告签字（一期） | ✓ | 🔵 | ✓ | 🔵 | ✓ | ⬜ | ⬜ |
| F6 | 调休流水（一期） | ✓ | 🔵 | ✓ | 🔵 | ✓ | ⬜ | ⬜ |
| F7 | 周/月审计邮件（一期） | ✓ | 🔵 | ✓ | 🔵 | 🔵 | ⬜ | ⬜ |
| F8 | 花名册映射（一期） | ✓ | 🔵 | ✓ | 🔵 | ⬜ | ⬜ | ⬜ |
| F9 | 法定假日历（一期） | ✓ | 🔵 | ✓ | 🔵 | ✓ | ⬜ | ⬜ |
| F10 | 大交通在途（一期） | ✓ | ⬜ | ✓ | ⬜ | ⬜ | ⬜ | ⬜ |
| F11 | 调休催用仅孔/王+CC徐/薛（一期） | ✓ | 🔵 | ✓ | ✓ | ✓ | ⬜ | ⬜ |
| F12 | 审批重叠（一期） | ✓ | ⬜ | ✓ | ⬜ | ⬜ | ⬜ | ⬜ |
| F13 | GPS 围栏强校验（**二期**） | ✓ | ⏸️ | ⏸️ | ⏸️ | ⏸️ | ⏸️ | ⏸️ |
| F14 | 封账与审计痕迹（一期） | ✓ | 🔵 | ✓ | ✓ | 🔵 | ⬜ | ⬜ |
| F15 | 金蝶差旅报销交叉审计（一期 v0.5 新增） | ✓ | ✓ | ✓ | 🔵 | 🔵 | ✓ | ⬜ |

> v0.5 注：F1 判定核心已切换为动态工时（work_hours.py，制度 3.1.1），单元测试覆盖 E24/E29/E30 边界；F15 代码为可运行骨架（登录/查询/判定/降级/邮件全链），🔵=待真实金蝶账套 dry-run 校准字段后转 ✓。

---

## 3. 开发日志

### 2026-11-29（L1/L4 v0.7：合并去重 `attendance_audit_technical_plans`、归档旧 v2 脚手架、明确企微独立一阶段 / 金蝶联动二阶段）
- **做了什么**：
  - 将原平行目录 `attendance_audit_technical_plans/` 的 5 篇文档去重并入本项目 `docs/` 并删除原目录：保留 `F16_vacation_ledger_rebuild.md` 与 `future_multimodal_llm_research.md` 至 `docs/proposals/`；精简并纠错 `wecom_openapi.md` 至 `docs/reference/`（修正企微汇报接口为两步 `oa/journal/get_record_list` + `get_record_detail`，补全接口实现现状对照）；彻底清除旧部署文档中的明文 PostgreSQL 密码，并对照真实 `db.py` / `cli.py` / `main.py` / `config.py` / `docker-compose.yml` 重写 `docs/DEPLOYMENT.md`。
  - 采用方案 A，将旧版 v2 重脚手架历史产物（`canvas/`、`pseudocode/`、`COMPLIANCE.md`、`CHECKLIST.md`、`specs/`、`plans/`、`ui/` 及重复的《候补核销规范》）统一冻结移入 `docs/archive/legacy_v2_scaffold/`；清理 `*.egg-info`、`__pycache__` 与本地日志产物。
  - 更新 `PRD.md`（v0.7）与 `README.md`：拍板两阶段演进边界——**一阶段依靠企业微信独立做考勤分析**，金蝶报销交叉审计由财务人工完成；**二阶段待金蝶 Agent 自动化后合并 F15 双向自动交叉审计**。
  - 通过 Chrome DevTools 完成维恩科仪企业微信管理后台**严格只读全量盘点**，形成 `docs/reference/wecom_live_inventory.md`，摸清全部打卡规则、5 个核心假勤审批模板 ID、11 种假期真实 ID 与逾期缺失现状、6 个启用汇报模板 ID（含带客户手写签名的《现场技术支持工作报告》）及自建应用权限缺口。
  - 沉淀审计与升级总方案 `docs/AUDIT_AND_UPGRADE_PLAN.md`，并按红绿灯 TDD 完成一阶段全部 3 个垂直薄切片：
    - **Slice 1**：`config.py` 注入 5 个真实审批模板 ID、6 个启用汇报模板 ID 与真实假期 ID（`1=年假/2=事假/3=病假/4=调休假`）；`wecom_api.py` 补齐 `fetch_approval_ids` 分页拉取，修复汇报接口为官方两步 `oa/journal/get_record_list` + `get_record_detail`；`services/daily_audit.py` 新增 `parse_approval_detail`、`sync_real_approvals`、`parse_journal_detail`（自动识别《现场技术支持工作报告》客户手写签名并幂等写入 `service_reports`，打通 F5 真实数据）。
    - **Slice 2**：`wecom_api.py` 新增只读假期接口 `fetch_vacation_corp_conf` / `fetch_user_vacation_quota`；新建 `services/vacation_audit.py` 同步真实余额并检出调休堆积（仅发 PM 禁发本人）、年假偏高、离职残留余额与病假 0 限额风险；接线 `audit_engine.py`、`cli.py`（`vacation-audit`）与 `docs/ARCHITECTURE.md` §3.0a/§3.5。
    - **Slice 3**：`services/daily_audit.py` 新增 `compute_approved_offset_hours`（同时识别请假与外出审批折抵）、`sync_single_approval`、`sync_period_approvals_and_reports`；升级 `main.py` 回调详情补全与 `POST /audit/vacation`；升级 `cli.py monthly --sync` 月审前置同步。
- **验证**：全套 96 项测试全绿 + `check_traceability.py` 83/83 1:1 对齐 + `ruff check`（新增/改动文件）零错误。
- **下一步**：负责人按 `docs/AUDIT_AND_UPGRADE_PLAN.md` §五完成企微后台 P0 手动操作（为 `Hermes Agent` 勾选「汇报」API 权限），随后安排部署与实弹验证。

### 2026-11-13（init：系统提示词收到工作区根，Python 环境改到根目录 `.venv`）
- **做了什么**：核对子目录系统提示词后直接删除，没有并入根目录。`attendance_audit_integration/.cursor`、`.agent` 与根目录对应文件内容相同；`.claude/skills/mvp-dev-framework` 与根目录 `.cursor/skills/mvp-dev-framework` 相同；`.codex/AGENTS.md`、包内 `AGENTS.md`、`CLAUDE.md` 都是根目录 `AGENTS.md` 与 `.cursor`/`.agent` 的复述或指针。其他子目录没有同类提示词。根目录 `.cursor`、`.agent`、`.env` 保留。业务包 `.env` 保留。在工作区根用 Python 3.14.8 建立 `.venv`。随后按人的要求删掉仅为指定解释器而加的 `.vscode`。按 `github_push setup` 把提交钩子装到 `attendance_audit_integration/tools/git-hooks/commit-msg`；`core.hooksPath` 已指向该目录，级别检查仍在同目录的 `prepare-commit-msg`。
- **变更级别**：init（工作区环境，不改需求、设计和公开签名）

### 2026-10-20（L1 v0.6：本轮只收口日审与月审）
- **做了什么**：人确认三件事。清理只删除 `.venv`、`.pytest_cache`、`__pycache__` 和空的 `backups`。治理档位改为 `lightweight`，写入 `tools/gate_overrides.conf`。本轮出口定为日审邮件和月审邮件；F10、F12、F15 搁置，代码和 `docs/archive/` 保留。
- **变更级别**：L1（PRD v0.6 交付边界）

### 2026-08-28 会话 N（L1 v0.5：规则口径对齐 2026-08-21 民主确认版制度 + F15 金蝶差旅报销交叉审计立项）
- **做了什么**：L1——用户确认：本项目全部规则口径基于 2025 旧制度（8/21 民主程序确认的新版制度已生效，旧版作废），须重新审计修订；并确认考勤审计需与金蝶出差报销交叉才能审差旅补助（缺口属实）。经检索代理盘点：8 个文件约 46 处旧参数落点（config.py 11 个常量 + 11 条测试断言 + PRD/ARCH/伪代码），且旧常量从未被引擎消费（判定仍按打卡条数）；被动抵扣 4h/在途分级/补助减半三项新规则完全缺失。用户拍板：规则对齐 + F15 一起立项（PRD 一次改到位）、F15 一期只做补助减半核对、金蝶复用现有客户端只读接入。
  - **PRD v0.5**：§4.1 规则参数表整体重写（8:30–18:30 大区间、动态 8.5h/9.0h、10:00 为推导值非卡点、被动抵扣月 4h、坐班取消遗忘补卡、加班无月上限废 16h、在途调休 ≤2h/2–4h=0.5天/>4h=1天、无酬缺勤 ÷21.75÷8×小时、旷工=出勤<4h 无审批预警 1 天）；§4.2-1 日审判定重写为动态公式；新增 §4.2-11 在途调休、§4.2-12 F15 规则条文；E24/E25 改口径，新增 E27–E33；新增 US-6；附录 A/C 对齐新制度条款号
  - **ARCHITECTURE**：§4.0 速查表重写；§4.2 判定主线由「数打卡条数折 0.5/1.0 天」改为动态工时判定黑盒；§4.6 由「旷工折算」改为「缺额核销 + 被动抵扣 4h 上限」；新增 §4.7 F15 流程图、§3.4 F15 依赖子图；§3.0a/3.0b/3.1/3.3b 增边（work_hours/kingdee_client/expense_cross_audit 共 11 条，对账 77/77）；§9 失败策略表增金蝶行（只读、重试 2 次→降级跳过不阻塞主流程）
  - **伪代码**：config.md 补全部工时常量；audit_engine.md 判定段重写（含「禁止写死 10:00」告诫）；cli.md 增 expense-cross 命令；新增 work_hours.md、kingdee_client.md、expense_cross_audit.md
  - **代码**：config.py 删 11 个旧常量、增 17 个新常量 + KINGDEE_* 配置；新增 work_hours.py（动态工时纯函数：截断/顺延/请假抵扣/三级判定）；daily_audit.py 接入动态判定（请假按小时折算、单侧缺卡改标待核不折天、缺额邮件含公式明细）；monthly_audit.py 废 late×0.5（absent×1 + 待核条数，兼容历史 late 行）；mail_sender.py 核对指引改新制度四条路径；新增 kingdee_client.py（只读双接口）、services/expense_cross_audit.py（补助减半核对 + 降级告警 + 待核邮件）；cli.py 增 `expense-cross` 命令（编排在 cli 层，守住 Services 互不调用铁律）
  - **测试**：TestWorkHourConstants 重写（新常量断言 + 旧常量「禁止复活」断言）；新增 test_work_hours_v05.py 14 项（10:00 推导边界、8:30 起算、18:30/19:00 截断、9.0h 顺延、10:00+N 请假顺延、4h 旷工/待核边界、补助减半 5 个判定边界）
- **变更级别**：L1（v0.5）
- **改动的文档/文件**：docs/PRD.md；docs/ARCHITECTURE.md；docs/pseudocode/{config,audit_engine,cli}.md + 新增 {work_hours,kingdee_client,expense_cross_audit}.md；src/.../（config.py、work_hours.py 新、kingdee_client.py 新、audit_engine.py、cli.py、mail_sender.py、services/daily_audit.py、services/monthly_audit.py、services/expense_cross_audit.py 新）；tests/unit/{test_phase4_remediation.py, test_work_hours_v05.py 新}；.env.example（KINGDEE_*）；docs/STATUS.md
- **验证**：`pytest` **79 项全绿**（含 check_traceability 对账门禁 77/77 边）✅；ReadLints 无错误 ✅；ruff 仍未安装（既有待办，未新增）
- **已知限制（诚实披露）**：① tools/generate_canvas.py 内置图定义未跟上新 Mermaid（21 张 Canvas 与 §3.4/§4.7/§4.2/§4.6 等新图存在偏差），列待办 2；② 被动抵扣 4h 的**月度累计追踪**未实现（日审邮件已提示上限、月审只列待核条数），E27 完整闭环列待办 4；③ F15 的 FormId/FieldKeys 按金蝶通用元数据假设，须真实账套 dry-run 校准（待办 3）；在途时长一期取 0 并在差异行注明；④ 9.0h 顺延日引擎观测不到真实午休时长，当前保守按 8.5h 判定（不误伤员工），午休留痕方案属 PRD 待定项；⑤ 生产库历史 `late` 行未重算（月审已兼容归入待核），历史周期是否重跑待人裁定（待办 12）
- **下一步**：【人】确认 4 项 HR 裁定 + 提供金蝶只读凭证；更新 generate_canvas.py（待办 2）

### 2026-07-14 会话 M（部署上线阿里云 + 修复 3 个部署阻断 bug + 修复员工花名册 userid 漂移导致的重复邮件）
- **做了什么**：L3——用户要求把会话 L 的改造部署到阿里云生产服务器（`39.104.202.152`），清空原考勤部分重新部署，跑一次真实数据审计验证能收到邮件。执行前先只读排查确认：该服务器是共享机（同时跑 Odoo/Umami/金蝶同步），考勤容器是用户主动停的（非故障）。用户明确选择「只用真实数据跑，不在生产库跑 mock_data_populator」。
  - **部署前备份**：服务器现有代码 tar + 员工花名册.xlsx、生产库 `wecom_attendance` 完整 `pg_dump`，均下载到本地 `backups/20260714_234510/`（已在 `.gitignore`）
  - **发现并修复 3 个会导致 docker 容器直接起不来的阻断问题**（均为部署环境 bug，非本次业务改动）：
    1. `Dockerfile` 仍 `COPY src/requirements.txt`，但该文件早已归档为 `docs/archive/requirements_txt_pre_v2.txt`（改用 pyproject.toml）——改为 `pip install .`，同时补回 `ENV PYTHONPATH=/app/src`（否则 `pip install .` 把包装进 site-packages 后，`config.py` 用文件路径倒推的 `ROOT_DIR` 会算错，导致 `.env`/`data`/`logs` 全部读不到）
    2. `main.py` 模块加载期直接 `WXBizMsgCrypt(TOKEN, AES_KEY, CORPID)`，服务器 `.env` 未配置这两个企微回调专用变量时会 `ValueError` 直接拖挂整个 uvicorn 进程（包括跟回调无关的 `/audit/run` 等核心接口）——改为 try/except 降级为 `wxcrypt=None` + 503，回调功能与核心审计解耦
    3. 服务器 `.env` 的 `DATABASE_URL` 指向 `postgres@localhost:5432`（该角色根本不存在，`localhost` 在容器网络里也不通）——改回 `docker_wissentek` 网络里唯一存在的 `umami` 角色 + `wissentek-postgres` 主机名
  - **发现并修复 1 个业务逻辑缺陷**：`run_daily_audit` 里"仅当 employees 表为空才 `sync_employee_roster`"——这正是会话 L 的邮箱域名纠错（`data/employee_roster.json` 已改用 `@palmarytech.com`/`@wissentek.com`）永远在生产环境生效不了的根因（表非空后这段同步再也不会跑）。改为**每次日审都强制同步**。
  - **改完上一条后验证时又炸出一个新问题**：企微通讯录接口这次返回的 `userid` 大小写/格式和库里旧存的不一致（如「杨震」旧存 `YangZhen`，企微现在返回 `YangZhen_1`；「徐宏玮」现在是带后缀的 `XuHongWei@ZhiNengGaoSuJingMiCeShi`——经查 department 字段确认这是维恩科仪内部真实在职员工，非外部联系人，只是历史上 userid 格式变了）。`sync_employee_roster` 原来按 `wecom_userid` UPSERT，userid 一变就插出重复行，造成：① employees 表 19 人变 37 行（新旧并存）；② **当天对真实员工发出了重复的"考勤对账确认"邮件**，其中"杨震"那条还发到了已废弃的错误域名（旧行的邮箱字段没被这次同步碰过）。
  - **修复**：`sync_employee_roster` 改为**先按姓名查是否已有记录**：有则 UPDATE 该行的 `wecom_userid`/`email`/`role`/`company`（吸收 userid 漂移），没有才走原来按 `wecom_userid` UPSERT 的新员工插入路径；同时用当次企微返回的 19 个权威 userid 清理掉库里残留的 18 行旧脏数据（`DELETE ... WHERE wecom_userid NOT IN (...)`）
  - **最终验证跑**：重新触发 `/audit/run`（真实企微数据，日期 2026-07-13）→ employees 稳定在 19 行、`sync_employee_roster` 日志显示"Synced 19 employees"无异常，`daily_attendance` 表当天 17 名考核员工全部 `is_anomaly=false`（此前两次误报的"缺卡"全部确认是 userid 漂移导致的假阳性，不是真实考勤问题）→ 按预期只发出 1 封"公司每日考勤汇总日报"到 `john.xu@palmarytech.com`，无异常告警误发
- **变更级别**：L3（均为实现层修复：部署配置 + 一处 UPSERT 匹配键逻辑；未改架构/PRD）
- **改动的文档/文件**：Dockerfile；docker-compose.yml（新增 `./logs:/app/logs` 挂载，此前日志只在容器内、重建即丢失，属可观测性补强）；src/attendance_audit_integration/main.py；src/attendance_audit_integration/services/daily_audit.py；src/attendance_audit_integration/services/roster_sync.py；docs/pseudocode/main.md；docs/pseudocode/audit_engine.md
- **验证**：本地 `pytest` 64 项全绿 ✅；`check_traceability.py` 66/66 ✅；服务器容器 `docker-compose ps` 稳定 Up，`docker logs` 无异常；生产库 `employees` 表人工核对 19 行、邮箱域名全部正确、无重复
- **已知限制/遗留**（诚实披露）：
  - 服务器 `.env` 仍缺 `WECOM_TOKEN`/`WECOM_ENCODING_AES_KEY`（企微回调解密）与 `WECOM_DAILY_REPORT_TEMPLATE_ID`（F4 日报模板）——均已降级为"功能不可用但不影响核心审计"，需要人工找到真实凭证后补进服务器 `.env`
  - 历史 `attendance_logs`/`approvals` 里存的是员工 userid 变更**之前**的旧字符串快照，本次未做跨版本 userid 归并回填，属已知限制（见 audit_engine.md 伪代码注记）
  - 测试过程中因上述 bug 对真实员工误发了 2~3 轮"考勤对账确认"类邮件（内容为假阳性异常告警，非真实数据泄露/错误结论），已用最终干净跑验证收敛；未额外发送致歉邮件说明，需人工判断是否要跟员工解释
- **下一步**：【人】决定是否需要跟收到误报邮件的员工说明；补齐服务器 `.env` 缺失的 4 个企微变量；明天 8:30 crontab 会自动跑一次今日真实日审，可用于最终确认整条链路（无需再手动触发）

### 2026-07-14 会话 L（测试造数真实优先改造 + 修复 field_work_reports 生产缺口）
- **做了什么**：L3——用户反馈：此前用某段真实时间窗口做审计验证时，测试数据是 `mock_data_populator.py` 100% 随机造的，无法拿真实历史核对审计结果对不对；要求"系统里本身有的数据不要mock，只有场景系统里真没出现才补造，且要能标出哪些是真哪些是mock"。排查后发现：
  - `populate_mock_data()` 开头 `TRUNCATE` 会把库里已有的真实历史数据先删掉再全灌假数据（本次问题的病根）
  - `daily_audit.run_daily_audit` 里其实已有一段成熟的"拉企微真实打卡→写库"逻辑，但被锁死在函数内部，`mock_data_populator` 没法复用
  - `wecom_api.fetch_daily_reports`（真实日报批量拉取）早就实现了，但全代码库从未被调用——`field_work_reports` 表在**生产环境**实际上也从未被真实数据填充过，F4 出差日报核查一直只能看见 mock 数据（比测试工具问题更严重的生产缺口）
  - `approvals`（请假/出差/加班）只有 Webhook 实时推送，无批量按日期拉历史的接口；`service_reports`（客户签字）无任何真实接口——这两类本轮确认仍只能造 mock（用户已确认范围）
  - 改造方案（用户逐项确认后执行）：① 把打卡同步逻辑抽成 `services/daily_audit.sync_real_punches`，`run_daily_audit` 与 `populate_test_data` 共用；② 新增 `sync_real_daily_reports` 并接入 `run_daily_audit`（修复生产缺口，字段抽取为最佳努力递归解析，非精确 control_id 映射，已在伪代码标注待办）；③ 新建 `test_data_provenance` 溯源表，仅登记 mock 行（表名+主键），未登记=真实；④ `populate_test_data(start_date, end_date)` 改为真实优先：先拉真实打卡/日报（不清空历史），仅当 E1/漏卡、E11/设备异常、E12/瞬移在整窗口里完全没出现时才各补 1 条并登记 provenance；approvals/service_reports 仍固定造数但全部登记 provenance；⑤ `_purge_previous_mock_rows` 用 provenance 精确删除代替 TRUNCATE，重跑幂等且不再误删真实数据；⑥ `run_demo_tests.py` 新增 `--start-date/--end-date` 让用户指定要验证的真实月份/时间窗口
  - 图层面：为避免新增 `mock→wecom_api`/`mock→services.daily_audit` 边，改为把 `sync_real_punches`/`sync_real_daily_reports` 挂到 `audit_engine.py` 门面 re-export（`mock_data_populator` 继续只经门面调用，不直连 services），架构图节点/边数量不变（仍 66/66 对账通过），本次定级 **L3**（伪代码大改，图不动）而非最初预估的 L2
- **变更级别**：L3
- **改动的文档/文件**：src/{db.py, mock_data_populator.py, audit_engine.py, services/daily_audit.py}；scripts/run_demo_tests.py；docs/pseudocode/{db.md, audit_engine.md, mock_data_populator.md, wecom_api.md}；docs/ARCHITECTURE.md（§3.0 mock 节点/边文案更新，未改图结构）；tools/generate_canvas.py + docs/canvas/02_module_structure.canvas；tests/unit/{test_mock_data_populator.py, test_mock_data_populator_smoke.py}（新增，共 11 项：纯逻辑判定 + 假游标干跑烟雾测试校验全部 SQL 占位符/参数数量一致）
- **验证**：`pytest` 64 项全绿（含新增 11 项）；`check_traceability.py` 66/66 ✅（图未变）；`generate_canvas.py` 21/21 图仍在复杂度红线内 ✅；本地无 Postgres 环境，`populate_test_data` 未做真实数据库集成测试，已用假游标校验 SQL 结构（占位符数量对齐），**下一步人工在有真实企微凭证的环境跑一次 `scripts/run_demo_tests.py --start-date ... --end-date ...` 验证真实拉取分支**
- **已知限制（诚实披露，未虚标）**：① `sync_real_daily_reports` 的字段抽取是通用递归最佳努力解析，未按该企业真实日报模板 control_id 精确映射，字段可能不准，raw_payload 已落库兜底；② E12 瞬移的"真实覆盖"判定是经纬度差值+时间差的粗粒度启发式，非精确速度计算，只用于决定"要不要补一条 mock"，不是审计结论；③ approvals/service_reports 本轮仍 100% mock（无真实批量拉取渠道），已在 provenance 表如实登记
- **下一步**：【人】在配置了真实企微凭证的环境跑一次 demo 测试，用真实发生过的月份核对审计结果；确认 field_work_reports 补上真实拉取后 F4 检查结果是否符合预期

### 2026-07-14 会话 K（自查修复：db 节点圆柱标签的溯源脚本隐患）
- **做了什么**：L3——会话 J 收尾后自查发现 §3.0/3.1b/3.2/3.3a 四处 `db[("db.py")]`（圆柱形节点+引号）会被 `check_traceability.py` 误解析出 `("db` 这种带括号的假模块名；当前之所以仍能对账 66/66，是因为 §3.3b 里 `db["db.py<br/>..."]`（普通方框、后处理）恰好把 `node_labels["db"]` 覆盖回正确值——这是"运气好"而非"设计对"，一旦以后只留圆柱写法就会误判。为消除该隐患：① 把 4 处圆柱形 `db[("db.py")]` 统一改成普通方框 `db["db.py"]`（图的视觉含义不变，圆柱形状仅保留给 §6b 里真正的数据库表节点）；② 加固 `_strip_label_quotes`，改为循环剥离最多两层「引号」/「圆括号」包裹，即使以后再出现圆柱+引号写法也能正确剥出模块名，不再依赖"后面某张图覆盖前面的错误映射"这种偶然顺序。
- **变更级别**：L3（不改图的节点/边语义，只改标签书写方式 + 脚本健壮性）
- **改动的文档/文件**：ARCHITECTURE.md（4 处 `db[("db.py")]` → `db["db.py"]`，边数不变仍 66 条）；tools/check_traceability.py（`_strip_label_quotes` 加固为可剥两层包裹）
- **验证**：`check_traceability.py` 66/66 ✅（修复前虽然也显示 66/66，但依赖的是模块名重复定义顺序的偶然性，非稳健对账）；`generate_canvas.py` 重新生成 21/21 图仍在复杂度红线内 ✅；`pytest` 53 项全绿 ✅
- **下一步**：同会话 J——【人】在 Obsidian 打开新的 02–02h / 03–03d / 05a–b 审图是否清晰；PRD §8 验收勾仍待人工确认

### 2026-07-14 会话 J（按 code_dev_audit_framework_v2 新约定重排全部图）
- **做了什么**：L2——用户要求按 `code_dev_audit_framework_v2` 脚手架新版框架总纲 3.1/3.3（图的双轨制 + 复杂度红线：单图 ≤12 节点/≤15 边/单节点度 ≤6）重排本项目全部 Mermaid+Canvas：
  - §2 系统上下文：合并 Cron/管理员为「触发源」，修正 App 节点连线度超限
  - §3 模块结构：原「总图+3子图」4 张图（含 19 节点/23 边/度 11 的严重超限总图）拆为 9 张小图（3.0/3.0a/3.0b/3.1/3.1b/3.2/3.2b/3.3a/3.3b），真实依赖边（66 条）原样保留、只是分散到更多小图
  - §4 审计规则：4.0/4.7 两张纯参数「伪图」（无实质连线）改写为速查表；4.2（16节点/18边）拆出 4.2a 防作弊子图（用 ⬅入口/➡出口 接口节点对应总图 📦 黑盒）；4.5（14节点）把复合校验 3 步黑盒化为 1 节点
  - §5 函数调用：5.1 合并两个渲染函数节点，消除度超限
  - §6 参数路径：拆为 6a 配置流 / 6b 数据流（原图混杂两件不相关的事）
  - 修复 `tools/check_traceability.py` 的引号解析 bug（新图普遍用带引号的多行标签，旧正则未去引号导致模块名带 `"` 前缀，误判 65 条边）；同时加固：黑盒节点若合并多个 `.py` 文件名，不登记为真实模块节点，避免误配对
  - 全量重写 `tools/generate_canvas.py`，Canvas 从 11 个扩展到 21 个，一图一文件对应新 Mermaid 结构；新增 3 张此前缺失的子图 Canvas（03a 防作弊 / 03b GPS围栏 / 03c 缺卡申诉，Mermaid 一直有但 Canvas 之前漏画）
- **变更级别**：L2
- **改动的文档/文件**：ARCHITECTURE.md（全篇重排）；tools/check_traceability.py（引号解析修复）；tools/generate_canvas.py（全量重写）；docs/canvas/*.canvas（21 个）；COMPLIANCE.md；CHECKLIST.md；STATUS.md
- **验证**：`check_traceability.py` 66/66 ✅；`pytest` 53 项全绿 ✅；`generate_canvas.py` 自检 21/21 图均在复杂度红线内 ✅
- **下一步**：【人】在 Obsidian 打开新的 02–02h / 03–03d / 05a–b 审图是否清晰；PRD §8 验收勾仍待人工确认

### 2026-07-14 会话 I（Canvas 总图+子图拆分）
- **做了什么**：L2——按 ARCHITECTURE §3/§5 同样策略，把拥挤的 `02_module_structure` / `04_function_calls` 单文件拆成总图 + 子图多文件；更新 `tools/generate_canvas.py` 并重新生成；ARCHITECTURE 增加 Canvas 对照表；COMPLIANCE 改为 11 个 Canvas。
- **变更级别**：L2
- **改动的文档/文件**：tools/generate_canvas.py；docs/canvas/02*.canvas、04*.canvas（新建 02a/b/c、04a/b/c）；ARCHITECTURE.md；COMPLIANCE.md；STATUS.md
- **下一步**：【人】在 Obsidian 打开 02 / 02a–c 与 04 / 04a–c 审图是否清晰

### 2026-07-14 会话 H（COMPLIANCE 补全 + 进度审计修正）
- **做了什么**：
  - **L4** `COMPLIANCE.md` 从空模板补全为完整交付文档（项目信息/12项质量保证/依赖/限制/合规/闸门/证据索引/支持约定）
  - **L4** CHECKLIST.md 审计修正：15 项已完成但漏勾的【AI】项补标 ✅
  - **L4** STATUS.md 审计修正：阶段门虚标（二/三从 ✅→🟢）、测试数（42→53）、待办队列（#2/#3 标 ✅）、F11/F3 矩阵修正、补录本会话日志
- **变更级别**：L4
- **改动的文档/文件**：COMPLIANCE.md, CHECKLIST.md, STATUS.md
- **验证**：53 项测试全绿 ✅；溯源对账 66/66 ✅
- **下一步**：安装 ruff + 设置 git hooks；F10/F12 排期；【人】PRD §8

### 2026-07-14 会话 G（图拆分 + Canvas 生成）
- **做了什么**：
  - **L2** `ARCHITECTURE.md` §3 模块结构图拆为 1 总图 + 3 子图（日审/月审/基础设施），原 68 边单图→每图 ≤15 边
  - **L2** `ARCHITECTURE.md` §5 函数调用图拆为 1 总图 + 3 子图（CLI 分发/日审链/月审链/周审+调休），原 30 节点单图→每图 ≤11 节点
  - **L2** 生成 5 个 Obsidian Canvas 文件到 `docs/canvas/`（01_system_context / 02_module_structure / 03_audit_rules / 04_function_calls / 05_param_flow），图解拆成文字卡片放图旁
  - **工具** 新增 `tools/generate_canvas.py`：解析 ARCHITECTURE.md Mermaid 块 → 自动生成 Canvas JSON
  - **CHECKLIST** Canvas 导出项标记 ✅
- **变更级别**：L2
- **改动的文档/文件**：ARCHITECTURE.md §3+§5, docs/canvas/*.canvas（5 个新文件）, tools/generate_canvas.py, CHECKLIST.md, STATUS.md
- **验证**：溯源对账 66/66 ✅；53 项测试全绿 ✅
- **下一步**：F10/F12 按优先级排期；【人】勾 PRD §8

### 2026-07-14 会话 F（PRD v0.4 同步修订）
- **做了什么**：
  - **L3** 修正 `expiry_checker.py` F11 催用收件人：禁止发被催员工，仅发 PM_EMAILS（孔紫初、王楠）
  - **L3** `config.py` 新增工时/打卡窗/补卡/加班上限 11 个硬参数常量
  - **L2** `ARCHITECTURE.md` §4 四处 Mermaid 图对齐 PRD v0.4：工时 09:00–17:30、F11 PM-only、F13 二期、新增打卡窗/补卡/加班上限节点
  - **L3** 伪代码 `audit_engine.md` 、`mail_sender.md` 同步门面拆分与 F11/F13 变更
  - **测试** 新增 F11 收件人验证 + 工时常量存在性测试
- **变更级别**：L2 + L3
- **改动的文档/文件**：expiry_checker.py, config.py, ARCHITECTURE.md §4, pseudocode/audit_engine.md, pseudocode/mail_sender.md, STATUS.md, test_phase4_remediation.py
- **下一步**：F10/F12 按优先级排期；【人】勾 PRD §8

### 2026-07-14 会话 E（一期范围锁定）
- **做了什么**：L1——按三份现行制度锁定一期 PRD v0.4：工时 09:00–17:30、午休 12:00–12:30、打卡窗 09:00–10:30 / 17:30–19:30、补卡≤3/月、加班≤16h；F13 与 WiFi/蓝牙归二期；F11 催用仅孔紫初/王楠；目录不改名；新增 `docs/specs/2026-07-14-stage-one-scope-lock-design.md`。
- **变更级别**：L1
- **改动的文档/文件**：docs/PRD.md、docs/STATUS.md、docs/specs/2026-07-14-stage-one-scope-lock-design.md
- **遗留问题**：~~ARCHITECTURE/伪代码/代码仍含旧工时与「催用抄送员工」口径~~ → 已在会话 F 中修正
- **下一步**：【人】勾 PRD §8；或授权做 L2 图对齐

### 2026-07-14 会话 D（框架评审整改）
- **做了什么**：
  - **Phase 2 — 代码拆分**：`audit_engine.py` 1113行 → 门面(70行) + 4工具模块(`geo`/`holiday`/`payroll_cycle`/`compensatory`) + 5服务模块(`services/daily_audit`/`weekly_audit`/`monthly_audit`/`expiry_checker`/`roster_sync`)。向后兼容：`AuditEngine` 类和所有旧 import 路径保持不变。
  - **Phase 3 — 防御加固**：`wecom_api.py` 添加 `_retry_request()` 指数退避(1s→2s→4s, max 3次)；`mail_sender.py` + `main.py` f-string log → %s 惰性格式化；`main.py` 弃用 `@app.on_event("startup")` → `lifespan`；硬编码排除名单/公司名 → `config.Settings`。
  - **Phase 1 — 架构文档**：`ARCHITECTURE.md` §3(模块结构图)/§5(函数调用图)/§6(参数路径图)/§8(速查表)/§12(决策记录) 全部重写对齐新代码结构。
  - **Phase 4 — 测试补充**：新增 `test_phase4_remediation.py` 28项测试覆盖所有新模块(geo边界/compensatory决策矩阵/payroll跨年/facade兼容/GPS围栏/瞬移检测)。
  - **Phase 5 — 溯源对账**：`check_traceability.py` 66声明边=66真实边 ✅。全套 42 项测试全绿。
- **变更级别**：L2（架构重构）+ L3（代码拆分+防御加固）
- **改动的文档/文件**：audit_engine.py(→facade), geo.py(new), holiday.py(new), payroll_cycle.py(new), compensatory.py(new), services/__init__.py(new), services/daily_audit.py(new), services/weekly_audit.py(new), services/monthly_audit.py(new), services/expiry_checker.py(new), services/roster_sync.py(new), wecom_api.py(retry), mail_sender.py(log fix), main.py(lifespan+log fix), config.py(new settings), ARCHITECTURE.md(3图重写), STATUS.md, test_phase4_remediation.py(new)
- **下一步**：F10(大交通在途)/F12(审批重叠)/F13(GPS围栏接日审主流程) 按优先级排期

### 2026-07-14 会话 C
- **做了什么**：L2——规则图补全硬参数（触发时刻、GPS200m、时速350、T+2 18:00、薪资26–25、旷工0.5/1.0、催用7/15/30等）；PRD 新增 §4.1 规则参数表。
- **变更级别**：L2
- **改动的文档/文件**：docs/ARCHITECTURE.md §4、docs/PRD.md §4
- **下一步**：工时已确认 09:00–17:30，已在会话 F 同步完成

### 2026-07-14 会话 B
- **做了什么**：L2——在 ARCHITECTURE §4 用 Mermaid 画出日审判定、GPS 200m、调休入账、月审封账、缺卡申诉等审计规则图；PRD §4 增加交叉引用。
- **变更级别**：L2
- **改动的文档/文件**：docs/ARCHITECTURE.md、docs/PRD.md
- **下一步**：人审规则图；Canvas 导出可选

### 2026-07-14 会话
- **做了什么**：L1——GPS 改为 >200m 无效；人数按 <20 人改性能预期；花名册迁 JSON（`data/employee_roster.json`），去掉运行时 xlsx；同步更新 PRD/ARCHITECTURE/伪代码/脚本/测试。
- **变更级别**：L1（全链文档+代码）
- **改动的文档/文件**：PRD、ARCHITECTURE、roster 模块与伪代码、scripts、docker-compose、STATUS、test_audit
- **遗留问题**：多数员工邮箱仍空，需人工补全 JSON；F13 尚未接到日审主流程
- **下一步**：补邮箱；P4 对账；本地 Postgres/Docker

### 2026-07-13 会话 3
- **做了什么**：将根目录 `docs/superpowers/` 改名为并迁入本项目 `docs/specs/`、`docs/plans/`；删除空的仓库根 `docs/`。
- **变更级别**：L4（文档归属整理）
- **改动的文档/文件**：`docs/specs/`、`docs/plans/`、README、STATUS
- **遗留问题**：无
- **下一步**：P4 对账 / 或本地 Docker Postgres

### 2026-07-13 会话 2
- **做了什么**：P3 继续——落地 E5（法定假禁调休 `decide_compensatory_accrual`）、E18（`payroll_period_locks` 封账拒重复终审）、attendance_logs 唯一键、cli 去 print+启动 validate、wecom 分批拉取+模板 ID 环境化；unit 测试扩至 10 项全绿。
- **变更级别**：L3（伪代码先改后代码）
- **改动的文档/文件**：audit_engine/db/cli/wecom_api/config、pseudocode 对应文件、test_audit.py、STATUS
- **功能矩阵变化**：F5/F6/F9/F14 测试或代码列推进；F14 代码 ✓
- **遗留问题**：对账门禁未绿；F8 Excel；P1 功能 F10/12/13；杨丽丽邮箱
- **下一步**：P4 `check_traceability` + Canvas

### 2026-07-13 会话 1
- **做了什么**：P0 归档+叠骨架；P1 重建 PRD/ARCHITECTURE；P2 全量伪代码；P3 起点 config 去密钥。
- **变更级别**：L1 + L2 + L3
- **下一步**：当时为继续 P3（本会话已推进）

---

## 4. Hooks 说明（monorepo）

```bash
cd attendance_audit_integration
python3 tools/check_stage.py
python3 tools/check_traceability.py
PYTHONPATH=src python3 -m pytest -m unit
```

已有数据库请执行一次：`PYTHONPATH=src python3 -m attendance_audit_integration.cli init-db`
