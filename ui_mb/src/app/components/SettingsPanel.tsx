import { useState } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Label } from "./ui/label";
import { Slider } from "./ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Separator } from "./ui/separator";
import { Check } from "lucide-react";

const DEFAULT_PROMPT = `你是一位专业的科技短视频脚本作家。请根据以下 GitHub 项目信息，生成一段 60 秒左右的短视频脚本。

要求：
- 开头 5 秒：用一句话吸引眼球，点出项目核心价值
- 中间 40 秒：介绍项目功能、使用场景、技术亮点
- 结尾 15 秒：总结推荐理由，引导关注点赞

风格：口语化、有节奏感，避免技术术语堆砌。`;

const TEMPLATES = [
  { id: "tech-dark", name: "科技暗黑" },
  { id: "minimal-light", name: "简约白底" },
  { id: "neon-cyber", name: "霓虹赛博" },
  { id: "github-green", name: "GitHub 绿" },
];

const VOICES: Record<string, string[]> = {
  openai: ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
  azure: ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunjianNeural"],
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
        <SectionHeader label="脚本生成" />
        <div className="bg-card border border-border rounded-md p-5 space-y-4">
          <div className="space-y-2">
            <Label className="text-sm text-foreground">生成 Prompt</Label>
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
                保存
              </Button>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setIsEditingPrompt(true)}>
                编辑
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => { setPrompt(DEFAULT_PROMPT); setIsEditingPrompt(false); }}
            >
              重置
            </Button>
            {promptSaved && (
              <small className="text-muted-foreground flex items-center gap-1">
                <Check className="w-3 h-3" /> 已保存
              </small>
            )}
          </div>
        </div>
      </section>

      {/* TTS Settings */}
      <section>
        <SectionHeader label="配音" />
        <div className="bg-card border border-border rounded-md p-5">
          <div className="grid grid-cols-2 gap-x-6 gap-y-5">
            <div className="space-y-2">
              <Label className="text-sm">TTS 服务</Label>
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
              <Label className="text-sm">声音</Label>
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
              <Label className="text-sm">情绪风格</Label>
              <Select value={emotion} onValueChange={setEmotion}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="neutral">标准</SelectItem>
                  <SelectItem value="cheerful">活泼</SelectItem>
                  <SelectItem value="serious">严肃</SelectItem>
                  <SelectItem value="calm">平静</SelectItem>
                  <SelectItem value="excited">激动</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <Label className="text-sm">
                语速 <span className="text-muted-foreground font-mono">{speed[0].toFixed(1)}×</span>
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
        <SectionHeader label="画面模板" />
        <div className="bg-card border border-border rounded-md p-5 space-y-5">
          <div className="space-y-3">
            <Label className="text-sm">模板</Label>
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
              <Label className="text-sm">标题样式</Label>
              <Select value={titleStyle} onValueChange={setTitleStyle}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bold">粗体大标题</SelectItem>
                  <SelectItem value="elegant">优雅细线</SelectItem>
                  <SelectItem value="neon">霓虹发光</SelectItem>
                  <SelectItem value="minimal">极简无衬</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">代码主题</Label>
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
              <Label className="text-sm">背景特效</Label>
              <Select value={backgroundEffect} onValueChange={setBackgroundEffect}>
                <SelectTrigger className="bg-input-background border-border h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="particles">粒子流</SelectItem>
                  <SelectItem value="grid">网格线</SelectItem>
                  <SelectItem value="gradient">渐变动态</SelectItem>
                  <SelectItem value="none">无特效</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <Label className="text-sm">
                节奏 <span className="text-muted-foreground">
                  {["慢", "中慢", "标准", "中快", "快"][pacing[0] - 1]}
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
                <small className="text-muted-foreground">慢</small>
                <small className="text-muted-foreground">快</small>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="flex justify-end">
        <Button>保存设置</Button>
      </div>
    </div>
  );
}
