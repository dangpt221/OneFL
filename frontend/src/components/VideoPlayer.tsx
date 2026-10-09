'use client';

import { useRef, useState, useEffect } from 'react';
import { Play, Pause, RotateCcw, Volume2, VolumeX, Shield, Film, EyeOff, Sparkles, ChevronDown, Loader2 } from 'lucide-react';
import { SubtitleCue } from '@/lib/types';

export type CleanChineseMode = 'cinema_bars' | 'bottom_bar' | 'smart_blur' | 'none';

interface VideoPlayerProps {
  videoUrl?: string;
  cues: SubtitleCue[];
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  seekTime?: number | null;
  isBurnedVideo?: boolean;
  initialCleanMode?: CleanChineseMode;
  onCleanModeChange?: (mode: CleanChineseMode) => void;
  loadingPercentage?: number;
  loadingMessage?: string;
}

export default function VideoPlayer({
  videoUrl,
  cues,
  currentTime,
  onTimeUpdate,
  seekTime,
  isBurnedVideo = false,
  initialCleanMode = 'cinema_bars',
  onCleanModeChange,
  loadingPercentage,
  loadingMessage,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [activeSubtitle, setActiveSubtitle] = useState<string | null>(null);
  const [showOverlay, setShowOverlay] = useState<boolean>(!isBurnedVideo);

  const [cleanMode, setCleanMode] = useState<CleanChineseMode>(initialCleanMode);
  const [isCleanMenuOpen, setIsCleanMenuOpen] = useState(false);
  const [topMaskPct, setTopMaskPct] = useState(11);
  const [bottomMaskPct, setBottomMaskPct] = useState(16);

  useEffect(() => {
    if (initialCleanMode) {
      setCleanMode(initialCleanMode);
    }
  }, [initialCleanMode]);

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

  // Find active subtitle cue at current time using Binary Search (O(log N))
  useEffect(() => {
    if (!cues || cues.length === 0) {
      setActiveSubtitle(null);
      return;
    }

    let left = 0;
    let right = cues.length - 1;
    let found = null;

    while (left <= right) {
      const mid = Math.floor((left + right) / 2);
      const cue = cues[mid];

      if (currentTime >= cue.start_time && currentTime <= cue.end_time) {
        found = cue;
        break;
      }

      if (currentTime < cue.start_time) {
        right = mid - 1;
      } else {
        left = mid + 1;
      }
    }

    if (found) {
      setActiveSubtitle(found.translated_text || found.original_text);
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

  const changeCleanMode = (mode: CleanChineseMode) => {
    setCleanMode(mode);
    setIsCleanMenuOpen(false);
    if (onCleanModeChange) {
      onCleanModeChange(mode);
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
      <div className="relative aspect-video w-full rounded-2xl bg-slate-950 overflow-hidden flex items-center justify-center shadow-inner select-none">
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
        ) : loadingPercentage !== undefined ? (
          <div className="text-center p-6 flex flex-col items-center justify-center w-full max-w-sm">
            <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mb-4" />
            <p className="text-sm font-semibold text-white mb-2">{loadingMessage || 'Đang tải video gốc...'}</p>
            <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden shadow-inner">
              <div 
                className="bg-indigo-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(0, loadingPercentage))}%` }}
              ></div>
            </div>
            <p className="text-xs mt-2 text-indigo-300 font-medium">{loadingPercentage}% hoàn tất</p>
          </div>
        ) : (
          <div className="text-center p-6 text-slate-400">
            <p className="text-sm font-semibold text-slate-300">Audio / Video Simulation Viewport</p>
            <p className="text-xs mt-1 text-slate-500">Live subtitle overlay is synchronized below</p>
          </div>
        )}

        {/* Clean Chinese Mask: Top Bar (Covers Bilibili Logo & Top Text/Watermarks) */}
        {!isBurnedVideo && (cleanMode === 'cinema_bars' || cleanMode === 'smart_blur') && (
          <div
            className={`absolute top-0 left-0 right-0 z-10 pointer-events-none transition-all duration-200 flex items-center justify-between px-3 text-[10px] text-slate-500 font-mono ${
              cleanMode === 'cinema_bars' ? 'bg-black' : 'backdrop-blur-md bg-black/40'
            }`}
            style={{ height: `${topMaskPct}%` }}
          >
            <span className="opacity-0">OneFL Studio</span>
          </div>
        )}

        {/* Clean Chinese Mask: Bottom Bar (Covers Chinese Hardsubs completely) + Centered Subtitle */}
        {!isBurnedVideo && (cleanMode === 'cinema_bars' || cleanMode === 'bottom_bar' || cleanMode === 'smart_blur') && (
          <div
            className={`absolute bottom-0 left-0 right-0 z-10 pointer-events-none flex items-center justify-center px-4 transition-all duration-200 ${
              cleanMode === 'smart_blur' ? 'backdrop-blur-md bg-black/60' : 'bg-black'
            }`}
            style={{ height: `${bottomMaskPct}%` }}
          >
            {showOverlay && activeSubtitle && (
              <div className="text-center font-medium text-xs sm:text-sm md:text-base leading-tight max-w-[92%] animate-fade-in">
                {activeSubtitle.split('\n').map((line, idx) => (
                  <div
                    key={idx}
                    className="text-yellow-300 font-bold drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]"
                  >
                    {line}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Fallback floating subtitle preview when cleanMode is 'none' */}
        {!isBurnedVideo && cleanMode === 'none' && showOverlay && activeSubtitle && (
          <div className="absolute bottom-6 left-0 right-0 px-6 text-center pointer-events-none transition-all animate-fade-in z-10">
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

        {/* Buttons & Clean Chinese Controls */}
        <div className="flex items-center justify-between pt-1 gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <button
              onClick={togglePlay}
              className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white transition-colors shadow-sm shadow-indigo-600/30 cursor-pointer"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
            </button>
            <button
              onClick={() => {
                if (videoRef.current) {
                  videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 5);
                }
              }}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
              title="Rewind 5s"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={() => setIsMuted(!isMuted)}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-rose-600" /> : <Volume2 className="w-4 h-4" />}
            </button>
          </div>

          <div className="flex items-center gap-2">
            {/* Clean Chinese Mode Selector Button */}
            {!isBurnedVideo && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setIsCleanMenuOpen(!isCleanMenuOpen)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold transition-all border cursor-pointer ${
                    cleanMode !== 'none'
                      ? 'bg-amber-50 text-amber-700 border-amber-300 shadow-xs'
                      : 'bg-slate-100 text-slate-500 hover:text-slate-700 border-slate-200'
                  }`}
                  title="Tùy chọn xóa chữ & phụ đề tiếng Trung trên video"
                >
                  <Shield className="w-3.5 h-3.5 text-amber-600" />
                  <span className="hidden sm:inline">
                    {cleanMode === 'cinema_bars' ? '🎬 Rạp Phim (Xóa Hết)' :
                     cleanMode === 'bottom_bar' ? '🛡️ Che Sub Dưới' :
                     cleanMode === 'smart_blur' ? '🌫️ Làm Mờ' : '❌ Không Che'}
                  </span>
                  <ChevronDown className="w-3 h-3 text-slate-400" />
                </button>

                {isCleanMenuOpen && (
                  <div className="absolute right-0 bottom-full mb-2 w-64 bg-white rounded-2xl border border-slate-200 shadow-xl p-2 z-40 space-y-1 animate-in fade-in">
                    <div className="px-2 py-1 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                      🛡️ Chế Độ Xóa Chữ Tiếng Trung:
                    </div>

                    <button
                      type="button"
                      onClick={() => changeCleanMode('cinema_bars')}
                      className={`w-full text-left p-2 rounded-xl flex items-center justify-between text-xs transition-colors cursor-pointer ${
                        cleanMode === 'cinema_bars' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div>
                        <div className="font-semibold flex items-center gap-1.5">
                          <span>🎬 Khung Rạp Phim 21:9</span>
                          <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.2 rounded-full font-bold">Khuyên dùng</span>
                        </div>
                        <div className="text-[10px] text-slate-500 font-normal mt-0.5">Che logo Bilibili ở trên &amp; sub Trung ở dưới</div>
                      </div>
                      {cleanMode === 'cinema_bars' && <span>✓</span>}
                    </button>

                    <button
                      type="button"
                      onClick={() => changeCleanMode('bottom_bar')}
                      className={`w-full text-left p-2 rounded-xl flex items-center justify-between text-xs transition-colors cursor-pointer ${
                        cleanMode === 'bottom_bar' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div>
                        <div className="font-semibold">🛡️ Chỉ Che Sub Đáy</div>
                        <div className="text-[10px] text-slate-500 font-normal mt-0.5">Chỉ che dải đen ở đáy để xóa sub Trung</div>
                      </div>
                      {cleanMode === 'bottom_bar' && <span>✓</span>}
                    </button>

                    <button
                      type="button"
                      onClick={() => changeCleanMode('smart_blur')}
                      className={`w-full text-left p-2 rounded-xl flex items-center justify-between text-xs transition-colors cursor-pointer ${
                        cleanMode === 'smart_blur' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div>
                        <div className="font-semibold">🌫️ Làm Mờ Thông Minh</div>
                        <div className="text-[10px] text-slate-500 font-normal mt-0.5">Làm nhòe/mờ logo và sub Trung</div>
                      </div>
                      {cleanMode === 'smart_blur' && <span>✓</span>}
                    </button>

                    <button
                      type="button"
                      onClick={() => changeCleanMode('none')}
                      className={`w-full text-left p-2 rounded-xl flex items-center justify-between text-xs transition-colors cursor-pointer ${
                        cleanMode === 'none' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div>
                        <div className="font-semibold">❌ Không Che Chữ</div>
                        <div className="text-[10px] text-slate-500 font-normal mt-0.5">Hiển thị khung hình gốc không che</div>
                      </div>
                      {cleanMode === 'none' && <span>✓</span>}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Toggle Subtitle Overlay (CC) */}
            <button
              onClick={() => setShowOverlay(!showOverlay)}
              className={`px-2.5 py-1 rounded-lg text-xs font-bold font-mono transition-all border cursor-pointer ${
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
              className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-bold text-indigo-700 transition-colors border border-slate-200 cursor-pointer"
            >
              {playbackRate}x
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

