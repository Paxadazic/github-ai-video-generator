import { useState } from "react";
import { motion } from "motion/react";
import { Button } from "./ui/button";
import { Switch } from "./ui/switch";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";
import { VideoPreview } from "./VideoPreview";
import { ProjectSelector, CANDIDATE_PROJECTS, GithubProject } from "./ProjectSelector";
import {
  TrendingUp,
  Star,
  X,
  ChevronRight,
  Check,
  Loader2,
} from "lucide-react";

const AUTO_PROJECTS = CANDIDATE_PROJECTS.slice(0, 5);

const PIPELINE_STEPS = [
  { id: "fetch", label: "Fetch Repository Data" },
  { id: "score", label: "Score & Filter" },
  { id: "script", label: "Generate Script" },
  { id: "tts", label: "Voice Synthesis" },
  { id: "render", label: "Render Video" },
];

const LANG_COLORS: Record<string, string> = {
  TypeScript: "bg-blue-500",
  Python: "bg-yellow-500",
  Go: "bg-cyan-500",
  Rust: "bg-orange-500",
  JavaScript: "bg-yellow-400",
};

function SectionHeader({ label }: { label: string }) {
  return (
    <p className="text-xs uppercase tracking-widest text-muted-foreground mb-4">{label}</p>
  );
}

