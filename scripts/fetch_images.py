"""离线采集维基共享资源图片到 ``web/public/images/attractions``。

用法：``python scripts/fetch_images.py [--city 北京] [--limit 5] [--width 800] [--dry-run]``

脚本只跑在本地，不在请求路径上；任何单张失败都只打印一行并继续，
进程退出码恒为 0。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.attraction_images import image_meta, image_meta_path, image_slug  # noqa: E402
from data.place_catalog import ATTRACTIONS  # noqa: E402

_API = "https://commons.wikimedia.org/w/api.php"
_USER_AGENT = "CloudTrip/1.0 (offline image fetcher)"
_SLEEP_S = 1.5
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "web", "public", "images", "attractions")
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(value: object) -> str:
    return _TAG_RE.sub("", str(value or "")).strip()


def _build_query(name: str, width: int) -> str:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": name,
        "gsrlimit": "1",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": str(width),
    }
    return f"{_API}?{urllib.parse.urlencode(params)}"


def _request(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _pick_image(payload: bytes) -> dict | None:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    if not isinstance(pages, dict):
        return None
    for page in pages.values():
        infos = (page or {}).get("imageinfo") or []
        if infos and isinstance(infos[0], dict):
            return infos[0]
    return None


def _collect(city: str | None, limit: int | None) -> list[tuple[str, str]]:
    if city:
        if city not in ATTRACTIONS:
            print(f"未找到城市：{city}")
            return []
        groups = [(city, ATTRACTIONS[city])]
    else:
        groups = list(ATTRACTIONS.items())

    targets: list[tuple[str, str]] = []
    for city_name, items in groups:
        picked = items if limit is None else items[:limit]
        for item in picked:
            targets.append((item["name"], city_name))
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="采集景点图片到本地目录")
    parser.add_argument("--city", default=None, help="只采集该城市的景点")
    parser.add_argument("--limit", type=int, default=None, help="每城最多采集数量")
    parser.add_argument("--width", type=int, default=800, help="缩略图宽度")
    parser.add_argument("--dry-run", action="store_true", help="只打印目标，不下载不写文件")
    args = parser.parse_args(argv)

    targets = _collect(args.city, args.limit)
    if not targets:
        return 0

    meta = image_meta() if not args.dry_run else {}
    downloaded = 0

    for name, _city_name in targets:
        query_url = _build_query(name, args.width)
        if args.dry_run:
            print(f"{name} → {query_url}")
            continue

        try:
            info = _pick_image(_request(query_url))
        except (urllib.error.URLError, OSError) as exc:
            print(f"跳过 {name}：请求失败（{exc}）")
            time.sleep(_SLEEP_S)
            continue
        if info is None:
            print(f"跳过 {name}：无搜索结果")
            time.sleep(_SLEEP_S)
            continue

        remote = info.get("thumburl") or info.get("url") or ""
        if not remote:
            print(f"跳过 {name}：缺少图片地址")
            time.sleep(_SLEEP_S)
            continue

        try:
            blob = _request(remote)
        except (urllib.error.URLError, OSError) as exc:
            print(f"跳过 {name}：下载失败（{exc}）")
            time.sleep(_SLEEP_S)
            continue

        mime = str(info.get("thumbmime") or info.get("mime") or "").lower()
        if mime and not mime.startswith("image/"):
            print(f"跳过 {name}：响应不是图片（{mime}）")
            time.sleep(_SLEEP_S)
            continue

        slug = image_slug(name)
        os.makedirs(_OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(_OUTPUT_DIR, f"{slug}.jpg"), "wb") as fp:
            fp.write(blob)

        extmetadata = info.get("extmetadata") or {}
        meta[name] = {
            "slug": slug,
            "source_url": info.get("descriptionurl") or info.get("url") or remote,
            "author": _strip_tags((extmetadata.get("Artist") or {}).get("value")),
            "license": _strip_tags((extmetadata.get("LicenseShortName") or {}).get("value")),
        }
        downloaded += 1
        print(f"已保存 {name} → {slug}.jpg")
        time.sleep(_SLEEP_S)

    if not args.dry_run:
        merged = {**image_meta(), **meta}
        with open(image_meta_path(), "w", encoding="utf-8") as fp:
            json.dump(merged, fp, ensure_ascii=False, indent=2)
        print(f"完成：新采集 {downloaded} 张，元数据共 {len(merged)} 条")
    return 0



if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # 退出码恒为 0，离线脚本不允许阻塞流水线
        print(f"采集异常终止：{exc}")
        sys.exit(0)