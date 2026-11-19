# -*- coding: utf-8 -*-
"""数据源现状基线抽样：按品类随机抽样，输出待人工核对的 CSV，并给出静态体检错误率。

抽样口径与 docs/data-baseline.md 保持一致：
- 五个品类，每品类最多 50 条（不足则全量）；
- 使用 random.seed(42)，同一份数据重复执行得到同一批样本；
- 「错误率」= 自动静态校验发现问题的条目数 / 该品类抽样条目数。
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import re
import sys
from collections.abc import Callable, Iterator
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import attraction_data, flight_data, food_data, hotel_data, train_data  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "_cache", "data-baseline-sample.csv")
DEFAULT_PER_CATEGORY = 50
DEFAULT_SEED = 42

CATEGORIES = ("attraction", "restaurant", "hotel", "train_route", "flight_route")

CSV_COLUMNS = (
    "category",
    "city",
    "name",
    "expected_fields",
    "auto_issues",
    "verify_result",
    "verify_note",
)

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_HHMM_RANGE_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-(0\d|1\d|2[0-3]):[0-5]\d$")

Sample = dict[str, Any]


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_attraction(item: dict) -> list[str]:
    issues: list[str] = []
    if _blank(item.get("address")):
        issues.append("address 缺失")
    if not _is_number(item.get("ticket_price")) or item["ticket_price"] < 0:
        issues.append(f"ticket_price 非法({item.get('ticket_price')!r})")
    open_time = item.get("open_time")
    if _blank(open_time):
        issues.append("open_time 缺失")
    elif open_time != "全天" and not _HHMM_RANGE_RE.match(str(open_time).split("(")[0]):
        issues.append(f"open_time 格式可疑({open_time!r})")
    return issues


def _check_restaurant(item: dict) -> list[str]:
    issues: list[str] = []
    if _blank(item.get("address")):
        issues.append("address 缺失")
    price = item.get("avg_price")
    if not _is_number(price) or price <= 0:
        issues.append(f"avg_price 非法({price!r})")
    return issues


def _check_hotel(item: dict) -> list[str]:
    issues: list[str] = []
    if _blank(item.get("address")):
        issues.append("address 缺失")
    price = item.get("price")
    if not _is_number(price) or price <= 0:
        issues.append(f"price 非法({price!r})")
    return issues


def _check_train_route(pair: str, rows: list[tuple]) -> list[str]:
    issues: list[str] = []
    if not rows:
        return ["trains 为空"]
    dep, dest = pair.split("-", 1)
    for row in rows:
        if len(row) != 8:
            issues.append(f"车次字段数异常({row!r})")
            continue
        code, from_station, to_station, depart_time, arrive_time, _dur, second, first = row
        if _blank(code) or _blank(from_station) or _blank(to_station):
            issues.append(f"车次 {code!r} 站名缺失")
        if not _HHMM_RE.match(str(depart_time)) or not _HHMM_RE.match(str(arrive_time)):
            issues.append(f"车次 {code} 时刻格式可疑")
        if not _is_number(second) or second <= 0 or not _is_number(first) or first <= 0:
            issues.append(f"车次 {code} 票价非法")
        if from_station == to_station:
            issues.append(f"车次 {code} 出发到达站相同")
    if not issues:
        depart_city, arrive_city = dep, dest
        stations = {row[1] for row in rows if isinstance(row, tuple) and len(row) == 8}
        stations |= {row[2] for row in rows if isinstance(row, tuple) and len(row) == 8}
        if stations and not any(depart_city in c for c in stations):
            issues.append(f"出发站与线路城市 {depart_city} 不符")
        if stations and not any(arrive_city in c for c in stations):
            issues.append(f"到达站与线路城市 {arrive_city} 不符")
    return issues


def _check_flight_route(departure: str, destination: str) -> list[str]:
    issues: list[str] = []
    flights = flight_data.get_flight_backup(departure, destination)
    if not flights:
        return ["routes 为空"]
    seen: set[str] = set()
    for flight in flights:
        no = flight.get("flight_no")
        if no in seen:
            issues.append(f"航班号重复({no})")
        seen.add(no)
        if not _HHMM_RE.match(str(flight.get("dep_time"))):
            issues.append(f"航班 {no} dep_time 格式可疑")
        if not _HHMM_RE.match(str(flight.get("arr_time"))):
            issues.append(f"航班 {no} arr_time 格式可疑")
        economy = (flight.get("cabin") or {}).get("经济舱")
        if not _is_number(economy) or economy <= 0:
            issues.append(f"航班 {no} 经济舱价格非法")
        if _blank(flight.get("dep_airport")) or _blank(flight.get("arr_airport")):
            issues.append(f"航班 {no} 机场缺失")
    return issues


def _yield_attractions() -> Iterator[Sample]:
    for city in sorted(attraction_data._ATTRACTION_DB):
        for item in attraction_data._ATTRACTION_DB[city]:
            yield {
                "category": "attraction",
                "city": city,
                "name": item.get("name", ""),
                "expected_fields": "name/address/ticket_price/open_time/tags/features/tips/indoor",
                "auto_issues": _check_attraction(item),
            }


def _yield_restaurants() -> Iterator[Sample]:
    for city in sorted(food_data._FOOD_DB):
        for item in food_data._FOOD_DB[city]:
            yield {
                "category": "restaurant",
                "city": city,
                "name": item.get("name", ""),
                "expected_fields": "name/address/cuisine/avg_price/signature/tags/reviews/tips",
                "auto_issues": _check_restaurant(item),
            }


def _yield_hotels() -> Iterator[Sample]:
    for city in sorted(hotel_data._HOTEL_DB):
        for item in hotel_data._HOTEL_DB[city]:
            yield {
                "category": "hotel",
                "city": city,
                "name": item.get("name", ""),
                "expected_fields": "name/room_type/price/address/facilities/reviews/tips",
                "auto_issues": _check_hotel(item),
            }


def _yield_train_routes() -> Iterator[Sample]:
    for pair in sorted(train_data._PAIRS):
        depart, dest = pair.split("-", 1)
        yield {
            "category": "train_route",
            "city": depart,
            "name": pair,
            "expected_fields": "trains(code/from_station/to_station/depart_time/"
            "arrive_time/duration/second_class/first_class)",
            "auto_issues": _check_train_route(pair, list(train_data._PAIRS[pair])),
        }


def _yield_flight_routes() -> Iterator[Sample]:
    seen: set[str] = set()
    for row in flight_data._TIMES:
        departure, destination = row[0], row[1]
        pair = sorted((departure, destination))
        key = "-".join(pair)
        if key in seen:
            continue
        seen.add(key)
        yield {
            "category": "flight_route",
            "city": departure,
            "name": f"{departure}-{destination}",
            "expected_fields": "routes(flight_no/airline/dep_time/arr_time/cabin/luggage)",
            "auto_issues": _check_flight_route(departure, destination),
        }


BUILDERS: dict[str, Callable[[], Iterator[Sample]]] = {
    "attraction": _yield_attractions,
    "restaurant": _yield_restaurants,
    "hotel": _yield_hotels,
    "train_route": _yield_train_routes,
    "flight_route": _yield_flight_routes,
}


def collect_samples(per_category: int = DEFAULT_PER_CATEGORY, seed: int = DEFAULT_SEED) -> list[Sample]:
    """按品类抽样；random.seed 固定后各品类按 CATEGORIES 顺序依次抽样，结果可复现。"""
    random.seed(seed)
    samples: list[Sample] = []
    for category in CATEGORIES:
        pool = list(BUILDERS[category]())
        picked = random.sample(pool, min(per_category, len(pool)))
        samples.extend(picked)
    return samples


def summarize(samples: list[Sample]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category in CATEGORIES:
        group = [s for s in samples if s["category"] == category]
        bad = [s for s in group if s["auto_issues"]]
        rows.append(
            {
                "category": category,
                "sampled": len(group),
                "flagged": len(bad),
                "error_rate": round(len(bad) / len(group), 4) if group else 0.0,
            }
        )
    total = len(samples)
    flagged = sum(1 for s in samples if s["auto_issues"])
    rows.append(
        {
            "category": "ALL",
            "sampled": total,
            "flagged": flagged,
            "error_rate": round(flagged / total, 4) if total else 0.0,
        }
    )
    return rows


def export_csv(samples: list[Sample], path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for sample in samples:
            writer.writerow(
                {
                    "category": sample["category"],
                    "city": sample["city"],
                    "name": sample["name"],
                    "expected_fields": sample["expected_fields"],
                    "auto_issues": "；".join(sample["auto_issues"]),
                    "verify_result": "pending",
                    "verify_note": "",
                }
            )


def format_summary(rows: list[dict[str, Any]]) -> str:
    lines = ["| 品类 | 抽样数 | 自动校验命中 | 错误率 |", "| --- | --- | --- | --- |"]
    for row in rows:
        lines.append(
            f"| {row['category']} | {row['sampled']} | {row['flagged']} | {row['error_rate']:.4f} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="数据源现状基线抽样")
    parser.add_argument("--out", default=DEFAULT_OUT, help="待核对 CSV 输出路径")
    parser.add_argument("--per-category", type=int, default=DEFAULT_PER_CATEGORY)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    if args.per_category <= 0:
        parser.error("--per-category 必须为正整数")

    samples = collect_samples(per_category=args.per_category, seed=args.seed)
    if not samples:
        print("未采集到任何样本：data/ 下没有可抽样数据", file=sys.stderr)
        return 1

    export_csv(samples, args.out)
    rows = summarize(samples)
    print(f"样本已写入 {args.out}（共 {len(samples)} 条，seed={args.seed}）")
    print(format_summary(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())