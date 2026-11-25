# 02 - Slice 2：全仓盲审缺陷与全场景异常韧性 TDD 完整记录

> **红灯测试文件**（全程锁定未篡改）：[test_full_scenarios_and_exceptions.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/tests/unit/test_full_scenarios_and_exceptions.py)（19 个独立黑盒测试函数，覆盖 16 组全场景与异常验收矩阵）  
> **覆盖范围**：企业微信自建应用与微信客服双通道对话、LangGraph 阶段 1–6 状态流转、SQLite 原子落盘与 24h 撤销、附件/ZIP 安全解析、Web 驾驶舱鉴权与 CRUD、世纪互联 OneDrive 真实客户端  
> **状态**：✅ RED（18 failed, 1 passed）→ GREEN（84/84 全仓绿灯，0 警告）

---

## 一、Red 阶段（独立黑盒测试实测复现 18 项真实生产缺陷）

- **编写者**：独立黑盒测试编写官 `blind-test-author`（严格读写隔离）
- **运行命令**：`cd /Users/john/Desktop/agentic_learning/wechat_AI_assistant && uv run pytest tests/unit/test_full_scenarios_and_exceptions.py -v --tb=short`
- **退出码**：`1`
- **结果**：**18 failed, 1 passed in 3.26s**（18 项全部精准复现了盲审揪出的真实 P0/P1/P2 生产漏洞）

| # | 用例名 | 对应盲审编号 | 通俗场景说明（给老板看） | Red 阶段实测暴露的问题 |
| :-: | :--- | :---: | :--- | :--- |
| 1 | `test_same_day_turns_without_external_msg_id_never_leak_state` | AUD-P0-1 | 同一天连续发消息不带消息 ID 时，上轮「修改/仅存想法」绝不串台到下一轮 | 🔴 第 2 轮普通问句被上轮 `user_correction` 劫持直接进起草模型 |
| 2 | `test_web_verify_code_locks_out_after_five_wrong_attempts` | AUD-P0-3a | Web 驾驶舱 6 位登录验证码连错 5 次后自动锁定防爆破 | 🔴 第 6 次输入原正确码仍返回 `200` 签发 Cookie |
| 3 | `test_web_patch_rejects_invalid_enums_dates_and_syncs_project_id` | AUD-P0-3b | Web 修改待办拦截非法状态/日期/倒挂周期，改项目名同步 `project_id` | 🔴 传 `status="hacked"` 返回 `200` 直接写脏库 |
| 4 | `test_web_promote_requires_idea_and_allows_zero_estimated_hours` | AUD-P0-3b | 仅允许把「想法」升级为项目任务，且允许 0 工时不估工时 | 🔴 普通待办也能被 `promote` 篡改返回 `200` |
| 5 | `test_commit_preserves_local_file_when_sqlite_commit_fails_and_blocks_double_commit` | AUD-P0-4a | 确认卡先本地原子落盘、后传云端删本地；重复确认不翻倍写入 | 🔴 SQLite 失败前本地附件已被提前删掉 |
| 6 | `test_no_idea_card_reply_two_and_empty_actions_handled_safely` | AUD-P0-4b | 无想法卡回 `2` 清晰指引改回 `1`/`0`；异常空动作卡回 `1` 自动关闭 | 🔴 提示缺指引且空动作卡无法关闭永久阻塞 |
| 7 | `test_wecom_download_sanitizes_path_traversal_filename` | AUD-P0-5a | 企微下载恶意文件名 `../../etc/evil.txt` 时净化路径防穿越 | 🔴 直接拼接 `../../` 触发 `FileNotFoundError` |
| 8 | `test_zip_extractor_blocks_sibling_prefix_traversal_and_streaming_oversize` | AUD-P0-5a | ZIP 防 `../` 逃逸 + 伪造 `file_size` 炸弹时通过真实流式计数拦截 | 🔴 伪造 `file_size=10` 绕过头部检查解出全量 4KB |
| 9 | `test_discard_pending_card_cleans_up_tmp_attachments` | AUD-P0-5b | 带临时附件的确认卡回复 `0` 作废后自动清理磁盘临时文件 | 🔴 作废后磁盘临时文件永久残留 |
| 10 | `test_batch_checkin_reports_missing_ids_and_prevents_hours_misparse` | AUD-P0-6 | 批量打卡汇报找不到的编号；`完成 1.5h` 防把 `1` 误当 `#1` 错杀；重复完成幂等 | 🔴 `#999` 未找到被静默吞掉 |
| 11 | `test_wecom_app_owner_whitelist_blocks_stranger_and_targets_owner` | AUD-P1-1 | 企微自建应用配置老板 ID 时拦截陌生人且定向推送，留空兼容 `@all` | 🔴 `Settings` 缺少 `wecom_app_owner_userid` 字段 |
| 12 | `test_send_app_push_refreshes_expired_token_and_raises_on_persistent_error` | AUD-P1-2 | 微信推送遇 `42001` 过期自动刷 token 重试，遇 `60020` 等硬错误抛错不静默 | 🔴 返回 `errcode=42001` 未刷新重试也未报错 |
| 13 | `test_database_zero_unclosed_connection_warnings_and_corrupt_json_resilience` | AUD-P1-3 | 数据库读写零未关闭连接警告；字段 JSON 损坏时降级空列表不崩 | 🔴 捕获 5 条 `ResourceWarning: unclosed database` |
| 14 | `test_deterministic_critic_rejects_invalid_or_reversed_dates_and_llm_critic_gets_dialogue` | AUD-P1-4 | 确定性核验拦截倒挂/非法日期；异构审计模型收到历史对话上下文 | 🔴 倒挂日期 `11-28 ~ 11-24` 返回空 `issues` 放行 |
| 15 | `test_undo_protects_shared_project_and_enforces_24h_window` | AUD-P1-5 | 撤销不误删仍有其他任务的共享项目；超 24 小时快照拒绝撤销 | 🔴 项目被误删导致跨批次任务 `project_id` 变 `None` |
| 16 | `test_wecom_standalone_haole_not_swallowed_and_merged_voice_asr_and_kf_error_route` | AUD-P1-6 | 无待合批时单发「好了」不吞；合并转发语音走 ASR；客服异常走客服回执；空输入 0 模型调用 | 🔴 单发「好了」被静默吞掉（`flushed == 0`） |
| 17 | `test_calc_business_date_rejects_huge_offset_and_search_escapes_percent` | AUD-P2-1/2 | 工作日推算拒绝天文数字偏移防卡死；搜索 `100%` 正确转义 `%` | 🔴 未校验边界抛出 `OverflowError` |
| 18 | `test_wecom_http_callback_signature_and_web_full_auth_crud_lifecycle` | AUD-P2-3 | 企微 HTTP 回调 GET/POST 验签解密 + Web 限流登录到 CRUD 登出全闭环 | 🟢 已绿（补齐端到端回归护城河） |
| 19 | `test_onedrive_client_put_chunked_upload_and_append_note` | AUD-P2-3 | OneDrive 小文件 PUT、大文件分片上传、返回 `size` 不匹配报错及纪要追加 | 🔴 单次 PUT 返回 `size` 不匹配未抛 `RuntimeError` |

