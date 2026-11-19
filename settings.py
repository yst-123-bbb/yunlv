# -*- coding: utf-8 -*-
"""云旅AI - 统一配置入口

所有运行期配置（含密钥）从环境变量与项目根目录的 .env 读取，
不再在源码中保存明文 Key。
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# 没有这些 Key 时对应能力会自动降级为本地模式
REQUIRED_KEYS = ("AMAP_KEY", "KIMI_API_KEY")


class ConfigError(RuntimeError):
    """生产环境缺少必要配置时抛出。"""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    amap_key: str = ""
    kimi_api_key: str = ""
    kimi_model: str = "moonshot-v1-8k"
    kimi_enabled: bool = True
    use_real_amap: bool = True
    trip_use_local_fallback: bool = True
    db_path: str = "datastore/cloudtrip.db"
    cache_backend: Literal["file", "sqlite"] = "file"
    cache_dir: str = "_cache"
    log_level: str = "INFO"
    app_env: Literal["dev", "prod"] = "dev"
    http_timeout_s: float = 10.0
    amap_daily_quota: int = 2000
    amap_quota_state: str = "_cache/amap_quota.json"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1/chat/completions"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_s: float = 30.0


settings = Settings()

# 自由制定对话用的 DeepSeek 配置，未填 Key 时对话自动降级为本地规则应答
DEEPSEEK_API_KEY: str = settings.deepseek_api_key
DEEPSEEK_BASE_URL: str = settings.deepseek_base_url
DEEPSEEK_MODEL: str = settings.deepseek_model
DEEPSEEK_TIMEOUT_S: float = settings.deepseek_timeout_s


def startup_check() -> list[str]:
    """返回缺失的配置项名称；生产环境缺失时直接抛 ConfigError。"""
    missing: list[str] = []
    if not settings.amap_key.strip():
        missing.append("AMAP_KEY")
    if not settings.kimi_api_key.strip():
        missing.append("KIMI_API_KEY")

    if settings.app_env == "prod" and missing:
        raise ConfigError(f"生产环境缺少必要配置: {', '.join(missing)}")
    return missing