"""行程校验器测试：五类校验码与人群强度提示。"""

from __future__ import annotations

from dataclasses import dataclass

from core.itinerary_validator import Issue, validate_itinerary

START_DATE = "2024-11-18"  # 周一


@dataclass
class FakePlace:
    name: str
    lng: float | None = None
    lat: float | None = None
    open_time: str = ""
    booking_required: bool = False
    booked: bool = False


def _itinerary(day: int, items: list[dict], day_date: str = START_DATE) -> list[dict]:
    return [{"day": day, "date": day_date, "items": items}]


def _item(name: str, start: str, end: str, lng=None, lat=None, indoor=False) -> dict:
    return {
        "name": name,
        "start": start,
        "end": end,
        "lng": lng,
        "lat": lat,
        "indoor": indoor,
    }


def _codes(issues: list[Issue]) -> list[str]:
    return [issue.code for issue in issues]


def test_time_overlap_reported_on_day_and_time() -> None:
    itinerary = _itinerary(
        1,
        [
            _item("岳麓山", "09:00", "11:00"),
            _item("岳麓书院", "10:30", "12:00"),
        ],
    )
    issues = validate_itinerary(itinerary, [], start_date=START_DATE)

    assert _codes(issues) == ["time_overlap"]
    assert issues[0].level == "error"
    assert issues[0].day == 1
    assert issues[0].start_time == "10:30"
    assert issues[0].refs == ["岳麓山", "岳麓书院"]


def test_distance_over_threshold() -> None:
    places = [
        FakePlace(name="天安门", lng=116.397, lat=39.908),
        FakePlace(name="颐和园", lng=116.275, lat=39.999),
    ]
    itinerary = _itinerary(
        1,
        [
            _item("天安门", "09:00", "10:00", lng=116.397, lat=39.908),
            _item("颐和园", "11:00", "13:00", lng=116.275, lat=39.999),
        ],
    )
    issues = validate_itinerary(itinerary, places, start_date=START_DATE)

    assert _codes(issues) == ["distance"]
    assert issues[0].level == "warn"
    assert issues[0].refs == ["天安门", "颐和园"]


def test_distance_within_threshold_is_ignored() -> None:
    itinerary = _itinerary(
        1,
        [
            _item("甲", "09:00", "10:00", lng=116.400, lat=39.900),
            _item("乙", "11:00", "12:00", lng=116.405, lat=39.905),
        ],
    )
    assert validate_itinerary(itinerary, [], start_date=START_DATE) == []


def test_distance_skipped_without_coords() -> None:
    places = [FakePlace(name="甲"), FakePlace(name="乙")]
    itinerary = _itinerary(
        1,
        [
            _item("甲", "09:00", "10:00"),
            _item("乙", "11:00", "12:00"),
        ],
    )
    assert validate_itinerary(itinerary, places, start_date=START_DATE) == []


def test_closed_day_on_monday() -> None:
    places = [FakePlace(name="湖南博物院", open_time="09:00-17:00（周一闭馆）")]
    itinerary = _itinerary(1, [_item("湖南博物院", "10:00", "12:00")])

    issues = validate_itinerary(itinerary, places, start_date=START_DATE)

    assert _codes(issues) == ["closed_day"]
    assert issues[0].level == "error"


def test_closed_day_not_triggered_on_other_weekday() -> None:
    places = [FakePlace(name="湖南博物院", open_time="09:00-17:00（周一闭馆）")]
    itinerary = _itinerary(1, [_item("湖南博物院", "10:00", "12:00")], "2024-11-20")

    assert validate_itinerary(itinerary, places, start_date=START_DATE) == []


def test_booking_required_without_booked_flag() -> None:
    places = [FakePlace(name="故宫博物院", booking_required=True)]
    itinerary = _itinerary(1, [_item("故宫博物院", "09:00", "12:00")])

    issues = validate_itinerary(itinerary, places, start_date=START_DATE)

    assert _codes(issues) == ["booking_required"]
    assert issues[0].level == "warn"


def test_booking_satisfied_when_marked_booked() -> None:
    places = [FakePlace(name="故宫博物院", booking_required=True, booked=True)]
    itinerary = _itinerary(1, [_item("故宫博物院", "09:00", "12:00")])

    assert validate_itinerary(itinerary, places, start_date=START_DATE) == []


def test_out_of_hours() -> None:
    places = [FakePlace(name="橘子洲", open_time="09:00-17:00")]
    itinerary = _itinerary(1, [_item("橘子洲", "08:00", "10:00")])

    issues = validate_itinerary(itinerary, places, start_date=START_DATE)

    assert _codes(issues) == ["out_of_hours"]
    assert issues[0].start_time == "08:00"


def test_out_of_hours_skipped_without_open_time() -> None:
    places = [FakePlace(name="橘子洲", open_time="")]
    itinerary = _itinerary(1, [_item("橘子洲", "23:00", "23:30")])

    assert validate_itinerary(itinerary, places, start_date=START_DATE) == []


def test_crowd_intensity_only_for_non_normal_mode() -> None:
    items = [
        _item("甲", "09:00", "10:00"),
        _item("乙", "11:00", "12:00"),
        _item("丙", "14:00", "15:00"),
    ]
    itinerary = _itinerary(2, items)

    assert validate_itinerary(itinerary, [], start_date=START_DATE) == []

    issues = validate_itinerary(itinerary, [], start_date=START_DATE, crowd_mode="family")
    assert _codes(issues) == ["crowd_intensity"]
    assert issues[0].day == 2
    assert issues[0].level == "warn"
    assert issues[0].refs == ["甲", "乙", "丙"]


def test_issues_sorted_by_day_then_start_time() -> None:
    itinerary = [
        {
            "day": 2,
            "date": "2024-11-19",
            "items": [
                _item("甲", "09:00", "11:00"),
                _item("乙", "10:00", "12:00"),
            ],
        },
        {
            "day": 1,
            "date": "2024-11-18",
            "items": [
                _item("丙", "09:00", "11:00"),
                _item("丁", "09:30", "10:30"),
            ],
        },
    ]
    issues = validate_itinerary(itinerary, [], start_date=START_DATE)

    assert [(issue.day, issue.start_time) for issue in issues] == [
        (1, "09:30"),
        (2, "10:00"),
    ]