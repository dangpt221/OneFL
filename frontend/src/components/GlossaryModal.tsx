'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import {
  X, BookOpen, Trash2, Sparkles, Loader2, Download, Upload,
  Plus, Search, Check, FolderDown, Edit2, AlertCircle
} from 'lucide-react';
import { GlossaryTerm, GenrePresetSummary } from '@/lib/types';
import { api } from '@/lib/api';

interface GlossaryModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  terms: GlossaryTerm[];
  onUpdated: () => void;
}

const CATEGORIES: { id: string; label: string; color: string; bg: string; border: string }[] = [
  { id: 'all', label: 'Tất cả', color: 'text-slate-700', bg: 'bg-slate-100', border: 'border-slate-300' },
  { id: 'PROPER_NAME', label: 'Tên riêng', color: 'text-indigo-700', bg: 'bg-indigo-50', border: 'border-indigo-200' },
  { id: 'LOCATION', label: 'Địa danh / Tinh cầu', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  { id: 'WEAPON_MECHA', label: 'Cơ giáp / Vũ khí', color: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200' },
  { id: 'RANK_REALM', label: 'Cảnh giới / Cấp bậc', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200' },
  { id: 'ORGANIZATION', label: 'Tổ chức / Phe phái', color: 'text-purple-700', bg: 'bg-purple-50', border: 'border-purple-200' },
  { id: 'SLANG_IDIOM', label: 'Thành ngữ / Lóng', color: 'text-cyan-700', bg: 'bg-cyan-50', border: 'border-cyan-200' },
  { id: 'DO_NOT_TRANSLATE', label: 'Giữ nguyên / DNT', color: 'text-slate-600', bg: 'bg-slate-100', border: 'border-slate-300' },
];

export default function GlossaryModal({
  isOpen,
  onClose,
  projectId,
  terms,
  onUpdated,
}: GlossaryModalProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Add Term Form
  const [sourceTerm, setSourceTerm] = useState('');
  const [targetTerm, setTargetTerm] = useState('');
  const [category, setCategory] = useState('PROPER_NAME');
  const [contextNote, setContextNote] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  // States
  const [isExtracting, setIsExtracting] = useState(false);
  const [isApplyingPreset, setIsApplyingPreset] = useState(false);
  const [presets, setPresets] = useState<GenrePresetSummary[]>([]);
  const [showPresetMenu, setShowPresetMenu] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingData, setEditingData] = useState<Partial<GlossaryTerm>>({});

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      api.getGlossaryPresets(projectId).then(setPresets).catch(console.error);
    }
  }, [isOpen, projectId]);

  if (!isOpen) return null;

  // Filtered terms
  const filteredTerms = terms.filter((term) => {
    const matchesCategory = selectedCategory === 'all' || term.category === selectedCategory;
    const matchesSearch =
      !searchQuery.trim() ||
      term.source_term.toLowerCase().includes(searchQuery.toLowerCase()) ||
      term.target_term.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (term.context_note && term.context_note.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCategory && matchesSearch;
  });

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: terms.length };
    for (const t of terms) {
      counts[t.category] = (counts[t.category] || 0) + 1;
    }
    return counts;
  }, [terms]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceTerm.trim() || !targetTerm.trim()) return;

    setIsAdding(true);
    try {
      await api.addGlossaryTerm(projectId, {
        source_term: sourceTerm.trim(),
        target_term: targetTerm.trim(),
        category,
        context_note: contextNote.trim(),
      });
      setSourceTerm('');
      setTargetTerm('');
      setContextNote('');
      onUpdated();
    } catch (e) {
      console.error(e);
    } finally {
      setIsAdding(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteGlossaryTerm(projectId, id);
      onUpdated();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveEdit = async (id: string) => {
    try {
      await api.updateGlossaryTerm(projectId, id, editingData);
      setEditingId(null);
      setEditingData({});
      onUpdated();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAutoExtract = async () => {
    setIsExtracting(true);
    try {
      await api.autoExtractGlossary(projectId);
      onUpdated();
    } catch (e) {
      console.error(e);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleApplyPreset = async (presetKey: string) => {
    setIsApplyingPreset(true);
    try {
      await api.applyGlossaryPreset(projectId, presetKey, false);
      setShowPresetMenu(false);
      onUpdated();
    } catch (e) {
      console.error(e);
    } finally {
      setIsApplyingPreset(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      let termsToImport: any[] = [];

      if (file.name.endsWith('.json')) {
        const parsed = JSON.parse(text);
        termsToImport = parsed.terms || parsed;
      } else if (file.name.endsWith('.csv')) {
        const lines = text.split('\n');
        for (let i = 1; i < lines.length; i++) {
          const parts = lines[i].split(',');
          if (parts.length >= 2 && parts[0].trim()) {
            termsToImport.push({
              source_term: parts[0].trim(),
              target_term: parts[1].trim(),
              category: parts[2]?.trim() || 'general',
              context_note: parts[3]?.trim() || '',
            });
          }
        }
      }

      if (termsToImport.length > 0) {
        await api.importGlossary(projectId, termsToImport, false);
        onUpdated();
      }
    } catch (err) {
      console.error('Failed to parse import file:', err);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white w-full max-w-4xl rounded-3xl p-6 relative border border-slate-200 shadow-2xl max-h-[92vh] flex flex-col">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-start justify-between mb-5 pr-8">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-pink-50 border border-pink-200 flex items-center justify-center text-pink-600 shadow-xs">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-heading font-bold text-xl text-slate-900">
                  Từ Điển Thuật Ngữ Điện Ảnh
                </h2>
                <span className="px-2.5 py-0.5 rounded-full bg-pink-100 text-pink-700 text-xs font-bold border border-pink-200">
                  {terms.length} thuật ngữ
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Quy chuẩn dịch thuật bắt buộc & Thư viện thuật ngữ tái sử dụng cho nhiều bộ phim.
              </p>
            </div>
          </div>

          {/* Top Actions: Presets, Import, Export */}
          <div className="flex items-center gap-2">
            {/* Presets Button & Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowPresetMenu(!showPresetMenu)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-semibold transition-all shadow-xs"
              >
                <FolderDown className="w-3.5 h-3.5" />
                <span>Nạp Mẫu Thể Loại</span>
              </button>

              {showPresetMenu && (
                <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-2xl border border-slate-200 p-2 shadow-2xl z-50 animate-in fade-in">
                  <div className="px-2.5 py-1 text-[11px] font-bold uppercase text-slate-400">
                    Chọn bộ thư viện mẫu
                  </div>
                  <div className="space-y-1">
                    {presets.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => handleApplyPreset(p.id)}
                        disabled={isApplyingPreset}
                        className="w-full text-left px-3 py-2 rounded-xl hover:bg-slate-50 flex items-start gap-2.5 transition-colors"
                      >
                        <span className="text-lg">{p.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-bold text-slate-800 flex items-center justify-between">
                            <span>{p.name}</span>
                            <span className="text-[10px] text-indigo-600 font-semibold bg-indigo-50 px-1.5 py-0.5 rounded">
                              {p.term_count} từ
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                            {p.description}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Export Dropdown */}
            <a
              href={api.getGlossaryExportUrl(projectId, 'json')}
              download
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-all shadow-xs"
              title="Xuất từ điển ra file JSON"
            >
              <Download className="w-3.5 h-3.5 text-slate-500" />
              <span>Xuất JSON</span>
            </a>

            {/* Import Button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".json,.csv"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-all shadow-xs"
              title="Nhập từ điển từ file JSON/CSV"
            >
              <Upload className="w-3.5 h-3.5 text-slate-500" />
              <span>Nhập File</span>
            </button>
          </div>
        </div>

        {/* Category Tabs */}
        <div className="flex items-center gap-1.5 mb-3.5 overflow-x-auto pb-1 scrollbar-none">
          {CATEGORIES.map((cat) => {
            const count = categoryCounts[cat.id] || 0;
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedCategory(cat.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all border ${
                  isSelected
                    ? `${cat.bg} ${cat.color} ${cat.border} shadow-xs`
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                }`}
              >
                <span>{cat.label}</span>
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                    isSelected ? 'bg-white/80' : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search & AI Auto-extract Bar */}
        <div className="flex items-center gap-2 mb-3.5">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Tìm kiếm theo từ gốc, từ dịch tiếng Việt hoặc ghi chú..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-pink-500 shadow-xs"
            />
          </div>

          <button
            type="button"
            onClick={handleAutoExtract}
            disabled={isExtracting}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-pink-500 to-indigo-600 hover:from-pink-600 hover:to-indigo-700 text-white text-xs font-bold transition-all disabled:opacity-50 shadow-md shadow-pink-500/20 whitespace-nowrap"
          >
            {isExtracting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Đang quét kịch bản...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>AI Quét Toàn Phim</span>
              </>
            )}
          </button>
        </div>

        {/* Add Term Form */}
        <form onSubmit={handleAdd} className="p-3 rounded-2xl bg-slate-50 border border-slate-200 mb-3.5">
          <div className="grid grid-cols-12 gap-2">
            <div className="col-span-3">
              <input
                type="text"
                placeholder="Từ gốc (VD: 机甲 / Mecha)"
                value={sourceTerm}
                onChange={(e) => setSourceTerm(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-pink-500 shadow-xs"
                required
              />
            </div>
            <div className="col-span-3">
              <input
                type="text"
                placeholder="Bản dịch tiếng Việt chuẩn (VD: Cơ giáp)"
                value={targetTerm}
                onChange={(e) => setTargetTerm(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-pink-500 shadow-xs"
                required
              />
            </div>
            <div className="col-span-3">
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
              >
                <option value="PROPER_NAME">👤 Tên riêng</option>
                <option value="LOCATION">🌍 Địa danh / Tinh cầu</option>
                <option value="WEAPON_MECHA">⚔️ Cơ giáp / Vũ khí</option>
                <option value="RANK_REALM">🎖️ Cảnh giới / Cấp bậc</option>
                <option value="ORGANIZATION">🏛️ Tổ chức / Phe phái</option>
                <option value="SLANG_IDIOM">💬 Thành ngữ / Tiếng lóng</option>
                <option value="DO_NOT_TRANSLATE">🚫 Cấm dịch / DNT</option>
              </select>
            </div>
            <div className="col-span-2">
              <input
                type="text"
                placeholder="Ghi chú ngữ cảnh (tùy chọn)"
                value={contextNote}
                onChange={(e) => setContextNote(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none shadow-xs"
              />
            </div>
            <div className="col-span-1">
              <button
                type="submit"
                disabled={isAdding}
                className="w-full h-full flex items-center justify-center rounded-lg bg-pink-600 hover:bg-pink-700 text-white text-xs font-bold transition-colors disabled:opacity-50 shadow-xs"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </div>
        </form>

        {/* Terms Table / List */}
        <div className="flex-1 overflow-y-auto pr-1 space-y-2">
          {filteredTerms.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs flex flex-col items-center gap-2">
              <AlertCircle className="w-6 h-6 text-slate-300" />
              <span>Không tìm thấy thuật ngữ nào phù hợp.</span>
              <button
                type="button"
                onClick={() => handleApplyPreset('sci_fi_mecha')}
                className="text-xs text-indigo-600 font-bold underline mt-1"
              >
                Nạp nhanh 19 thuật ngữ mẫu Khoa Huyễn & Cơ Giáp
              </button>
            </div>
          ) : (
            filteredTerms.map((term) => {
              const isEditing = editingId === term.id;
              const catObj = CATEGORIES.find((c) => c.id === term.category) || CATEGORIES[1];

              return (
                <div
                  key={term.id}
                  className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-200 hover:border-pink-300 transition-all shadow-2xs group"
                >
                  <div className="flex items-center gap-4 flex-1 min-w-0 pr-4">
                    {/* Source & Target Term */}
                    <div className="min-w-[140px]">
                      <span className="text-xs font-bold text-slate-900">{term.source_term}</span>
                    </div>

                    <span className="text-slate-300 font-bold">→</span>

                    <div className="min-w-[150px]">
                      {isEditing ? (
                        <input
                          type="text"
                          value={editingData.target_term ?? term.target_term}
                          onChange={(e) =>
                            setEditingData({ ...editingData, target_term: e.target.value })
                          }
                          className="px-2 py-1 rounded bg-white border border-indigo-400 text-xs text-indigo-700 font-bold focus:outline-none"
                        />
                      ) : (
                        <span className="text-xs font-bold text-pink-600">{term.target_term}</span>
                      )}
                    </div>

                    {/* Category Badge */}
                    <span
                      className={`px-2.5 py-0.5 rounded-md text-[10px] font-bold border whitespace-nowrap ${catObj.bg} ${catObj.color} ${catObj.border}`}
                    >
                      {catObj.label}
                    </span>

                    {/* Context Note */}
                    <div className="flex-1 min-w-0">
                      {isEditing ? (
                        <input
                          type="text"
                          value={editingData.context_note ?? term.context_note ?? ''}
                          onChange={(e) =>
                            setEditingData({ ...editingData, context_note: e.target.value })
                          }
                          placeholder="Ghi chú ngữ cảnh..."
                          className="w-full px-2 py-1 rounded bg-white border border-slate-300 text-[11px] text-slate-700 focus:outline-none"
                        />
                      ) : term.context_note ? (
                        <p className="text-[11px] text-slate-500 truncate" title={term.context_note}>
                          {term.context_note}
                        </p>
                      ) : (
                        <span className="text-[11px] text-slate-300 italic">Không có ghi chú</span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    {isEditing ? (
                      <button
                        type="button"
                        onClick={() => handleSaveEdit(term.id)}
                        className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 transition-colors"
                        title="Lưu"
                      >
                        <Check className="w-4 h-4" />
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setEditingId(term.id);
                          setEditingData({
                            target_term: term.target_term,
                            context_note: term.context_note,
                          });
                        }}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors opacity-0 group-hover:opacity-100"
                        title="Chỉnh sửa nhanh"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => handleDelete(term.id)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
                      title="Xóa thuật ngữ"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-100 mt-3">
          <div className="text-xs text-slate-500">
            Hiển thị <span className="font-bold text-slate-900">{filteredTerms.length}</span> / {terms.length} thuật ngữ
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all shadow-md shadow-slate-900/10"
          >
            Đóng Studio
          </button>
        </div>
      </div>
    </div>
  );
}
