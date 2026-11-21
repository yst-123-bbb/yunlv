"""离线采集维基共享资源图片到 ``web/public/images/attractions``。

用法：``python scripts/fetch_images.py [--city 北京] [--limit 5] [--width 800] [--dry-run]``

脚本只跑在本地，不在请求路径上；任何单张失败都只打印一行并继续，
进程退出码恒为 0。
"""

from __future__ import annotations

import argparse
import http.client
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

# 部分景点名在共享资源上语义过泛（会搜到地铁站、施工照），用更精确的检索词覆盖。
_QUERY_OVERRIDES: dict[str, str] = {
    "深圳湾公园": "Shenzhen Bay Park",
    "迪士尼乐园": "Shanghai Disneyland Enchanted Storybook Castle",
    "长沙世界之窗": "Window of the World Changsha",
    "东方明珠": "Oriental Pearl Tower Shanghai skyline",
    "香港迪士尼乐园": "Hong Kong Disneyland castle",
    "尖沙咀海滨长廊": "Tsim Sha Tsui Waterfront Promenade",
    "庙街夜市": "Temple Street Night Market",
}

# 经拼图逐格视觉核验确认配图张冠李戴的条目，补更精确的检索词。
_QUERY_OVERRIDES.update({
    "世界之窗": "Window of the World Shenzhen",
    "亚龙湾": "Yalong Bay Sanya beach",
    "蜈支洲岛": "Wuzhizhou Island Sanya",
    "环岛路": "Xiamen Island Ring Road",
    "栈桥": "Zhanqiao Pier Qingdao",
    "五四广场": "May Fourth Square Qingdao sculpture",
    "黑龙潭公园": "Black Dragon Pool Lijiang",
    "南京路步行街": "Nanjing Road Shanghai pedestrian street night",
    "解放碑步行街": "Jiefangbei Chongqing pedestrian street",
    "苏州博物馆": "Suzhou Museum I. M. Pei",
})

# 地标级景点按宽度排序可能选到局部特写/仰视近景，需要精确指定共享资源上的文件。
_FILE_OVERRIDES: dict[str, str] = {
    "迪士尼乐园": "File:Enchanted Storybook Castle (125424).jpg",
    "尖沙咀海滨长廊": "File:The Avenue of the Stars And the Tsim Sha Tsui Promenade... (19424936394).jpg",
    "栈桥": "File:20240729 Zhanqiao 01.jpg",
    "环岛路": "File:Huandao Rd.JPG",
    "解放碑步行街": "File:Jiefangbei.jpg",
    "苏州博物馆": "File:Suzhou Museum - new buildings.jpg",
}

_ALLOWED_MIMES = frozenset({"image/jpeg", "image/png"})
_MIN_WIDTH = 1200
_MIN_HEIGHT = 600
_MIN_RATIO = 1.2
_MAX_RATIO = 2.0
_TARGET_RATIO = 1.5
_NEGATIVE_TERMS = (
    "construction",
    "metro",
    "subway",
    "station",
    "map",
    "diagram",
    "logo",
    "floor plan",
    "ticket",
    "poster",
    "flag",
    "coat of arms",
    "emblem",
    "panorama",
    "platform",
    "railway station",
    "train station",
    "bus terminal",
    "airport terminal",
    "interchange",
    "overpass",
    "road sign",
    "notice",
    "regulation",
    "manuscript",
    "brochure",
    "leaflet",
    "advertisement",
    "exhibition hall",
    "book cover",
    "stone rubbing",
    "站台",
    "候车",
    "广告",
    "规划",
    "条例",
    "拓片",
    "书页",
    "封面",
)
_RATE_LIMIT_CODE = 429
_RATE_LIMIT_RETRIES = 2
_RATE_LIMIT_WAIT_S = 90


def _strip_tags(value: object) -> str:
    return _TAG_RE.sub("", str(value or "")).strip()


def _build_query(query: str, width: int) -> str:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": query,
        "gsrlimit": "20",
        "prop": "imageinfo",
        # mime 不在 size 里，必须显式写进 iiprop 才能拿到筛选所需的 imageinfo.mime
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": str(width),
    }
    return f"{_API}?{urllib.parse.urlencode(params)}"


def _build_file_query(title: str, width: int) -> str:
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": str(width),
    }
    return f"{_API}?{urllib.parse.urlencode(params)}"


