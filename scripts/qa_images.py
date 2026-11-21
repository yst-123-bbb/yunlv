"""配图人工质检拼图脚本。

按 ``data/attraction_images.json`` 的顺序把已落盘的景点图片拼成带全局序号的
contact sheet，并输出 ``index.json`` 供人工逐格核对「图片是否对应该景点」。

脚本只读本地数据与图片，不联网、不修改图片，退出码恒为 0；
缺少 Pillow 时打印提示并直接返回。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from data.attraction_images import image_meta, image_slug  # noqa: E402

IMAGE_ROOT = os.path.join(_ROOT, "web", "public", "images", "attractions")
DEFAULT_OUT = os.path.join(_ROOT, "scripts", "_qa_sheets")
MISSING_LABEL = "缺少 Pillow，跳过"


def _city_map() -> dict[str, str]:
    """景点名 -> 城市，用于 index.json 的可读标注；数据缺失时降级为空字符串。"""
    try:
        from data.place_catalog import ATTRACTIONS
    except Exception:
        return {}
    mapping: dict[str, str] = {}
    for city, items in ATTRACTIONS.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                if name and name not in mapping:
                    mapping[name] = city
    return mapping


def _collect() -> tuple[list[dict], int]:
    cities = _city_map()
    items: list[dict] = []
    missing = 0
    for name, meta in image_meta().items():
        clean = (name or "").strip()
        if not clean or not isinstance(meta, dict):
            continue
        slug = str(meta.get("slug") or "").strip() or image_slug(clean)
        path = os.path.join(IMAGE_ROOT, f"{slug}.jpg")
        if not os.path.isfile(path):
            missing += 1
            continue
        items.append(
            {
                "name": clean,
                "city": cities.get(clean, ""),
                "slug": slug,
                "file": f"web/public/images/attractions/{slug}.jpg",
                "_path": path,
            }
        )
    return items, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成景点配图质检拼图")
    parser.add_argument("--per-sheet", type=int, default=12)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--cell", type=int, default=480)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except Exception:
        print(MISSING_LABEL)
        return 0

    cols = max(1, args.cols)
    per_sheet = max(1, args.per_sheet)
    cell_w = max(1, args.cell)
    cell_h = max(1, round(cell_w / 1.5))
    try:
        font = ImageFont.load_default(size=40)
    except Exception:
        font = ImageFont.load_default()

    items, missing = _collect()
    for index, item in enumerate(items, start=1):
        item["index"] = index

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    def render_sheet(chunk: list[dict], out_path: str) -> bool:
        rows = [chunk[i : i + cols] for i in range(0, len(chunk), cols)]
        sheet = Image.new("RGB", (cols * cell_w, len(rows) * cell_h), (255, 255, 255))
        draw = ImageDraw.Draw(sheet, "RGBA")
        for row_i, row in enumerate(rows):
            for col_i, item in enumerate(row):
                try:
                    with Image.open(item["_path"]) as raw:
                        cell = ImageOps.fit(raw.convert("RGB"), (cell_w, cell_h))
                except Exception:
                    continue
                x, y = col_i * cell_w, row_i * cell_h
                sheet.paste(cell, (x, y))
                label = str(item["index"])
                box = draw.textbbox((0, 0), label, font=font)
                pad = 6
                draw.rectangle(
                    [x, y, x + box[2] - box[0] + pad * 2, y + box[3] - box[1] + pad * 2],
                    fill=(255, 255, 255, 190),
                )
                draw.text((x + pad - box[0], y + pad - box[1]), label, fill=(0, 0, 0), font=font)
        sheet.save(out_path, "JPEG", quality=85)
        return True

    sheets = [items[i : i + per_sheet] for i in range(0, len(items), per_sheet)]
    for sheet_no, chunk in enumerate(sheets, start=1):
        out_path = os.path.join(out_dir, f"sheet_{sheet_no:02d}.jpg")
        try:
            render_sheet(chunk, out_path)
        except Exception as exc:  # 单张拼图失败不应中断整体质检流程
            print(f"sheet_{sheet_no:02d}.jpg 生成失败：{exc}")
            continue
        print(f"sheet_{sheet_no:02d}.jpg（{len(chunk)} 张）")
        for item in chunk:
            print(f"  {item['index']}-{item['name']}")

    index_payload = [
        {k: item[k] for k in ("index", "name", "city", "slug", "file")} for item in items
    ]
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as fp:
        json.dump(index_payload, fp, ensure_ascii=False, indent=2)

    print(f"共 {len(items)} 张已拼成 {len(sheets)} 张图，缺图跳过 {missing} 条，输出目录 {out_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # 退出码恒为 0
        print(f"质检拼图异常：{exc}")
        sys.exit(0)