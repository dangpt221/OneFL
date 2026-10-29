'use client';

import { useState, useEffect } from 'react';
import { X, Flame, CheckCircle2, Loader2, Video, FileText } from 'lucide-react';
import { Project, BurnOptions, VideoCleanupOptions, CleanChineseMode, SubtitlePreset, SubtitleCue } from '@/lib/types';
import { resolveBurnPresentation } from '@/lib/burnPresentation';
import BurnStylePreview from './BurnStylePreview';
import { defaultCleanupOptions, validCleanupRegions } from '@/lib/videoCleanup';
import VideoCleanupEditor from './VideoCleanupEditor';
import CleanupQualitySummary from './CleanupQualitySummary';
import { isProjectBusy } from '@/lib/projectView';
import { api } from '@/lib/api';
import { getFriendlyStageName } from '@/components/PipelineProgressTracker';

interface BurnProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: Project;
  onBurnStarted: (options?: BurnOptions) => Promise<void>;
  cuesCount?: number;
  cues?: SubtitleCue[];
}

export default function BurnProgressModal({
  isOpen,
  onClose,
  project,
  onBurnStarted,
  cuesCount,
  cues,
}: BurnProgressModalProps) {
  const existingCfg = project.settings_override || {};
  const initial = resolveBurnPresentation(existingCfg);
  const [subtitlePreset, setSubtitlePreset] = useState<SubtitlePreset>(initial.subtitle_preset);
  const [bilingual, setBilingual] = useState<boolean>(existingCfg.bilingual || false);
  const [cleanChineseMode, setCleanChineseMode] = useState<CleanChineseMode>(initial.clean_chinese_mode);
  const [topMaskPct, setTopMaskPct] = useState<number>(initial.top_mask_pct);
  const [bottomMaskPct, setBottomMaskPct] = useState<number>(initial.bottom_mask_pct);
  const [showAdvancedMask, setShowAdvancedMask] = useState<boolean>(false);
  const [cleanupOptions, setCleanupOptions] = useState<VideoCleanupOptions>(() => ({...defaultCleanupOptions(), ...existingCfg.cleanup_options}));

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [configureAgain, setConfigureAgain] = useState(false);
  useEffect(() => {
    if (isOpen) {
      const cfg = project.settings_override || {};
      const presentation = resolveBurnPresentation(cfg);
      setSubtitlePreset(presentation.subtitle_preset); setBilingual(presentation.bilingual);
      setCleanChineseMode(presentation.clean_chinese_mode);
      setTopMaskPct(presentation.top_mask_pct); setBottomMaskPct(presentation.bottom_mask_pct);
      setCleanupOptions({...defaultCleanupOptions(), ...cfg.cleanup_options});
      setError(''); setConfigureAgain(false);
    }
  }, [isOpen, project.id]);
  useEffect(() => { if (project.status === 'COMPLETED') setConfigureAgain(false); }, [project.burned_video_url]);
  if (!isOpen) return null;

  const isBurning = isProjectBusy(project) || submitting;
  const isCompleted = project.status === 'COMPLETED' && !!project.burned_video_url && !configureAgain;

  const handleStart = async () => {
    if (cleanChineseMode === 'inpaint' && (!validCleanupRegions(cleanupOptions.regions) ||
      (!cleanupOptions.auto_detect_chinese && cleanupOptions.regions.length === 0))) {
      setError('Bật tự dò chữ Trung hoặc chọn vùng hợp lệ cần xóa.'); return;
    }
    setSubmitting(true); setError('');
    try { await onBurnStarted({
      subtitle_preset: subtitlePreset,
      bilingual: bilingual,
      mask_original_sub: cleanChineseMode !== 'none',
      clean_chinese_mode: cleanChineseMode,
      top_mask_pct: topMaskPct,
      bottom_mask_pct: bottomMaskPct,
      ...(cleanChineseMode === 'inpaint' ? {cleanup_options: cleanupOptions} : {}),
    }); } catch (error) { setError(error instanceof Error ? error.message : 'Không tạo được job render'); }
    finally { setSubmitting(false); }
  };

  return (
    <div role="dialog" aria-modal="true" aria-label="Burn Video" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
      <div className={`bg-white w-full ${['inpaint', 'white_bars'].includes(cleanChineseMode) ? 'max-w-3xl' : 'max-w-lg'} rounded-3xl p-6 relative border border-slate-200 shadow-2xl space-y-5 max-h-[92vh] overflow-y-auto`}>
        {/* Close Button */}
        <button aria-label="Đóng"
          onClick={onClose}
          className="absolute right-5 top-5 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600 shadow-2xs">
            <Flame className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-heading font-bold text-xl text-slate-900">Video Subtitle Burner</h3>
            <p className="text-xs text-slate-500">Xử lý chữ/logo gốc trước khi burn phụ đề Việt.</p>
          </div>
        </div>

        {/* Status Box */}
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500 font-semibold">Trạng thái hiện tại:</span>
            <span className="font-bold text-slate-900 uppercase">{project.status}</span>
          </div>

          <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-gradient-to-r from-amber-500 to-rose-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${project.progress_percentage}%` }}
            />
          </div>

          <div className="flex justify-between items-center text-[11px] text-slate-500 font-medium">
            <span className="truncate max-w-[280px]">
              {project.error_message && !project.error_message.includes('Traceback') && !project.error_message.includes('Error')
                ? project.error_message
                : `Giai đoạn: ${getFriendlyStageName(project.current_stage) || 'Sẵn sàng'}`}
            </span>
            <span className="font-bold text-amber-600 shrink-0">{project.progress_percentage}%</span>
          </div>
        </div>

        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-700">{error}</p>}
        {/* Burn Style & Presentation Customizer (Only shown before burning starts) */}
        {!isBurning && !isCompleted && (
          <div className="space-y-4 pt-1">
            <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-3 space-y-2">
              <p className="text-xs text-indigo-950">Kiểu theo ảnh: chữ trắng đậm nghiêng, in hoa và viền đen; dải che trên/dưới màu trắng.</p>
              <button type="button" onClick={() => {
                setSubtitlePreset('comic'); setCleanChineseMode('white_bars'); setBilingual(false);
                setTopMaskPct(11); setBottomMaskPct(15); setShowAdvancedMask(true);
              }} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white">Áp dụng kiểu mẫu</button>
            </div>
            <BurnStylePreview source={project.dubbed_video_url || (project.local_video_path ? project.original_video_url : undefined)}
              cues={cues} options={{subtitle_preset: subtitlePreset, clean_chinese_mode: cleanChineseMode,
                mask_original_sub: cleanChineseMode !== 'none', top_mask_pct: topMaskPct, bottom_mask_pct: bottomMaskPct, bilingual}} />
            {/* Clean Chinese Section */}
            <div className="space-y-2.5 bg-amber-50/60 p-4 rounded-2xl border border-amber-200/80">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">🛡️</span>
                  <div>
                    <h4 className="text-xs font-bold text-amber-950 uppercase tracking-wider">
                      Xử lý phụ đề và logo gốc
                    </h4>
                    <p className="text-[11px] text-amber-800/80">
                      Chọn vùng che phù hợp; kiểm tra nội dung trước khi xuất video.
                    </p>
                  </div>
                </div>
              </div>

              {/* Modes Selection Grid */}
              <div className="grid grid-cols-2 gap-2 pt-1">
                <button type="button" aria-pressed={cleanChineseMode === 'white_bars'} onClick={() => setCleanChineseMode('white_bars')}
                  className={`col-span-2 p-3 rounded-xl border text-left text-xs ${cleanChineseMode === 'white_bars' ? 'border-amber-600 bg-white ring-2 ring-amber-500/20' : 'border-amber-200 bg-white/70'}`}>
                  <strong>Dải trắng trên và dưới</strong>
                  <p className="mt-1 text-slate-600">Che kín vùng logo/sub gốc bằng nền trắng; chỉnh độ cao từng dải bên dưới.</p>
                </button>
                <button type="button" onClick={() => setCleanChineseMode('inpaint')}
                  className={`col-span-2 p-3 rounded-xl border text-left text-xs ${cleanChineseMode === 'inpaint' ? 'border-amber-600 bg-white ring-2 ring-amber-500/20' : 'border-amber-200 bg-white/70'}`}>
                  <strong>Xóa chữ/logo — phục hồi nền</strong>
                  <p className="mt-1 text-slate-600">Tự dò chữ Trung và xóa vùng logo đã chọn; giữ nguyên kích thước video.</p>
                </button>
                <button type="button" onClick={() => setCleanChineseMode('none')}
                  className={`p-2.5 rounded-xl border text-left text-xs ${cleanChineseMode === 'none' ? 'border-amber-600 bg-white ring-2 ring-amber-500/20' : 'border-amber-200 bg-white/70'}`}>
                  Không Che (Giữ khung hình gốc)
                </button>
                <button
                  type="button"
                  onClick={() => setCleanChineseMode('cinema_bars')}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                    cleanChineseMode === 'cinema_bars'
                      ? 'border-amber-600 bg-white ring-2 ring-amber-500/20 shadow-xs'
                      : 'border-amber-200/70 bg-white/70 hover:bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-slate-900">🎬 Rạp Phim (Trên &amp; Dưới)</span>
                    <span className="text-[9px] bg-amber-100 text-amber-800 font-bold px-1.5 py-0.5 rounded-full">Khuyên dùng</span>
                  </div>
                  <p className="text-[10px] text-slate-500 leading-snug">
                    Che dải đen trên và dưới; nội dung gốc trong dải bị che khuất.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setCleanChineseMode('bottom_bar')}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                    cleanChineseMode === 'bottom_bar'
                      ? 'border-amber-600 bg-white ring-2 ring-amber-500/20 shadow-xs'
                      : 'border-amber-200/70 bg-white/70 hover:bg-white'
                  }`}
                >
                  <div className="text-xs font-bold text-slate-900 mb-1">🛡️ Chỉ Che Sub Đáy</div>
                  <p className="text-[10px] text-slate-500 leading-snug">
                    Chỉ che dải đen ở đáy để xóa sạch phụ đề Trung, giữ nguyên góc trên.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setCleanChineseMode('smart_blur')}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                    cleanChineseMode === 'smart_blur'
                      ? 'border-amber-600 bg-white ring-2 ring-amber-500/20 shadow-xs'
                      : 'border-amber-200/70 bg-white/70 hover:bg-white'
                  }`}
                >
                  <div className="text-xs font-bold text-slate-900 mb-1">🌫️ Làm Mờ (Blur)</div>
                  <p className="text-[10px] text-slate-500 leading-snug">
                    Làm nhòe/mờ logo góc trên và sub ở đáy, không dùng thanh đen.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setCleanChineseMode('cinema_zoom')}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                    cleanChineseMode === 'cinema_zoom'
                      ? 'border-amber-600 bg-white ring-2 ring-amber-500/20 shadow-xs'
                      : 'border-amber-200/70 bg-white/70 hover:bg-white'
                  }`}
                >
                  <div className="text-xs font-bold text-slate-900 mb-1">🔍 Phóng To Cắt Viền</div>
                  <p className="text-[10px] text-slate-500 leading-snug">
                    Zoom 108% đẩy sạch logo Bilibili và sub Trung ra ngoài khung hình.
                  </p>
                </button>
              </div>

              {/* Advanced Mask Sliders Toggle */}
              {cleanChineseMode === 'inpaint' && <VideoCleanupEditor
                source={project.dubbed_video_url || (project.local_video_path ? project.original_video_url : undefined)}
                value={cleanupOptions} onChange={setCleanupOptions} />}
              {cleanChineseMode !== 'none' && cleanChineseMode !== 'inpaint' && (
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={() => setShowAdvancedMask(!showAdvancedMask)}
                    className="text-[11px] text-amber-800 font-semibold hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <span>{showAdvancedMask ? '▲ Thu gọn điều chỉnh độ rộng dải che' : '▼ Tùy chỉnh độ cao dải che (Sub to / Logo cao)'}</span>
                  </button>

                  {showAdvancedMask && (
                    <div className="mt-2.5 p-3 rounded-xl bg-white/80 border border-amber-200/80 space-y-3 animate-in fade-in">
                      <div className="space-y-1">
                        <div className="flex justify-between text-[11px] font-semibold text-slate-700">
                          <span>Độ cao dải che phụ đề ở đáy:</span>
                          <span className="text-amber-700 font-bold">{bottomMaskPct}% chiều cao</span>
                        </div>
                        <input
                          aria-label="Chiều cao dải dưới (%)"
                          type="range"
                          min={0}
                          max={35}
                          step={1}
                          value={bottomMaskPct}
                          onChange={(e) => setBottomMaskPct(parseInt(e.target.value))}
                          className="w-full accent-amber-600"
                        />
                        <div className="flex justify-between text-[9px] text-slate-400">
                          <span>10% (Sub nhỏ)</span>
                          <span>16% (Tiêu chuẩn Bilibili)</span>
                          <span>24% (Sub 2 dòng to)</span>
                        </div>
                      </div>

                      {(['white_bars', 'cinema_bars', 'smart_blur', 'cinema_zoom'].includes(cleanChineseMode)) && (
                        <div className="space-y-1 pt-1 border-t border-amber-100">
                          <div className="flex justify-between text-[11px] font-semibold text-slate-700">
                            <span>Độ cao dải che logo/watermark ở trên:</span>
                            <span className="text-amber-700 font-bold">{topMaskPct}% chiều cao</span>
                          </div>
                          <input
                            aria-label="Chiều cao dải trên (%)"
                            type="range"
                            min={0}
                            max={28}
                            step={1}
                            value={topMaskPct}
                            onChange={(e) => setTopMaskPct(parseInt(e.target.value))}
                            className="w-full accent-amber-600"
                          />
                          <div className="flex justify-between text-[9px] text-slate-400">
                            <span>6% (Logo nhỏ)</span>
                            <span>11% (Tiêu chuẩn Bilibili)</span>
                            <span>18% (Banner cao)</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">Kiểu Dáng Phụ Đề Xuất Bản:</h4>

            {/* Presets */}
            <div className="grid grid-cols-3 gap-2">
              <button type="button" aria-pressed={subtitlePreset === 'comic'} onClick={() => setSubtitlePreset('comic')}
                className={`col-span-3 rounded-xl border p-3 text-left ${subtitlePreset === 'comic' ? 'border-indigo-600 bg-indigo-50 ring-2 ring-indigo-500/20' : 'border-slate-200 hover:bg-slate-50'}`}>
                <strong className="text-sm text-slate-900">Chữ theo mẫu — đậm nghiêng, viền đen</strong>
                <p className="mt-1 text-[11px] text-slate-600">Chữ trắng in hoa, dáng hẹp. Bản dịch đã lưu giữ nguyên nội dung.</p>
              </button>
              <button
                type="button"
                onClick={() => setSubtitlePreset('cinema')}
                className={`p-3 rounded-2xl border text-left transition-all cursor-pointer ${
                  subtitlePreset === 'cinema'
                    ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                    : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="text-base mb-1">🎬</div>
                <div className="text-xs font-bold text-slate-900">Điện Ảnh</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Trắng viền đổ bóng</div>
              </button>

              <button
                type="button"
                onClick={() => setSubtitlePreset('yellow_highlight')}
                className={`p-3 rounded-2xl border text-left transition-all cursor-pointer ${
                  subtitlePreset === 'yellow_highlight'
                    ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                    : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="text-base mb-1">🌟</div>
                <div className="text-xs font-bold text-slate-900">Vlog Nổi Bật</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Chữ vàng viền nét</div>
              </button>

              <button
                type="button"
                onClick={() => setSubtitlePreset('box_banner')}
                className={`p-3 rounded-2xl border text-left transition-all cursor-pointer ${
                  subtitlePreset === 'box_banner'
                    ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                    : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="text-base mb-1">🛡️</div>
                <div className="text-xs font-bold text-slate-900">Hộp Đen Nền</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Nền đen mờ bao chữ</div>
              </button>
            </div>

            {/* Checkbox Options */}
            <div className="space-y-2 bg-slate-50 p-3.5 rounded-2xl border border-slate-200/80">
              <label className="flex items-center justify-between text-xs cursor-pointer">
                <div>
                  <span className="font-bold text-slate-800">Phụ đề Song Ngữ (Dual Subtitles)</span>
                  <p className="text-[11px] text-slate-500">Hiển thị tiếng gốc phía trên và tiếng Việt phía dưới</p>
                </div>
                <input
                  type="checkbox"
                  checked={bilingual}
                  onChange={(e) => setBilingual(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300"
                />
              </label>
            </div>
          </div>
        )}

        {((cuesCount !== undefined ? cuesCount : (project.cue_count || 0)) === 0) && (
          <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 font-medium flex items-center space-x-2">
            <span>⚠️</span>
            <span>Dự án chưa có phụ đề. Vui lòng bấm <strong>&quot;🚀 Nhận diện &amp; Dịch AI&quot;</strong> trước khi Burn Video!</span>
          </div>
        )}

        {/* Completed Downloads */}
        {isCompleted ? (
          <div className="space-y-3">
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center gap-2 text-xs font-bold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Video đã được render và đóng gói hoàn chỉnh thành công!</span>
            </div>

            <button onClick={() => setConfigureAgain(true)} className="rounded-lg border p-2 text-sm">Render lại với cấu hình khác</button>
            {project.settings_override?.clean_chinese_mode === 'inpaint' && project.settings_override?.mask_original_sub !== false &&
              <CleanupQualitySummary projectId={project.id} outputUrl={project.burned_video_url} />}
            <div className="grid grid-cols-2 gap-2">
              <a
                href={project.burned_video_url}
                download
                className="flex items-center justify-center gap-2 p-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-700 text-white text-xs font-bold shadow-md shadow-indigo-500/20 transition-all"
              >
                <Video className="w-4 h-4" />
                <span>Tải Video Hoàn Chỉnh (.MP4)</span>
              </a>

              <a
                href={api.getExportUrl(project.id, 'ass', {preset: resolveBurnPresentation(project.settings_override).subtitle_preset,
                  bilingual: resolveBurnPresentation(project.settings_override).bilingual})}
                download
                className="flex items-center justify-center gap-2 p-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold border border-slate-200 transition-colors"
              >
                <FileText className="w-4 h-4" />
                <span>Tải Phụ Đề .ASS</span>
              </a>
            </div>
          </div>
        ) : (
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors cursor-pointer"
            >
              Hủy
            </button>
            <button
              onClick={handleStart}
              disabled={isBurning || ((cuesCount !== undefined ? cuesCount : (project.cue_count || 0)) === 0)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-600 hover:to-rose-600 text-white text-xs font-bold shadow-md shadow-rose-500/20 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
            >
              {isBurning ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Đang Render Phụ Đề GPU...
                </>
              ) : ((cuesCount !== undefined ? cuesCount : (project.cue_count || 0)) === 0) ? (
                <span>⚠️ Chưa có phụ đề để Burn</span>
              ) : (
                <>
                  <Flame className="w-4 h-4" /> Bắt Đầu Burn Video
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
