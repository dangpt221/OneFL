'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { DubbingTimingReport } from '@/lib/types';

export default function DubbingQualitySummary({ projectId, audioUrl }: { projectId: string; audioUrl?: string | null }) {
  const [result, setResult] = useState<{ audioUrl: string; report?: DubbingTimingReport | null; error?: string } | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!audioUrl) return;
    const controller = new AbortController();
    api.getDubbingTiming(projectId, controller.signal).then(report => {
      if (!controller.signal.aborted) setResult({ audioUrl, report });
    }).catch(error => {
      if (!controller.signal.aborted) setResult({ audioUrl, error: error instanceof Error ? error.message : 'Không đọc được báo cáo.' });
    });
    return () => controller.abort();
  }, [projectId, audioUrl, retry]);
  if (!audioUrl) return null;
  const current = result?.audioUrl === audioUrl ? result : null;
  const report = current?.report;
  const changed = report?.cues.filter(cue => cue.speedup > 1.01 || cue.overlaps) || [];
  return (
    <section aria-label="Kiểm tra đồng bộ" className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-3 text-xs text-slate-700">
      <p className="font-bold text-indigo-800">Kiểm tra đồng bộ lồng tiếng</p>
      {!current && <p className="mt-1">Đang tải kết quả…</p>}
      {current?.error && <div role="alert" className="mt-1 text-rose-700">{current.error}
        <button type="button" onClick={() => setRetry(value => value + 1)} className="ml-2 underline">Thử lại</button>
      </div>}
      {current?.report === null && <p className="mt-1">Bản lồng tiếng này chưa có báo cáo. Tạo lại lồng tiếng để kiểm tra theo mốc sub.</p>}
      {report && <>
        <p className="mt-1">Đã kiểm tra {report.cue_count} câu theo mốc sub · Tăng tốc tối đa {report.max_speedup.toFixed(2)}× · {report.overlap_cue_count} câu chồng thời gian.</p>
        {(report.overlap_cue_count > 0 || report.max_speedup > 1.5) && <p className="mt-1 text-amber-800">Nghe lại các câu chồng nhau hoặc tăng tốc nhiều; có thể rút gọn lời và sửa thời gian.</p>}
        {changed.length > 0 && <details className="mt-2">
          <summary className="cursor-pointer text-indigo-700">Xem các câu cần chú ý ({changed.length})</summary>
          <div className="mt-2 max-h-48 overflow-auto">
            <table className="w-full text-left"><thead><tr><th>Câu</th><th>Audio (giây)</th><th>Tốc độ</th><th>Chồng</th></tr></thead>
              <tbody>{changed.slice(0, 50).map((cue, index) => <tr key={`${cue.cue_index}-${index}`}>
                <td>#{cue.cue_index}</td><td>{cue.start_time.toFixed(3)}–{cue.audio_end.toFixed(3)}</td>
                <td>{cue.speedup.toFixed(2)}×</td><td>{cue.overlaps ? 'Có' : '—'}</td>
              </tr>)}</tbody>
            </table>
          </div>
          {changed.length > 50 && <p>Hiện 50 câu đầu cần chú ý.</p>}
        </details>}
        <p className="mt-2 text-slate-500">Đây là kiểm tra thời lượng audio; chưa đánh giá phát âm hay độ đúng của bản dịch.</p>
      </>}
    </section>
  );
}
