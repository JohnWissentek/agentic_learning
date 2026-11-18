# 黄金真实样本实弹回放器与一页纸轨迹表模板 (Golden Trace Harness)

静态流程图看不见动态分支遗漏。通过一个 60 行左右的轻量回放脚本（如 `scripts/replay_golden_traces.py`），在本地临时数据库上跑一遍 8～12 条真实刁钻样本，自动拦截以下四项运行证据并渲染成 Markdown 表：

---

## 1. 黄金样本集必选的 8 类典型与刁钻场景

构造 `GOLDEN_SAMPLES` 列表时，至少覆盖以下 8 类（不要只放阳光大道样本）：

1. **`G01_fast_shortcut`（0 模型快捷口令）**：如 `完成 #1` / `看板` → 验证 **LLM 调用次数 == 0**，库表状态准确变更并留存撤销快照。
2. **`G02_untrusted_sender`（非白名单越权攻击）**：陌生外部 ID 发来带提示词注入的内容 → 验证入口直接拦截，**LLM == 0、工具 == 0、全表 Diff == 0**。
3. **`G03_duplicate_delivery`（回调/轮询重推幂等）**：相同 `msg_id` 连续投递 2 次 → 验证第 2 次 **LLM == 0**，待确认卡/正式表绝不产生重复记录。
4. **`G04_mixed_attachment_qa`（带附件混合意图）**：上传 PDF/Excel 附件同时配一句查档提问 → 验证无论路由去哪条分支，**附件提取与原件归档钩子均未漏调**。
5. **`G05_orphan_confirm`（无待确认卡误发确认）**：当前无挂起提案时发送 `1` 或 `确认` → 验证安全兜底改判，绝不误写正式表或抛异常崩溃。
6. **`G06_empty_grounding`（查无依据防幻觉）**：询问库里完全不存在的历史项目数据 → 验证闭卷拒答兜底，绝不编造数字。
7. **`G07_core_triage_hitl`（核心交办与两段式落盘）**：带具体金额/日期的交办 → 先只进 `pending_proposals` 草稿表（正式表 `+0`），紧接模拟本人回复确认后，验证凭有效令牌原子写入正式表。
8. **`G08_corrupt_or_oversize_file`（坏格式/加密附件降级）**：传入损坏或受密码保护的文档 → 验证优雅返回安全占位说明，单进程服务不崩溃、临时文件已清理。

---

## 2. 回放脚本采集器核心设计模式（Python 参考骨架）

```python
# 核心思路：不改业务源码，仅在回放脚本中用轻量包装器统计调用轨迹与 SQLite 表行数变化
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TurnTrace:
    sample_id: str
    input_summary: str
    route_taken: str = "-"
    llm_calls: list[str] = field(default_factory=list)     # 例: ["fast:router", "producer:drafter"]
    tool_calls: list[str] = field(default_factory=list)    # 例: ["extract_pdf", "check_schedule"]
    db_diff: dict[str, int] = field(default_factory=dict)  # 例: {"pending_proposals": +1, "list_items": 0}
    reply_preview: str = ""
    verdict: str = "PASS"


def snapshot_table_counts(conn, tables: list[str]) -> dict[str, int]:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def compute_db_diff(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {t: after[t] - before[t] for t in before if after[t] != before[t]}
```

---

## 3. 输出给人类审阅的一页纸 Markdown 体检表格式

每次运行回放后，直接打印或写入如下表格（人类 3 分钟扫完即可拍板）：

```markdown
| 编号 | 真实输入样本摘要 | 实际命中路由 | LLM 调用明细 | 关键工具调用链 | 数据库表行数 Diff | 最终回复前 40 字 | 门禁判定 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| G01 | 本人发：`完成 #1` | `shortcut` | `0 次` | `complete_item` → `sync` | `undo_snapshots +1` | `✅ 已标记完成...` | 🟢 PASS |
| G02 | 外部号发注入指令 | `blocked` | `0 次` | `无` | `全表 0 变化` | `(静默丢弃)` | 🟢 PASS |
| G04 | 报价PDF + 查历史价 | `quick_qa` | `fast×1, prod×1` | `retrieve` (缺 `extract`!) | `raw_sources +0` ⚠️ | `未查到记录...` | 🔴 FAIL |
```
