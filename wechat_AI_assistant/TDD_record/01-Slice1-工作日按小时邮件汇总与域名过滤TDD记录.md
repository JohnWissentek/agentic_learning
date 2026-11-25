# 01 - Slice 1：工作日按小时邮件汇总与域名过滤 TDD 完整记录

> **对应规格**：[2026-11-24-mail-hourly-window-design.md](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/docs/superpowers/specs/2026-11-24-mail-hourly-window-design.md)  
> **红灯测试文件**（全程锁定未篡改）：[test_mail_hourly_window.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/tests/unit/test_mail_hourly_window.py)（14 个独立黑盒契约用例）  
> **状态**：✅ RED（14/14 预期失败）→ GREEN（65/65 全仓绿灯）

---

## 一、需求大白话摘要（为什么要改这个？）

改造前，邮件是全天每 2 分钟轮询一次、按环境变量关键词搜正文、来一封就单独推一条微信确认卡。这在真实业务里会带来 3 个痛点：
1. **夜间与周末打扰**：半夜欧洲来信也推送、也耗费模型费用；
2. **同一小时来两封信会互相顶掉确认卡**：第二张卡自动把第一张卡标成“被取代”，导致第一封信无法回复 `1` 确认；
3. **仅配置香港/国际版 Outlook 邮箱、不依赖世纪互联 OneDrive 时，轮询后台任务不会启动**。

本次改造后：
- **工作日固定节奏**：周一至周五 `08:30`（补前一晚 21:00 后及周末积压）以及 `09:00 ~ 21:00` 整点汇总；夜里和周末不拉取、不调模型、不发微信；本小时没邮件则完全静默。
- **域名名单热更新**：直接读 [mail_domains.json](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/config/mail_domains.json)（初始 5 个域名：`palmarytech.com`、`wissentek.com`、`budi.de`、`vandf.com`、`tera-instruments.com`），支持子域名、排除邮箱自身地址、过滤退订/验证码/noreply 噪音，改文件保存即下一班生效，文件损坏时安全中止不丢信。
- **收件合批一张卡、发件只汇总不建卡**：同一小时多封收件合并走一次路径④（绕过路由模型，不误判闲聊），只出一张待确认卡；发件不调模型不建卡，只在同一条微信里列出，并确定性标出「可能在等对方」。
- **防覆盖保护与失败回滚**：库中已有待确认卡时推迟分析新收件（只提醒并汇总已发送），微信推送失败时自动撤销本班新建卡片且不前移水位，下一班整批重试。

---

## 二、Red 阶段（独立黑盒测试先跑出预期红灯）

- **编写者**：独立黑盒测试编写官 `blind-test-author`（严格读写隔离，零查看 `src/` 业务实现）
- **运行命令**：`cd /Users/john/Desktop/agentic_learning/wechat_AI_assistant && uv run pytest tests/unit/test_mail_hourly_window.py -q`
- **退出码**：`1`
- **结果**：**14 failed in 0.17s**（全部 14 项因契约接口与 `mail_poll_cursor` 尚未实现而按预期触发 `AttributeError`）

