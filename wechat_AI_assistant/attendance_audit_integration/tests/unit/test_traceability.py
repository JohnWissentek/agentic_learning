"""
溯源对账测试门禁:图-代码不一致 = 测试红 = 不许交付。

ARCHITECTURE.md 尚未建立时跳过(项目早期阶段);一旦架构文档存在即强制对账。
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


@pytest.mark.unit
def test_diagram_code_traceability():
    arch = ROOT / "docs" / "ARCHITECTURE.md"
    if not arch.exists():
        pytest.skip("docs/ARCHITECTURE.md 尚未建立,跳过对账(设计阶段完成后必须通过)")

    from check_traceability import run_check

    assert run_check(ROOT) == 0, "图-代码溯源对账失败,详见上方输出"
