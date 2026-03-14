import { useEffect, useState } from "react";
import { api, type OsEvent } from "@/lib/api";
import { timeAgo, fmtTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/Pagination";

const PAGE_SIZE = 50;

const SOURCE_LABELS: Record<string, string> = {
  zsh: "Terminal",
  bash: "Terminal",
  powershell: "PowerShell",
  chrome: "Chrome",
  safari: "Safari",
  edge: "Edge",
};

const TYPE_COLORS: Record<string, "default" | "secondary" | "outline"> = {
  shell_command: "default",
  browser_url: "secondary",
};

export function OsEventsPanel() {
  const [events, setEvents] = useState<OsEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState("");

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const load = async (p: number, eventType = filter) => {
    setLoading(true);
    try {
      const data = await api.osEvents(PAGE_SIZE, (p - 1) * PAGE_SIZE, eventType);
      setEvents(data.events ?? []);
      setTotal(data.total ?? 0);
      setPage(p);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { load(1); }, []);

  const setFilterAndLoad = (f: string) => {
    setFilter(f);
    load(1, f);
  };

  return (
    <div className="space-y-4 pb-16" data-testid="os-events-panel">
      <div className="flex justify-between items-center gap-2">
        <div className="flex gap-1">
          <Button
            variant={filter === "" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilterAndLoad("")}
          >
            All
          </Button>
          <Button
            variant={filter === "shell_command" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilterAndLoad("shell_command")}
          >
            Commands
          </Button>
          <Button
            variant={filter === "browser_url" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilterAndLoad("browser_url")}
          >
            URLs
          </Button>
        </div>
        <Button variant="outline" size="sm" onClick={() => load(1)}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <p className="text-muted-foreground text-center py-12">Loading...</p>
      ) : !events.length ? (
        <div className="text-muted-foreground text-center py-12">
          <p>No OS events captured yet</p>
          <p className="text-xs mt-2">Shell commands and browser URLs will appear here</p>
        </div>
      ) : (
        <div className="space-y-1">
          {events.map((e) => (
            <Card key={e.id} data-testid="os-event-card">
              <CardContent className="p-2 px-3">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground shrink-0 w-32">
                    {fmtTime(e.timestamp)}
                  </span>
                  <span className="text-[10px] text-muted-foreground/60 shrink-0 w-16">
                    {timeAgo(e.timestamp)}
                  </span>
                  <Badge variant={TYPE_COLORS[e.event_type] || "outline"} className="shrink-0 text-[10px]">
                    {SOURCE_LABELS[e.source] || e.source}
                  </Badge>
                  <span className="text-xs text-foreground/80 font-mono truncate flex-1">
                    {e.data}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="fixed bottom-0 left-0 right-0 bg-background/80 backdrop-blur-sm border-t py-2 flex justify-center z-50">
        <Pagination page={page} totalPages={totalPages} onPageChange={load} />
      </div>
    </div>
  );
}
