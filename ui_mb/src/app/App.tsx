import { useState } from "react";
import { ScrollArea } from "./components/ui/scroll-area";
import { SettingsPanel } from "./components/SettingsPanel";
import { GenerationPanel } from "./components/GenerationPanel";
import { Github } from "lucide-react";

const TABS = [
  { id: "generate", label: "一键生成" },
  { id: "settings", label: "参数设置" },
] as const;

type TabId = typeof TABS[number]["id"];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("generate");

  return (
    <div className="size-full bg-background flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 bg-card border-b border-border px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Github className="w-5 h-5 text-foreground" />
            <div>
              <h1 className="text-sm text-foreground">GitHub Trending 视频流水线</h1>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-600 inline-block" />
            <small className="text-muted-foreground">运行中</small>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex-shrink-0 bg-card border-b border-border px-6">
        <div className="max-w-3xl mx-auto flex gap-0">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`px-4 py-3 text-sm border-b-2 transition-colors ${
                activeTab === id
                  ? "border-foreground text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="max-w-3xl mx-auto px-6 py-6">
          {activeTab === "generate" ? <GenerationPanel /> : <SettingsPanel />}
        </div>
      </ScrollArea>
    </div>
  );
}