def _request(url: str) -> bytes:
    attempts = _RATE_LIMIT_RETRIES + 1
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code != _RATE_LIMIT_CODE or attempt == attempts - 1:
                raise
            print(f"触发限流，{_RATE_LIMIT_WAIT_S} 秒后重试……")
            time.sleep(_RATE_LIMIT_WAIT_S)
    raise urllib.error.URLError("请求重试次数已用尽")


def _image_infos(payload: bytes) -> list[dict]:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    pages = (data.get("query") or {}).get("pages") or {}
    if not isinstance(pages, dict):
        return []
    infos: list[dict] = []
    for page in pages.values():
        page = page or {}
        entries = page.get("imageinfo") or []
        if entries and isinstance(entries[0], dict):
            info = entries[0]
            # 文件名（含扩展名）在 page 层，imageinfo 里没有，负面词过滤需要它
            if not info.get("title"):
                info["title"] = page.get("title") or ""
            infos.append(info)
    return infos


def _is_eligible(info: dict) -> bool:
    mime = str(info.get("mime") or "").lower()
    if mime not in _ALLOWED_MIMES:
        return False
    width, height = info.get("width"), info.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return False
    if width < _MIN_WIDTH or height < _MIN_HEIGHT:
        return False
    ratio = width / height
    if not _MIN_RATIO <= ratio <= _MAX_RATIO:
        return False
    extmetadata = info.get("extmetadata") or {}
    description = _strip_tags((extmetadata.get("ImageDescription") or {}).get("value"))
    haystack = f"{info.get('title') or ''} {description}".lower()
    return not any(term in haystack for term in _NEGATIVE_TERMS)


def _pick_image(payload: bytes) -> dict | None:
    eligible = [info for info in _image_infos(payload) if _is_eligible(info)]
    if not eligible:
        return None
    eligible.sort(
        key=lambda info: (
            -info["width"],
            abs(info["width"] / info["height"] - _TARGET_RATIO),
        )
    )
    return eligible[0]


def _collect(
    city: str | None, limit: int | None, only: set[str] | None = None
) -> list[tuple[str, str]]:
    if city:
        if city not in ATTRACTIONS:
            print(f"未找到城市：{city}")
            return []
        groups = [(city, ATTRACTIONS[city])]
    else:
        groups = list(ATTRACTIONS.items())

    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _city_name, items in groups:
        picked = items if limit is None else items[:limit]
        for item in picked:
            name = item["name"]
            if only is not None and name not in only:
                continue
            seen.add(name)
            targets.append((name, _QUERY_OVERRIDES.get(name, name)))
    if only is not None:
        missing = only - seen
        if missing:
            print(f"未找到景点：{'、'.join(sorted(missing))}")
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="采集景点图片到本地目录")
    parser.add_argument("--city", default=None, help="只采集该城市的景点")
    parser.add_argument("--limit", type=int, default=None, help="每城最多采集数量")
    parser.add_argument("--only", default=None, help="只采集指定景点，逗号分隔")
    parser.add_argument("--width", type=int, default=1000, help="缩略图宽度")
    parser.add_argument("--dry-run", action="store_true", help="只打印目标，不下载不写文件")
    args = parser.parse_args(argv)

    only = {n.strip() for n in args.only.split(",") if n.strip()} if args.only else None
    targets = _collect(args.city, args.limit, only)
    if not targets:
        return 0

    meta = image_meta() if not args.dry_run else {}
    downloaded = 0

    for name, query in targets:
        pinned = _FILE_OVERRIDES.get(name)
        query_url = (
            _build_file_query(pinned, args.width)
            if pinned
            else _build_query(query, args.width)
        )
        if args.dry_run:
            print(f"{name} → {query_url}")
            continue

        try:
            info = _pick_image(_request(query_url))
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            print(f"跳过 {name}：请求失败（{exc}）")
            time.sleep(_SLEEP_S)
            continue
        if info is None:
            print(f"跳过 {name}：无合格图片")
            time.sleep(_SLEEP_S)
            continue

        remote = info.get("thumburl") or info.get("url") or ""
        if not remote:
            print(f"跳过 {name}：缺少图片地址")
            time.sleep(_SLEEP_S)
            continue

        try:
            blob = _request(remote)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
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
            "url": remote,
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