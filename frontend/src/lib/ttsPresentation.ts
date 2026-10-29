import type { Project, TTSVoice } from './types';

export const DEFAULT_TTS_VOICE = 'vieneu-ngoc-huyen';

export function resolveDubbingVoice(project: Pick<Project, 'default_voice' | 'last_dub_config'>,
  voices: Pick<TTSVoice, 'id' | 'is_default'>[] = []): string {
  return project.last_dub_config?.voice || project.default_voice ||
    voices.find(voice => voice.is_default)?.id || DEFAULT_TTS_VOICE;
}
