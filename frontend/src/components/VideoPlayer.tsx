'use client';

import { useRef, useState, useEffect } from 'react';
import { Play, Pause, RotateCcw, Volume2, VolumeX, FastForward } from 'lucide-react';
import { SubtitleCue } from '@/lib/types';

interface VideoPlayerProps {
  videoUrl?: string;
  cues: SubtitleCue[];
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  seekTime?: number | null;
  isBurnedVideo?: boolean;
}

export default function VideoPlayer({
  videoUrl,
  cues,
  currentTime,
  onTimeUpdate,
  seekTime,
  isBurnedVideo = false,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [activeSubtitle, setActiveSubtitle] = useState<string | null>(null);
  const [showOverlay, setShowOverlay] = useState<boolean>(!isBurnedVideo);

  // Automatically disable subtitle overlay when playing a video with hardcoded/burned subtitles
  useEffect(() => {
    setShowOverlay(!isBurnedVideo);
  }, [isBurnedVideo, videoUrl]);

  // Sync seek requests
  useEffect(() => {
    if (seekTime !== null && seekTime !== undefined && videoRef.current) {
      videoRef.current.currentTime = seekTime;
      onTimeUpdate(seekTime);
    }
  }, [seekTime]);

  // Find active subtitle cue at current time
  useEffect(() => {
    const active = cues.find(c => currentTime >= c.start_time && currentTime <= c.end_time);
    if (active) {
      setActiveSubtitle(active.translated_text || active.original_text);
    } else {
      setActiveSubtitle(null);
    }
  }, [currentTime, cues]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const target = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = target;
      onTimeUpdate(target);
    }
  };

  const cyclePlaybackRate = () => {
    const rates = [0.75, 1.0, 1.25, 1.5, 2.0];
    const nextIdx = (rates.indexOf(playbackRate) + 1) % rates.length;
    const nextRate = rates[nextIdx];
    setPlaybackRate(nextRate);
    if (videoRef.current) {
      videoRef.current.playbackRate = nextRate;
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-white rounded-3xl p-4 flex flex-col justify-between border border-slate-200 shadow-sm relative overflow-hidden group">
      {/* Video Viewport */}
      <div className="relative aspect-video w-full rounded-2xl bg-slate-950 overflow-hidden flex items-center justify-center shadow-inner">
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            className="w-full h-full object-contain"
            muted={isMuted}
          />
        ) : (
          <div className="text-center p-6 text-slate-400">
            <p className="text-sm font-semibold text-slate-300">Audio / Video Simulation Viewport</p>
            <p className="text-xs mt-1 text-slate-500">Live subtitle overlay is synchronized below</p>
          </div>
        )}

        {/* Cinematic Subtitle Preview Overlay */}
        {showOverlay && activeSubtitle && (
          <div className="absolute bottom-6 left-0 right-0 px-6 text-center pointer-events-none transition-all animate-fade-in">
            <div className="inline-block bg-black/80 backdrop-blur-md px-4 py-2 rounded-xl border border-white/20 text-white font-medium text-sm sm:text-base leading-snug max-w-[90%] shadow-2xl">
              {activeSubtitle.split('\n').map((line, idx) => (
                <div key={idx} className="drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] text-yellow-300 font-semibold">
                  {line}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Control Bar */}
      <div className="mt-3 space-y-2">
        {/* Timeline Slider */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-500 min-w-[40px] font-semibold">{formatTime(currentTime)}</span>
          <input
            type="range"
            min={0}
            max={duration || 100}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
          />
          <span className="text-xs font-mono text-slate-500 min-w-[40px] font-semibold">{formatTime(duration)}</span>
        </div>

        {/* Buttons */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-2">
            <button
              onClick={togglePlay}
              className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white transition-colors shadow-sm shadow-indigo-600/30"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
            </button>
            <button
              onClick={() => {
                if (videoRef.current) {
                  videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 5);
                }
              }}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
              title="Rewind 5s"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={() => setIsMuted(!isMuted)}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-rose-600" /> : <Volume2 className="w-4 h-4" />}
            </button>
          </div>

          <div className="flex items-center gap-2">
            {/* Toggle Subtitle Overlay (CC) */}
            <button
              onClick={() => setShowOverlay(!showOverlay)}
              className={`px-2.5 py-1 rounded-lg text-xs font-bold font-mono transition-all border ${
                showOverlay
                  ? 'bg-indigo-600 text-white border-indigo-700 shadow-xs'
                  : 'bg-slate-100 text-slate-400 hover:text-slate-600 border-slate-200 line-through'
              }`}
              title={showOverlay ? 'Đang bật lớp phụ đề xem trước (Nhấp để tắt)' : 'Đang tắt phụ đề xem trước (Nhấp để bật)'}
            >
              CC
            </button>

            <button
              onClick={cyclePlaybackRate}
              className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-bold text-indigo-700 transition-colors border border-slate-200"
            >
              {playbackRate}x
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
