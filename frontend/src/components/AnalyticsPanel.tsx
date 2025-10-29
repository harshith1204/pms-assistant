import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  ResponsiveContainer,
  BarChart,
  LineChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Line,
  Bar,
} from "recharts";

export type AnalyticsPayload = {
  timestamp: string;
  query?: string;
  summary?: string;
  kpis?: Array<{ label: string; value: number | string; delta?: string; icon?: string }>;
  visualization?: {
    format: "recharts";
    chart: { type: "bar" | "line" };
    xKey: string;
    yKey: string;
    data: Array<Record<string, any>>;
  } | null;
  raw_data?: any[] | null;
  meta?: Record<string, any>;
};

function formatNumber(val: number | string) {
  if (typeof val === "number") return new Intl.NumberFormat().format(val);
  return String(val);
}

export function AnalyticsPanel({ payload, className }: { payload: AnalyticsPayload; className?: string }) {
  const viz = payload.visualization;
  const kpis = payload.kpis || [];

  return (
    <div className={cn("w-full", className)}>
      {(payload.summary || kpis.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 mb-3">
          {kpis.slice(0, 4).map((k, idx) => (
            <Card key={`${k.label}-${idx}`} className="border-border/60">
              <CardContent className="p-3">
                <div className="text-xs text-muted-foreground">{k.label}</div>
                <div className="text-xl font-semibold">{k.icon ? `${k.icon} ` : ""}{formatNumber(k.value)}</div>
                {k.delta && <div className="text-xs text-muted-foreground">{k.delta}</div>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {viz?.format === "recharts" && viz?.chart?.type === "bar" && (
        <div className="h-[280px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={viz.data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={viz.xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey={viz.yKey} name="Count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {viz?.format === "recharts" && viz?.chart?.type === "line" && (
        <div className="h-[280px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={viz.data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={viz.xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey={viz.yKey} name="Count" stroke="#8b5cf6" dot={true} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default AnalyticsPanel;
