import { useState } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Label } from "./ui/label";
import { Slider } from "./ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Separator } from "./ui/separator";
import { Check } from "lucide-react";

const DEFAULT_PROMPT = `You are a professional technology short-video scriptwriter. Based on the following GitHub repository details, generate an engaging 60-second video script.

Structure:
- Hook (0-5s): One punchy sentence highlighting the core problem and solution.
- Value (5-45s): Key features, practical use cases, and technical strengths.
- CTA (45-60s): Summary recommendation and call to action to check out the repo.

Style: Conversational, clear, well-paced, developer-focused without unnecessary jargon.`;

const TEMPLATES = [
  { id: "tech-dark", name: "Tech Dark" },
  { id: "minimal-light", name: "Minimal Light" },
  { id: "neon-cyber", name: "Neon Cyber" },
  { id: "github-green", name: "GitHub Green" },
];

const VOICES: Record<string, string[]> = {
  openai: ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
  azure: ["en-US-GuyNeural", "en-US-AriaNeural", "en-US-JennyNeural", "en-GB-RyanNeural"],
  elevenlabs: ["Rachel", "Drew", "Clyde", "Paul", "Domi", "Dave"],
};

type TtsService = "openai" | "azure" | "elevenlabs";

function SectionHeader({ label }: { label: string }) {
  return (
    <p className="text-xs uppercase tracking-widest text-muted-foreground mb-4">{label}</p>
  );
}

