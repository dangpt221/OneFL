'use client';

import { useState } from 'react';
import { X, UploadCloud, Video, Sparkles, Loader2, FileCheck, Link as LinkIcon, Globe, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newProjectId: string) => void;
}

export default function CreateProjectModal({ isOpen, onClose, onSuccess }: CreateProjectModalProps) {
  const [sourceType, setSourceType] = useState<'upload' | 'bilibili'>('bilibili');
  
  // Form fields
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [sourceLanguage, setSourceLanguage] = useState('zh');
  const [targetLanguage, setTargetLanguage] = useState('vi');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  
  // Bilibili URL fields
  const [videoUrl, setVideoUrl] = useState('');
  const [isInspectingUrl, setIsInspectingUrl] = useState(false);
  const [urlInfo, setUrlInfo] = useState<any | null>(null);
  
  const [autoStart, setAutoStart] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      if (!title) {
        setTitle(file.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const handleUrlBlurOrPaste = async (urlToInspect: string) => {
    const trimmed = urlToInspect.trim();
    if (!trimmed || (!trimmed.startsWith('http://') && !trimmed.startsWith('https://'))) {
      return;
    }

    setIsInspectingUrl(true);
    setErrorMessage(null);

    try {
      const info = await api.inspectUrlInfo(trimmed);
      if (info && info.success) {
        setUrlInfo(info);
        if (!title || title === 'Bilibili Video') {
          setTitle(info.title || 'Bilibili Video');
        }
        if (info.suggested_source_language) {
          setSourceLanguage(info.suggested_source_language);
        }
      }
    } catch (err: any) {
      console.warn('Could not inspect url:', err);
    } finally {
      setIsInspectingUrl(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (sourceType === 'bilibili') {
      if (!videoUrl.trim()) {
        setErrorMessage('Vui lòng nhập đường link video Bilibili (ví dụ: https://www.bilibili.com/video/BV... hoặc b23.tv)');
        return;
      }
    } else {
      if (!title.trim() && !selectedFile) {
        setErrorMessage('Vui lòng nhập tên dự án hoặc chọn file video');
        return;
      }
    }

    setIsLoading(true);

    try {
      if (sourceType === 'bilibili') {
        // Create project directly from URL
        const project = await api.createProjectFromUrl({
          url: videoUrl.trim(),
          title: title.trim() || urlInfo?.title || 'Bilibili Video',
          source_language: sourceLanguage,
          target_language: targetLanguage,
          auto_start_pipeline: autoStart,
        });

        onSuccess(project.id);
        onClose();
      } else {
        // 1. Create project container
        const project = await api.createProject({
          title: title || selectedFile?.name?.replace(/\.[^/.]+$/, '') || 'Video Project',
          description,
          source_language: sourceLanguage,
          target_language: targetLanguage,
        });

        // 2. Upload video file if selected
        if (selectedFile) {
          await api.uploadVideo(project.id, selectedFile, autoStart);
        } else if (autoStart) {
          await api.triggerPipeline(project.id);
        }

        onSuccess(project.id);
        onClose();
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Lỗi khi tạo dự án dịch thuật');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-white w-full max-w-xl rounded-3xl p-6 relative border border-slate-200 shadow-2xl">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Title */}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600 shadow-xs">
            <Video className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-heading font-bold text-xl text-slate-900">Tạo Dự Án Dịch & Lồng Tiếng Video</h2>
            <p className="text-xs text-slate-500">Hỗ trợ tải video từ Bilibili, Douyin hoặc tải file lên từ máy tính.</p>
          </div>
        </div>

        {/* Source Type Tabs */}
        <div className="grid grid-cols-2 gap-2 p-1 bg-slate-100 rounded-2xl mb-5 border border-slate-200">
          <button
            type="button"
            onClick={() => {
              setSourceType('bilibili');
              setSourceLanguage('zh');
            }}
            className={`py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center space-x-2 transition-all ${
              sourceType === 'bilibili'
                ? 'bg-white text-indigo-700 shadow-xs ring-1 ring-slate-200'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>🇨🇳 Tải từ Link Bilibili</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-pink-100 text-pink-700 font-extrabold">Hot</span>
          </button>

          <button
            type="button"
            onClick={() => setSourceType('upload')}
            className={`py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center space-x-2 transition-all ${
              sourceType === 'upload'
                ? 'bg-white text-indigo-700 shadow-xs ring-1 ring-slate-200'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>📁 Tải File Từ Máy</span>
          </button>
        </div>

        {errorMessage && (
          <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs font-medium text-rose-700 flex items-center space-x-2">
            <span>⚠️</span>
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Bilibili URL Input */}
          {sourceType === 'bilibili' ? (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Đường dẫn link Bilibili (URL) *
                </label>
                <div className="relative">
                  <input
                    type="url"
                    value={videoUrl}
                    onChange={(e) => {
                      setVideoUrl(e.target.value);
                      handleUrlBlurOrPaste(e.target.value);
                    }}
                    onBlur={(e) => handleUrlBlurOrPaste(e.target.value)}
                    placeholder="https://www.bilibili.com/video/BV1... hoặc b23.tv/..."
                    className="w-full pl-9 pr-24 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-900 placeholder:text-slate-400 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-colors"
                    required
                  />
                  <LinkIcon className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  
                  <button
                    type="button"
                    onClick={() => handleUrlBlurOrPaste(videoUrl)}
                    disabled={isInspectingUrl || !videoUrl}
                    className="absolute right-1.5 top-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold border border-indigo-200 disabled:opacity-50"
                  >
                    {isInspectingUrl ? 'Đang đọc...' : 'Kiểm tra'}
                  </button>
                </div>
              </div>

              {/* URL Preview Info Card */}
              {urlInfo && urlInfo.success && (
                <div className="p-3 bg-indigo-50/70 border border-indigo-200 rounded-xl flex items-center space-x-3 text-slate-800">
                  <div className="w-16 h-12 bg-slate-200 rounded-lg overflow-hidden shrink-0 flex items-center justify-center border border-indigo-100">
                    {urlInfo.thumbnail ? (
                      <img src={urlInfo.thumbnail} alt="thumb" className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-xl">📺</span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold text-slate-900 line-clamp-1">{urlInfo.title}</p>
                    <p className="text-[11px] text-slate-600 mt-0.5">
                      Kênh: <strong>{urlInfo.uploader || 'Bilibili Creator'}</strong> • Thời lượng: {Math.round(urlInfo.duration || 0)}s
                    </p>
                  </div>
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                </div>
              )}
            </div>
          ) : (
            /* Upload Dropzone */
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Tệp Video hoặc Âm Thanh
              </label>
              <label className="flex flex-col items-center justify-center p-5 rounded-2xl border-2 border-dashed border-slate-300 hover:border-indigo-500 bg-slate-50 hover:bg-slate-100/80 cursor-pointer transition-all group">
                <input
                  type="file"
                  accept="video/*,audio/*,.mp4,.mkv,.mov,.mp3,.wav"
                  onChange={handleFileChange}
                  className="hidden"
                />
                {selectedFile ? (
                  <div className="flex items-center gap-3 text-emerald-600">
                    <FileCheck className="w-8 h-8" />
                    <div className="text-left">
                      <p className="text-sm font-bold text-slate-900">{selectedFile.name}</p>
                      <p className="text-xs text-slate-500">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                  </div>
                ) : (
                  <div className="text-center">
                    <UploadCloud className="w-8 h-8 text-indigo-600 mx-auto mb-2 group-hover:scale-110 transition-transform" />
                    <p className="text-sm text-slate-700 font-semibold">Bấm để chọn file hoặc kéo thả vào đây</p>
                    <p className="text-xs text-slate-500 mt-1">MP4, MKV, MOV, WAV, MP3</p>
                  </div>
                )}
              </label>
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Tên Dự Án (Tiêu Đề Video) *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={sourceType === 'bilibili' ? "Tự động lấy theo tên video Bilibili..." : "e.g. Review Phim Thần Thoại..."}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-900 placeholder:text-slate-400 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-colors"
              required={sourceType !== 'bilibili'}
            />
          </div>

          {/* Languages Selector */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Ngôn Ngữ Gốc (Source)
              </label>
              <select
                value={sourceLanguage}
                onChange={(e) => setSourceLanguage(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-900 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-colors font-medium"
              >
                <option value="zh">🇨🇳 Tiếng Trung (中文 - Bilibili / Douyin)</option>
                <option value="en">🇺🇸 Tiếng Anh (English)</option>
                <option value="ja">🇯🇵 Tiếng Nhật (日本語)</option>
                <option value="ko">🇰🇷 Tiếng Hàn (한국어)</option>
                <option value="auto">🌐 Tự động nhận diện (Auto-detect)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Ngôn Ngữ Dịch (Target)
              </label>
              <select
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-900 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-colors font-bold text-indigo-700"
              >
                <option value="vi">🇻🇳 Tiếng Việt (Vietnamese)</option>
              </select>
            </div>
          </div>

          {/* Auto start checkbox */}
          <div className="flex items-center gap-3 pt-1">
            <input
              type="checkbox"
              id="autoStart"
              checked={autoStart}
              onChange={(e) => setAutoStart(e.target.checked)}
              className="w-4 h-4 rounded text-indigo-600 bg-white border-slate-300 focus:ring-indigo-500"
            />
            <label htmlFor="autoStart" className="text-xs text-slate-700 font-medium cursor-pointer">
              Tự động tải video, nhận diện giọng nói và dịch phụ đề AI ngay khi tạo
            </label>
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-700 hover:to-cyan-700 text-white text-xs font-bold shadow-md shadow-indigo-500/20 transition-all disabled:opacity-50 cursor-pointer"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{sourceType === 'bilibili' ? 'Đang Tải Video Bilibili...' : 'Đang Tạo Dự Án...'}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>{sourceType === 'bilibili' ? '🚀 Tải Video Bilibili & Bắt Đầu Dịch' : 'Bắt Đầu Dịch Thuật'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