---

## 二、Green 阶段源码修订明细（零改动测试断言）

| 修改文件 | 核心修复内容 | 闭合缺陷 |
| :--- | :--- | :---: |
| [config.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/config.py) | 新增可选 `WECOM_APP_OWNER_USERID` 配置（留空时完全兼容现有单人企业 `@all`） | AUD-P1-1 |
| [db.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/storage/db.py) | `_connect()` 改为 `@contextmanager` 强保 `conn.close()`；`apply_proposal_atomic` 前置原子 CAS 锁；新增 `update_items_onedrive_docs`；`undo_last_commit` 保护跨批次共享项目并支持 ISO 时间戳；`complete_item` 重复完成幂等；`update_item_fields` 改项目名自动同步 `project_id`；`promote_idea_to_project` 校验仅限 `idea`；`search_sources` 转义 LIKE `%`/`_`；全量 JSON 容错 | AUD-P0-3b / P0-4a / P0-6 / P1-3 / P1-5 / P2-2 |
| [graph.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/graph.py) | 每轮显式全字段初始化 `WorkflowState` + 唯一 `run_thread_id` 根除跨轮串台；`weakref.finalize` 兜底关闭 `_ckpt_conn`；空输入 0 模型短路；`commit_pending_proposal` 先本地 SQLite 原子落盘后云端归档清理，无想法卡/空动作卡安全指引关闭；作废卡自动清理 `tmp_cache`；批量打卡如实回报无效 ID + `完成 1.5h` 剔除工时字面量防误杀；异构 Critic 补传近期对话上下文；清除全部静默 `except: pass` | AUD-P0-1 / P0-4a / P0-4b / P0-5b / P0-6 / P1-2 / P1-4 / P1-5 / P1-6 |
| [critic_rules.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/nodes/critic_rules.py) | 确定性核验严格拦截非法日历日期（如 `2026-02-30`）与结束早于开始的倒挂排期 | AUD-P1-4 |
| [extractors.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/storage/extractors.py) | ZIP 路径穿越改用严格 `dest.is_relative_to(tmp_root)`；解压改用 64KB 流式分块实际字节累计拦截炸弹（免疫伪造 `file_size`） | AUD-P0-5a |
| [wecom_gateway.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/intake/wecom_gateway.py) | `_download_media` 净化路径穿越文件名并强制落在 `tmp_dir`；自建应用支持可选单人白名单 + 定向推送 + `in_flight` 并发防重；`send_app_push` 校验 `errcode` 并在 `42001/40014` 自动刷新 token 重试；单发「好了」无待合批不吞消息；`merged_msg` 内语音接入 ASR；客服通道异常回执优先走 `send_kf_text` | AUD-P0-5a / P1-1 / P1-2 / P1-6 |
| [web/app.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/web/app.py) | `AuthManager` 6 位验证码连续 5 次失败自动销毁并锁定 10 分钟（防爆破）；`ItemUpdateBody` / `ItemCreateBody` / `PromoteIdeaBody` 强枚举 + ISO 日期 + 起止顺序校验；`promote` 允许 `0.0h` 并对非想法返回 `400`；早报 `intent` 修正为 `digest:morning`；清除全部静默 `pass` 并优雅回收后台 Task | AUD-P0-3a / P0-3b / P1-2 / P2-1 / P2-2 |
| [schedule_tools.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/tools/schedule_tools.py) | `calc_business_date` 限制偏移量 `abs(offset) <= 3650` 防模型幻觉卡死 | AUD-P2-1 |
| [onedrive_tools.py](file:///Users/john/Desktop/agentic_learning/wechat_AI_assistant/src/wechat_assistant/tools/onedrive_tools.py) | 单次 PUT 校验返回 `size` 完整性；MSAL 注入 20s 超时保护 | AUD-P2-1 / P2-3 |

---

## 三、Green 阶段全仓终端实证

- **运行命令**：`cd /Users/john/Desktop/agentic_learning/wechat_AI_assistant && uv run pytest -v --tb=short`
- **退出码**：`0`
- **实测结果**：**84 passed in 9.61s**（原有 51 条 + Slice 1 14 条 + Slice 2 19 条，**0 失败、0 跳过、0 未关闭数据库警告**！）
