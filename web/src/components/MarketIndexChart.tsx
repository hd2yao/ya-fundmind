import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { MarketIndexHistoryPoint } from "../api/types";

function formatValue(value: unknown) {
  return typeof value === "number"
    ? value.toLocaleString("zh-CN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    : "--";
}

function formatReturn(value: unknown) {
  return typeof value === "number" ? `${value > 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
}

function returnClass(value: unknown) {
  if (typeof value !== "number" || value === 0) return "market-chart-tooltip__neutral";
  return value > 0 ? "number-positive" : "number-negative";
}

function MarketChartTooltip({
  active,
  payload,
  label,
  seriesLabel
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: MarketIndexHistoryPoint }>;
  label?: string | number;
  seriesLabel: string;
}) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="market-chart-tooltip">
      <span>{label || point.date}</span>
      <strong>{seriesLabel}收盘 {formatValue(point.close)}</strong>
      <b className={returnClass(point.change_pct)}>当日 {formatReturn(point.change_pct)}</b>
    </div>
  );
}

export function MarketIndexChart({
  name,
  points,
  seriesLabel = "指数"
}: {
  name: string;
  points: MarketIndexHistoryPoint[];
  seriesLabel?: string;
}) {
  return (
    <>
      <div className="market-index-chart" role="img" aria-label={`${name} ${seriesLabel}日线图`}>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={points} margin={{ top: 12, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="#d7dfdc" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              minTickGap={32}
              tick={{ fontSize: 11, fill: "#5f6f6a" }}
              tickLine={false}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "#5f6f6a" }}
              tickFormatter={(value) => formatValue(value)}
              tickLine={false}
              width={72}
            />
            <Tooltip content={(props) => <MarketChartTooltip {...props} seriesLabel={seriesLabel} />} />
            <Line
              type="monotone"
              dataKey="close"
              name="收盘"
              stroke="#087c71"
              strokeWidth={2.4}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="market-index-data">
        <summary>查看{seriesLabel}日线数据</summary>
        <div className="table-wrap market-index-data__table">
          <table className="data-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>开盘</th>
                <th>最高</th>
                <th>最低</th>
                <th>收盘</th>
                <th>涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.date}>
                  <td>{point.date}</td>
                  <td>{formatValue(point.open)}</td>
                  <td>{formatValue(point.high)}</td>
                  <td>{formatValue(point.low)}</td>
                  <td>{formatValue(point.close)}</td>
                  <td className={returnClass(point.change_pct)}>{formatReturn(point.change_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
