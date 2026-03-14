import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FramesPanel } from "@/components/FramesPanel";
import { AudioPanel } from "@/components/AudioPanel";
import { EpisodesPanel } from "@/components/EpisodesPanel";
import { PlaybooksPanel } from "@/components/PlaybooksPanel";
import { UsagePanel } from "@/components/UsagePanel";
import { api } from "@/lib/api";

function Header() {
  const [status, setStatus] = useState({
    online: false,
    episodes: 0,
    playbooks: 0,
    cost: 0,
  });

  useEffect(() => {
    const load = async () => {
      try {
        const [s, u] = await Promise.all([api.status(), api.usage(30)]);
        setStatus({
          online: true,
          episodes: s.episode_count,
          playbooks: s.playbook_count,
          cost: u.total_cost_usd,
        });
      } catch {
        setStatus((prev) => ({ ...prev, online: false }));
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b">
      <h1 className="text-sm font-semibold tracking-wider">BISIMULATOR</h1>
      <div className="flex items-center gap-5 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              status.online ? "bg-green-500" : "bg-destructive"
            }`}
          />
          Engine
        </span>
        <span>{status.episodes} episodes</span>
        <span>{status.playbooks} playbooks</span>
        <span className="font-medium text-primary">${status.cost.toFixed(4)}</span>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <div className="p-6">
        <Tabs defaultValue="frames">
          <TabsList>
            <TabsTrigger value="frames">Capture</TabsTrigger>
            <TabsTrigger value="audio">Audio</TabsTrigger>
            <TabsTrigger value="episodes">Episodes</TabsTrigger>
            <TabsTrigger value="playbooks">Playbook</TabsTrigger>
            <TabsTrigger value="usage">Usage</TabsTrigger>
          </TabsList>
          <div className="mt-4">
            <TabsContent value="frames"><FramesPanel /></TabsContent>
            <TabsContent value="audio"><AudioPanel /></TabsContent>
            <TabsContent value="episodes"><EpisodesPanel /></TabsContent>
            <TabsContent value="playbooks"><PlaybooksPanel /></TabsContent>
            <TabsContent value="usage"><UsagePanel /></TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  );
}
