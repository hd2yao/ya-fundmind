import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function TrendChart({
  data
}: {
  data: Array<{ as_of?: string; warning_count?: number; insufficient_sample_theme_count?: number }>;
}) {
  return (
    <div className="chart-frame" aria-label="数据质量趋势图">
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 10, right: 12, bottom: 4, left: -20 }}>
          <CartesianGrid stroke="#d7dfdc" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="as_of" tick={{ fontSize: 11, fill: "#5f6f6a" }} minTickGap={24} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#5f6f6a" }} />
          <Tooltip />
          <Line type="monotone" dataKey="warning_count" name="warning" stroke="#9a5a00" strokeWidth={2} dot={false} />
          <Line
            type="monotone"
            dataKey="insufficient_sample_theme_count"
            name="样本不足主题"
            stroke="#285f9e"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
