# 07 - 全仓 v2.0 盲审 P0/P1 修复与清库冷启动 TDD 验收记录

> **触发背景**：董事长下达 `/goal` 指令，要求在清空早期 v1.0 遗留测试数据后，按严格防串谋 TDD 流程重新执行一轮全仓深度审计、红转绿测试与阿里云冷启动上线验收。  
> **红灯测试文件**（全程锁定零修改）：[test_clean_slate_and_audit_fixes.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/tests/unit/test_clean_slate_and_audit_fixes.py)（10 组独立黑盒契约测试）  
> **状态**：✅ **盲审挖出 5 P0 + 8 P1 → 10/10 精准红灯 → 首轮 105/105 全仓绿灯 + 14/14 黄金样本通过 → 阿里云备份清库冷启动实测通过**

---

## 一、独立盲审官揪出的 5 项 P0 阻断与核心 P1 缺陷（已全部闭环）

### P0 阻断级缺陷（5/5 清零）
1. **邮件新建任务 `conversationId` 代码自动回填**：为每封白名单邮件分配短编号 `MAIL-k`，并在 `graph.py` 新增 `_backfill_mail_conversation_ids`——即使大模型漏填或抄错百字节 Base64 `conversationId`，代码也会从可信系统元数据自动回填绑定，保证后续来信与发件 100% 串线归入同一任务卡。
2. **仅抄送董事长（`cc_observer`）代码级硬拦截**：在 `critic_rules.py` 新增确定性拦截规则，只要邮件仅抄送董事长且提案将董事长/本人填为 `owner` 或 `assignee`，直接打回；同步防止 `format_decision_card` 在 `assignee` 缺失时用 `owner` 静默顶替。
3. **系统可信元数据与不可信邮件正文物理隔离**：重构 `mail_poller.wrap_untrusted_email`，将 `[SYSTEM_TRUSTED_MAIL_META]`（角色推断、已绑定任务 `#ID`、规范化 `From/To/Cc`、`conversationId`）置于 `[UNTRUSTED_EXTERNAL_DATA]` 标签**外部**，彻底封堵正文伪造角色提示的 Prompt Injection。
4. **纯知会邮件批次（0 新建、0 更新，仅 `fyi_notices`）绝不建待确认卡**：`_node_hitl_preview_gate` 直接输出纯知会摘要、不写入 `pending_proposals`，杜绝纯知会消息永久阻塞后续整点邮件分拣。
5. **微信快捷修改已落盘任务字段 + 严防误完结**：新增零模型快捷口令 `#ID 截止改到 YYYY-MM-DD`、`#ID 实施人改为 XX`、`#ID 负责人改为 XX`（带日历合法性校验，自动清除对应 `missing_required_fields`，保持任务状态不变）；同时 `mutate_existing_item` 必须命中明确完结动词才允许调用 `complete_item`，彻底杜绝误把任务结项。

### 核心 P1 缺陷与模板对齐（全部清零）
- **邮件正文完整读取**：`fetch_mail_folder_messages` 升级拉取 `body,hasAttachments` 并加 `Prefer: outlook.body-content-type="text"`，突破 255 字符 `bodyPreview` 截断。
- **时间轴幂等去重**：`task_timeline` 新增局部唯一索引 `idx_task_timeline_dedup(item_id, source_ref)`，重复追加同一 `source_ref` 绝不产生重复记录。
- **`From/To/Cc` 边界修正**：修复「内部→内部（仅 Cc 董事长）」误把发件人当实施人的问题；修复「外部→同时 To 董事长和同事」漏提示同送同事的问题。
- **空库冷启动与边界安全**：空库早报安全渲染 `在途任务：0 项`；空库/不存在 ID 发 `查 #1 沟通记录` 明确报未找到；空内容 `评价 #1：` / `备注 #1：` / `#1 进展：` 零模型友好提示；Web API `GET /api/items/999/timeline` 返回标准 `404`。
- **早报 v2.0 与纯更新落盘精度**：调度器标题对齐 `🌅 早间工作报告`；临期预警纳入未来 2 天内到期任务；未来开始任务不再误报 `已进行 1 天`；超 8 条在途任务显式输出 `另有 N 项`；纯 `task_updates` 落盘与撤销汇报准确（不打印空编号，不向 `日常事务` 写空纪要）。
- **上下文检索 & DB 一致性 & Web 驾驶舱**：`ContextAssembler` 全面挂载 v2.0 `assignee`/`external_partner`/`deliverable`/`blocker_note` 及 `task_updates`/`fyi_notices`；所有 DB 读写接口统一经 `_hydrate_item_row` 返回反序列化结构；修复前端 `saveTimeline` 覆盖空截止日及 `General Ops`/`Chairman` 英文默认值；升级 OneDrive 看板表头输出 v2.0 字段。

---

## 二、Red → Green 终端新鲜实证

- **Red 阶段**（独立盲测官 `blind-test-author`）：
  `cd wechat_AI_assistant && uv run pytest tests/unit/test_clean_slate_and_audit_fixes.py -v --tb=short` → 退出码 `1`，**`10 failed in 1.36s`**。
- **Green 阶段**（锁定全部测试零改动）：
  - 全仓测试：`uv run pytest -W error::ResourceWarning -v --tb=short` → 退出码 `0`，**`105 passed in 13.25s`**（原 95 条 + 新增 10 条全部一次变绿）。
  - 黄金样本：`uv run python -W error::ResourceWarning scripts/replay_golden_traces.py` → 退出码 `0`，**`GOLDEN_REPLAY_SUMMARY: total=14 passed=14 failed=0`**。

---

## 三、阿里云 ECS（`firematrix`）备份清库与冷启动实测验收

- **清库前完整热备**：停服刷盘后完整备份至 `/root/backups/wechat-agent-pre-clean-reset-20261125/`（`app.db` 448KB、`checkpoints.db` 1.4MB，`BACKUP_VERIFIED_OK`）。
- **严格保留认证与游标**：完整保留 `/opt/wechat-agent/data/owner_whitelist.txt` 与 `/opt/wechat-agent/data/kf_cursor.txt`（`WHITELIST_AND_CURSOR_PRESERVED_OK`）。
- **冷启动空库重建验证**：
  - `projects=0`、`list_items=0`、`task_timeline=0`、`pending_proposals=0`、`raw_sources=0`、`conversation_turns=0`、`seen_external_ids=0`、`mail_poll_cursor=0`、`undo_snapshots=0`；
  - `idx_task_timeline_dedup`、`sources_fts`、`conversation_turns_fts` 全部自动创建（`COLD_START_DB_SCHEMA_OK=True`）。
- **线上服务与实弹探针**：
  - `systemctl is-active wechat-agent` → **`active`**
  - `https://assistant.fire-matrix.com/healthz` → **`HTTP 200`**，`https://wechat.fire-matrix.com/` → **`HTTP 200`**
  - 香港 Outlook 只读实弹探针（`probe_04_mail_readonly.py`）：`mail_read status=200 fetched=3`、`mail_send_negative status=403`（`PROBE_04_ALL_PASSED`）
  - 远端临时库冷启动冒烟校验：`REMOTE_CLEAN_SLATE_SMOKE=ALL_PASSED`；校验完毕线上生产库仍为干净 `0` 条记录，日志零报错。
