import { useEffect, useState } from "react";
import { api, type Playbook } from "@/lib/api";
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
  nascent: "outline",
  developing: "secondary",
  mature: "default",
  mastered: "default",
};

export function PlaybooksPanel() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [distilling, setDistilling] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.playbooks();
      setPlaybooks(data.playbooks);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const runDistill = async () => {
    if (!confirm("Run weekly distillation? This will call Opus (~$1-2).")) return;
    setDistilling(true);
    try {
      const result = await api.distill();
      alert(`Distillation complete: ${result.playbook_entries_updated} entries updated`);
      load();
    } catch (e) {
      alert(`Failed: ${e}`);
    }
    setDistilling(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <span className="text-sm text-muted-foreground">{playbooks.length} entries</span>
        <div className="flex gap-2">
          <Button variant="default" size="sm" onClick={runDistill} disabled={distilling}>
            {distilling ? "Running..." : "Run Distill"}
          </Button>
          <Button variant="outline" size="sm" onClick={load}>
            Refresh
          </Button>
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
                  <CardTitle className="text-sm">{p.name}</CardTitle>
                  <Badge variant={maturityVariant[p.maturity] ?? "outline"}>{p.maturity}</Badge>
                </div>
                <CardDescription>{p.context}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm mb-3">{parseAction(p.action)}</p>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {(p.confidence * 100).toFixed(0)}%
                  </span>
                  <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${p.confidence * 100}%` }}
                    />
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
