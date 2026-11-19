"""四类查询结果的统一数据模型与 provider 异常。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TransportOffer(BaseModel):
    mode: Literal["train", "flight"]
    code: str
    from_station: str
    to_station: str
    depart_time: str
    arrive_time: str
    duration_min: int
    price_cny: float
    seat_class: str
    source: str
    source_url: str
    fetched_at: str
    confidence: float = Field(ge=0.0, le=1.0)


class PlaceItem(BaseModel):
    name: str
    type: str
    city: str
    address: str = ""
    lng: float | None = None
    lat: float | None = None
    open_time: str = ""
    avg_price: float | None = None
    phone: str = ""
    indoor: bool = False
    source: str
    source_url: str
    fetched_at: str
    confidence: float = Field(ge=0.0, le=1.0)


class TicketOffer(BaseModel):
    name: str
    city: str
    price_min: float
    price_max: float
    open_time: str = ""
    booking_required: bool = False
    booking_channel: str = ""
    source: str
    source_url: str
    fetched_at: str
    confidence: float = Field(ge=0.0, le=1.0)


class NoteItem(BaseModel):
    title: str
    author: str
    summary: str
    source_url: str
    fetched_at: str
    confidence: float = Field(ge=0.0, le=1.0)


class ProviderError(RuntimeError):
    """Provider 层可预期的失败基类。"""


class ProviderUnavailable(ProviderError):
    """数据源不可用：网络失败、限流、被风控拦截等。"""


class ExtractionInvalid(ProviderError):
    """抓取成功但内容无法解析为合法模型；携带原始片段便于排查。"""

    def __init__(self, message: str, raw_excerpt: str = "") -> None:
        super().__init__(message)
        self.raw_excerpt = raw_excerpt