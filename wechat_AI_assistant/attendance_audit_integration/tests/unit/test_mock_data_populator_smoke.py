"""无真实 Postgres 时的干跑烟雾测试：用假游标校验 SQL 占位符数量与整体调用链不炸。

不验证 SQL 的业务语义（那需要真实数据库），只保证：
1. 每条 cursor.execute(sql, params) 的 %s 占位符个数与 params 个数一致；
2. populate_test_data 在真实拉取为空、场景缺口全部命中的路径下能跑完整个流程。
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

import attendance_audit_integration.mock_data_populator as mdp


class FakeCursor:
    def __init__(self, employees):
        self._employees = employees
        self._next_id = 1
        self._last_result = None
        self.rowcount = 0
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, sql, params=None):
        params = params or ()
        placeholder_count = len(re.findall(r"%s", sql))
        assert placeholder_count == len(params), (
            "SQL 占位符(%s)数量(%d) 与传入参数数量(%d) 不一致:\n%s"
            % (placeholder_count, placeholder_count, len(params), sql)
        )
        self.executed.append((sql, params))
        normalized = " ".join(sql.split())

        if normalized.startswith("SELECT wecom_userid, name FROM employees"):
            self._last_result = list(self._employees)
        elif normalized.startswith("SELECT table_name, record_pk FROM test_data_provenance"):
            self._last_result = []
        elif normalized.startswith("SELECT approval_no, wecom_userid, start_time, end_time FROM approvals"):
            self._last_result = []
        elif "FROM attendance_logs" in normalized and "GROUP BY" in normalized:
            self._last_result = []  # 模拟真实打卡窗口完全无数据，逼所有场景走 mock 补齐分支
        elif "RETURNING id" in normalized:
            self._last_result = [(self._next_id,)]
            self._next_id += 1
            self.rowcount = 1
        elif normalized.startswith("INSERT"):
            self.rowcount = 1
            self._last_result = None
        else:
            self._last_result = None
            self.rowcount = 0

    def fetchone(self):
        if isinstance(self._last_result, list):
            return self._last_result[0] if self._last_result else None
        return self._last_result

    def fetchall(self):
        return self._last_result or []

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def cursor(self, cursor_factory=None):
        return self._cursor

    def commit(self):
        self.commits += 1

    def close(self):
        pass


@pytest.mark.unit
def test_populate_test_data_dry_run_smoke(monkeypatch):
    employees = [("user_a", "张三"), ("user_b", "李四"), ("user_c", "王五")]
    fake_cursor = FakeCursor(employees)
    fake_conn = FakeConnection(fake_cursor)

    monkeypatch.setattr(mdp, "get_db_connection", lambda: fake_conn)
    monkeypatch.setattr(mdp, "sync_real_punches", lambda cursor, ids, s, e: 0)
    monkeypatch.setattr(mdp, "sync_real_daily_reports", lambda cursor, s, e: 0)
    # 固定为周一，避开真实节假日库查询（未打真实 Postgres 时 is_workday_db 会自开连接）
    monkeypatch.setattr(mdp, "is_workday_db", lambda d: d.weekday() < 5)

    end_date = date(2026, 7, 14)
    start_date = end_date - timedelta(days=6)

    summary = mdp.populate_test_data(start_date, end_date)

    assert summary["real_punches"] == 0
    assert summary["real_daily_reports"] == 0
    # 真实打卡窗口全空 → 三个场景应各自补 1 条（E12 需要 >=2 名员工才会补）
    assert summary["mock_scenario_backfill"]["E1"] is True
    assert summary["mock_scenario_backfill"]["E11"] is True
    assert summary["mock_scenario_backfill"]["E12"] is True
    assert summary["mock_expiry_fixtures"] == len(employees)
    assert fake_conn.commits > 0
