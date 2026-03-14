import { useEffect, useState } from "react";
import { api, type UsageSummary } from "@/lib/api";
import { fmtTokens } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function UsagePanel() {
  const [data, setData] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setData(await api.usage(30));
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  if (loading) return <p className="text-muted-foreground text-center py-12">Loading...</p>;
  if (!data) return <p className="text-muted-foreground text-center py-12">Failed to load</p>;

  const maxDayCost = Math.max(...data.by_day.map((d) => d.total_cost), 0.01);

  return (
    <div className="space-y-4" data-testid="usage-panel">
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={load}>Refresh</Button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-2xl font-bold text-primary">${data.total_cost_usd.toFixed(4)}</div>
            <p className="text-xs text-muted-foreground mt-1">Total Cost ({data.days}d)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-2xl font-bold text-primary">{fmtTokens(data.total_input_tokens)}</div>
            <p className="text-xs text-muted-foreground mt-1">Input Tokens</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-2xl font-bold text-primary">{fmtTokens(data.total_output_tokens)}</div>
            <p className="text-xs text-muted-foreground mt-1">Output Tokens</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-2xl font-bold text-primary">{data.total_calls}</div>
            <p className="text-xs text-muted-foreground mt-1">API Calls</p>
          </CardContent>
        </Card>
      </div>

      {/* By layer */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">By Layer / Model</CardTitle>
        </CardHeader>
        <CardContent>
          {!data.by_layer.length ? (
            <p className="text-muted-foreground text-sm text-center py-4">No usage recorded yet</p>
          ) : (
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
                {data.by_layer.map((r, i) => (
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
          )}
        </CardContent>
      </Card>

      {/* By day */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Daily Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {!data.by_day.length ? (
            <p className="text-muted-foreground text-sm text-center py-4">No daily data yet</p>
          ) : (
            <div className="space-y-2">
              {data.by_day.map((d) => (
                <div key={d.day} className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground w-20 shrink-0">{d.day}</span>
                  <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${(d.total_cost / maxDayCost) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium w-16 text-right">
                    ${d.total_cost.toFixed(4)}
                  </span>
                  <span className="text-[10px] text-muted-foreground w-14 text-right">
                    {d.call_count} calls
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
