# -*- coding: utf-8 -*-
"""文件缓存模块 - 缓存高德API请求结果，减少重复调用"""
import sys
import os
import json
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_THIS_DIR)
CACHE_DIR = os.path.join(_BASE, "_cache")
CACHE_TTL = 3600  # 默认1小时

if not os.path.exists(CACHE_DIR):
    try:
        os.makedirs(CACHE_DIR)
    except Exception:
        pass


def _safe_key(key):
    """生成安全的文件名"""
    import hashlib
    key_str = str(key).encode("utf-8")
    return hashlib.md5(key_str).hexdigest()


def get(key):
    """读取缓存"""
    try:
        fp = os.path.join(CACHE_DIR, _safe_key(key) + ".json")
        if not os.path.exists(fp):
            return None
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = float(data.get("ts", 0))
        if time.time() - ts > CACHE_TTL:
            return None
        return data.get("value")
    except Exception:
        return None


def set(key, value, ttl=None):
    """写入缓存"""
    try:
        fp = os.path.join(CACHE_DIR, _safe_key(key) + ".json")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "value": value, "ttl": ttl or CACHE_TTL},
                      f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def cached(key, func, *args, **kwargs):
    """装饰器风格的缓存调用"""
    result = get(key)
    if result is not None:
        return result
    result = func(*args, **kwargs)
    if result:
        set(key, result)
    return result


def clear():
    """清空缓存"""
    cnt = 0
    try:
        for fn in os.listdir(CACHE_DIR):
            if fn.endswith(".json"):
                try:
                    os.remove(os.path.join(CACHE_DIR, fn))
                    cnt += 1
                except Exception:
                    continue
    except Exception:
        pass
    return cnt


def info():
    """缓存信息"""
    cnt = 0
    size = 0
    try:
        for fn in os.listdir(CACHE_DIR):
            if fn.endswith(".json"):
                fp = os.path.join(CACHE_DIR, fn)
                cnt += 1
                size += os.path.getsize(fp)
    except Exception:
        pass
    return {"count": cnt, "size_kb": round(size / 1024, 1)}


if __name__ == "__main__":
    inf = info()
    print("缓存目录: " + CACHE_DIR)
    print("文件数: " + str(inf["count"]) + "  大小: " + str(inf["size_kb"]) + "KB")
    print("\n可用命令:")
    print("  python utils/cache.py  - 查看状态")
    print("  python -c \"from utils.cache import clear; print('删除'+str(clear())+'个文件')\" - 清空缓存")