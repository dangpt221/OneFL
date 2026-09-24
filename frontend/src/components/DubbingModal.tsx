'use client';

import { api } from '@/lib/api';
import { Project, TTSVoice } from '@/lib/types';
import { useEffect, useRef, useState } from 'react';

interface DubbingModalProps {
  project: Project;
  isOpen: boolean;
  onClose: () => void;
  onDubbingStarted: () => void;
  cuesCount?: number;
}

export default function DubbingModal({ project, isOpen, onClose, onDubbingStarted, cuesCount }: DubbingModalProps) {
  const [voices, setVoices] = useState<TTSVoice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>(project.default_voice || 'vieneu-truc-ly');
  const [model, setModel] = useState<string>('tts-1');
  const [speed, setSpeed] = useState<number>(1.0);
  const [mixOriginal, setMixOriginal] = useState<boolean>(true);
  const [duckingVolume, setDuckingVolume] = useState<number>(0.18);

  const [isPlayingPreview, setIsPlayingPreview] = useState<boolean>(false);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadVoices();
    } else {
      stopAudio();
    }
  }, [isOpen]);

  const loadVoices = async () => {
    try {
      const data = await api.getTTSVoices();
      setVoices(data);
      if (!selectedVoice && data.length > 0) {
        setSelectedVoice(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load voices:', err);
    }
  };

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsPlayingPreview(false);
  };

  const handlePlayPreview = async (voiceId: string) => {
    try {
      setErrorMsg(null);
      if (isPlayingPreview && selectedVoice === voiceId) {
        stopAudio();
        return;
      }

      setPreviewLoading(true);
      const res = await api.previewTTSVoice(voiceId, speed);
      setPreviewLoading(false);

      if (res && res.preview_url) {
        setCurrentAudioUrl(res.preview_url);
        if (audioRef.current) {
          audioRef.current.src = res.preview_url;
          audioRef.current.play();
          setIsPlayingPreview(true);
        }
      }
    } catch (err: any) {
      setPreviewLoading(false);
      setErrorMsg('Không thể phát thử giọng nói. Vui lòng thử lại!');
    }
  };

  const handleStartDubbing = async () => {
    try {
      setIsSubmitting(true);
      setErrorMsg(null);
      stopAudio();

      await api.startProjectDubbing(project.id, {
        voice: selectedVoice,
        model: model,
        speed: speed,
        ducking_volume: duckingVolume,
        mix_original: mixOriginal
      });

      setIsSubmitting(false);
      onDubbingStarted();
      onClose();
    } catch (err: any) {
      setIsSubmitting(false);
      setErrorMsg(err.message || 'Lỗi khi kích hoạt lồng tiếng.');
    }
  };

  if (!isOpen) return null;

  const currentVoiceObj = voices.find(v => v.id === selectedVoice) || voices[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 overflow-y-auto">
      {/* Hidden audio element for previews */}
      <audio
        ref={audioRef}
        onEnded={() => setIsPlayingPreview(false)}
        onError={() => setIsPlayingPreview(false)}
      />

      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-xl shadow-xs">
              🎙️
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Lồng Tiếng AI (AI Video Dubbing)</h2>
              <p className="text-xs text-slate-500">Tự động lồng tiếng khớp mốc thời gian phụ đề cho video của bạn</p>
            </div>
          </div>
          <button
            onClick={() => { stopAudio(); onClose(); }}
            className="w-8 h-8 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600 flex items-center justify-center transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-slate-800">
          {errorMsg && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium flex items-center space-x-2">
              <span>⚠️</span>
              <span>{errorMsg}</span>
            </div>
          )}

          {((cuesCount !== undefined ? cuesCount : (project.cue_count || 0)) === 0) && (
            <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 font-medium flex items-center space-x-2">
              <span>⚠️</span>
              <span>Dự án chưa có câu thoại phụ đề nào. Vui lòng bấm <strong>&quot;🚀 Nhận diện &amp; Dịch AI&quot;</strong> tại thanh công cụ trước khi thực hiện lồng tiếng!</span>
            </div>
          )}

          {/* Voice Selection Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                <span>Chọn Giọng Đọc AI</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
                  {voices.length} giọng sẵn sàng
                </span>
              </label>

              {currentVoiceObj && (
                <button
                  type="button"
                  onClick={() => handlePlayPreview(currentVoiceObj.id)}
                  disabled={previewLoading}
                  className="px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 text-xs font-semibold flex items-center space-x-1.5 transition-all shadow-2xs cursor-pointer"
                >
                  {previewLoading ? (
                    <span className="inline-block animate-spin">⏳</span>
                  ) : isPlayingPreview ? (
                    <span>⏹️ Dừng nghe thử</span>
                  ) : (
                    <span>🔊 Nghe thử giọng</span>
                  )}
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-56 overflow-y-auto pr-1">
              {voices.map((v) => {
                const isSelected = selectedVoice === v.id;
                return (
                  <div
                    key={v.id}
                    onClick={() => setSelectedVoice(v.id)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer relative flex flex-col justify-between ${isSelected
                      ? 'border-indigo-600 bg-indigo-50/40 ring-2 ring-indigo-500/20 shadow-xs'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/70 bg-white'
                      }`}
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <div className="flex items-center space-x-2">
                          <input
                            type="radio"
                            name="voice_radio"
                            checked={isSelected}
                            onChange={() => setSelectedVoice(v.id)}
                            className="text-indigo-600 focus:ring-indigo-500"
                          />
                          <span className="text-sm font-bold text-slate-900">{v.name}</span>
                        </div>
                        {v.badge && (
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${v.recommended
                            ? 'bg-amber-100 text-amber-800 border border-amber-200'
                            : 'bg-slate-100 text-slate-600 border border-slate-200'
                            }`}>
                            {v.badge}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed pl-5">
                        {v.description}
                      </p>
                    </div>

                    <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 pl-5">
                      <span>{v.category}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedVoice(v.id);
                          handlePlayPreview(v.id);
                        }}
                        className="text-indigo-600 hover:text-indigo-800 font-semibold hover:underline flex items-center space-x-1"
                      >
                        <span>🔊 Thử giọng</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Review Phim Mode & Audio Mixing */}
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Chế Độ Hòa Âm (Audio Mixing)</h4>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label
                onClick={() => setMixOriginal(true)}
                className={`p-3 rounded-lg border flex items-start space-x-3 cursor-pointer transition-all ${mixOriginal
                  ? 'border-indigo-600 bg-white ring-2 ring-indigo-500/10 shadow-2xs'
                  : 'border-slate-200 bg-white/60 hover:bg-white'
                  }`}
              >
                <input
                  type="radio"
                  checked={mixOriginal}
                  onChange={() => setMixOriginal(true)}
                  className="mt-1 text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <div className="text-xs font-bold text-slate-900">🎬 Chuẩn Review Phim / Recap</div>
                  <div className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                    Giữ nhạc nền video gốc ở mức nhỏ (18%) và phủ giọng đọc AI lên trên rõ ràng.
                  </div>
                </div>
              </label>

              <label
                onClick={() => setMixOriginal(false)}
                className={`p-3 rounded-lg border flex items-start space-x-3 cursor-pointer transition-all ${!mixOriginal
                  ? 'border-indigo-600 bg-white ring-2 ring-indigo-500/10 shadow-2xs'
                  : 'border-slate-200 bg-white/60 hover:bg-white'
                  }`}
              >
                <input
                  type="radio"
                  checked={!mixOriginal}
                  onChange={() => setMixOriginal(false)}
                  className="mt-1 text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <div className="text-xs font-bold text-slate-900">🎙️ Chỉ Giọng Lồng Tiếng</div>
                  <div className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                    Tắt toàn bộ âm thanh gốc, chỉ phát giọng nói AI theo thời gian phụ đề.
                  </div>
                </div>
              </label>
            </div>

            {mixOriginal && (
              <div className="pt-2 flex items-center justify-between text-xs">
                <span className="text-slate-600 font-medium">Âm lượng nhạc nền video gốc:</span>
                <div className="flex items-center space-x-2">
                  <input
                    type="range"
                    min="0.05"
                    max="0.40"
                    step="0.01"
                    value={duckingVolume}
                    onChange={(e) => setDuckingVolume(parseFloat(e.target.value))}
                    className="w-32 accent-indigo-600"
                  />
                  <span className="font-bold text-slate-800 w-10 text-right">{Math.round(duckingVolume * 100)}%</span>
                </div>
              </div>
            )}
          </div>

          {/* Speed & Quality Settings */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs font-bold text-slate-700">Tốc độ đọc giọng AI:</label>
                <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                  {speed.toFixed(1)}x
                </span>
              </div>
              <input
                type="range"
                min="0.8"
                max="1.5"
                step="0.1"
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between text-[10px] text-slate-400 mt-1 font-medium">
                <span>0.8x (Chậm)</span>
                <span>1.0x (Tự nhiên)</span>
                <span>1.5x (Nhanh)</span>
              </div>
            </div>

            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1.5">Mô hình chất lượng:</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="tts-1">OpenAI TTS-1 (Tốc độ cao - Tiêu chuẩn)</option>
                <option value="tts-1-hd">OpenAI TTS-1 HD (Chất lượng phòng thu cao cấp)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <div className="text-xs text-slate-500">
            Tổng số câu lồng tiếng: <strong className="text-slate-800">{cuesCount !== undefined ? cuesCount : (project.cue_count || 0)} câu</strong>
          </div>

          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={() => { stopAudio(); onClose(); }}
              className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
            >
              Hủy bỏ
            </button>
            <button
              type="button"
              onClick={handleStartDubbing}
              disabled={isSubmitting || ((cuesCount !== undefined ? cuesCount : (project.cue_count || 0)) === 0)}
              className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm shadow-indigo-600/30 flex items-center space-x-2 transition-all disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <span className="inline-block animate-spin">⏳</span>
                  <span>Đang khởi chạy...</span>
                </>
              ) : ((cuesCount !== undefined ? cuesCount : (project.cue_count || 0)) === 0) ? (
                <span>⚠️ Chưa có phụ đề để lồng tiếng</span>
              ) : (
                <span>🎙️ Bắt Đầu Lồng Tiếng Ngay</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
