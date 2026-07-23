import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { FundHistoryPoint } from "../api/types";

function formatNav(value: unknown) {
  return typeof value === "number" ? value.toFixed(4) : "--";
}

export function FundNavChart({
  code,
  points
}: {
  code: string;
  points: FundHistoryPoint[];
}) {
  return (
    <>
      <div className="fund-nav-chart" role="img" aria-label={`${code} 历史净值曲线`}>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={points} margin={{ top: 12, right: 10, bottom: 4, left: 2 }}>
            <CartesianGrid stroke="#d7dfdc" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              minTickGap={28}
              tick={{ fontSize: 11, fill: "#5f6f6a" }}
              tickLine={false}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "#5f6f6a" }}
              tickFormatter={(value) => formatNav(value)}
              tickLine={false}
              width={52}
            />
            <Tooltip
              formatter={(value) => [formatNav(value), "单位净值"]}
              labelFormatter={(label) => `日期 ${label}`}
            />
            <Line
              type="monotone"
              dataKey="unit_nav"
              name="单位净值"
              stroke="#087c71"
              strokeWidth={2.25}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="fund-nav-data">
        <summary>查看净值数据表</summary>
        <div className="table-shell fund-nav-data__table">
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>单位净值</th>
                <th>累计净值</th>
                <th>日增长率</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.date}>
                  <td>{point.date}</td>
                  <td>{formatNav(point.unit_nav)}</td>
                  <td>{formatNav(point.accumulated_nav)}</td>
                  <td>{typeof point.daily_return === "number" ? `${point.daily_return.toFixed(2)}%` : "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
