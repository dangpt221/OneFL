'use client';

import { useState, useMemo, useDeferredValue, useEffect, useRef } from 'react';
import {
  Play,
  Sparkles,
  Check,
  Search,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Zap,
  CheckSquare,
  Square,
  SlidersHorizontal,
} from 'lucide-react';
import { SubtitleCue, SpeakerProfile } from '@/lib/types';
import { api } from '@/lib/api';

interface SubtitleEditorProps {
  projectId: string;
  cues: SubtitleCue[];
  speakers?: SpeakerProfile[];
  currentTime: number;
  onSeek: (time: number) => void;
  onCueUpdated: (cue: SubtitleCue) => void;
  onRetranslateRequested: (cueIds: string[]) => void;
}

export default function SubtitleEditor({
  projectId,
  cues,
  speakers = [],
  currentTime,
  onSeek,
  onCueUpdated,
  onRetranslateRequested,
}: SubtitleEditorProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const deferredSearchTerm = useDeferredValue(searchTerm);

  const [selectedSpeakerFilter, setSelectedSpeakerFilter] = useState<string>('ALL');
  const [selectedCueIds, setSelectedCueIds] = useState<string[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Performance Pagination state
  const [pageSize, setPageSize] = useState<number>(50);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [jumpPageInput, setJumpPageInput] = useState<string>('');
  const [jumpCueInput, setJumpCueInput] = useState<string>('');
  const [autoFollowVideo, setAutoFollowVideo] = useState<boolean>(true);

  const listContainerRef = useRef<HTMLDivElement>(null);
  const activeCardRef = useRef<HTMLDivElement>(null);

  const allSpeakerTags = useMemo(() => {
    return Array.from(new Set(cues.map(c => c.speaker_tag).filter(Boolean)));
  }, [cues]);

  const formatTimestamp = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    const ms = Math.floor((secs % 1) * 10);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms}`;
  };

  const handleStartEdit = (cue: SubtitleCue) => {
    setEditingId(cue.id);
    setEditText(cue.translated_text || cue.original_text);
  };

  const handleSaveEdit = async (cue: SubtitleCue) => {
    if (editText === cue.translated_text) {
      setEditingId(null);
      return;
    }

    setIsSaving(true);
    try {
      const updated = await api.updateCue(projectId, cue.id, {
        translated_text: editText,
      });
      onCueUpdated(updated);
      setEditingId(null);
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleSelectCue = (id: string) => {
    setSelectedCueIds(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  // Filter cues efficiently
  const filteredCues = useMemo(() => {
    return cues.filter(c => {
      if (selectedSpeakerFilter !== 'ALL' && c.speaker_tag !== selectedSpeakerFilter) {
        return false;
      }
      if (!deferredSearchTerm) return true;
      const term = deferredSearchTerm.toLowerCase();
      return (
        c.original_text.toLowerCase().includes(term) ||
        (c.translated_text && c.translated_text.toLowerCase().includes(term)) ||
        c.speaker_tag.toLowerCase().includes(term)
      );
    });
  }, [cues, selectedSpeakerFilter, deferredSearchTerm]);

  const totalPages = Math.max(1, Math.ceil(filteredCues.length / pageSize));

  // Ensure current page is valid when filters change
  useEffect(() => {
    setCurrentPage(prev => Math.min(prev, totalPages));
  }, [totalPages]);

  // Paginated slice for buttery-smooth 60fps DOM performance
  const paginatedCues = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredCues.slice(start, start + pageSize);
  }, [filteredCues, currentPage, pageSize]);

  // Find currently active cue index
  const activeCueIndex = useMemo(() => {
    return filteredCues.findIndex(
      c => currentTime >= c.start_time && currentTime <= c.end_time
    );
  }, [filteredCues, currentTime]);

  // Auto-follow video playhead to current page
  useEffect(() => {
    if (!autoFollowVideo || activeCueIndex === -1) return;
    const targetPage = Math.floor(activeCueIndex / pageSize) + 1;
    if (targetPage !== currentPage) {
      setCurrentPage(targetPage);
    }
  }, [activeCueIndex, autoFollowVideo, pageSize, currentPage]);

  // Scroll active cue into view inside current page
  useEffect(() => {
    if (activeCardRef.current && autoFollowVideo) {
      activeCardRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
  }, [activeCueIndex, autoFollowVideo]);

  const handlePageChange = (newPage: number) => {
    const clamped = Math.max(1, Math.min(totalPages, newPage));
    setCurrentPage(clamped);
    if (listContainerRef.current) {
      listContainerRef.current.scrollTop = 0;
    }
  };

  const handleJumpToPage = (e: React.FormEvent) => {
    e.preventDefault();
    const p = parseInt(jumpPageInput, 10);
    if (!isNaN(p)) {
      handlePageChange(p);
      setJumpPageInput('');
    }
  };

  const handleJumpToCue = (e: React.FormEvent) => {
    e.preventDefault();
    const idxNum = parseInt(jumpCueInput, 10);
    if (!isNaN(idxNum)) {
      const matchIndex = filteredCues.findIndex(c => c.cue_index === idxNum);
      if (matchIndex !== -1) {
        const targetPage = Math.floor(matchIndex / pageSize) + 1;
        handlePageChange(targetPage);
        onSeek(filteredCues[matchIndex].start_time);
        setJumpCueInput('');
      }
    }
  };

  const isCurrentPageAllSelected = useMemo(() => {
    if (paginatedCues.length === 0) return false;
    return paginatedCues.every(c => selectedCueIds.includes(c.id));
  }, [paginatedCues, selectedCueIds]);

  const toggleSelectCurrentPage = () => {
    const pageIds = paginatedCues.map(c => c.id);
    if (isCurrentPageAllSelected) {
      setSelectedCueIds(prev => prev.filter(id => !pageIds.includes(id)));
    } else {
      setSelectedCueIds(prev => Array.from(new Set([...prev, ...pageIds])));
    }
  };

  const toggleSelectAll = () => {
    if (selectedCueIds.length === cues.length) {
      setSelectedCueIds([]);
    } else {
      setSelectedCueIds(cues.map(c => c.id));
    }
  };

  return (
    <div className="bg-white rounded-3xl p-5 flex flex-col h-full border border-slate-200 shadow-sm overflow-hidden">
      {/* Top Search, Speaker Filter, and Batch Bar */}
      <div className="space-y-3 mb-3 pb-3 border-b border-slate-100 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Search Input with Debounce */}
          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
            <div className="relative w-full">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Tìm phụ đề, dịch thuật hoặc nhân vật (#câu, từ khóa)..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-900 placeholder:text-slate-400 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white transition-colors"
              />
            </div>
          </div>

          {/* Action & Stats Buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-slate-500 font-semibold px-2.5 py-1 bg-slate-100 rounded-lg">
              {filteredCues.length} / {cues.length} câu
            </span>

            {selectedCueIds.length > 0 && (
              <button
                onClick={() => onRetranslateRequested(selectedCueIds)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 text-white text-xs font-bold shadow-sm transition-all hover:opacity-95"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Dịch Lại ({selectedCueIds.length})</span>
              </button>
            )}

            <button
              onClick={toggleSelectCurrentPage}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium transition-colors border border-slate-200"
              title="Chọn/bỏ chọn tất cả 50 câu trên trang hiện tại"
            >
              {isCurrentPageAllSelected ? (
                <CheckSquare className="w-3.5 h-3.5 text-indigo-600" />
              ) : (
                <Square className="w-3.5 h-3.5 text-slate-400" />
              )}
              <span>Trang này</span>
            </button>

            <button
              onClick={toggleSelectAll}
              className="px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium transition-colors border border-slate-200"
            >
              {selectedCueIds.length === cues.length ? 'Bỏ chọn hết' : 'Chọn tất cả'}
            </button>
          </div>
        </div>

        {/* Speaker Filter Pills */}
        {allSpeakerTags.length > 1 && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
            <span className="text-[11px] font-semibold text-slate-400 shrink-0">Nhân vật:</span>
            <button
              onClick={() => setSelectedSpeakerFilter('ALL')}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                selectedSpeakerFilter === 'ALL'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              Tất cả ({cues.length})
            </button>
            {allSpeakerTags.map((tag) => {
              const spk = speakers.find((s) => s.speaker_tag === tag);
              const count = cues.filter(c => c.speaker_tag === tag).length;
              return (
                <button
                  key={tag}
                  onClick={() => setSelectedSpeakerFilter(tag)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors shrink-0 flex items-center gap-1.5 ${
                    selectedSpeakerFilter === tag
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {spk?.avatar_color && (
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: spk.avatar_color }}
                    />
                  )}
                  <span>{spk?.display_name || tag}</span>
                  <span className="text-[10px] opacity-75 font-mono">({count})</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Subtitles Scrollable Table - Virtualized to current page only */}
      <div
        ref={listContainerRef}
        className="flex-1 overflow-y-auto pr-1 space-y-2.5 min-h-[300px]"
      >
        {paginatedCues.length === 0 ? (
          <div className="text-center py-16 text-slate-400">
            <MessageSquare className="w-10 h-10 mx-auto mb-2 opacity-30 text-indigo-500" />
            <p className="text-xs font-medium text-slate-500">Không tìm thấy câu phụ đề nào phù hợp</p>
          </div>
        ) : (
          paginatedCues.map((cue) => {
            const isActive = currentTime >= cue.start_time && currentTime <= cue.end_time;
            const isSelected = selectedCueIds.includes(cue.id);

            return (
              <div
                key={cue.id}
                ref={isActive ? activeCardRef : undefined}
                className={`p-3.5 rounded-2xl transition-all border ${
                  isActive
                    ? 'bg-indigo-50/90 border-indigo-400 shadow-md ring-2 ring-indigo-200/50'
                    : isSelected
                    ? 'bg-indigo-50/30 border-indigo-300 shadow-xs'
                    : 'bg-white hover:bg-slate-50/80 border-slate-200 shadow-2xs'
                }`}
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  {/* Checkbox, Index & Time */}
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelectCue(cue.id)}
                      className="w-3.5 h-3.5 rounded bg-white border-slate-300 text-indigo-600 focus:ring-0 cursor-pointer"
                    />
                    <button
                      onClick={() => onSeek(cue.start_time)}
                      className={`flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-lg border transition-colors font-bold ${
                        isActive
                          ? 'bg-indigo-600 text-white border-indigo-700 shadow-xs'
                          : 'text-indigo-700 hover:text-indigo-900 bg-indigo-50 hover:bg-indigo-100 border-indigo-200/60'
                      }`}
                      title="Nhảy đến đoạn này trên video"
                    >
                      <Play className="w-2.5 h-2.5 fill-current" />
                      <span>{formatTimestamp(cue.start_time)}</span>
                    </button>
                    <span className="text-[10px] text-slate-400 font-bold font-mono">
                      #{cue.cue_index}
                    </span>
                    {isActive && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-indigo-600 text-white animate-pulse">
                        Đang phát
                      </span>
                    )}
                  </div>

                  {/* Speaker & CPS Badges */}
                  <div className="flex items-center gap-2">
                    {/* Character Tag / Interactive Selector */}
                    {(() => {
                      const curSpk = speakers.find((s) => s.speaker_tag === cue.speaker_tag);
                      const curColor = curSpk?.avatar_color || '#6366f1';
                      const curName = curSpk?.display_name || cue.speaker_tag;

                      return (
                        <div className="relative flex items-center">
                          <span
                            className="w-2 h-2 rounded-full absolute left-2 pointer-events-none z-10"
                            style={{ backgroundColor: curColor }}
                          />
                          <select
                            value={cue.speaker_tag}
                            onChange={async (e) => {
                              const newTag = e.target.value;
                              try {
                                const updated = await api.updateCue(projectId, cue.id, { speaker_tag: newTag });
                                onCueUpdated(updated);
                              } catch (err) {
                                console.error(err);
                              }
                            }}
                            className="appearance-none pl-5 pr-3 py-0.5 rounded-lg text-[10px] font-bold bg-slate-100 hover:bg-indigo-50 text-slate-800 border border-slate-200 hover:border-indigo-300 transition-colors cursor-pointer focus:outline-none"
                            title="Nhấp để đổi nhân vật phát ngôn cho câu thoại này"
                          >
                            {speakers.length > 0 ? (
                              speakers.map((s) => (
                                <option key={s.speaker_tag} value={s.speaker_tag}>
                                  {s.display_name} ({s.speaker_tag})
                                </option>
                              ))
                            ) : (
                              <option value={cue.speaker_tag}>{curName}</option>
                            )}
                          </select>
                        </div>
                      );
                    })()}

                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        cue.cps > 20
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : cue.cps > 17
                          ? 'bg-amber-50 text-amber-700 border border-amber-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                      title={`Tốc độ đọc: ${cue.cps} ký tự/giây`}
                    >
                      {cue.cps} CPS
                    </span>
                  </div>
                </div>

                {/* Text Content Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  {/* Original Text */}
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-800">
                    <span className="text-[9px] uppercase tracking-wider text-slate-400 font-bold block mb-1">
                      Lời gốc (ASR)
                    </span>
                    <p className="leading-relaxed font-medium">{cue.original_text}</p>
                  </div>

                  {/* Translated Text (Editable) */}
                  <div className="p-2.5 rounded-xl bg-indigo-50/40 border border-indigo-200 text-slate-900">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] uppercase tracking-wider text-indigo-700 font-bold">
                        Bản Dịch Tiếng Việt
                      </span>
                      {cue.is_edited && (
                        <span className="text-[9px] text-indigo-600 font-bold flex items-center gap-1">
                          <Check className="w-2.5 h-2.5" /> Đã chỉnh
                        </span>
                      )}
                    </div>

                    {editingId === cue.id ? (
                      <div className="space-y-2">
                        <textarea
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          rows={2}
                          className="w-full p-2 rounded-lg bg-white border border-indigo-500 text-slate-900 text-xs focus:outline-none shadow-xs"
                          autoFocus
                        />
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => setEditingId(null)}
                            className="px-2 py-1 rounded bg-slate-100 text-[10px] text-slate-600 hover:text-slate-900"
                          >
                            Hủy
                          </button>
                          <button
                            onClick={() => handleSaveEdit(cue)}
                            disabled={isSaving}
                            className="px-2.5 py-1 rounded bg-indigo-600 text-[10px] font-bold text-white hover:bg-indigo-700"
                          >
                            Lưu
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p
                        onClick={() => handleStartEdit(cue)}
                        className="leading-relaxed cursor-pointer hover:text-indigo-600 transition-colors whitespace-pre-line font-medium"
                        title="Bấm để chỉnh sửa bản dịch câu này"
                      >
                        {cue.translated_text || (
                          <span className="text-slate-400 italic">Nhấp để nhập lời dịch...</span>
                        )}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* High Performance Pagination & Jump Bar */}
      <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3 shrink-0 text-xs">
        {/* Page Switcher Buttons */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => handlePageChange(1)}
            disabled={currentPage === 1}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
            title="Về trang đầu"
          >
            <ChevronsLeft className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
            title="Trang trước"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          <div className="flex items-center px-2 py-1 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 font-mono">
            Trang <span className="text-indigo-600 mx-1 font-bold">{currentPage}</span> / {totalPages}
          </div>

          <button
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
            title="Trang sau"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handlePageChange(totalPages)}
            disabled={currentPage >= totalPages}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
            title="Đến trang cuối"
          >
            <ChevronsRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Quick Jump & Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Jump to Cue Number */}
          <form onSubmit={handleJumpToCue} className="flex items-center gap-1">
            <span className="text-[11px] text-slate-400 font-medium">Câu:</span>
            <input
              type="text"
              placeholder="#100"
              value={jumpCueInput}
              onChange={(e) => setJumpCueInput(e.target.value)}
              className="w-14 px-2 py-1 text-center font-mono text-xs rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              className="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-[10px] font-semibold text-slate-700 transition-colors"
            >
              Nhảy
            </button>
          </form>

          {/* Jump to Page Number */}
          <form onSubmit={handleJumpToPage} className="flex items-center gap-1">
            <span className="text-[11px] text-slate-400 font-medium">Trang:</span>
            <input
              type="text"
              placeholder="1"
              value={jumpPageInput}
              onChange={(e) => setJumpPageInput(e.target.value)}
              className="w-12 px-2 py-1 text-center font-mono text-xs rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              className="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-[10px] font-semibold text-slate-700 transition-colors"
            >
              Đi
            </button>
          </form>

          {/* Page Size Select */}
          <div className="flex items-center gap-1 border-l border-slate-200 pl-2">
            <SlidersHorizontal className="w-3 h-3 text-slate-400" />
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="px-2 py-1 rounded-lg border border-slate-200 bg-slate-50 text-[11px] font-medium text-slate-700 focus:outline-none cursor-pointer"
              title="Số câu hiển thị trên 1 trang"
            >
              <option value={25}>25 / trang</option>
              <option value={50}>50 / trang</option>
              <option value={100}>100 / trang</option>
              <option value={200}>200 / trang</option>
            </select>
          </div>

          {/* Auto Follow Toggle */}
          <button
            onClick={() => setAutoFollowVideo(!autoFollowVideo)}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-colors ${
              autoFollowVideo
                ? 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
                : 'bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200'
            }`}
            title="Tự động lật trang và cuộn đến câu thoại đang phát theo video"
          >
            <Zap className={`w-3 h-3 ${autoFollowVideo ? 'fill-amber-500 text-amber-500' : ''}`} />
            <span>{autoFollowVideo ? 'Bám video: Bật' : 'Bám video: Tắt'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
