'use client';

import { useState } from 'react';
import { X, Flame, CheckCircle2, Loader2, Video, FileText } from 'lucide-react';
import { Project } from '@/lib/types';
import { api } from '@/lib/api';
import { getFriendlyStageName } from '@/components/PipelineProgressTracker';

interface BurnProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: Project;
  onBurnStarted: (options?: { subtitle_preset?: string; bilingual?: boolean; mask_original_sub?: boolean }) => void;
  cuesCount?: number;
}

export default function BurnProgressModal({
  isOpen,
  onClose,
  project,
  onBurnStarted,
  cuesCount,
}: BurnProgressModalProps) {
  const existingCfg = project.settings_override || {};
  const [subtitlePreset, setSubtitlePreset] = useState<string>(existingCfg.subtitle_preset || 'box_banner');
  const [bilingual, setBilingual] = useState<boolean>(existingCfg.bilingual || false);
  const [maskOriginalSub, setMaskOriginalSub] = useState<boolean>(existingCfg.mask_original_sub !== false);

  if (!isOpen) return null;

  const isBurning = project.status === 'BURNING';
  const isCompleted = project.status === 'COMPLETED' && !!project.burned_video_url;

  const handleStart = () => {
    onBurnStarted({
      subtitle_preset: subtitlePreset,
      bilingual: bilingual,
      mask_original_sub: maskOriginalSub
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-white w-full max-w-lg rounded-3xl p-6 relative border border-slate-200 shadow-2xl space-y-5 max-h-[92vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
            <Flame className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-heading font-bold text-xl text-slate-900">Video Subtitle Burner</h3>
            <p className="text-xs text-slate-500">Render phụ đề cứng & Tự động tăng tốc GPU (NVENC/QSV/AMF).</p>
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

        {/* Burn Style & Presentation Customizer (Only shown before burning starts) */}
        {!isBurning && !isCompleted && (
          <div className="space-y-4 pt-1">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">Tùy Chọn Kiểu Dáng Xuất Bản:</h4>

            {/* Presets */}
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setSubtitlePreset('box_banner')}
                className={`p-3 rounded-2xl border text-left transition-all ${
                  subtitlePreset === 'box_banner'
                    ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                    : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="text-base mb-1">🛡️</div>
                <div className="text-xs font-bold text-slate-900">Hộp Đen Mờ</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Che sạch sub cũ</div>
              </button>

              <button
                type="button"
                onClick={() => setSubtitlePreset('cinema')}
                className={`p-3 rounded-2xl border text-left transition-all ${
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
                className={`p-3 rounded-2xl border text-left transition-all ${
                  subtitlePreset === 'yellow_highlight'
                    ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                    : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="text-base mb-1">🌟</div>
                <div className="text-xs font-bold text-slate-900">Vlog Nổi Bật</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Chữ vàng viền nét</div>
              </button>
            </div>

            {/* Checkbox Options */}
            <div className="space-y-2.5 bg-slate-50 p-3.5 rounded-2xl border border-slate-200/80">
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

              <div className="border-t border-slate-200/60" />

              <label className="flex items-center justify-between text-xs cursor-pointer">
                <div>
                  <span className="font-bold text-slate-800">Dải Đen Che Phụ Đề Gốc</span>
                  <p className="text-[11px] text-slate-500">Tạo dải nền tinh tế che 100% chữ hardsub cũ của video</p>
                </div>
                <input
                  type="checkbox"
                  checked={maskOriginalSub}
                  onChange={(e) => setMaskOriginalSub(e.target.checked)}
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
                href={api.getExportUrl(project.id, 'ass')}
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
