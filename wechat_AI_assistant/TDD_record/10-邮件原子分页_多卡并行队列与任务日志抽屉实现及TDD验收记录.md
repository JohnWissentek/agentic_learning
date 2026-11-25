# 10 - 邮件逐封六要素原子分页、方案 A 多确认卡并行队列、默认三工作日截止与任务日志抽屉实现及 TDD 验收记录

> **日期**：2026-11-25  
> **实施范围**：基于生产环境真实使用反馈，连续完成 4 项高频体验与工程防线升级，全部按「先红灯黑盒契约测试 → 实现源码 → 全量绿灯 + 黄金轨迹 → 阿里云 `firematrix` 生产机实弹验收」闭环交付。  
> **最终总成绩**：`uv run pytest -q` → **`139 passed, 0 failed`**（Exit `0`）｜`scripts/replay_golden_traces.py` → **`14/14 PASS`**（Exit `0`）｜JS 语法检查 `JS_SYNTAX_OK`｜阿里云 `firematrix` `/healthz` = `version: "3.0.0"` 线上健康运行。

---

## 一、 4 项功能的问题背景、设计决策与代码定位

### 1. 每小时邮件汇总「逐封 6 要素标准模板」与「整封原子分页防丢包」
- **生产痛点**：
  1. 旧版在存在未回复待确认卡时，每小时仅发送一行分号拼接的主题列表，无发件人/主送/抄送/主要内容/处理建议，无法快速决策；
  2. 升级为逐封 6 要素后，首次 5 封实弹推送（3696 字节）因 `主送/抄送` 展开完整邮箱导致膨胀，底层 `_split_chunks(..., limit=1800)` 按行硬切为 3 段（`1509B` / `1747B` / `438B`）且 0 间隔连发，导致第 2 段被企微→微信插件静默丢弃、第 3 封与第 5 封被拦腰截断。
- **核心实现**：
  - **红区契约与提示词**：[schemas.py](../src/wechat_assistant/schemas.py) 新增 `MailDigestItem`、`MailBatchDigest`、`TriageProposal.mail_digests`；[system_prompts.py](../src/wechat_assistant/prompts/system_prompts.py) 要求每封 `MAIL-k` 产出结构化摘要与五选一处理建议，且禁止面向董事长暴露 `MAIL-1` / `MAIL-2` 内部编号（改用自然中文「第 2 封」）。
  - **精简联系人 + 整封原子块**：[mail_poller.py](../src/wechat_assistant/intake/mail_poller.py) 新增 `_format_person_display`（内部同事只显姓名，外部联系人显 `姓名(域名)` 或去重邮箱，空抄送显式标 `无`）；`format_mail_digest_section` 将每封邮件作为 `\n\n` 分隔的原子块（标题与第 1 封绑定）。
  - **微信插件安全分页与节流**：[wecom_gateway.py](../src/wechat_assistant/intake/wecom_gateway.py) 将 `send_app_push` 单段阈值收紧为 `1100` 字节且 `≤650` 字符，`_split_chunks` 优先按 `\n\n` 整块切分（**绝不把单封邮件切分到两段**），多页自动加 `【i/N】` 页码并以 `0.6s` 间隔推送。
- **测试文件**：[test_mail_digest_standard_template.py](../tests/unit/test_mail_digest_standard_template.py)（5 项黑盒测试，先红后绿）。

### 2. 方案 A：多张待确认卡并行队列（不阻塞、不覆盖、不重复刷屏）
- **生产痛点**：旧「单卡阻塞锁」下，只要中午确认卡 `#2` 没及时回复，后续每个整点都卡住不生成新确认卡，并反复重推同一批邮件；同时 5 封邮件合并推理时 `max_tokens=2048` + 冗余工具往返容易触发截断重试。
- **核心实现**：
  - **存储层**：[db.py](../src/wechat_assistant/storage/db.py) 新增 `list_pending_proposals`、`get_pending_proposal`；`save_pending_proposal` 默认并行新增不覆盖旧卡，仅在显式指定 `replace_proposal_id` 时替换目标卡。
  - **契约与上下文**：[schemas.py](../src/wechat_assistant/schemas.py) 在 `AgentDecision` 新增 `target_proposal_ids`（批量/定点确认或作废）与 `replace_proposal_id`（定点修订单卡）；[context_assembler.py](../src/wechat_assistant/context_assembler.py) 向主脑完整挂载全部待确认卡片。
  - **编排与邮件通道**：[graph.py](../src/wechat_assistant/graph.py) 支持按 `#编号` 批量确认/作废、定点修订与剩余队列提示，并将 `max_tokens` 提至 `3072`、邮件批次免除冗余工具往返（实弹耗时降至 `47.3s`）；[mail_poller.py](../src/wechat_assistant/intake/mail_poller.py) 移除旧单卡阻塞，直接并行生成新卡并推进收件水位防重复推送，同时保留百炼 503 自动降级为确定性 6 要素明细（不推进水位以便下班恢复补卡）。
