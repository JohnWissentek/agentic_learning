"""pytest 全局配置：测试日志写入 logs/test.log，共享 fixture 放这里。"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _test_logging():
    """测试期间日志写入 logs/test.log（DEBUG级），排查失败先看日志。"""
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    handler = logging.FileHandler(log_dir / "test.log", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
    ))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    yield
    root.removeHandler(handler)


@pytest.fixture
def fixtures_dir() -> Path:
    """tests/fixtures/ 目录，存放真实API返回样本等测试数据。"""
    return ROOT / "tests" / "fixtures"
