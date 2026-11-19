import * as echarts from "echarts";
import type { EffectScatterSeriesOption, EChartsOption, LinesSeriesOption } from "echarts";
import { useEffect, useMemo, useRef, useState } from "react";

import { useEcharts } from "../hooks/useEcharts";

const CHINA_GEO_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json";
const MAP_NAME = "china";
const CHART_HEIGHT = 420;
const DAY_COLORS = [
  "#5b8ff9",
  "#f6bd16",
  "#5ad8a6",
  "#e8684a",
  "#6dc8ec",
  "#9270ca",
  "#ff9d4d",
];

let chinaMapPromise: Promise<void> | null = null;

function ensureChinaMap(): Promise<void> {
  if (!chinaMapPromise) {
    chinaMapPromise = fetch(CHINA_GEO_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`geo_http_${response.status}`);
        }
        return response.json();
      })
      .then((geoJson) => {
        echarts.registerMap(MAP_NAME, geoJson);
      })
      .catch((error: unknown) => {
        chinaMapPromise = null;
        throw error;
      });
  }
  return chinaMapPromise;
}

export interface ItineraryStop {
  name: string;
  start?: string;
  end?: string;
  lng?: number | null;
  lat?: number | null;
  indoor?: boolean;
}

export interface ItineraryDay {
  day: number;
  date: string;
  items: ItineraryStop[];
}

interface TimelineMapProps {
  itinerary: ItineraryDay[];
}

interface GeoStop {
  name: string;
  order: number;
  start: string;
  end: string;
  lng: number;
  lat: number;
}

function toMinutes(hhmm: string | undefined): number | null {
  const matched = /^(\d{1,2}):(\d{2})$/.exec(hhmm ?? "");
  if (!matched) {
    return null;
  }
  const hours = Number(matched[1]);
  const minutes = Number(matched[2]);
  if (hours > 23 || minutes > 59) {
    return null;
  }
  return hours * 60 + minutes;
}

/** 上一站结束到下一站开始的移动耗时（分钟），跨零点或时间不合法时返回 null */
function travelMinutes(previousEnd: string, nextStart: string): number | null {
  const end = toMinutes(previousEnd);
  const start = toMinutes(nextStart);
  if (end === null || start === null || start < end) {
    return null;
  }
  return start - end;
}

function geoStops(day: ItineraryDay): GeoStop[] {
  const stops: GeoStop[] = [];
  for (const stop of day.items) {
    if (typeof stop.lng !== "number" || typeof stop.lat !== "number") {
      continue;
    }
    stops.push({
      name: stop.name,
      order: stops.length + 1,
      start: stop.start ?? "",
      end: stop.end ?? "",
      lng: stop.lng,
      lat: stop.lat,
    });
  }
  return stops;
}

function buildOption(itinerary: ItineraryDay[]): EChartsOption {
  const series: (LinesSeriesOption | EffectScatterSeriesOption)[] = [];

  itinerary.forEach((day, dayIndex) => {
    const stops = geoStops(day);
    if (stops.length === 0) {
      return;
    }
    const color = DAY_COLORS[dayIndex % DAY_COLORS.length];

    series.push({
      name: `第${day.day}天站点`,
      type: "effectScatter",
      coordinateSystem: "geo",
      rippleEffect: { brushType: "stroke", scale: 3 },
      symbolSize: 9,
      itemStyle: { color },
      label: {
        show: true,
        position: "right",
        formatter: (params) => {
          const order = Array.isArray(params.value) ? params.value[2] : "";
          return `${order}. ${params.name}`;
        },
        fontSize: 11,
      },
      data: stops.map((stop) => ({
        name: stop.name,
        value: [stop.lng, stop.lat, stop.order],
      })),
    });

    const segments = stops.slice(1).map((stop, index) => {
      const previous = stops[index];
      return {
        coords: [
          [previous.lng, previous.lat],
          [stop.lng, stop.lat],
        ],
        value: travelMinutes(previous.end, stop.start) ?? 0,
        name: `${previous.name} → ${stop.name}`,
      };
    });
    if (segments.length === 0) {
      return;
    }

    series.push({
      name: `第${day.day}天路线`,
      type: "lines",
      coordinateSystem: "geo",
      polyline: false,
      lineStyle: { color, width: 1.5, opacity: 0.7, curveness: 0.2 },
      label: {
        show: true,
        position: "middle",
        formatter: (params) => {
          const minutes = Number(params.value);
          return Number.isFinite(minutes) && minutes > 0 ? `${minutes}分钟` : "";
        },
        fontSize: 11,
      },
      data: segments,
    });
  });

  return {
    tooltip: { trigger: "item" },
    geo: {
      map: MAP_NAME,
      roam: true,
      scaleLimit: { min: 1, max: 8 },
      itemStyle: { areaColor: "#f2f5fa", borderColor: "#c9d3e0" },
      emphasis: { itemStyle: { areaColor: "#dfe8f5" }, label: { show: false } },
    },
    series,
  };
}

function MapCanvas({ option }: { option: EChartsOption }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  useEcharts(containerRef, option);
  return (
    <div
      ref={containerRef}
      className="timelineMap__chart"
      style={{ width: "100%", height: CHART_HEIGHT }}
    />
  );
}

export function TimelineMap({ itinerary }: TimelineMapProps) {
  const [mapState, setMapState] = useState<"loading" | "ready" | "unavailable">("loading");
  const option = useMemo(() => buildOption(itinerary), [itinerary]);

  useEffect(() => {
    let cancelled = false;
    ensureChinaMap()
      .then(() => {
        if (!cancelled) {
          setMapState("ready");
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        // 地图数据拉取失败只降级为时间轴列表，不影响页面其余部分
        console.warn("地图数据加载失败，降级为时间轴列表", error);
        setMapState("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="timelineMap">
      {mapState === "ready" ? <MapCanvas option={option} /> : null}
      {mapState === "loading" ? <p className="timelineMap__hint">地图加载中…</p> : null}
      {mapState === "unavailable" ? (
        <p className="timelineMap__hint">地图数据不可用，已降级为时间轴视图。</p>
      ) : null}

      {itinerary.length === 0 ? (
        <p className="timelineMap__hint">暂无行程</p>
      ) : (
        <ol className="timelineMap__days">
          {itinerary.map((day) => (
            <li key={day.day} className="timelineMap__day">
              <h3 className="timelineMap__dayTitle">
                第{day.day}天 · {day.date}
              </h3>
              <ul className="timelineMap__stops">
                {day.items.map((stop, index) => (
                  <li key={`${day.day}-${index}-${stop.name}`} className="timelineMap__stop">
                    <span className="timelineMap__time">
                      {stop.start ?? "--"}–{stop.end ?? "--"}
                    </span>
                    <span className="timelineMap__name">{stop.name}</span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export default TimelineMap;