"""示例单元测试：验证配置校验逻辑。命名规范见 04_TESTING_STANDARD.md。"""
import pytest

from attendance_audit_integration import config


@pytest.mark.unit
def test_get_missing_key_returns_default():
    assert config.get("NO_SUCH_KEY_XYZ", "fallback") == "fallback"


@pytest.mark.unit
def test_validate_missing_required_key_exits(monkeypatch):
    # PRD: 配置缺失应启动即退出，而非运行中崩溃
    monkeypatch.setattr(config, "REQUIRED_KEYS", ["NO_SUCH_KEY_XYZ"])
    monkeypatch.delenv("NO_SUCH_KEY_XYZ", raising=False)
    with pytest.raises(SystemExit):
        config.validate()
