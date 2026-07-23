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
            <Tooltip
              formatter={(value) => [formatValue(value), "收盘"]}
              labelFormatter={(label) => `日期 ${label}`}
            />
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
                  <td>{typeof point.change_pct === "number" ? `${point.change_pct.toFixed(2)}%` : "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
