# -*- coding: utf-8 -*-
"""工具函数 - 彩色打印/数据标记"""
import sys
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_THIS_DIR)
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

try:
    from config import COLORS, HOLIDAYS
except Exception:
    COLORS = {"OKGREEN": "", "OKBLUE": "", "OKCYAN": "", "WARNING": "", "FAIL": "", "ENDC": ""}
    HOLIDAYS = []


def cprint(text, color="OKGREEN"):
    prefix = COLORS.get(color, "")
    suffix = COLORS.get("ENDC", "") if prefix else ""
    try:
        print(prefix + str(text) + suffix)
    except Exception:
        print(text)


def title(text, level=1):
    width = 56
    bar = "=" * width if level == 1 else "-" * width
    print()
    cprint(bar, "OKCYAN" if level == 1 else "OKBLUE")
    cprint("  " + str(text), "OKGREEN")
    cprint(bar, "OKCYAN" if level == 1 else "OKBLUE")


def mark_source(data, realtime=False):
    label = "实时数据" if realtime else "兜底数据"
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                item["_source"] = label
    elif isinstance(data, dict):
        data["_source"] = label
    return data


def dedup(items):
    seen = set()
    result = []
    for it in items:
        key = str(it.get("name", str(it))) if isinstance(it, dict) else str(it)
        if key and key not in seen:
            seen.add(key)
            result.append(it)
    return result


def is_holiday(date_str):
    try:
        parts = str(date_str).split("-")
        if len(parts) >= 3:
            return parts[1] + "-" + parts[2] in HOLIDAYS
    except Exception:
        pass
    return False