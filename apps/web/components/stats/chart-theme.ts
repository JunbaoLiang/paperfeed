"use client";

import { useSyncExternalStore } from "react";

/**
 * Chart palette — validated with the six-checks palette validator against
 * both chart surfaces (light #fffefa, dark #1d1913):
 *   light: #2e6fc0 / #b02c1c / #c98500  (worst adjacent CVD ΔE 28.0)
 *   dark:  #3987e5 / #e0664c / #c98500  (worst adjacent CVD ΔE 23.8)
 * Fixed slot order: 1=impressions(blue) 2=clicks(vermilion) 3=saves(amber).
 */
export interface ChartColors {
  series1: string;
  series2: string;
  series3: string;
  grid: string;
  axis: string;
  surface: string;
  ink: string;
}

const LIGHT: ChartColors = {
  series1: "#2e6fc0",
  series2: "#b02c1c",
  series3: "#c98500",
  grid: "#e3dccd",
  axis: "#a99f8d",
  surface: "#fffefa",
  ink: "#211c15",
};

const DARK: ChartColors = {
  series1: "#3987e5",
  series2: "#e0664c",
  series3: "#c98500",
  grid: "#322b1f",
  axis: "#6e6552",
  surface: "#1d1913",
  ink: "#ece4d4",
};

const QUERY = "(prefers-color-scheme: dark)";

function subscribe(onChange: () => void): () => void {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

const getSnapshot = () => window.matchMedia(QUERY).matches;
const getServerSnapshot = () => false;

/** Dark mode gets its own validated steps — not an automatic flip. */
export function useChartColors(): ChartColors {
  const dark = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return dark ? DARK : LIGHT;
}

/** "2026-07-01" → "07-01" for axis ticks. */
export function shortDay(day: string): string {
  return day.slice(5);
}
