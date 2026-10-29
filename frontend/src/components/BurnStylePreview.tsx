'use client';
import { useEffect, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import type { BurnOptions, SubtitleCue } from '@/lib/types';
import { comicText, resolveBurnPresentation, subtitlePreviewStyle } from '@/lib/burnPresentation';

const SAMPLE = 'Ta đã hỏi ở Túy Tiên Lầu rồi, mười hai bàn tiệc.';

export default function BurnStylePreview({source, cues = [], options}: {
  source?: string; cues?: SubtitleCue[]; options: BurnOptions;
}) {
  const presentation = resolveBurnPresentation(options);
  const root = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [size, setSize] = useState({width: 640, height: 360});
  const [aspect, setAspect] = useState(16 / 9);
  const [time, setTime] = useState(0);
  const [error, setError] = useState('');
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  useEffect(() => {
    if (!root.current) return;
    const observer = new ResizeObserver(([entry]) => setSize({width: entry.contentRect.width, height: entry.contentRect.height}));
    observer.observe(root.current); return () => observer.disconnect();
  }, []);
  useEffect(() => {setError(''); setTime(0); setAspect(16 / 9); setPlaying(false); setDuration(0);}, [source]);
  const togglePlayback = async () => {
    if (!video.current) return;
    if (!video.current.paused) {video.current.pause(); return;}
    setError('');
    try {await video.current.play();}
    catch (error) {setError(error instanceof Error ? error.message : 'Không phát được video xem trước.');}
  };
  const active = cues.filter(cue => cue.start_time <= time && cue.end_time > time);
  const translated = active.map(cue => cue.translated_text || cue.original_text).join('\n') || SAMPLE;
  const text = presentation.subtitle_preset === 'comic' ? comicText(translated) : translated;
  const mode = presentation.clean_chinese_mode;
  const white = mode === 'white_bars';
  const top = ['white_bars', 'cinema_bars', 'smart_blur'].includes(mode) ? presentation.top_mask_pct : 0;
  const bottom = ['white_bars', 'cinema_bars', 'bottom_bar', 'smart_blur'].includes(mode) ? presentation.bottom_mask_pct : 0;
  const scale = size.height / 720;
  return <section aria-label="Xem trước kiểu xuất" className="space-y-2">
    <p className="text-xs font-semibold text-slate-800">Xem trước kiểu xuất</p>
    <div ref={root} data-testid="burn-style-preview" className="relative overflow-hidden rounded-xl bg-slate-800"
      style={{aspectRatio: aspect}}>
      {source && <video ref={video} src={source} preload="metadata" playsInline className="block h-full w-full"
        aria-label="Video xem trước kiểu xuất" onError={() => setError('Không mở được video xem trước. Kiểu chữ mẫu vẫn hiển thị.')}
        onLoadedMetadata={e => {const video = e.currentTarget; if (video.videoWidth && video.videoHeight) setAspect(video.videoWidth / video.videoHeight);
          setDuration(Number.isFinite(video.duration) ? video.duration : 0);}}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onTimeUpdate={e => setTime(e.currentTarget.currentTime)} />}
      {top > 0 && <div data-testid="preview-top-band" aria-hidden="true" className="absolute inset-x-0 top-0 pointer-events-none"
        style={{height: `${top}%`, backgroundColor: white ? '#ffffff' : mode === 'smart_blur' ? '#00000066' : '#000000', backdropFilter: mode === 'smart_blur' ? 'blur(8px)' : undefined}} />}
      {bottom > 0 && <div data-testid="preview-bottom-band" aria-hidden="true" className="absolute inset-x-0 bottom-0 pointer-events-none"
        style={{height: `${bottom}%`, backgroundColor: white ? '#ffffff' : mode === 'smart_blur' ? '#00000066' : '#000000', backdropFilter: mode === 'smart_blur' ? 'blur(8px)' : undefined}} />}
      <div className="absolute inset-x-0 flex justify-center text-center pointer-events-none" style={{bottom: (presentation.subtitle_preset === 'box_banner' ? 36 : 30) * scale}}>
        <p data-testid="preview-styled-subtitle" style={subtitlePreviewStyle(presentation.subtitle_preset, size.width, size.height)}>{text}</p>
      </div>
    </div>
    {source && <div className="flex items-center gap-2">
      <button type="button" onClick={togglePlayback} disabled={!duration}
        aria-label={playing ? 'Tạm dừng xem trước' : 'Phát video xem trước'}
        className="rounded-lg bg-indigo-600 p-2 text-white disabled:opacity-40">
        {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
      </button>
      <input type="range" min={0} max={duration || 1} step={0.1} value={time} disabled={!duration}
        aria-label="Thời gian video xem trước (giây)" className="min-w-0 flex-1 accent-indigo-600"
        onChange={e => {const next = Number(e.target.value); if (video.current) video.current.currentTime = next; setTime(next);}} />
      <span className="text-[10px] tabular-nums text-slate-600">{time.toFixed(1)} / {duration.toFixed(1)}s</span>
    </div>}
    <p className="text-[11px] text-slate-500">{active.length ? 'Đang hiển thị câu tại thời điểm phát.' : 'Đang hiển thị câu mẫu để so kiểu chữ.'} Xem trước minh họa; kiểm tra video render để chốt vị trí và xuống dòng.</p>
    {presentation.bilingual && <p className="text-[11px] text-slate-500">Bản xuất song ngữ có thêm dòng gốc phía trên.</p>}
    {['inpaint', 'cinema_zoom'].includes(mode) && <p className="text-[11px] text-slate-500">Phục hồi nền/cắt khung hình chỉ áp dụng khi render.</p>}
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
  </section>;
}
