"""生成景点图片命名清单：景点名 → 期望文件名 → Commons 搜索链接。

与 ``scripts/fetch_images.py`` 共用同一套 md5 命名规则，用于人工补图：
浏览器里点开"Commons搜索链接"找到合适的图，另存为"期望文件名"，
放进 ``web/public/images/attractions/`` 即可，无需改任何代码。

用法：``python scripts/gen_image_manifest.py``
输出：``data/image_manifest.tsv``（UTF-8 BOM，Excel 可直接打开）
"""

from __future__ import annotations

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.attraction_images import image_slug  # noqa: E402
from data.place_catalog import ATTRACTIONS  # noqa: E402

_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "image_manifest.tsv"
)
_SEARCH = "https://commons.wikimedia.org/w/index.php?title=Special:MediaSearch&type=image&search="


def main() -> int:
    lines = ["城市\t景点名\t期望文件名\tCommons搜索链接"]
    count = 0
    for city, items in ATTRACTIONS.items():
        for item in items:
            name = item["name"]
            lines.append(
                f"{city}\t{name}\t{image_slug(name)}.jpg\t{_SEARCH}{urllib.parse.quote(name)}"
            )
            count += 1
    with open(_OUT, "w", encoding="utf-8-sig") as fp:
        fp.write("\n".join(lines) + "\n")
    print(f"已生成 {_OUT}，共 {count} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())