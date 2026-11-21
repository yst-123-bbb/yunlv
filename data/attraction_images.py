"""景点图片地址与离线采集元数据。

图片路径由景点名做 md5 前缀得到，因此后端无需知道图片是否已落盘；
文件缺失由前端 ``PlaceImage`` 的 ``onError`` 回退占位。
"""

from __future__ import annotations

import hashlib
import json
import os

IMAGE_DIR: str = "/images/attractions"

_META_FILE = "attraction_images.json"
_DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_META_CACHE: dict[str, dict] | None = None


def image_slug(name: str) -> str:
    return hashlib.md5(name.strip().encode("utf-8")).hexdigest()[:12]


def _version(name: str) -> str:
    url = (image_meta().get(name) or {}).get("url")
    if not isinstance(url, str) or not url:
        return ""
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]


def image_url(name: str) -> str:
    if not name:
        return ""
    path = f"{IMAGE_DIR}/{image_slug(name)}.jpg"
    version = _version(name)
    return f"{path}?v={version}" if version else path


def image_remote_url(name: str) -> str:
    if not name:
        return ""
    url = (image_meta().get(name) or {}).get("url")
    return url if isinstance(url, str) else ""


def image_meta_path() -> str:
    return os.path.join(_DATA_DIR, "data", _META_FILE)


def reload_meta() -> dict[str, dict]:
    global _META_CACHE
    _META_CACHE = None
    return image_meta()


def image_meta() -> dict[str, dict]:
    global _META_CACHE
    if _META_CACHE is not None:
        return _META_CACHE
    try:
        with open(image_meta_path(), encoding="utf-8") as fp:
            payload = json.load(fp)
    except (OSError, json.JSONDecodeError):
        payload = None
    _META_CACHE = payload if isinstance(payload, dict) else {}
    return _META_CACHE