import { Project } from './types';

const busyStatuses = new Set(['QUEUED', 'PROCESSING', 'INGESTING', 'ASR_PROCESSING', 'SPEAKER_PROFILING', 'TRANSLATING', 'BURNING', 'DUBBING']);
export function isProjectBusy(project: Pick<Project, 'status' | 'active_job_id'>): boolean {
  return !!project.active_job_id || busyStatuses.has(project.status);
}

export type VideoChoice = 'auto' | 'original' | 'dubbed' | 'burned';
export function resolvePlayback(project: Project, choice: VideoChoice) {
  let kind: Exclude<VideoChoice, 'auto'>;
  if (choice === 'original' && project.original_video_url) kind = 'original';
  else if (choice === 'burned' && project.burned_video_url) kind = 'burned';
  else if (choice === 'dubbed' && (project.dubbed_video_url || project.dubbed_audio_url)) kind = 'dubbed';
  else kind = project.burned_video_url ? 'burned' : project.dubbed_video_url || project.dubbed_audio_url ? 'dubbed' : 'original';
  let videoUrl = kind === 'burned' ? project.burned_video_url : kind === 'dubbed' ? project.dubbed_video_url || project.original_video_url : project.original_video_url;
  if (videoUrl && /(?:bilibili\.com|b23\.tv|youtube\.com|youtu\.be|douyin\.com)/.test(videoUrl)) videoUrl = undefined;
  return { kind, videoUrl, isBurnedVideo: kind === 'burned',
    dubbedAudioUrl: kind === 'dubbed' && !project.dubbed_video_url ? project.dubbed_audio_url : undefined };
}
