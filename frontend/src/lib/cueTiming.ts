/** Return a user-facing error without converting blank input into zero. */
export function validateCueTiming(start: string, end: string, duration?: number | null): string {
  const from = Number(start), to = Number(end);
  if (!start.trim() || !end.trim() || !Number.isFinite(from) || !Number.isFinite(to)) return 'Nhập đủ thời gian bắt đầu và kết thúc hợp lệ.';
  if (from < 0 || to <= from) return 'Thời gian phải thỏa 0 ≤ bắt đầu < kết thúc.';
  if (duration && duration > 0 && to > duration) return 'Thời gian kết thúc vượt độ dài video.';
  return '';
}

export function formatCueTimestamp(seconds: number): string {
  const total = Math.max(0, Math.round(seconds * 1000));
  const hours = Math.floor(total / 3600000);
  const minutes = Math.floor(total / 60000) % 60;
  const secs = Math.floor(total / 1000) % 60;
  const pad = (value: number, width = 2) => String(value).padStart(width, '0');
  return `${hours ? `${pad(hours)}:` : ''}${pad(minutes)}:${pad(secs)}.${pad(total % 1000, 3)}`;
}
