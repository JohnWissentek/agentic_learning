#!/usr/bin/env python3
"""
阶段门闸门(00 总纲 2.4 闸门8):交叉核对 STATUS.md 阶段门 与 CHECKLIST.md 勾选。

拦截两类违规:
    A. 虚标——STATUS 把某阶段标 ✅,但 CHECKLIST 该阶段还有未勾条目
    B. 跳阶段——状态序列不是 "✅…✅ [🔵] ⬜…⬜" 的合法形态

通过时打印当前阶段与剩余未勾项,充当进度提醒(todo 指针)。
仅用标准库。用法: python tools/check_stage.py [--root 项目根]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STAGE_COUNT = 6
CN_NUMS = "一二三四五六"
UNCHECKED_RE = re.compile(r"^\s*-\s*(⬜|\[ \])")
CHECKED_RE = re.compile(r"^\s*-\s*(✅|☑|\[x\])", re.IGNORECASE)
STAGE_HEADER_RE = re.compile(r"^##\s*阶段([一二三四五六])")
GATE_ROW_RE = re.compile(r"^\|\s*([一二三四五六])、[^|]*\|\s*(⬜|🔵|✅)")


def parse_checklist(checklist_md: Path) -> dict[int, tuple[int, list[str]]]:
    """返回 {阶段序号: (未勾数, 未勾条目样例)}。"""
    stages: dict[int, tuple[int, list[str]]] = {}
    current = 0
    unchecked_count = 0
    samples: list[str] = []
    for line in checklist_md.read_text(encoding="utf-8").splitlines():
        header = STAGE_HEADER_RE.match(line)
        if header:
            if current:
                stages[current] = (unchecked_count, samples)
            current = CN_NUMS.index(header.group(1)) + 1
            unchecked_count, samples = 0, []
            continue
        if current and UNCHECKED_RE.match(line):
            unchecked_count += 1
            if len(samples) < 3:
                samples.append(line.strip()[:60])
    if current:
        stages[current] = (unchecked_count, samples)
    return stages


def parse_status_gates(status_md: Path) -> list[str]:
    """返回六个阶段的状态符号列表,如 ['✅','🔵','⬜',…];解析失败返回空表。"""
    gates: dict[int, str] = {}
    for line in status_md.read_text(encoding="utf-8").splitlines():
        row = GATE_ROW_RE.match(line.strip())
        if row:
            gates[CN_NUMS.index(row.group(1)) + 1] = row.group(2)
    return [gates[i] for i in range(1, STAGE_COUNT + 1)] if len(gates) == STAGE_COUNT else []


def check(root: Path) -> int:
    status_md = root / "docs" / "STATUS.md"
    checklist_md = root / "docs" / "CHECKLIST.md"

    if not status_md.exists() or not checklist_md.exists():
        print("[SKIP] STATUS.md 或 CHECKLIST.md 尚未建立,跳过阶段门检查。")
        return 0

    gates = parse_status_gates(status_md)
    stages = parse_checklist(checklist_md)
    if not gates or len(stages) < STAGE_COUNT:
        print("[WARN] 阶段门表或 Checklist 阶段结构解析失败(可能表格式被改动),"
              "本次放行——请尽快修复表格式,否则阶段门闸门形同虚设。", file=sys.stderr)
        return 0

    problems: list[str] = []

    # 规则A: 反虚标
    for i, gate in enumerate(gates, start=1):
        if gate == "✅":
            unchecked_count, samples = stages[i]
            if unchecked_count:
                problems.append(
                    f"阶段{CN_NUMS[i - 1]}在 STATUS 已标 ✅,但 CHECKLIST 还有 "
                    f"{unchecked_count} 项未勾,例如: " + "; ".join(samples)
                )

    # 规则B: 反跳阶段(合法形态: ✅…✅ [🔵] ⬜…⬜)
    seen_non_pass = False
    seen_in_progress = False
    for i, gate in enumerate(gates, start=1):
        if gate == "✅" and seen_non_pass:
            problems.append(f"阶段{CN_NUMS[i - 1]}标了 ✅,但它前面还有未通过的阶段——不许跳阶段")
        if gate == "🔵":
            if seen_in_progress:
                problems.append(f"出现多个 🔵 进行中阶段(阶段{CN_NUMS[i - 1]})——一次只推进一个阶段")
            if seen_non_pass:
                problems.append(f"阶段{CN_NUMS[i - 1]}标了 🔵,但它前面还有 ⬜ 未开始的阶段")
            seen_in_progress = True
        if gate != "✅":
            seen_non_pass = True

    if problems:
        print("❌ 阶段门检查未通过(00 总纲:不许跳阶段,不许虚标):")
        for p in problems:
            print(f"   {p}")
        return 1

    # 通过: 打印进度指针
    current_stage = next((i for i, g in enumerate(gates, start=1) if g != "✅"), None)
    if current_stage is None:
        print("✅ 阶段门检查通过:六阶段全部完成。")
    else:
        unchecked_count, samples = stages[current_stage]
        print(f"✅ 阶段门检查通过。当前阶段:阶段{CN_NUMS[current_stage - 1]},"
              f"出口条件还剩 {unchecked_count} 项未勾。")
        for s in samples:
            print(f"   下一项 → {s}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="阶段门与 Checklist 一致性检查")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    sys.exit(check(args.root))


if __name__ == "__main__":
    main()