export function SettingsPanel() {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [isEditingPrompt, setIsEditingPrompt] = useState(false);
  const [promptSaved, setPromptSaved] = useState(false);

  const [ttsService, setTtsService] = useState<TtsService>("openai");
  const [voice, setVoice] = useState("nova");
  const [speed, setSpeed] = useState([1.0]);
  const [emotion, setEmotion] = useState("neutral");

  const [selectedTemplate, setSelectedTemplate] = useState("tech-dark");
  const [titleStyle, setTitleStyle] = useState("bold");
  const [codeTheme, setCodeTheme] = useState("dracula");
  const [backgroundEffect, setBackgroundEffect] = useState("particles");
  const [pacing, setPacing] = useState([3]);

  const [serverStatus, setServerStatus] = useState<"Stopped" | "Starting" | "Running" | "Error">("Running");
  const [lanUrl, setLanUrl] = useState("http://192.168.1.152:8000");
  const [serverMessage, setServerMessage] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/server/status");
      if (res.ok) {
        const body = await res.json();
        if (body.data) {
          setServerStatus(body.data.status);
          if (body.data.lanUrl) setLanUrl(body.data.lanUrl);
          if (body.data.message) setServerMessage(body.data.message);
          return;
        }
      }
    } catch (_) {}
    try {
      const res2 = await fetch("http://127.0.0.1:8001/api/server/status");
      if (res2.ok) {
        const body2 = await res2.json();
        if (body2.data) {
          setServerStatus(body2.data.status);
          if (body2.data.lanUrl) setLanUrl(body2.data.lanUrl);
          if (body2.data.message) setServerMessage(body2.data.message);
          return;
        }
      }
    } catch (_) {}
    setServerStatus("Stopped");
  };

  const callServerCmd = async (action: "start" | "restart" | "stop") => {
    setIsBusy(true);
    setServerStatus("Starting");
    try {
      const res = await fetch(`/api/server/${action}`, { method: "POST" });
      if (res.ok) {
        const b = await res.json();
        if (b.data?.message) setServerMessage(b.data.message);
      }
    } catch (_) {
      try {
        await fetch(`http://127.0.0.1:8001/api/server/${action}`, { method: "POST" });
      } catch (_) {}
    }
    setTimeout(() => {
      setIsBusy(false);
      fetchStatus();
    }, 1500);
  };

  const handleSavePrompt = () => {
    setIsEditingPrompt(false);
    setPromptSaved(true);
    setTimeout(() => setPromptSaved(false), 2000);
  };

  const handleTtsServiceChange = (val: string) => {
    const service = val as TtsService;
    setTtsService(service);
    setVoice(VOICES[service][0]);
  };

  return (
    <div className="space-y-8">
      {/* Script Settings */}
      <section>
        <SectionHeader label="Script Generation" />
        <div className="bg-card border border-border rounded-md p-5 space-y-4">
          <div className="space-y-2">
            <Label className="text-sm text-foreground">Prompt Template</Label>
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={!isEditingPrompt}
              rows={7}
              className="text-sm resize-none bg-background border-border disabled:opacity-70"
            />
          </div>
          <div className="flex items-center gap-2">
            {isEditingPrompt ? (
              <Button size="sm" onClick={handleSavePrompt}>
                <Check className="w-3.5 h-3.5 mr-1.5" />
                Save
              </Button>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setIsEditingPrompt(true)}>
                Edit
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => { setPrompt(DEFAULT_PROMPT); setIsEditingPrompt(false); }}
            >
              Reset
            </Button>
            {promptSaved && (
              <small className="text-muted-foreground flex items-center gap-1">
                <Check className="w-3.5 h-3.5" /> Saved
              </small>
            )}
          </div>
        </div>
      </section>

      {/* TTS Settings */}
      <section>
        <SectionHeader label="Voice & Audio" />
        <div className="bg-card border border-border rounded-md p-5">
          <div className="grid grid-cols-2 gap-x-6 gap-y-5">
            <div className="space-y-2">
              <Label className="text-sm">TTS Service</Label>
              <Select value={ttsService} onValueChange={handleTtsServiceChange}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI TTS</SelectItem>
                  <SelectItem value="azure">Azure TTS</SelectItem>
                  <SelectItem value="elevenlabs">ElevenLabs</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">Voice</Label>
              <Select value={voice} onValueChange={setVoice}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {VOICES[ttsService].map((v) => (
                    <SelectItem key={v} value={v}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">Tone / Emotion</Label>
              <Select value={emotion} onValueChange={setEmotion}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="neutral">Neutral</SelectItem>
                  <SelectItem value="cheerful">Cheerful</SelectItem>
                  <SelectItem value="serious">Authoritative</SelectItem>
                  <SelectItem value="calm">Calm</SelectItem>
                  <SelectItem value="excited">Excited</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <Label className="text-sm">
                Speaking Rate <span className="text-muted-foreground font-mono">{speed[0].toFixed(1)}×</span>
              </Label>
              <Slider
                value={speed}
                onValueChange={setSpeed}
                min={0.5}
                max={2.0}
                step={0.1}
              />
              <div className="flex justify-between">
                <small className="text-muted-foreground">0.5×</small>
                <small className="text-muted-foreground">2.0×</small>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Template Settings */}
      <section>
        <SectionHeader label="Visual Templates" />
        <div className="bg-card border border-border rounded-md p-5 space-y-5">
          <div className="space-y-3">
            <Label className="text-sm">Template Style</Label>
            <div className="flex gap-2">
              {TEMPLATES.map((tpl) => (
                <button
                  key={tpl.id}
                  onClick={() => setSelectedTemplate(tpl.id)}
                  className={`flex-1 py-2 text-xs border rounded transition-colors ${
                    selectedTemplate === tpl.id
                      ? "border-foreground bg-foreground text-background"
                      : "border-border text-muted-foreground hover:border-foreground hover:text-foreground bg-card"
                  }`}
                >
                  {tpl.name}
                </button>
              ))}
            </div>
          </div>

          <Separator className="bg-border" />

          <div className="grid grid-cols-2 gap-x-6 gap-y-5">
            <div className="space-y-2">
              <Label className="text-sm">Title Style</Label>
              <Select value={titleStyle} onValueChange={setTitleStyle}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bold">Bold Title</SelectItem>
                  <SelectItem value="elegant">Elegant Sans</SelectItem>
                  <SelectItem value="neon">Neon Glow</SelectItem>
                  <SelectItem value="minimal">Minimal Mono</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">Code Theme</Label>
              <Select value={codeTheme} onValueChange={setCodeTheme}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dracula">Dracula</SelectItem>
                  <SelectItem value="github-dark">GitHub Dark</SelectItem>
                  <SelectItem value="monokai">Monokai</SelectItem>
                  <SelectItem value="nord">Nord</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">Background Effect</Label>
              <Select value={backgroundEffect} onValueChange={setBackgroundEffect}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="particles">Particles</SelectItem>
                  <SelectItem value="grid">Grid Pattern</SelectItem>
                  <SelectItem value="gradient">Gradient Flow</SelectItem>
                  <SelectItem value="none">None</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <Label className="text-sm">
                Pacing <span className="text-muted-foreground">
                  {["Slow", "Relaxed", "Standard", "Brisk", "Fast"][pacing[0] - 1]}
                </span>
              </Label>
              <Slider
                value={pacing}
                onValueChange={setPacing}
                min={1}
                max={5}
                step={1}
              />
              <div className="flex justify-between">
                <small className="text-muted-foreground">Slow</small>
                <small className="text-muted-foreground">Fast</small>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Local Server Control */}
      <section className="space-y-4">
        <SectionHeader label="Local Server Control" />
        <div className="bg-card border border-border rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold">FastAPI / Uvicorn Server</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  serverStatus === "Running" ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20" :
                  serverStatus === "Starting" ? "bg-amber-500/10 text-amber-500 border border-amber-500/20" :
                  serverStatus === "Error" ? "bg-rose-500/10 text-rose-500 border border-rose-500/20" :
                  "bg-zinc-500/10 text-zinc-500 border border-zinc-500/20"
                }`}>
                  ● {serverStatus}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Port 8000 · Host 0.0.0.0 · Python .venv · LAN: <span className="font-mono">{lanUrl}</span>
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => callServerCmd("start")}
                disabled={serverStatus === "Running" || isBusy}
              >
                Start Server
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => callServerCmd("restart")}
                disabled={isBusy}
              >
                Restart Server
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => callServerCmd("stop")}
                disabled={serverStatus === "Stopped" || isBusy}
              >
                Stop Server
              </Button>
            </div>
          </div>
          {serverMessage && (
            <p className="text-xs text-muted-foreground bg-muted p-2 rounded font-mono">
              {serverMessage}
            </p>
          )}
        </div>
      </section>

      <div className="flex justify-end">
        <Button>Save Settings</Button>
      </div>
    </div>
  );
}
