import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";
import { Star, TrendingUp, Search, Check, X } from "lucide-react";

export interface GithubProject {
  id: string;
  name: string;
  fullName: string;
  description: string;
  language: string;
  stars: number;
  forks: number;
  todayStars: number;
  tags: string[];
  score: number;
}

const CANDIDATE_PROJECTS: GithubProject[] = [
  {
    id: "1",
    name: "shadcn-ui",
    fullName: "shadcn-ui/ui",
    description: "Beautifully designed components that you can copy and paste into your apps.",
    language: "TypeScript",
    stars: 89400,
    forks: 5600,
    todayStars: 1240,
    tags: ["UI", "React", "Tailwind"],
    score: 98,
  },
  {
    id: "2",
    name: "ollama",
    fullName: "ollama/ollama",
    description: "Get up and running with large language models locally.",
    language: "Go",
    stars: 124000,
    forks: 9800,
    todayStars: 2100,
    tags: ["AI", "LLM", "本地部署"],
    score: 97,
  },
  {
    id: "3",
    name: "open-webui",
    fullName: "open-webui/open-webui",
    description: "User-friendly AI interface supporting Ollama and OpenAI-compatible APIs.",
    language: "Python",
    stars: 65000,
    forks: 7200,
    todayStars: 1850,
    tags: ["AI", "WebUI", "LLM"],
    score: 95,
  },
  {
    id: "4",
    name: "mastra",
    fullName: "mastra-ai/mastra",
    description: "The TypeScript AI agent framework. Build, test, and deploy AI workflows.",
    language: "TypeScript",
    stars: 18000,
    forks: 1200,
    todayStars: 980,
    tags: ["AI", "Agent", "框架"],
    score: 93,
  },
  {
    id: "5",
    name: "astro",
    fullName: "withastro/astro",
    description: "The web framework for content-driven websites.",
    language: "TypeScript",
    stars: 48000,
    forks: 2500,
    todayStars: 620,
    tags: ["前端", "框架", "SSG"],
    score: 89,
  },
  {
    id: "6",
    name: "dify",
    fullName: "langgenius/dify",
    description: "Dify is an open-source LLM app development platform.",
    language: "Python",
    stars: 82000,
    forks: 11000,
    todayStars: 1560,
    tags: ["AI", "LLM", "平台"],
    score: 96,
  },
  {
    id: "7",
    name: "rustdesk",
    fullName: "rustdesk/rustdesk",
    description: "An open-source remote desktop application.",
    language: "Rust",
    stars: 79000,
    forks: 9400,
    todayStars: 780,
    tags: ["工具", "远程", "Rust"],
    score: 88,
  },
  {
    id: "8",
    name: "fabric",
    fullName: "danielmiessler/fabric",
    description: "fabric is an open-source framework for augmenting humans using AI.",
    language: "Go",
    stars: 29000,
    forks: 3100,
    todayStars: 890,
    tags: ["AI", "工具", "生产力"],
    score: 91,
  },
];

const LANG_COLORS: Record<string, string> = {
  TypeScript: "bg-blue-500",
  Python: "bg-yellow-500",
  Go: "bg-cyan-500",
  Rust: "bg-orange-500",
  JavaScript: "bg-yellow-400",
};

interface ProjectSelectorProps {
  open: boolean;
  onClose: () => void;
  selected: string[];
  onConfirm: (ids: string[]) => void;
}

export function ProjectSelector({ open, onClose, selected, onConfirm }: ProjectSelectorProps) {
  const [search, setSearch] = useState("");
  const [localSelected, setLocalSelected] = useState<string[]>(selected);

  const filtered = CANDIDATE_PROJECTS.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase()) ||
      p.tags.some((t) => t.toLowerCase().includes(search.toLowerCase()))
  );

  const toggleSelect = (id: string) => {
    setLocalSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < 5 ? [...prev, id] : prev
    );
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-card border border-border max-w-xl p-0 gap-0">
        <DialogHeader className="px-5 pt-5 pb-4 border-b border-border">
          <DialogTitle className="text-foreground">选择推荐项目</DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">
            最多选择 5 个 · 已选 {localSelected.length}/5
          </p>
        </DialogHeader>

        <div className="px-5 py-3 border-b border-border">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <Input
              placeholder="搜索项目…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9 text-sm bg-background border-border"
            />
          </div>
        </div>

        <ScrollArea className="h-[380px]">
          <ul className="divide-y divide-border">
            {filtered.map((project) => {
              const isSelected = localSelected.includes(project.id);
              const isDisabled = !isSelected && localSelected.length >= 5;

              return (
                <li key={project.id}>
                  <button
                    onClick={() => !isDisabled && toggleSelect(project.id)}
                    disabled={isDisabled}
                    className={`w-full text-left px-5 py-4 flex items-start gap-3 transition-colors ${
                      isSelected
                        ? "bg-muted"
                        : isDisabled
                        ? "opacity-40 cursor-not-allowed"
                        : "hover:bg-muted/50"
                    }`}
                  >
                    <div className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${
                      isSelected ? "border-foreground bg-foreground" : "border-border"
                    }`}>
                      {isSelected && <Check className="w-2.5 h-2.5 text-background" />}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-mono text-foreground">{project.fullName}</span>
                        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${LANG_COLORS[project.language] ?? "bg-muted-foreground"}`} />
                        <small className="text-muted-foreground">{project.language}</small>
                      </div>
                      <p className="text-sm text-muted-foreground truncate mb-2">{project.description}</p>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1">
                          <Star className="w-3 h-3 text-muted-foreground" />
                          <small className="text-muted-foreground tabular-nums">{(project.stars / 1000).toFixed(1)}k</small>
                        </div>
                        <div className="flex items-center gap-1">
                          <TrendingUp className="w-3 h-3 text-muted-foreground" />
                          <small className="text-muted-foreground tabular-nums">+{project.todayStars.toLocaleString()}</small>
                        </div>
                        <div className="ml-auto flex gap-1">
                          {project.tags.map((tag) => (
                            <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-accent text-muted-foreground rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </ScrollArea>

        <div className="px-5 py-4 border-t border-border flex items-center justify-between">
          <small className="text-muted-foreground">{filtered.length} 个候选项目</small>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>取消</Button>
            <Button
              size="sm"
              disabled={localSelected.length === 0}
              onClick={() => { onConfirm(localSelected); onClose(); }}
            >
              确认 ({localSelected.length})
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export { CANDIDATE_PROJECTS };
