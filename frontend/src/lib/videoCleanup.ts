import type { CleanupRegion, VideoCleanupOptions } from './types';

export const defaultCleanupOptions = (): VideoCleanupOptions => ({
  auto_detect_chinese: true, scan_interval_seconds: .5, confidence: .6, padding: 4, regions: [],
});

export function validCleanupRegions(regions: Array<Pick<CleanupRegion, 'x' | 'y' | 'width' | 'height'>>): boolean {
  return regions.length <= 12 && regions.every(r => [r.x, r.y, r.width, r.height].every(Number.isFinite) &&
    r.x >= 0 && r.y >= 0 && r.width > 0 && r.height > 0 &&
    r.x + r.width <= 1.000001 && r.y + r.height <= 1.000001 && r.width * r.height <= .5);
}

export function regionFromDrag(start: [number, number], end: [number, number],
  bounds: {left: number; top: number; width: number; height: number}, time: number): CleanupRegion | null {
  if (!bounds.width || !bounds.height) return null;
  const point = ([x, y]: [number, number]) => [
    Math.max(0, Math.min(1, (x - bounds.left) / bounds.width)),
    Math.max(0, Math.min(1, (y - bounds.top) / bounds.height)),
  ];
  const a = point(start), b = point(end);
  const region = {x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(a[0] - b[0]),
    height: Math.abs(a[1] - b[1]), track: false, reference_time: time};
  return region.width * bounds.width >= 4 && region.height * bounds.height >= 4 && validCleanupRegions([region]) ? region : null;
}