- **生产实弹验证**：16:26 实弹扫描 5 封邮件，在不覆盖旧卡 `#2` 的前提下并行生成确认卡 `#3`（8 段均 `≤1081B` 间隔送达），16:27 复扫返回 `pushed: False` 验证零重复刷屏。
- **测试文件**：[test_parallel_pending_cards_plan_a.py](../tests/unit/test_parallel_pending_cards_plan_a.py)（3 项黑盒测试）及同步更新的 G12 黄金样本 [replay_golden_traces.py](../scripts/replay_golden_traces.py)。

### 3. 新任务默认目标截止时间 = 任务建立后 3 个工作日
- **生产痛点**：邮件和日常口头交办大多不专门说截止日期，此前强制留空导致每张确认卡反复弹出 `⚠️ 缺失必填提示：缺少目标截止时间`。
- **核心实现**：
  - [graph.py](../src/wechat_assistant/graph.py) `build_calendar_anchor_text` 注入确定性 `新任务默认截止（建立后3个工作日）=YYYY-MM-DD`，底盘兜底使用 `calc_business_date(base_d, 3)` 自动补齐（自动跳过周末；若开始日在未来则取开始日后 3 个工作日）并移除 `missing_required_fields` 中的 `planned_end_at`；
  - [system_prompts.py](../src/wechat_assistant/prompts/system_prompts.py)、[web/app.py](../src/wechat_assistant/web/app.py)（`POST /api/items`）、[task_card_schema.json](../report_templates/task_card_schema.json) 与 [早间工作报告.md](../report_templates/早间工作报告.md) 全链路统一。
- **测试文件**：[test_default_deadline_three_biz_days.py](../tests/unit/test_default_deadline_three_biz_days.py)（3 项黑盒测试，先红后绿）。

### 4. 每任务逐条备注日志：Dashboard 右侧抽屉 + 微信对话双入口互通
- **生产痛点**：后端虽已有 `POST /api/items/{id}/note` 与 `comments`/`ceo_evaluation`/`timeline` 存储，但 Dashboard 网页缺少单任务日志抽屉入口，`comments`/`ceo_evaluation` 仅记 `YYYY-MM-DD` 缺少 `HH:MM` 时间戳，且微信 `view_timeline_ids` 回查时未展示 `comments` 与 `ceo_evaluation`。
- **核心实现**：
  - **精确时间戳存储**：[db.py](../src/wechat_assistant/storage/db.py) 在 `append_task_comment` 与 `append_task_ceo_evaluation` 中同步写入 `date`（`YYYY-MM-DD`）与 `timestamp`（`YYYY-MM-DD HH:MM`），向后兼容旧记录。
  - **Dashboard 右侧任务日志抽屉**：[index.html](../src/wechat_assistant/web/static/index.html) 在主表格每行任务旁与 Schedule Load 视图新增 `💬 日志` 气泡入口（带条数角标），点击滑出右侧 **Task Updates Drawer**：
    - 支持按「全部 / 备注日志 / 进展往来 / CEO 评价」筛选统一时间轴；
    - 顶部快捷输入框默认「📝 备注 / 日志」，支持 `Cmd+Enter` 立刻调用 `POST /api/items/{id}/note` 落盘并刷新云端看板；
    - 支持展开/收起行内编辑交付成果、实施人、外部协作、阶段与卡点。
  - **微信自然对话追记与回查**：[system_prompts.py](../src/wechat_assistant/prompts/system_prompts.py) 强化按 `#编号` 或任务/项目名称匹配并直接走 `direct_ops.note_appends` 追记备注（不建重复卡）；[graph.py](../src/wechat_assistant/graph.py) 升级 `view_timeline_ids` 同步输出「补充备注/日志 + 往来沟通与进展 + CEO 评价」。
- **测试文件**：[test_dashboard_task_log_drawer.py](../tests/unit/test_dashboard_task_log_drawer.py)（3 项黑盒测试：HTML 抽屉契约、Web 多条带时间戳追加不覆盖、微信自然对话连续追记与回查）。

---

## 二、 完整验收命令与新鲜实证（Exit Code = 0）

| 验证项 | 执行命令 / 端点 | 实测结果 | 退出码 |
| :--- | :--- | :--- | :---: |
| 前端 JS 语法检查 | `node --check /tmp/dashboard_check.js` | `JS_SYNTAX_OK` | `0` |
| 全仓 TDD 自动化测试 | `uv run pytest -q --tb=short` | **`139 passed in 8.79s`** | `0` |
| 14 条黄金样本轨迹回放 | `uv run python -W error::ResourceWarning scripts/replay_golden_traces.py` | **`total=14 passed=14 failed=0`** | `0` |
| 阿里云生产服务状态 | `systemctl is-active wechat-agent` | `active` | `0` |
| 本机与公网健康检查 | `http://127.0.0.1:8090/healthz` & `https://assistant.fire-matrix.com/healthz` | `{"status":"ok","service":"wechat-ai-assistant","version":"3.0.0"}` | `0` |
| 公网驾驶舱抽屉上线核验 | `curl -sS https://assistant.fire-matrix.com/ \| grep -c "openTaskDrawer"` | `3` | `0` |
| 生产邮箱实弹扫描与防重 | `run_mail_window_once`（16:26 实弹 + 16:27 复扫） | 16:26 并行出卡 `#3`（8 段 `≤1081B` 全部 `ok`），16:27 `pushed: False` 零重复 | `0` |
