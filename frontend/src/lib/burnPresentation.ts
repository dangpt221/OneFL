import type { CSSProperties } from 'react';
import type { BurnOptions, CleanChineseMode, SubtitlePreset } from './types';

export type BurnPresentation = Required<Pick<BurnOptions, 'subtitle_preset' | 'clean_chinese_mode' |
  'mask_original_sub' | 'top_mask_pct' | 'bottom_mask_pct' | 'bilingual'>>;

const modes: CleanChineseMode[] = ['white_bars', 'cinema_bars', 'bottom_bar', 'smart_blur', 'cinema_zoom', 'inpaint', 'none'];
const presets: SubtitlePreset[] = ['comic', 'cinema', 'box_banner', 'yellow_highlight'];
const percent = (value: unknown, fallback: number, max: number): number =>
  typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(max, value)) : fallback;

export function resolveBurnPresentation(saved: Partial<BurnOptions> | null = {}): BurnPresentation {
  const config = saved ?? {};
  const mode = config.mask_original_sub === false ? 'none' : modes.includes(config.clean_chinese_mode!) ? config.clean_chinese_mode! : 'white_bars';
  return {
    subtitle_preset: presets.includes(config.subtitle_preset!) ? config.subtitle_preset! : 'comic',
    clean_chinese_mode: mode, mask_original_sub: mode !== 'none', bilingual: config.bilingual ?? false,
    top_mask_pct: percent(config.top_mask_pct, 11, 28), bottom_mask_pct: percent(config.bottom_mask_pct, 15, 35),
  };
}

export const comicText = (text: string): string => text.toLocaleUpperCase('vi-VN');

/** Same script-space dimensions as ASS (1280x720). Browser font metrics remain approximate. */
export function subtitlePreviewStyle(preset: SubtitlePreset, width: number, height: number): CSSProperties & {fontSize: number} {
  const scale = Math.max(.01, Number.isFinite(height) ? height / 720 : .5);
  const comic = preset === 'comic';
  return {
    fontFamily: 'Arial, "DejaVu Sans", sans-serif', fontWeight: 700, fontStyle: comic ? 'italic' : 'normal',
    fontSize: (comic ? 36 : 24) * scale, lineHeight: 1.2,
    color: preset === 'yellow_highlight' ? '#ffff00' : '#ffffff',
    WebkitTextStroke: `${(comic ? 3 : 2.2) * scale}px black`, paintOrder: 'stroke fill',
    textShadow: `${scale}px ${scale}px ${scale}px black`, transform: comic ? 'scaleX(0.8)' : undefined,
    transformOrigin: 'center', backgroundColor: preset === 'box_banner' ? '#000000' : 'transparent',
    whiteSpace: 'pre-line', overflowWrap: 'anywhere', margin: 0,
    maxWidth: Math.max(1, width - 40 * scale),
  };
}
