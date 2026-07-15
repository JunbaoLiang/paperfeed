"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DailyMetric } from "@/lib/types";
import { shortDay, useChartColors } from "@/components/stats/chart-theme";
import { ChartTip, LegendRow } from "@/components/stats/ChartBits";

const CHART_HEIGHT = 230;

const AXIS_TICK_STYLE = {
  fontSize: 10,
  fontFamily: "var(--font-plex-mono), ui-monospace, monospace",
} as const;

interface ChartProps {
  daily: DailyMetric[]; // ascending by day
}

/** (a) CTR over the last 90 days — single series, headline in card header. */
export function CtrChart({ daily }: ChartProps) {
  const colors = useChartColors();
  const rows = daily.map((d) => ({
    day: shortDay(d.day),
    ctr: Math.round(d.ctr * 1000) / 10, // percent, 1 decimal
  }));

  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <LineChart data={rows} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
        <CartesianGrid stroke={colors.grid} strokeWidth={1} vertical={false} />
        <XAxis
          dataKey="day"
          tick={{ ...AXIS_TICK_STYLE, fill: colors.axis }}
          tickLine={false}
          axisLine={{ stroke: colors.grid }}
          minTickGap={36}
        />
        <YAxis
          tick={{ ...AXIS_TICK_STYLE, fill: colors.axis }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v}%`}
          width={44}
        />
        <Tooltip
          cursor={{ stroke: colors.grid, strokeWidth: 1 }}
          content={(props) => (
            <ChartTip {...props} format={(v) => `${v.toFixed(1)}%`} />
          )}
        />
        <Line
          type="monotone"
          dataKey="ctr"
          name="CTR"
          stroke={colors.series2}
          strokeWidth={2}
          strokeLinecap="round"
          dot={false}
          isAnimationActive={false}
          activeDot={{ r: 4.5, strokeWidth: 2, stroke: colors.surface }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/**
 * (b) Impressions / clicks / saves — grouped bars.
 * Windowed to the most recent days so grouped bars stay readable
 * (90 days × 3 series would be sub-pixel); the 90-day trend lives in
 * the CTR chart above.
 */
export function EngagementChart({
  daily,
  windowDays = 14,
}: ChartProps & { windowDays?: number }) {
  const colors = useChartColors();
  const rows = daily.slice(-windowDays).map((d) => ({
    day: shortDay(d.day),
    impressions: d.impressions,
    clicks: d.clicks,
    saves: d.saves,
  }));

  return (
    <div>
      <LegendRow
        entries={[
          { label: "曝光 impressions", color: colors.series1 },
          { label: "点击 clicks", color: colors.series2 },
          { label: "收藏 saves", color: colors.series3 },
        ]}
      />
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart
          data={rows}
          margin={{ top: 8, right: 12, left: -14, bottom: 0 }}
          barGap={2}
          barCategoryGap="22%"
        >
          <CartesianGrid stroke={colors.grid} strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="day"
            tick={{ ...AXIS_TICK_STYLE, fill: colors.axis }}
            tickLine={false}
            axisLine={{ stroke: colors.grid }}
            minTickGap={24}
          />
          <YAxis
            tick={{ ...AXIS_TICK_STYLE, fill: colors.axis }}
            tickLine={false}
            axisLine={false}
            width={44}
            tickFormatter={(v: number) => v.toLocaleString()}
          />
          <Tooltip
            cursor={{ fill: `${colors.grid}55` }}
            content={(props) => <ChartTip {...props} />}
          />
          <Bar
            dataKey="impressions"
            name="曝光"
            fill={colors.series1}
            radius={[3, 3, 0, 0]}
            maxBarSize={14}
            isAnimationActive={false}
          />
          <Bar
            dataKey="clicks"
            name="点击"
            fill={colors.series2}
            radius={[3, 3, 0, 0]}
            maxBarSize={14}
            isAnimationActive={false}
          />
          <Bar
            dataKey="saves"
            name="收藏"
            fill={colors.series3}
            radius={[3, 3, 0, 0]}
            maxBarSize={14}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** (c) Profile drift — cosine distance of today's profile vs 30 days ago. */
export function DriftChart({ daily }: ChartProps) {
  const colors = useChartColors();
  const rows = daily.map((d) => ({
    day: shortDay(d.day),
    drift:
      typeof d.profile_drift === "number"
        ? Math.round(d.profile_drift * 1000) / 1000
        : null,
  }));
  const hasAny = rows.some((r) => r.drift !== null);

  if (!hasAny) {
    return (
      <div className="flex h-[230px] items-center justify-center rounded-md border border-dashed border-line-strong">
        <p className="px-6 text-center font-data text-[11px] text-ink-faint">
          画像 drift 需要至少 30 天的画像历史 — 数据积累中
        </p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <LineChart data={rows} margin={{ top: 8, right: 12, left: -4, bottom: 0 }}>
        <CartesianGrid stroke={colors.grid} strokeWidth={1} vertical={false} />
        <XAxis
          dataKey="day"
          tick={{ ...AXIS_TICK_STYLE, fill: colors.axis }}
          tickLine={false}
          axisLine={{ stroke: colors.grid }}
          minTickGap={36}
        />
        <YAxis
          tick={{ ...AXIS_TICK_STYLE, fill: colors.axis }}
          tickLine={false}
          axisLine={false}
          width={44}
          domain={[0, "auto"]}
          tickFormatter={(v: number) => v.toFixed(2)}
        />
        <Tooltip
          cursor={{ stroke: colors.grid, strokeWidth: 1 }}
          content={(props) => (
            <ChartTip {...props} format={(v) => v.toFixed(3)} />
          )}
        />
        <Line
          type="monotone"
          dataKey="drift"
          name="profile drift"
          stroke={colors.series1}
          strokeWidth={2}
          strokeLinecap="round"
          dot={false}
          connectNulls
          isAnimationActive={false}
          activeDot={{ r: 4.5, strokeWidth: 2, stroke: colors.surface }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
