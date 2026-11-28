#!/usr/bin/env python3
"""
过程规则检查(00 总纲 2.4 第 2 条机器闸门),由 pre-commit hook 调用。

规则:凡是触碰 src/** 或 docs/**(STATUS.md 自身除外)的提交,
必须同时包含 docs/STATUS.md 的改动——强制"每次工作必更新状态总账"。

仅用标准库。独立运行方式:
    python tools/check_process.py            # 检查当前 staged 内容
"""
from __future__ import annotations

import subprocess
import sys


def staged_files() -> list[str]:
    """返回本次提交 staged 的文件路径列表(相对仓库根)。"""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def check(files: list[str]) -> int:
    substantive = [
        f for f in files
        if (f.startswith("src/") or f.startswith("docs/") or f.startswith("tests/"))
        and f != "docs/STATUS.md"
    ]
    if not substantive:
        return 0  # 本次提交不含实质工作内容(如只改 README/工具),不强制

    if "docs/STATUS.md" in files:
        return 0

    print("❌ 本次提交修改了实质内容,但未更新 docs/STATUS.md(项目状态总账)。")
    print("   受影响文件(前5条):")
    for f in substantive[:5]:
        print(f"     {f}")
    print("   请更新 STATUS.md(当前状态/功能矩阵/开发日志)后重新 git add 提交。")
    print("   依据:00 总纲 2.2——不更新状态总账,视同工作未完成。")
    return 1


def main() -> None:
    try:
        files = staged_files()
    except subprocess.CalledProcessError as e:
        print(f"[WARN] 无法读取 git staged 列表,跳过过程检查: {e}", file=sys.stderr)
        sys.exit(0)
    sys.exit(check(files))


if __name__ == "__main__":
    main()
