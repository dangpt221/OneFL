type TimedCue = { start_time: number; end_time: number };

/** Indexed half-open intervals; return all active cues in export order. */
export function indexAllSubtitleTimeline<T extends TimedCue>(input: T[]) {
  const cues = [...input].sort((a, b) => a.start_time - b.start_time);
  const maximumEnd = new Float64Array(Math.max(1, cues.length * 4));
  function build(node: number, left: number, right: number): number {
    if (left === right) return maximumEnd[node] = cues[left].end_time;
    const mid = (left + right) >>> 1;
    return maximumEnd[node] = Math.max(build(node * 2, left, mid), build(node * 2 + 1, mid + 1, right));
  }
  if (cues.length) build(1, 0, cues.length - 1);
  return (time: number): T[] => {
    const active: T[] = [];
    function find(node: number, left: number, right: number): void {
      if (cues[left].start_time > time || maximumEnd[node] <= time) return;
      if (left === right) { active.push(cues[left]); return; }
      const mid = (left + right) >>> 1;
      find(node * 2, left, mid);
      find(node * 2 + 1, mid + 1, right);
    }
    if (cues.length) find(1, 0, cues.length - 1);
    return active;
  };
}

/** Compatibility for callers that need only the latest starting active cue. */
export function indexSubtitleTimeline<T extends TimedCue>(input: T[]) {
  const allAt = indexAllSubtitleTimeline(input);
  return (time: number): T | undefined => {
    const active = allAt(time);
    return active[active.length - 1];
  };
}

/** Mark overlapping cues without allocating every pair in a dense overlap. */
export function overlappingCueIds<T extends TimedCue & { id: string }>(input: T[]): Set<string> {
  const cues = [...input].sort((a, b) => a.start_time - b.start_time);
  const ids = new Set<string>();
  let latestEnd = -Infinity;
  cues.forEach((cue, index) => {
    if (cue.start_time < latestEnd || (index + 1 < cues.length && cues[index + 1].start_time < cue.end_time)) ids.add(cue.id);
    latestEnd = Math.max(latestEnd, cue.end_time);
  });
  return ids;
}
