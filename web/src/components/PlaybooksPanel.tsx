import { useEffect, useState } from "react";
import { api, type Playbook } from "@/lib/api";
import { useSelection } from "@/hooks/useSelection";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

function parseAction(raw: string): string {
  try {
    const parsed = JSON.parse(raw);
    return parsed.action || raw;
  } catch {
    return raw;
  }
}

const maturityVariant: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  nascent: "outline", developing: "secondary", mature: "default", mastered: "default",
};

export function PlaybooksPanel() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [distilling, setDistilling] = useState(false);

  const load = async () => {
    setLoading(true);
    try { setPlaybooks((await api.playbooks()).playbooks); } catch (e) { console.error(e); }
    setLoading(false);
  };

  const sel = useSelection("playbook_entries", load);

  const runDistill = async () => {
    if (!confirm("Run daily distillation? This will call Opus.")) return;
    setDistilling(true);
    try {
      const result = await api.distill();
      alert(`Distillation complete: ${result.playbook_entries_updated} entries updated`);
      load();
    } catch (e) { alert(`Failed: ${e}`); }
    setDistilling(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4" data-testid="playbooks-panel">
      <div className="flex justify-between items-center">
        <div className="flex gap-2 items-center">
          <input type="checkbox" checked={playbooks.length > 0 && playbooks.every((p) => sel.selected.has(p.id))}
            onChange={() => sel.toggleAll(playbooks.map((p) => p.id))} />
          {sel.selected.size > 0 && (
            <Button variant="destructive" size="sm" onClick={sel.deleteSelected} disabled={sel.deleting}>
              Delete {sel.selected.size}
            </Button>
          )}
          <span className="text-sm text-muted-foreground" data-testid="entries-count">{playbooks.length} entries</span>
        </div>
        <div className="flex gap-2">
          <Button variant="default" size="sm" onClick={runDistill} disabled={distilling}>
            {distilling ? "Running..." : "Run Distill"}
          </Button>
          <Button variant="outline" size="sm" onClick={load}>Refresh</Button>
        </div>
      </div>

      {loading ? (
        <p className="text-muted-foreground text-center py-12">Loading...</p>
      ) : !playbooks.length ? (
        <div className="text-muted-foreground text-center py-12">
          <p>No playbook entries yet</p>
          <p className="text-xs mt-2">Run distill after accumulating some episodes</p>
        </div>
      ) : (
        <div className="space-y-3">
          {playbooks.map((p) => (
            <Card key={p.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <input type="checkbox" checked={sel.selected.has(p.id)} onChange={() => sel.toggle(p.id)} />
                  <CardTitle className="text-sm">{p.name}</CardTitle>
                  <Badge variant={maturityVariant[p.maturity] ?? "outline"}>{p.maturity}</Badge>
                </div>
                <CardDescription className="pl-6">{p.context}</CardDescription>
              </CardHeader>
              <CardContent className="pl-9">
                <p className="text-sm mb-3">{parseAction(p.action)}</p>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">{(p.confidence * 100).toFixed(0)}%</span>
                  <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${p.confidence * 100}%` }} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
