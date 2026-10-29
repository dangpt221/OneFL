import { Project, SubtitleCue, SpeakerProfile, RelationshipMatrix, GlossaryTerm, GenrePresetSummary, SystemInfo, TTSVoice, TTSPreviewResponse, DubRequest, DubbingTimingReport, BurnOptions, CleanupReport } from './types';

const API_BASE = '/api/v1';

async function checkedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, { ...init, cache: 'no-store', credentials: 'same-origin' });
  if (!response.ok) {
    let detail = `Yêu cầu thất bại (${response.status})`;
    try { const body = await response.json(); detail = typeof body.detail === 'string' ? body.detail : detail; } catch { /* Non-JSON proxy response. */ }
    if (response.status === 401 && typeof window !== 'undefined') window.location.assign('/login');
    throw new Error(detail);
  }
  return response;
}

export const api = {
  // Projects
  async listProjects(): Promise<{ total: number; items: Project[] }> {
    const res = await checkedFetch(`${API_BASE}/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  },

  async getProject(id: string): Promise<Project> {
    const res = await checkedFetch(`${API_BASE}/projects/${id}`);
    if (!res.ok) throw new Error('Failed to fetch project');
    return res.json();
  },

  async createProject(data: { title: string; description?: string; source_language: string; target_language: string }): Promise<Project> {
    const res = await checkedFetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create project');
    return res.json();
  },

  async uploadVideo(
    projectId: string,
    file: File,
    autoStart: boolean = true,
    onProgress?: (progress: number) => void
  ): Promise<Project> {
    const chunkSize = 10 * 1024 * 1024;
    const totalChunks = Math.ceil(file.size / chunkSize);
    if (!totalChunks) throw new Error('Video trống');
    const storageKey = `onefl-upload:${projectId}:${file.name}:${file.size}:${file.lastModified}`;
    let uploadId = localStorage.getItem(storageKey);
    let state: { received: Record<string, unknown>; upload_id: string; finalized: boolean } | null = null;
    if (uploadId) {
      try { state = await (await checkedFetch(`${API_BASE}/projects/${projectId}/uploads/${uploadId}`)).json(); }
      catch { uploadId = null; }
    }
    if (!state) {
      state = await (await checkedFetch(`${API_BASE}/projects/${projectId}/uploads`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, size: file.size, total_chunks: totalChunks }),
      })).json();
      uploadId = state!.upload_id;
      localStorage.setItem(storageKey, uploadId!);
    }
    for (let index = 0; index < totalChunks; index++) {
      if (!state!.received[String(index)] && !state!.finalized) {
        const offset = index * chunkSize;
        const data = new FormData();
        data.append('file', file.slice(offset, offset + chunkSize), file.name);
        data.append('upload_id', uploadId!);
        data.append('chunk_index', String(index));
        data.append('offset', String(offset));
        for (let attempt = 0; ; attempt++) {
          try { await checkedFetch(`${API_BASE}/projects/${projectId}/upload-chunk`, { method: 'POST', body: data }); break; }
          catch (error) { if (attempt >= 2) throw error; await new Promise(resolve => setTimeout(resolve, 500 * 2 ** attempt)); }
        }
      }
      onProgress?.(Math.round((index + 1) / totalChunks * 100));
    }
    const response = await checkedFetch(`${API_BASE}/projects/${projectId}/uploads/${uploadId}/finalize?auto_start_pipeline=${autoStart}`, { method: 'POST' });
    localStorage.removeItem(storageKey);
    return response.json();
  },

  async inspectUrlInfo(url: string): Promise<any> {
    const res = await checkedFetch(`${API_BASE}/projects/url-info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error('Failed to inspect URL info');
    return res.json();
  },

  async createProjectFromUrl(data: {
    url: string;
    title?: string;
    source_language: string;
    target_language: string;
    auto_start_pipeline?: boolean;
    settings_override?: Record<string, any>;
  }): Promise<Project> {
    const res = await checkedFetch(`${API_BASE}/projects/from-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create project from URL');
    return res.json();
  },

  async deleteProject(id: string): Promise<void> {
    const res = await checkedFetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete project');
  },

  async resetProjectStatus(projectId: string, targetStatus: string = 'WAITING_REVIEW'): Promise<any> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/reset-status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_status: targetStatus })
    });
    if (!res.ok) throw new Error('Failed to reset project status');
    return res.json();
  },

  async resumeProjectDubbing(projectId: string): Promise<any> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/resume-dubbing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    if (!res.ok) throw new Error('Failed to resume project dubbing');
    return res.json();
  },

  // Subtitles
  async getSubtitles(projectId: string): Promise<{ total_cues: number; items: SubtitleCue[] }> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/subtitles`);
    if (!res.ok) throw new Error('Failed to fetch subtitles');
    return res.json();
  },

  async updateCue(projectId: string, cueId: string, data: Partial<SubtitleCue>): Promise<SubtitleCue> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/subtitles/${cueId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to update subtitle cue');
    return res.json();
  },

  async retranslateCues(projectId: string, cueIds: string[], customInstruction?: string): Promise<SubtitleCue[]> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/subtitles/retranslate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cue_ids: cueIds,
        custom_instruction: customInstruction,
      }),
    });
    const queued = await res.json();
    for (;;) {
      const job = await (await checkedFetch(`${API_BASE}/projects/${projectId}/jobs/${queued.job_id}`)).json();
      if (job.status === 'FAILED' || job.status === 'CANCELLED') throw new Error(job.error || 'Dịch lại bị dừng');
      if (job.status === 'SUCCEEDED') {
        const subtitles = await api.getSubtitles(projectId);
        return subtitles.items.filter(c => cueIds.includes('ALL') || cueIds.includes(c.id));
      }
      await new Promise(resolve => setTimeout(resolve, 1500));
    }
  },

  getExportUrl(projectId: string, format: 'ass' | 'srt' | 'vtt', options?: { bilingual?: boolean; preset?: string }): string {
    const params = new URLSearchParams();
    if (options?.bilingual) params.set('bilingual', 'true');
    if (options?.preset) params.set('preset', options.preset);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return `${API_BASE}/projects/${projectId}/subtitles/export/${format}${qs}`;
  },

  // Speakers & Matrix
  async getSpeakerMatrix(projectId: string): Promise<{ speakers: SpeakerProfile[]; relationships: RelationshipMatrix[] }> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/speakers`);
    if (!res.ok) throw new Error('Failed to fetch speaker matrix');
    return res.json();
  },

  async createSpeaker(projectId: string, data: Partial<SpeakerProfile>): Promise<SpeakerProfile> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/speakers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create speaker');
    return res.json();
  },

  async updateSpeaker(projectId: string, speakerTag: string, data: Partial<SpeakerProfile>): Promise<SpeakerProfile> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/speakers/${speakerTag}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to update speaker');
    return res.json();
  },

  async deleteSpeaker(projectId: string, speakerTag: string): Promise<void> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/speakers/${speakerTag}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete speaker');
  },

  async applySpeakerPreset(projectId: string, presetKey: string, overrideExisting: boolean = false): Promise<any> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/speakers/apply-preset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset_key: presetKey, override_existing: overrideExisting }),
    });
    if (!res.ok) throw new Error('Failed to apply speaker preset');
    return res.json();
  },

  getSpeakerExportUrl(projectId: string, format: 'json' | 'csv' = 'json'): string {
    return `${API_BASE}/projects/${projectId}/speakers/export?format=${format}`;
  },

  async importSpeakers(projectId: string, data: { speakers?: any[]; relationships?: any[]; override_existing?: boolean }): Promise<any> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/speakers/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to import speakers');
    return res.json();
  },

  async upsertRelationship(projectId: string, data: Omit<RelationshipMatrix, 'id' | 'project_id'>): Promise<RelationshipMatrix> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/speakers/relationships`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to update relationship');
    return res.json();
  },

  async deleteRelationship(projectId: string, relationshipId: string): Promise<void> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/speakers/relationships/${relationshipId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete relationship');
  },

  // Glossary
  async getGlossary(projectId: string, category?: string, q?: string): Promise<{ total: number; items: GlossaryTerm[] }> {
    const params = new URLSearchParams();
    if (category && category !== 'all') params.append('category', category);
    if (q) params.append('q', q);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/glossary${queryString}`);
    if (!res.ok) throw new Error('Failed to fetch glossary');
    return res.json();
  },

  async addGlossaryTerm(projectId: string, data: { source_term: string; target_term: string; category?: string; context_note?: string; priority?: string }): Promise<GlossaryTerm> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/glossary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to add glossary term');
    return res.json();
  },

  async updateGlossaryTerm(projectId: string, termId: string, data: Partial<GlossaryTerm>): Promise<GlossaryTerm> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/glossary/${termId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to update glossary term');
    return res.json();
  },

  async deleteGlossaryTerm(projectId: string, termId: string): Promise<void> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/glossary/${termId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete glossary term');
  },

  async autoExtractGlossary(projectId: string): Promise<GlossaryTerm[]> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/glossary/auto-extract`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to auto-extract glossary');
    return res.json();
  },

  async getGlossaryPresets(projectId: string): Promise<GenrePresetSummary[]> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/glossary/presets`);
    if (!res.ok) throw new Error('Failed to fetch presets');
    return res.json();
  },

  async applyGlossaryPreset(projectId: string, presetKey: string, overrideExisting: boolean = false): Promise<any> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/glossary/apply-preset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset_key: presetKey, override_existing: overrideExisting }),
    });
    if (!res.ok) throw new Error('Failed to apply glossary preset');
    return res.json();
  },

  getGlossaryExportUrl(projectId: string, format: 'json' | 'csv' = 'json'): string {
    return `${API_BASE}/projects/${projectId}/glossary/export?format=${format}`;
  },

  async importGlossary(projectId: string, terms: any[], overrideExisting: boolean = false): Promise<any> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/glossary/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ terms, override_existing: overrideExisting }),
    });
    if (!res.ok) throw new Error('Failed to import glossary');
    return res.json();
  },

  // TTS & AI Dubbing
  async getDubbingTiming(projectId: string, signal?: AbortSignal): Promise<DubbingTimingReport | null> {
    const res = await checkedFetch(`${API_BASE}/tts/projects/${projectId}/timing`, { signal, cache: 'no-store' });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error('Không đọc được báo cáo đồng bộ lồng tiếng.');
    return res.json();
  },

  async getTTSVoices(): Promise<TTSVoice[]> {
    const res = await checkedFetch(`${API_BASE}/tts/voices`);
    if (!res.ok) throw new Error('Failed to fetch TTS voices');
    return res.json();
  },

  async previewTTSVoice(voice: string, speed: number = 1.0, sampleText?: string, model?: string): Promise<TTSPreviewResponse> {
    const res = await checkedFetch(`${API_BASE}/tts/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice, speed, sample_text: sampleText, model }),
    });
    if (!res.ok) throw new Error('Failed to generate voice preview');
    return res.json();
  },

  async startProjectDubbing(projectId: string, data: DubRequest): Promise<{ success: boolean; message: string; status: string }> {
    const res = await checkedFetch(`${API_BASE}/tts/projects/${projectId}/dub`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to start dubbing');
    return res.json();
  },

  async getProjectDubStatus(projectId: string): Promise<any> {
    const res = await checkedFetch(`${API_BASE}/tts/projects/${projectId}/dub`);
    if (!res.ok) throw new Error('Failed to fetch dub status');
    return res.json();
  },

  // Pipeline
  async triggerPipeline(projectId: string, stage?: string, forceReprocess: boolean = false): Promise<{ success: boolean; message: string }> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/pipeline/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage, force_reprocess: forceReprocess }),
    });
    if (!res.ok) throw new Error('Failed to trigger pipeline');
    return res.json();
  },

  async startBurning(
    projectId: string,
    options?: BurnOptions
  ): Promise<{ success: boolean; message: string }> {
    const res = await checkedFetch(`${API_BASE}/projects/${projectId}/pipeline/burn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options || {}),
    });
    if (!res.ok) throw new Error('Failed to start burning');
    return res.json();
  },

  // Settings
  async getCleanupReport(projectId: string, signal?: AbortSignal): Promise<CleanupReport> {
    return (await checkedFetch(`${API_BASE}/projects/${projectId}/pipeline/cleanup-report`, {signal})).json();
  },

  async getSystemSettings(): Promise<SystemInfo> {
    const res = await checkedFetch(`${API_BASE}/settings/info`);
    if (!res.ok) throw new Error('Failed to fetch system settings');
    return res.json();
  },

  async testApiKey(provider: 'gemini' | 'openai', apiKey?: string, model?: string): Promise<{ success: boolean; error?: string; raw_response?: any }> {
    const res = await checkedFetch(`${API_BASE}/settings/test-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: apiKey, model }),
    });
    return res.json();
  },
};
