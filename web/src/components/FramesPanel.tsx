import { useCallback, useEffect, useState } from "react";
import { api, frameImageUrl, type Frame } from "@/lib/api";
import { timeAgo, fmtTime } from "@/lib/utils";
import { useSelection } from "@/hooks/useSelection";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/Pagination";

const PAGE_SIZE = 30;

function FrameCard({ frame, expanded, checked, onToggle, onCheck }: {
  frame: Frame; expanded: boolean; checked: boolean; onToggle: () => void; onCheck: () => void;
}) {
  return (
    <Card className="cursor-pointer hover:bg-accent/50 transition-colors" onClick={onToggle} data-testid="frame-card">
      <CardContent className="p-3">
        <div className="flex items-start gap-3">
          <input type="checkbox" checked={checked} onChange={onCheck} onClick={(e) => e.stopPropagation()} className="mt-1 shrink-0" />
          <div className="shrink-0 w-40">
            <div className="text-xs text-muted-foreground">{fmtTime(frame.timestamp)}</div>
            <div className="text-[10px] text-muted-foreground/60">{timeAgo(frame.timestamp)}</div>
          </div>
          <div className="shrink-0 w-36">
            <div className="text-xs font-medium text-primary truncate">{frame.app_name}</div>
            <div className="text-[10px] text-muted-foreground truncate">{frame.window_name}</div>
            <Badge variant="secondary" className="mt-1 text-[10px]">display {frame.display_id}</Badge>
          </div>
          <div className={`text-xs text-foreground/80 whitespace-pre-wrap break-words flex-1 ${expanded ? "" : "max-h-12 overflow-hidden"}`}>
            {frame.text}
          </div>
        </div>
        {expanded && frame.image_path && (
          <img src={frameImageUrl(frame.id)} alt={`Screenshot ${frame.id}`} className="mt-2 w-full rounded border" loading="lazy" />
        )}
      </CardContent>
    </Card>
  );
}

export function FramesPanel() {
  const [frames, setFrames] = useState<Frame[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const load = useCallback(async (p?: number) => {
    const target = p ?? page;
    setLoading(true);
    try {
      const data = await api.frames(PAGE_SIZE, (target - 1) * PAGE_SIZE);
      setFrames(data.frames);
      setTotal(data.total ?? 0);
      setPage(target);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [page]);

  const sel = useSelection("frames", () => load());
  useEffect(() => { load(1); }, [load]);

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-4 pb-16" data-testid="frames-panel">
      <div className="flex justify-between">
        <div className="flex gap-2">
          <input type="checkbox" checked={frames.length > 0 && frames.every((f) => sel.selected.has(f.id))}
            onChange={() => sel.toggleAll(frames.map((f) => f.id))} />
          {sel.selected.size > 0 && (
            <Button variant="destructive" size="sm" onClick={sel.deleteSelected} disabled={sel.deleting}>
              Delete {sel.selected.size}
            </Button>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={() => load(1)}>Refresh</Button>
      </div>
      {loading ? (
        <p className="text-muted-foreground text-center py-12">Loading...</p>
      ) : !frames.length ? (
        <p className="text-muted-foreground text-center py-12">No frames captured yet</p>
      ) : (
        <div className="space-y-2">
          {frames.map((f) => (
            <FrameCard key={f.id} frame={f} expanded={expandedIds.has(f.id)}
              checked={sel.selected.has(f.id)} onToggle={() => toggleExpand(f.id)} onCheck={() => sel.toggle(f.id)} />
          ))}
        </div>
      )}
      <div className="fixed bottom-0 left-0 right-0 bg-background/80 backdrop-blur-sm border-t py-2 flex justify-center z-50">
        <Pagination page={page} totalPages={totalPages} onPageChange={load} />
      </div>
    </div>
  );
}
