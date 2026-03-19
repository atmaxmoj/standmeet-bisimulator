import { useState, useEffect, useMemo, type ComponentType } from "react";
import { Button } from "@/components/ui/button";
import { EpisodesPanel } from "@/components/EpisodesPanel";
import { PlaybooksPanel } from "@/components/PlaybooksPanel";
import { RoutinesPanel } from "@/components/RoutinesPanel";
import { UsagePanel } from "@/components/UsagePanel";
import { LogsPanel } from "@/components/LogsPanel";
import { ManagePanel } from "@/components/ManagePanel";
import { SourceDataPanel } from "@/components/SourceDataPanel";
import { api, type SourceManifest } from "@/lib/api";

const staticPanels: Record<string, ComponentType> = {
  episodes: EpisodesPanel,
  playbooks: PlaybooksPanel,
  routines: RoutinesPanel,
  usage: UsagePanel,
  logs: LogsPanel,
  chat: ManagePanel,
};

const memorySidebarItems = [
  { key: "episodes", label: "Episodes" },
  { key: "playbooks", label: "Playbooks" },
  { key: "routines", label: "Routines" },
];

const systemSidebarItems = [
  { key: "usage", label: "Usage" },
  { key: "logs", label: "Logs" },
  { key: "chat", label: "Manage" },
];

function PipelineToggle({ online, captureAlive, paused, toggling, onToggle }: {
  online: boolean; captureAlive: boolean; paused: boolean; toggling: boolean; onToggle: () => void;
}) {
  return (
    <div className="flex items-center gap-2" data-testid="pipeline-toggle">
      <span className={`w-2 h-2 rounded-full ${captureAlive ? "bg-green-500" : online ? "bg-yellow-500" : "bg-red-500"}`} />
      <button
        onClick={onToggle}
        disabled={toggling}
        className="relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        style={{ backgroundColor: paused ? "hsl(var(--muted))" : "hsl(var(--primary))" }}
        role="switch"
        aria-checked={!paused}
        data-testid="pipeline-switch"
      >
        <span className={`pointer-events-none block h-3.5 w-3.5 rounded-full bg-background shadow-sm ring-0 transition-transform ${paused ? "translate-x-0.5" : "translate-x-[18px]"}`} />
      </button>
      <span className="text-xs">{paused ? "Paused" : "Recording"}</span>
    </div>
  );
}

function Header() {
  const [status, setStatus] = useState({
    online: false, episodes: 0, playbooks: 0, routines: 0, cost: 0, captureAlive: false,
  });
  const [paused, setPaused] = useState(false);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, u, p] = await Promise.all([api.status(), api.usage(30), api.pipeline()]);
        setStatus({
          online: true,
          episodes: s.episode_count,
          playbooks: s.playbook_count,
          routines: s.routine_count ?? 0,
          cost: u.total_cost_usd,
          captureAlive: s.capture_alive,
        });
        setPaused(p.paused);
      } catch {
        setStatus((prev) => ({ ...prev, online: false }));
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const togglePipeline = async () => {
    setToggling(true);
    try {
      const res = paused ? await api.pipelineResume() : await api.pipelinePause();
      setPaused(res.paused);
    } finally {
      setToggling(false);
    }
  };

  return (
    <header className="shrink-0 flex items-center justify-between px-6 py-4 border-b bg-background" data-testid="header">
      <h1 className="text-sm font-semibold tracking-wider">OBSERVER</h1>
      <div className="flex items-center gap-5 text-xs text-muted-foreground">
        <PipelineToggle online={status.online} captureAlive={status.captureAlive} paused={paused} toggling={toggling} onToggle={togglePipeline} />
        <span data-testid="episode-count">{status.episodes} episodes</span>
        <span data-testid="playbook-count">{status.playbooks} playbooks</span>
        <span data-testid="routine-count">{status.routines} routines</span>
        <span className="font-medium text-primary" data-testid="total-cost">${status.cost.toFixed(4)}</span>
      </div>
    </header>
  );
}

export default function App() {
  const [active, setActive] = useState("episodes");
  const [sources, setSources] = useState<SourceManifest[]>([]);

  const sourceManifestMap = useMemo(
    () => new Map(sources.map(s => [`source:${s.name}`, s])),
    [sources],
  );

  useEffect(() => {
    api.sources().then(data => setSources(data.sources)).catch(() => {});
  }, []);

  // When sources load, set active to first source if no active selection yet
  useEffect(() => {
    if (sources.length > 0 && !sourceManifestMap.has(active) && !staticPanels[active]) {
      setActive(`source:${sources[0].name}`);
    }
  }, [sources, sourceManifestMap, active]);

  const captureSidebarItems = sources.map(s => ({ key: `source:${s.name}`, label: s.display_name }));

  const sidebarGroups = [
    ...(captureSidebarItems.length > 0 ? [{ label: "Sources", items: captureSidebarItems }] : []),
    { label: "Memory", items: memorySidebarItems },
    { label: "System", items: systemSidebarItems },
  ];

  const renderPanel = () => {
    const manifest = sourceManifestMap.get(active);
    if (manifest) return <SourceDataPanel manifest={manifest} />;
    const StaticPanel = staticPanels[active];
    if (StaticPanel) return <StaticPanel />;
    return <p className="p-6 text-muted-foreground">Select a panel</p>;
  };

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-48 shrink-0 border-r p-3 space-y-4 overflow-y-auto" data-testid="sidebar">
          {sidebarGroups.map((group) => (
            <div key={group.label}>
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1 px-2">{group.label}</p>
              {group.items.map((item) => (
                <Button
                  key={item.key}
                  variant={active === item.key ? "secondary" : "ghost"}
                  className="w-full justify-start h-8 text-xs"
                  onClick={() => setActive(item.key)}
                  data-testid={`nav-${item.key}`}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          ))}
        </aside>
        <main className="flex-1 overflow-y-auto">
          {renderPanel()}
        </main>
      </div>
    </div>
  );
}
