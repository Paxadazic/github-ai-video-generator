import { useState } from "react";
import { Button } from "./ui/button";
import { Separator } from "./ui/separator";
import { Slider } from "./ui/slider";
import { Play, Pause, Volume2, VolumeX, Download, RotateCcw, Send, Smartphone, X, Copy, Check } from "lucide-react";

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
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [hostIp, setHostIp] = useState("192.168.1.152");
  const [copied, setCopied] = useState(false);

  const duration = 63;
  const currentTime = Math.floor((progress[0] / 100) * duration);
  const formatTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const directPhoneUrl = `http://${hostIp}:8000`;

  const handleCopyLink = () => {
    navigator.clipboard.writeText(directPhoneUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

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
              <small className="text-zinc-600">Today</small>
            </div>
            <div>
              <p className="text-white font-mono text-xs">Go</p>
              <small className="text-zinc-600">Language</small>
            </div>
          </div>
        </div>

        {/* Subtitle */}
        <div className="absolute bottom-10 left-0 right-0 px-4 text-center">
          <span className="bg-black/60 text-white text-[11px] px-2 py-0.5 rounded">
            Run large language models locally with complete privacy and speed
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
            { label: "Duration", value: "1:03" },
            { label: "Size", value: "18 MB" },
            { label: "Subtitles", value: "24 Lines" },
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
            Regenerate
          </Button>
          <Button size="sm" className="flex-1" onClick={onPublish}>
            <Send className="w-3.5 h-3.5 mr-1.5" />
            Publish Video
          </Button>
        </div>

        <Button
          variant="outline"
          size="sm"
          className="w-full flex items-center justify-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setShowPhoneModal(true)}
        >
          <Smartphone className="w-3.5 h-3.5" />
          Push to Phone (QR & Direct Link)
        </Button>
      </div>

      {showPhoneModal && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowPhoneModal(false);
          }}
        >
          <div className="bg-card border border-border rounded-lg max-w-md w-full shadow-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-foreground" />
                <h3 className="font-semibold text-sm">Push Video to Phone</h3>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="w-6 h-6 rounded"
                onClick={() => setShowPhoneModal(false)}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <div className="flex flex-col items-center justify-center text-center space-y-2">
              <div className="p-3 bg-white rounded-md border border-border shadow-sm">
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&margin=4&data=${encodeURIComponent(directPhoneUrl)}`}
                  alt="QR Code"
                  className="w-44 h-44 block"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Scan with phone camera to stream video or save to Photos / Gallery
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Host LAN IP / Hostname</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={hostIp}
                  onChange={(e) => setHostIp(e.target.value)}
                  className="flex-1 bg-muted px-2.5 py-1 text-xs rounded border border-border font-mono"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-7"
                  onClick={() => setHostIp("192.168.1.152")}
                >
                  Reset
                </Button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Direct Mobile Video Link</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={directPhoneUrl}
                  className="flex-1 bg-muted px-2.5 py-1 text-xs rounded border border-border font-mono text-muted-foreground truncate"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-7"
                  onClick={handleCopyLink}
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                </Button>
              </div>
            </div>

            <details className="text-xs space-y-1 text-muted-foreground">
              <summary className="cursor-pointer font-medium hover:text-foreground">
                Android USB Transfer (ADB Push)
              </summary>
              <div className="pt-2">
                <p className="text-[11px] mb-1">Run in terminal if phone is connected via USB:</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    readOnly
                    value={`adb push "data/objects/.../output.mp4" /sdcard/Movies/output.mp4`}
                    className="flex-1 bg-muted px-2 py-1 text-[11px] rounded border border-border font-mono truncate"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs h-7"
                    onClick={() => navigator.clipboard.writeText(`adb push "data/objects/output.mp4" /sdcard/Movies/output.mp4`)}
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
