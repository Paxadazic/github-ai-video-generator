import { useState } from "react";
import { Button } from "./ui/button";
import { Separator } from "./ui/separator";
import { Slider } from "./ui/slider";
import { Play, Pause, Volume2, VolumeX, Download, RotateCcw, Send } from "lucide-react";

interface VideoPreviewProps {
  projectName: string;
  onRegenerate: () => void;
  onPublish: () => void;
}

export function VideoPreview({ projectName, onRegenerate, onPublish }: VideoPreviewProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [progress, setProgress] = useState([12]);
  const [volume, setVolume] = useState([80]);

  const duration = 63;
  const currentTime = Math.floor((progress[0] / 100) * duration);
  const formatTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="bg-card border border-border rounded-md overflow-hidden">
      {/* Phone-frame preview — dark by design (it's a video player) */}
      <div className="bg-zinc-950 relative" style={{ aspectRatio: "9/16", maxHeight: 420 }}>
        <div className="absolute inset-0 flex flex-col items-center justify-center px-6 gap-4">
          <div className="text-center">
            <small className="text-zinc-500 font-mono uppercase tracking-widest">GitHub Trending</small>
            <p className="text-white mt-1">{projectName}</p>
          </div>

          <div className="w-full bg-zinc-900 border border-zinc-800 rounded text-[9px] font-mono p-3">
            <div className="flex gap-1.5 mb-2 opacity-60">
              <div className="w-2 h-2 rounded-full bg-zinc-600" />
              <div className="w-2 h-2 rounded-full bg-zinc-600" />
              <div className="w-2 h-2 rounded-full bg-zinc-600" />
            </div>
            <div className="text-zinc-400 space-y-0.5 leading-relaxed">
              <div><span className="text-purple-400">import</span> <span className="text-zinc-200">{"{ ollama }"}</span> <span className="text-purple-400">from</span> <span className="text-green-400">'ollama'</span></div>
              <div><span className="text-blue-400">const</span> <span className="text-zinc-200">res</span> = <span className="text-blue-400">await</span> <span className="text-zinc-300">ollama</span>.<span className="text-yellow-300">chat</span>{"({"}</div>
              <div className="pl-3"><span className="text-red-300">model</span>: <span className="text-green-400">'llama3'</span>,</div>
              <div className="pl-3"><span className="text-red-300">messages</span>: [...]</div>
              <div>{"})"}  </div>
            </div>
          </div>

          <div className="flex gap-6 text-center">
            <div>
              <p className="text-white font-mono text-xs">124k</p>
              <small className="text-zinc-600">Stars</small>
            </div>
            <div>
              <p className="text-white font-mono text-xs">+2.1k</p>
              <small className="text-zinc-600">今日</small>
            </div>
            <div>
              <p className="text-white font-mono text-xs">Go</p>
              <small className="text-zinc-600">语言</small>
            </div>
          </div>
        </div>

        {/* Subtitle */}
        <div className="absolute bottom-10 left-0 right-0 px-4 text-center">
          <span className="bg-black/60 text-white text-[11px] px-2 py-0.5 rounded">
            本地运行大模型，无需联网，保护隐私
          </span>
        </div>

        {/* Play overlay */}
        {!isPlaying && (
          <button
            onClick={() => setIsPlaying(true)}
            className="absolute inset-0 flex items-center justify-center"
          >
            <div className="w-12 h-12 rounded-full border border-white/30 bg-white/10 flex items-center justify-center backdrop-blur-sm">
              <Play className="w-5 h-5 text-white fill-white ml-0.5" />
            </div>
          </button>
        )}
      </div>

      {/* Controls */}
      <div className="p-4 space-y-3">
        <div className="space-y-1">
          <Slider
            value={progress}
            onValueChange={setProgress}
            min={0}
            max={100}
            step={0.5}
          />
          <div className="flex justify-between">
            <small className="text-muted-foreground tabular-nums">{formatTime(currentTime)}</small>
            <small className="text-muted-foreground tabular-nums">{formatTime(duration)}</small>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="icon"
            variant="ghost"
            className="w-8 h-8"
            onClick={() => setIsPlaying(!isPlaying)}
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </Button>

          <Button
            size="icon"
            variant="ghost"
            className="w-8 h-8 text-muted-foreground"
            onClick={() => setIsMuted(!isMuted)}
          >
            {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </Button>

          <div className="w-20">
            <Slider
              value={isMuted ? [0] : volume}
              onValueChange={setVolume}
              min={0}
              max={100}
              step={1}
            />
          </div>

          <div className="ml-auto flex items-center gap-1">
            <Button size="icon" variant="ghost" className="w-8 h-8 text-muted-foreground">
              <Download className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>

        <Separator className="bg-border" />

        <div className="grid grid-cols-3 gap-3 text-center">
          {[
            { label: "时长", value: "1:03" },
            { label: "文件", value: "18 MB" },
            { label: "字幕", value: "24 行" },
          ].map(({ label, value }) => (
            <div key={label} className="py-2 bg-muted rounded">
              <p className="text-sm text-foreground tabular-nums">{value}</p>
              <small className="text-muted-foreground">{label}</small>
            </div>
          ))}
        </div>

        <div className="flex gap-2 pt-1">
          <Button variant="outline" size="sm" className="flex-1" onClick={onRegenerate}>
            <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
            重新生成
          </Button>
          <Button size="sm" className="flex-1" onClick={onPublish}>
            <Send className="w-3.5 h-3.5 mr-1.5" />
            发布视频
          </Button>
        </div>
      </div>
    </div>
  );
}