| # | 用例名 | 覆盖场景 | Red 阶段实测结果 |
| :-: | :--- | :--- | :---: |
| 1 | `test_active_mail_slot_workdays_and_quiet_hours` | 工作日 `08:30`/`09:00–21:00` 5 分钟窗口；`08:00`/`22:00`/周末返回 `None` | 🔴 FAILED (`AttributeError`) |
| 2 | `test_seed_watermark_monday_0830_and_wednesday_1500` | 周一 `08:30` 首次水位=上周五 `21:00 UTC`；周三 `15:00`=当天 `08:30 UTC` | 🔴 FAILED (`AttributeError`) |
| 3 | `test_db_mail_watermark_persistence` | `mail_poll_cursor` 按 `inbox`/`sent` 独立持久化与重启恢复 | 🔴 FAILED (`AttributeError`) |
| 4 | `test_domain_allowlist_subdomains_colleague_and_self_exclusion` | 子域名/同事命中、伪子域名/非白名单/仅自身地址/噪音全部拒绝 | 🔴 FAILED (`AttributeError`) |
| 5 | `test_two_inbox_emails_batched_into_single_card_bypassing_router` | 同小时 2 封收件合成 1 次分拣、0 次路由模型、1 张卡、裹不可信标签 | 🔴 FAILED (`AttributeError`) |
| 6 | `test_sent_mail_not_triaged_and_marks_waiting_hint` | 已发送不调模型不建卡，汇总列出并标出「可能在等对方」 | 🔴 FAILED (`AttributeError`) |
| 7 | `test_domains_json_reloaded_and_corrupt_json_keeps_watermark` | 每班热重读 JSON；损坏且无缓存时不拉不移水位；有缓存回退 | 🔴 FAILED (`AttributeError`) |
| 8 | `test_existing_pending_card_defers_inbox_but_still_sends_sent_list` | 已有待确认卡时推迟收件且不标 seen/不移收件水位；发件照常推送并推进 | 🔴 FAILED (`AttributeError`) |
| 9 | `test_push_failure_cancels_new_card_and_preserves_watermark_for_retry` | 推送失败取消本班新建卡、水位与 seen 不动；下一班恢复重试成功 | 🔴 FAILED (`AttributeError`) |
| 10 | `test_noise_and_non_allowlist_marked_seen_without_push` | 噪音/非白名单不推微信不调模型，写入 seen 并正常推进水位 | 🔴 FAILED (`AttributeError`) |
| 11 | `test_inbox_cap_ten_leaves_eleventh_for_next_slot` | 11 封收件仅分析最旧 10 封，第 11 封留待下班（水位=第 11 封时间-2 分钟） | 🔴 FAILED (`AttributeError`) |
| 12 | `test_duplicate_internet_message_id_skipped` | 2 分钟重叠查询窗口内已 seen 的 `internetMessageId` 自动跳过 | 🔴 FAILED (`AttributeError`) |
| 13 | `test_long_sent_list_truncated_preserving_full_card` | 确认卡全文绝不截断，超长已发送截断至 `<=1800` 字并附未列出计数 | 🔴 FAILED (`AttributeError`) |
| 14 | `test_monday_0830_first_run_uses_seed_watermark_and_backlog_header` | 周一 `08:30` 首次运行带「含此前未推送的邮件」积压标题 | 🔴 FAILED (`AttributeError`) |

---

## 三、Green 阶段（锁定测试，最小充分实现生产代码）

修改文件清单（全程未改动任何既有或新增测试文件）：
1. [mail_domains.json](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/config/mail_domains.json)：新增 5 个核心合作与内部域名配置。
2. [db.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/storage/db.py#L242-L283)：新增 `mail_poll_cursor` 表与 `get_mail_watermark` / `set_mail_watermark` 持久化方法。
3. [graph.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/graph.py#L90-L92)：新增 `force_work_triage` 透传开关，批量收件直接进入路径④并跳过 `qwen3.8-flash` 路由模型。
4. [mail_poller.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/intake/mail_poller.py)：完整实现工作日时点调度、首次水位种子、域名热重读、按文件夹分页拉取（`$top=50` + `@odata.nextLink`）、MSAL HTTP 20s 超时保护、10 封上限、待确认卡推迟、1800 字安全截断与推送失败回滚；同时完整保留旧 `poll_mailbox_once` 向后兼容。
5. [app.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/web/app.py#L322-L337)：在 FastAPI `lifespan` 中挂载 `mail_hourly_scheduler_loop`，且解除对 `od_client` 的硬绑定（香港/国际版邮箱凭据齐全即可独立启动）。

---

## 四、Green 阶段终端实证

- **运行命令**：`cd /Users/john/Desktop/agentic_learning/wechat_AI_assistant && uv run pytest -v`
- **退出码**：`0`
- **实测结果**：**65 passed in 3.34s**（原有 51 条 + Slice 1 新增 14 条，0 失败、0 跳过，一次全绿！）
