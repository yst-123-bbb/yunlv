"""C-CFG@1 配置读取：默认值、缺失配置检查与 prod 启动校验。"""

from __future__ import annotations

import pytest

from settings import ConfigError, settings, startup_check


def test_settings_defaults():
    assert settings.kimi_model
    assert settings.db_path
    assert isinstance(settings.amap_daily_quota, int)
    assert isinstance(settings.http_timeout_s, float)
    assert settings.app_env in ("dev", "prod")
    assert settings.cache_backend in ("file", "sqlite")


def test_config_error_is_runtime_error():
    assert issubclass(ConfigError, RuntimeError)


def test_startup_check_reports_missing_keys(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "amap_key", "")
    monkeypatch.setattr(settings, "kimi_api_key", "")

    missing = startup_check()

    assert isinstance(missing, list)
    assert missing
    names = [str(item).lower() for item in missing]
    assert any("amap" in name for name in names)
    assert any("kimi" in name for name in names)


def test_startup_check_returns_empty_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "amap_key", "test-amap-key")
    monkeypatch.setattr(settings, "kimi_api_key", "test-kimi-key")

    assert startup_check() == []


def test_startup_check_raises_in_prod_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "amap_key", "")
    monkeypatch.setattr(settings, "kimi_api_key", "")

    with pytest.raises(ConfigError):
        startup_check()