# 06 - v2.0 扁平单层独立任务卡、邮件 `From/To/Cc` 角色推断与早报重构 TDD 记录

> **对应单一真理源规格**：[早间工作报告.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/report_templates/早间工作报告.md) · [邮件汇总模板.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/report_templates/邮件汇总模板.md) · [task_card_schema.json](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/report_templates/task_card_schema.json)  
> **红灯测试文件**（全程锁定未篡改）：[test_task_card_v2_and_mail_roles.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/tests/unit/test_task_card_v2_and_mail_roles.py)（11 个独立黑盒契约测试函数）  
> **状态**：✅ RED（11/11 预期失败）→ GREEN（**95/95 全仓绿灯 + 14/14 黄金样本通过**）

---

## 一、需求演进大白话总结

结合今早 `08:30` 实战推送的早报与香港 Outlook 邮件汇总，本次按董事长拍板完成了 5 项产品级升级：
1. **拍平「项目嵌套任务」为「单层独立任务卡」**：一件事 = 一张独立任务卡 `#ID`，办完回复 `完成 #ID` 即闭环；大项目名改为轻量归属标签（零嵌套、零复读，仍支持按项目筛选与 OneDrive 目录归档）。
2. **成果导向 1～7 标准字段 + 备注/CEO 评价彻底分离**：每张卡标准落库 `1）目标与交付成果`、`2）当前进度与往来沟通（专属时间轴）`、`3）责任分工（负责人/实施人/外部协作）`、`4）时间排期（缺截止日标【待补齐】绝不瞎猜当天）`、`5）卡点与关联档案`、`6）补充备注（Comments）`、`7）CEO 评价（私密只追加不覆盖）`。
3. **邮件 `From / To / Cc` 精准角色推断 + `conversationId` 双向串线**：代码先基于 `internal_domains` 算出董事长角色——**只要您仅被抄送（`cc_observer`），绝不把您填为负责人或实施人**；已有邮件会话自动归入老任务时间轴，您发出的回复也零模型调用自动归入对应任务时间轴。
4. **微信 4 个零模型快捷口令**：`评价 #ID：...`、`备注 #ID：...`、`#ID 进展：...`、`查 #ID 沟通记录`（即使大模型 503 宕机也 100% 毫秒级生效）。
5. **去重确认卡标题前缀 & 无损平滑迁移线上库**：消除 `确认 #9｜确认 #9｜` 重复前缀；旧版 `list_items` 自动平滑补列，既有线上数据零丢失。

---

## 二、Red → Green 全链路实证

- **Red 阶段**（独立盲测官 `blind-test-author`）：
  `uv run pytest tests/unit/test_task_card_v2_and_mail_roles.py -v --tb=short` → 退出码 `1`，**`11 failed, 0 passed in 1.35s`**（全部精准命中尚未实现的迁移列、角色推断、时间轴与接口）。
- **Green 阶段**（锁死测试，完成 Slice A `db.py`/`critic_rules.py` → Slice B `mail_poller.py`/`mail_domains.json` → Slice C `graph.py`/`system_prompts.py`/`web/app.py`）：
  - 全仓测试：`uv run pytest -v --tb=short` → 退出码 `0`，**`95 passed in 9.82s`**（原有 84 条 + 新增 11 条，0 失败、0 跳过、0 未关闭连接警告）。
  - 黄金样本：`uv run python -W error::ResourceWarning scripts/replay_golden_traces.py` → 退出码 `0`，**`14/14 PASS`**。

---

## 三、阿里云 ECS（`firematrix`）生产部署与无损迁移实证

- **部署时间**：`2026-11-25 10:55 CST`
- **库前热备份**：`/root/backups/wechat-agent-v2-20261125/app.db.bak`（`DB_BACKUP_OK`）
- **同步范围**：`src/`、`config/mail_domains.json`、`report_templates/`、`scripts/` → `/opt/wechat-agent/app/`（`V2_SYNC_OK`）
- **服务与健康检查**：
  - `systemctl is-active wechat-agent` → **`active`**（重启时间 `2026-11-25 10:55:39 CST`，启动日志零报错、零密钥泄露）
  - `https://assistant.fire-matrix.com/healthz` → **`HTTP 200`**（`{"status":"ok","service":"wechat-ai-assistant","version":"0.1.0"}`）
  - `https://wechat.fire-matrix.com/` → **`HTTP 200`**
- **线上 SQLite 无损迁移验证**：
  - 既有任务条数完好保留：**`ITEMS_COUNT: 4`**
  - 专属时间轴表创建成功：**`TIMELINE_TABLE: True`**
  - v2.0 全部新增字段迁移到位：**`V2_COLS_OK: True`**
  - 邮件域名分组加载正常：`internal_domains=['palmarytech.com', 'wissentek.com']`，`partner_domains=['budi.de', 'tera-instruments.com', 'vandf.com']`
