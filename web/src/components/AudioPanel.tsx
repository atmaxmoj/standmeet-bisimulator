import { useEffect, useState } from "react";
import { api, type AudioFrame } from "@/lib/api";
import { timeAgo, fmtTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const PAGE_SIZE = 30;

export function AudioPanel() {
  const [frames, setFrames] = useState<AudioFrame[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const load = async (p: number) => {
    setLoading(true);
    try {
      const data = await api.audio(PAGE_SIZE, (p - 1) * PAGE_SIZE);
      setFrames(data.audio ?? []);
      setHasMore((data.audio ?? []).length === PAGE_SIZE);
      setPage(p);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { load(1); }, []);

  return (
    <div className="space-y-4" data-testid="audio-panel">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground" data-testid="page-indicator">Page {page}</span>
          <Button variant="outline" size="sm" onClick={() => load(page - 1)} disabled={page <= 1}>
            Prev
          </Button>
          <Button variant="outline" size="sm" onClick={() => load(page + 1)} disabled={!hasMore}>
            Next
          </Button>
        </div>
        <Button variant="outline" size="sm" onClick={() => load(1)}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <p className="text-muted-foreground text-center py-12">Loading...</p>
      ) : !frames.length ? (
        <div className="text-muted-foreground text-center py-12">
          <p>No audio transcriptions yet</p>
          <p className="text-xs mt-2">First chunk arrives after 5 minutes of recording</p>
        </div>
      ) : (
        <div className="space-y-2">
          {frames.map((a) => (
            <Card key={a.id} data-testid="audio-card">
              <CardContent className="p-3">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xs text-muted-foreground">{fmtTime(a.timestamp)}</span>
                  <span className="text-[10px] text-muted-foreground/60">{timeAgo(a.timestamp)}</span>
                  <Badge variant="outline">{a.language || "?"}</Badge>
                  <span className="text-[10px] text-muted-foreground">{a.duration_seconds.toFixed(0)}s</span>
                </div>
                <p className="text-sm text-foreground/80 whitespace-pre-wrap">{a.text}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