export function GenerationPanel() {
  const [isAuto, setIsAuto] = useState(true);
  const [selectedIds, setSelectedIds] = useState<string[]>(AUTO_PROJECTS.map((p) => p.id));
  const [selectorOpen, setSelectorOpen] = useState(false);

  const [generating, setGenerating] = useState(false);
  const [generationStep, setGenerationStep] = useState(-1);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generatedProject, setGeneratedProject] = useState<GithubProject | null>(null);
  const [published, setPublished] = useState(false);

  const selectedProjects = CANDIDATE_PROJECTS.filter((p) => selectedIds.includes(p.id));

  const handleAutoToggle = (checked: boolean) => {
    setIsAuto(checked);
    if (checked) setSelectedIds(AUTO_PROJECTS.map((p) => p.id));
  };

  const handleGenerate = async () => {
    if (selectedProjects.length === 0) return;
    setGenerating(true);
    setGenerationStep(0);
    setGenerationProgress(0);
    setGeneratedProject(null);
    setPublished(false);

    for (let i = 0; i < PIPELINE_STEPS.length; i++) {
      setGenerationStep(i);
      const stepDuration = [600, 400, 800, 1000, 1200][i];
      const start = (i / PIPELINE_STEPS.length) * 100;
      const end = ((i + 1) / PIPELINE_STEPS.length) * 100;

      await new Promise<void>((resolve) => {
        let t = 0;
        const interval = setInterval(() => {
          t += 50;
          setGenerationProgress(start + ((end - start) * t) / stepDuration);
          if (t >= stepDuration) { clearInterval(interval); resolve(); }
        }, 50);
      });
    }

    setGenerationProgress(100);
    setGenerationStep(PIPELINE_STEPS.length);
    setGenerating(false);
    setGeneratedProject(selectedProjects[0]);
  };

  const handleRegenerate = () => {
    setGeneratedProject(null);
    setGenerationStep(-1);
    setGenerationProgress(0);
    setPublished(false);
  };

  return (
    <div className="space-y-8">
      {/* Project selection */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Repository Selection</p>
          <div className="flex items-center gap-2">
            <small className="text-muted-foreground">{isAuto ? "Auto" : "Manual"}</small>
            <Switch
              checked={isAuto}
              onCheckedChange={handleAutoToggle}
            />
          </div>
        </div>

        <div className="bg-card border border-border rounded-md overflow-hidden">
          {isAuto ? (
            <>
              <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
                <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" />
                <small className="text-muted-foreground">GitHub Trending Top 5 Today</small>
              </div>
              <ul>
                {AUTO_PROJECTS.map((project, index) => (
                  <li
                    key={project.id}
                    className={`flex items-center gap-3 px-4 py-3 ${
                      index < AUTO_PROJECTS.length - 1 ? "border-b border-border" : ""
                    }`}
                  >
                    <span className="text-xs text-muted-foreground w-4 tabular-nums">{index + 1}</span>
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${LANG_COLORS[project.language] ?? "bg-muted-foreground"}`} />
                    <span className="text-sm flex-1 font-mono">{project.fullName}</span>
                    <div className="flex items-center gap-1">
                      <Star className="w-3 h-3 text-muted-foreground" />
                      <small className="text-muted-foreground tabular-nums">{(project.stars / 1000).toFixed(1)}k</small>
                    </div>
                    <div className="flex items-center gap-1">
                      <TrendingUp className="w-3 h-3 text-muted-foreground" />
                      <small className="text-muted-foreground tabular-nums">+{project.todayStars.toLocaleString()}</small>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <button
                onClick={() => setSelectorOpen(true)}
                className="flex items-center gap-3 w-full px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors border-b border-border"
              >
                Select Candidate Repositories
                <ChevronRight className="w-4 h-4 ml-auto" />
              </button>
              {selectedProjects.length > 0 ? (
                <ul>
                  {selectedProjects.map((project, index) => (
                    <li
                      key={project.id}
                      className={`flex items-center gap-3 px-4 py-3 ${
                        index < selectedProjects.length - 1 ? "border-b border-border" : ""
                      }`}
                    >
                      <span className="text-xs text-muted-foreground w-4 tabular-nums">{index + 1}</span>
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${LANG_COLORS[project.language] ?? "bg-muted-foreground"}`} />
                      <span className="text-sm flex-1 font-mono">{project.fullName}</span>
                      <button
                        onClick={() => setSelectedIds((ids) => ids.filter((id) => id !== project.id))}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 py-8 text-center">
                  <small className="text-muted-foreground">No repositories selected yet</small>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {/* Generate */}
      <div className="flex justify-center">
        <Button
          size="lg"
          onClick={handleGenerate}
          disabled={generating || selectedProjects.length === 0}
          className="px-10"
        >
          {generating ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Generating…
            </>
          ) : (
            "Generate Video"
          )}
        </Button>
      </div>

      {/* Pipeline progress */}
      {generationStep >= 0 && (
        <motion.section
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <SectionHeader label="Pipeline Progress" />
          <div className="bg-card border border-border rounded-md overflow-hidden">
            {/* Progress bar */}
            <div className="h-0.5 bg-border">
              <div
                className="h-full bg-foreground transition-all duration-300"
                style={{ width: `${generationProgress}%` }}
              />
            </div>
            <ul>
              {PIPELINE_STEPS.map((step, index) => {
                const isDone = generationStep > index || (!generating && generationStep >= PIPELINE_STEPS.length);
                const isActive = generating && generationStep === index;

                return (
                  <li
                    key={step.id}
                    className={`flex items-center gap-3 px-4 py-3 ${
                      index < PIPELINE_STEPS.length - 1 ? "border-b border-border" : ""
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 transition-colors ${
                      isDone
                        ? "border-foreground bg-foreground"
                        : isActive
                        ? "border-foreground"
                        : "border-border"
                    }`}>
                      {isDone && <Check className="w-2.5 h-2.5 text-background" />}
                      {isActive && <Loader2 className="w-2.5 h-2.5 text-foreground animate-spin" />}
                    </div>
                    <span className={`text-sm transition-colors ${
                      isDone ? "text-muted-foreground line-through" : isActive ? "text-foreground" : "text-muted-foreground"
                    }`}>
                      {step.label}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        </motion.section>
      )}

      {/* Video preview */}
      {generatedProject && !published && (
        <motion.section
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <SectionHeader label="Video Preview" />
          <VideoPreview
            projectName={generatedProject.name}
            onRegenerate={handleRegenerate}
            onPublish={() => setPublished(true)}
          />
        </motion.section>
      )}

      {published && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-card border border-border rounded-md p-8 text-center"
        >
          <Check className="w-5 h-5 mx-auto mb-3 text-foreground" />
          <p className="text-sm text-foreground mb-1">Video Published</p>
          <small className="text-muted-foreground">Spotlight video for "{generatedProject?.fullName}" is ready.</small>
          <div className="mt-4">
            <Button variant="outline" size="sm" onClick={handleRegenerate}>
              Generate Next Video
            </Button>
          </div>
        </motion.div>
      )}

      <ProjectSelector
        open={selectorOpen}
        onClose={() => setSelectorOpen(false)}
        selected={selectedIds}
        onConfirm={(ids) => setSelectedIds(ids)}
      />
    </div>
  );
}
