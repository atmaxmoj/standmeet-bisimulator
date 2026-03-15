import { useEffect, useState } from "react";
import { api, type UsageSummary } from "@/lib/api";
import { fmtTokens } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <Card>
      <CardContent className="pt-6 text-center">
        <div className="text-2xl font-bold text-primary">{value}</div>
        <p className="text-xs text-muted-foreground mt-1">{label}</p>
      </CardContent>
    </Card>
  );
}

function LayerTable({ rows }: { rows: UsageSummary["by_layer"] }) {
  if (!rows.length) return <p className="text-muted-foreground text-sm text-center py-4">No usage recorded yet</p>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Layer</TableHead>
          <TableHead>Model</TableHead>
          <TableHead className="text-right">Calls</TableHead>
          <TableHead className="text-right">Input</TableHead>
          <TableHead className="text-right">Output</TableHead>
          <TableHead className="text-right">Cost</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => (
          <TableRow key={i}>
            <TableCell>{r.layer}</TableCell>
            <TableCell className="text-muted-foreground">{r.model}</TableCell>
            <TableCell className="text-right">{r.call_count}</TableCell>
            <TableCell className="text-right">{fmtTokens(r.total_input)}</TableCell>
            <TableCell className="text-right">{fmtTokens(r.total_output)}</TableCell>
            <TableCell className="text-right font-medium">${r.total_cost.toFixed(4)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function DailyChart({ days }: { days: UsageSummary["by_day"] }) {
  if (!days.length) return <p className="text-muted-foreground text-sm text-center py-4">No daily data yet</p>;
  const maxCost = Math.max(...days.map((d) => d.total_cost), 0.01);
  return (
    <div className="space-y-2">
      {days.map((d) => (
        <div key={d.day} className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground w-20 shrink-0">{d.day}</span>
          <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${(d.total_cost / maxCost) * 100}%` }} />
          </div>
          <span className="text-xs font-medium w-16 text-right">${d.total_cost.toFixed(4)}</span>
          <span className="text-[10px] text-muted-foreground w-14 text-right">{d.call_count} calls</span>
        </div>
      ))}
    </div>
  );
}

export function UsagePanel() {
  const [data, setData] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try { setData(await api.usage(30)); } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  if (loading) return <p className="text-muted-foreground text-center py-12">Loading...</p>;
  if (!data) return <p className="text-muted-foreground text-center py-12">Failed to load</p>;

  return (
    <div className="space-y-4" data-testid="usage-panel">
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={load}>Refresh</Button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard value={`$${data.total_cost_usd.toFixed(4)}`} label={`Total Cost (${data.days}d)`} />
        <StatCard value={fmtTokens(data.total_input_tokens)} label="Input Tokens" />
        <StatCard value={fmtTokens(data.total_output_tokens)} label="Output Tokens" />
        <StatCard value={String(data.total_calls)} label="API Calls" />
      </div>
      <Card>
        <CardHeader><CardTitle className="text-sm">By Layer / Model</CardTitle></CardHeader>
        <CardContent><LayerTable rows={data.by_layer} /></CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-sm">Daily Breakdown</CardTitle></CardHeader>
        <CardContent><DailyChart days={data.by_day} /></CardContent>
      </Card>
    </div>
  );
}
