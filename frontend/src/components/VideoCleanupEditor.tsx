'use client';
import { useRef, useState } from 'react';
import type { CleanupRegion, VideoCleanupOptions } from '@/lib/types';
import { regionFromDrag, validCleanupRegions } from '@/lib/videoCleanup';

export default function VideoCleanupEditor({source, value, onChange}: {
  source?: string; value: VideoCleanupOptions; onChange: (options: VideoCleanupOptions) => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const start = useRef<[number, number] | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [draft, setDraft] = useState<CleanupRegion | null>(null);
  const [error, setError] = useState('');
  const update = (index: number, changes: Partial<CleanupRegion>) => onChange({...value,
    regions: value.regions.map((region, i) => i === index ? {...region, ...changes} : region)});
  const add = (region: CleanupRegion | null) => {
    if (!region || value.regions.length >= 12) {setError('Chọn vùng từ 4 pixel, tối đa nửa khung hình và 12 vùng.'); return;}
    onChange({...value, regions: [...value.regions, region]}); setError('');
  };
  return <div className="space-y-3 text-xs" data-testid="cleanup-editor">
    <label className="flex items-center gap-2 font-semibold">
      <input type="checkbox" checked={value.auto_detect_chinese}
        onChange={e => onChange({...value, auto_detect_chinese: e.target.checked})} /> Tự dò và xóa chữ Trung
    </label>
    {value.auto_detect_chinese && <label className="flex flex-wrap items-center gap-2">Chu kỳ dò chữ
      <select aria-label="Chu kỳ dò chữ" value={value.scan_interval_seconds}
        onChange={e => onChange({...value, scan_interval_seconds: Number(e.target.value)})} className="rounded border p-1.5">
        <option value={.2}>0,2 giây — chữ đổi nhanh</option><option value={.5}>0,5 giây</option>
        <option value={1}>1 giây — tiết kiệm CPU</option><option value={2}>2 giây</option>
      </select>
    </label>}
    <p className="text-slate-600">Khoanh thêm logo dạng hình hoặc chữ bị bỏ sót. Chọn thời điểm logo rõ, rồi bật bám theo nếu logo di chuyển.</p>
    {source ? <>
      <div className="relative overflow-hidden rounded-lg bg-slate-950">
        <video ref={video} src={source} preload="metadata" playsInline controls={!drawing}
          className="block w-full h-auto" aria-label="Video chọn vùng xóa"
          onLoadedMetadata={() => {setDuration(video.current?.duration || 0); setError('');}}
          onTimeUpdate={() => setTime(video.current?.currentTime || 0)}
          onError={() => setError('Không mở được video chọn vùng. Kiểm tra video nguồn đã tải xong.')} />
        <div className={`absolute inset-0 ${drawing ? 'cursor-crosshair touch-none' : 'pointer-events-none'}`}
          data-testid="cleanup-canvas"
          onPointerDown={e => {
            if (!drawing) return;
            video.current?.pause(); start.current = [e.clientX, e.clientY]; e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={e => {if (start.current) setDraft(regionFromDrag(start.current, [e.clientX, e.clientY], e.currentTarget.getBoundingClientRect(), time));}}
          onPointerCancel={() => {start.current = null; setDraft(null);}}
          onPointerUp={e => {
            if (!start.current) return;
            add(regionFromDrag(start.current, [e.clientX, e.clientY], e.currentTarget.getBoundingClientRect(), time));
            start.current = null; setDraft(null);
          }}>
          {[...value.regions, ...(draft ? [draft] : [])].map((r, i) => <div key={i}
            className="absolute border-2 border-amber-400 bg-amber-400/20 text-white text-xs"
            style={{left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.width * 100}%`, height: `${r.height * 100}%`}}>{i + 1}</div>)}
        </div>
      </div>
      <label className="flex items-center gap-2">Thời điểm {time.toFixed(1)} giây
        <input aria-label="Thời điểm chọn logo" type="range" min={0} max={duration || 1} step={.1} value={time}
          className="min-w-0 flex-1" onChange={e => {if (video.current) video.current.currentTime = Number(e.target.value); setTime(Number(e.target.value));}} />
      </label>
      <button type="button" aria-pressed={drawing} onClick={() => {video.current?.pause(); setDrawing(!drawing);}}
        className="rounded border border-amber-500 px-3 py-2">{drawing ? 'Kết thúc khoanh vùng' : 'Khoanh vùng trên video'}</button>
    </> : <p role="status">Cần tải xong video nguồn để khoanh trực tiếp. Bạn có thể nhập tọa độ theo % bên dưới.</p>}
    <button type="button" disabled={value.regions.length >= 12}
      onClick={() => add({x: .02, y: .02, width: .15, height: .1, track: false, reference_time: time})}
      className="ml-2 rounded border px-3 py-2 disabled:opacity-50">Thêm vùng bằng tọa độ</button>
    {value.regions.map((r, index) => <fieldset key={index} className="rounded-lg border border-amber-200 bg-white p-3 space-y-2">
      <legend>Vùng {index + 1}</legend>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {(['x', 'y', 'width', 'height'] as const).map((key, i) => <label key={key}>
          {['Trái (%)', 'Trên (%)', 'Rộng (%)', 'Cao (%)'][i]}
          <input aria-label={`Vùng ${index + 1} ${key}`} type="number" min={0} max={100} step={.1}
            className="mt-1 w-full rounded border p-1.5" value={Number((r[key] * 100).toFixed(2))}
            onChange={e => update(index, {[key]: Number(e.target.value) / 100})} />
        </label>)}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2"><input type="checkbox" checked={r.track}
          onChange={e => update(index, {track: e.target.checked})} /> Bám theo logo di chuyển</label>
        <label>Mốc mẫu (giây) <input aria-label={`Mốc mẫu vùng ${index + 1}`} type="number" min={0} step={.1}
          value={r.reference_time} onChange={e => update(index, {reference_time: Number(e.target.value)})} className="w-20 rounded border p-1" /></label>
        <button type="button" onClick={() => onChange({...value, regions: value.regions.filter((_, i) => i !== index)})}
          className="text-red-700 underline">Xóa vùng {index + 1}</button>
      </div>
    </fieldset>)}
    {!validCleanupRegions(value.regions) && <p role="alert" className="text-red-700">Vùng xóa vượt khung hình hoặc lớn hơn 50% ảnh.</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <p className="text-slate-600">Ảnh này chỉ hiển thị vùng chọn. Nền được phục hồi khi render; nền nhiều chi tiết có thể nhòe hoặc nhấp nháy. Cần xem lại video trước khi đăng.</p>
  </div>;
}
