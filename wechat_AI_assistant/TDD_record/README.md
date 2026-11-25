# TDD_record — 全项目防串谋 TDD 测试、盲审修复与生产部署档案

本目录完整记录 `wechat_AI_assistant`（个人微信/企微 + 香港/国际版 Outlook 邮箱 + LangGraph 六阶段工作流 + 嵌入式 Web 驾驶舱 + 世纪互联 OneDrive）**全项目、全应用场景、全异常场景**的防同源串谋 TDD 闭环与阿里云生产部署实证。

---

## 总成绩单（2026-11-25 11:35 `/goal` 清库冷启动与盲审闭环最终核验）

| 维度 | 指标 | 实测结果 |
| :--- | :--- | :--- |
| **全仓自动化测试套件** | `uv run pytest -W error::ResourceWarning -v` | ✅ **105 passed, 0 failed**（13.25s，Exit Code `0`，含原有 51 + Slice 1 14 + Slice 2 19 + v2.0 11 + 清库冷启动与盲审修复 10） |
| **两轮独立盲审隐患清零** | `adversarial-code-auditor` 两轮累计 | ✅ 首轮 6 P0 + 6 P1 + 3 P2 + 二轮 v2.0 盲审 **5 P0 + 8 P1**，**100% 闭环修复** |
| **黄金样本实弹轨迹体检** | `scripts/replay_golden_traces.py`（`-W error::ResourceWarning`） | ✅ **14/14 全部通过**，0 未关闭数据库连接警告 |
| **阿里云 `firematrix` 清库冷启动** | 完整热备 + 清空旧测试库 + 保留白名单/游标 + 冷启动 | ✅ `wechat-agent` = **`active`**，`healthz` = **`200 OK`**，生产库 0 脏数据，`COLD_START_DB_SCHEMA_OK=True` |
| **阿里云直连香港邮箱实弹探针** | `scripts/probe_04_mail_readonly.py`（生产机现场实跑） | ✅ `mail_read` = **`200 OK`**（`john.xu@palmarytech.com`），`sendMail` = **`403 Forbidden`**（物理只读防线） |

---

## 文档索引（按编号顺序阅读）

| 编号 | 文档 | 核心内容 |
| :---: | :--- | :--- |
| `00` | [00-TDD测试计划与全场景覆盖矩阵.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/TDD_record/00-TDD测试计划与全场景覆盖矩阵.md) | 覆盖企微双通道、香港邮箱小时窗、LangGraph 阶段 1–6、Web 驾驶舱与 OneDrive 的完整场景与异常清单 |
| `01` | [01-Slice1-工作日按小时邮件汇总与域名过滤TDD记录.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/TDD_record/01-Slice1-工作日按小时邮件汇总与域名过滤TDD记录.md) | 工作日 `08:30` + `09:00–21:00` 按小时邮件汇总、域名 JSON 热更新与防覆盖保护（14 红 → 65 绿） |
| `02` | [02-Slice2-全仓盲审缺陷与全场景异常韧性TDD记录.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/TDD_record/02-Slice2-全仓盲审缺陷与全场景异常韧性TDD记录.md) | 企微对话、阶段 1–6、数据库、安全解压、Web 鉴权 CRUD、OneDrive 全部 19 项黑盒契约测试与源码修订（18 红 → 84 绿） |
| `03` | [03-全仓独立挑刺盲审与修复台账.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/TDD_record/03-全仓独立挑刺盲审与修复台账.md) | 独立只读盲审官揪出的 6 P0 + 6 P1 + 3 P2 逐项台账 + 357 行「红区短文件」人工签字清单 |
| `04` | [04-黄金样本实弹轨迹体检报告.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/TDD_record/04-黄金样本实弹轨迹体检报告.md) | 14 条董事长真实与极端异常场景的一页纸实弹流转轨迹表及回放揪出的 2 个隐蔽组合漏洞修复记录 |
| `05` | [05-阿里云生产部署与端到端实测验收报告.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/TDD_record/05-阿里云生产部署与端到端实测验收报告.md) | 阿里云 `firematrix` 备份、同步、香港 Outlook 实弹探针、重启健康检查与日志清零实证 |
| `06` | [06-TaskCard-v2扁平任务卡与邮件角色推断TDD记录.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/TDD_record/06-TaskCard-v2扁平任务卡与邮件角色推断TDD记录.md) | v2.0 扁平单层任务卡、邮件 `From/To/Cc` 角色推断与会话串线、早报 v2.0 与微信快捷口令（11 红 → 95 绿） |
| `07` | [07-全仓盲审P0P1修复与清库冷启动TDD验收记录.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/TDD_record/07-全仓盲审P0P1修复与清库冷启动TDD验收记录.md) | `/goal` 二轮全仓盲审 5 P0 + 8 P1 闭环修复、10 组冷启动与防注入红灯测试（10 红 → 105 绿）及阿里云备份清库冷启动验收 |
