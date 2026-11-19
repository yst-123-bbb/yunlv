import { init } from "echarts";
import type { ECharts, EChartsOption } from "echarts";
import { useEffect, useRef } from "react";
import type { RefObject } from "react";

/**
 * 把 ECharts 实例绑定到 ref 指向的容器：挂载时 init，卸载时 dispose，
 * 容器尺寸变化时 resize。option 变化只做 setOption，不重建实例。
 */
export function useEcharts(
  ref: RefObject<HTMLDivElement | null>,
  option: EChartsOption,
): void {
  const chartRef = useRef<ECharts | null>(null);

  useEffect(() => {
    const container = ref.current;
    if (!container) {
      return;
    }
    const chart = init(container);
    chartRef.current = chart;

    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(container);

    return () => {
      window.removeEventListener("resize", resize);
      observer?.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, [ref]);

  // 天数变化会让 series 数量增减，因此以 notMerge 方式整体替换 option，避免残留旧序列
  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);
}