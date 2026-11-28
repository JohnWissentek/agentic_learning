"""诊断包标准件测试：能生成、含三类内容、密钥已脱敏。"""

import zipfile

import pytest

from attendance_audit_integration import diagnostics


@pytest.mark.unit
def test_export_creates_zip_with_masked_env(tmp_path, monkeypatch):
    # 构造带"密钥"的临时项目环境
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "app.log").write_text("2026-01-01 INFO test", encoding="utf-8")
    (tmp_path / ".env").write_text("API_SECRET=super_secret_value_123\n", encoding="utf-8")
    monkeypatch.setattr(diagnostics, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(diagnostics, "LOG_DIR", tmp_path / "logs")

    zip_path = diagnostics.export(out_dir=tmp_path)

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "logs/app.log" in names
        assert "env_masked.txt" in names
        assert "health.json" in names
        env_txt = zf.read("env_masked.txt").decode("utf-8")
        # 密钥值必须已脱敏
        assert "super_secret_value_123" not in env_txt
        assert "API_SECRET=supe****" in env_txt
