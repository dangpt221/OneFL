export type ProjectStatus = 
  | 'CREATED'
  | 'PROCESSING'
  | 'INGESTING'
  | 'ASR_PROCESSING'
  | 'SPEAKER_PROFILING'
  | 'TRANSLATING'
  | 'WAITING_REVIEW'
  | 'BURNING'
  | 'COMPLETED'
  | 'FAILED'
  | (string & {});

export interface Project {
  id: string;
  title: string;
  description?: string;
  original_video_url?: string;
  local_video_path?: string;
  burned_video_url?: string;
  dubbed_video_url?: string;
  dubbed_audio_url?: string;
  default_voice?: string;
  subtitles_ass_path?: string;
  subtitles_srt_path?: string;
  video_duration_seconds: number;
  source_language: string;
  target_language: string;
  status: ProjectStatus;
  active_job_id?: string | null;
  content_revision?: number;
  last_job_kind?: string | null;
  last_dub_config?: Partial<DubRequest> | null;
  current_stage: string;
  progress_percentage: number;
  error_message?: string;
  settings_override?: Record<string, any>;
  cue_count?: number;
  speaker_count?: number;
  glossary_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SubtitleCue {
  id: string;
  project_id: string;
  cue_index: number;
  start_time: number;
  end_time: number;
  original_text: string;
  translated_text?: string;
  speaker_tag: string;
  target_speaker_tag?: string;
  cps: number;
  line_count: number;
  max_line_length: number;
  has_guardrail_violation: boolean;
  violation_notes?: string;
  is_edited: boolean;
  created_at: string;
  updated_at: string;
}

export interface SpeakerProfile {
  id: string;
  project_id: string;
  speaker_tag: string;
  display_name?: string;
  original_name?: string;
  aliases?: string;
  avatar_color?: string;
  gender: 'male' | 'female' | 'neutral' | 'unknown';
  age_group: 'child' | 'teen' | 'young_adult' | 'adult' | 'senior' | 'immortal';
  role?: string;
  tone?: string;
  tts_voice?: string;
  tts_speed?: number;
  notes?: string;
  dialogue_count?: number;
}

export interface TTSVoice {
  id: string;
  provider: string;
  name: string;
  gender: string;
  accent: string;
  recommended: boolean;
  is_default: boolean;
  badge: string;
  category: string;
  description: string;
  sample_text: string;
}

export interface TTSPreviewResponse {
  voice_id: string;
  name: string;
  speed: number;
  preview_url: string;
  sample_text: string;
}

export interface DubRequest {
  voice: string;
  model?: string;
  speed?: number;
  ducking_volume?: number;
  mix_original?: boolean;
  speaker_voice_map?: Record<string, string>;
  use_speaker_matrix?: boolean;
}

export interface URLInfoResponse {
  success: boolean;
  url: string;
  platform: string;
  title: string;
  duration: number;
  thumbnail: string;
  uploader?: string;
  suggested_source_language: string;
  error?: string;
}

export interface CreateProjectFromURLRequest {
  url: string;
  title?: string;
  source_language: string;
  target_language: string;
  auto_start_pipeline?: boolean;
  settings_override?: Record<string, any>;
}

export interface RelationshipMatrix {
  id: string;
  project_id: string;
  source_speaker: string;
  target_speaker: string;
  self_pronoun: string;
  target_pronoun: string;
  relationship_type?: string;
  honorific_notes?: string;
}

export interface GlossaryTerm {
  id: string;
  project_id: string;
  source_term: string;
  target_term: string;
  category: string;
  context_note?: string;
  priority?: string;
  case_sensitive?: string;
}

export interface GenrePresetSummary {
  id: string;
  name: string;
  icon: string;
  genre: string;
  description: string;
  term_count: number;
  speaker_count: number;
}

export interface SystemInfo {
  app_name: string;
  env: string;
  debug: boolean;
  primary_provider: string;
  fallback_provider: string;
  gemini_configured: boolean;
  gemini_model: string;
  openai_configured: boolean;
  openai_model: string;
  ffmpeg_available: boolean;
  guardrails_enabled: boolean;
  max_line_length: number;
  max_cps: number;
  storage_driver: string;
}
export interface CueTimingMeasurement {
  cue_index: number;
  start_time: number;
  end_time: number;
  source_duration: number;
  fitted_duration: number;
  audio_end: number;
  speedup: number;
  overlaps: boolean;
}

export interface DubbingTimingReport {
  version: number;
  cue_count: number;
  overlap_cue_count: number;
  max_speedup: number;
  cues: CueTimingMeasurement[];
}

