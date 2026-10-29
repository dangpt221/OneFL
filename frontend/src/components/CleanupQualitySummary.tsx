'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { CleanupReport } from '@/lib/types';

export default function CleanupQualitySummary({projectId, outputUrl}: {projectId: string; outputUrl?: string}) {
  const [report, setReport] = useState<CleanupReport | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setReport(null); setError('');
    api.getCleanupReport(projectId, controller.signal).then(data => {if (!controller.signal.aborted) setReport(data);})
      .catch(error => {if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Không đọc được báo cáo');});
    return () => controller.abort();
  }, [projectId, outputUrl, attempt]);
  return <div className="rounded-xl border bg-amber-50 p-3 text-xs space-y-1" aria-live="polite">
    <p className="font-semibold">Kết quả xóa chữ/logo</p>
    {report ? <>
      <p>Đã xử lý {report.processed_frames.toLocaleString()} khung hình; {report.masked_frames.toLocaleString()} khung có vùng xóa.</p>
      <p>Dò được {report.chinese_detections} lượt chữ Trung; {report.tracking_misses} lượt không bám được logo.</p>
      {report.tracking_misses > 0 && <p className="text-amber-900">Có vùng không bám được; hãy xem lại logo di chuyển.</p>}
      <p>Số liệu xử lý chưa xác nhận mọi chữ/logo đã biến mất. Hãy xem lại video hoàn chỉnh.</p>
    </> : error ? <p role="alert">{error} <button type="button" className="underline" onClick={() => setAttempt(attempt + 1)}>Đọc lại báo cáo</button></p> : <p>Đang đọc báo cáo…</p>}
  </div>;
}
