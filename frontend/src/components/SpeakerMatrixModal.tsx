'use client';

import { useState, useRef } from 'react';
import {
  X, Users, ArrowRight, Save, Plus, Trash2,
  Download, Upload, Sparkles, RefreshCw, FolderDown,
  Volume2, ShieldAlert, Check, Loader2, MessageSquare
} from 'lucide-react';
import { SpeakerProfile, RelationshipMatrix } from '@/lib/types';
import { api } from '@/lib/api';

interface SpeakerMatrixModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  speakers: SpeakerProfile[];
  relationships: RelationshipMatrix[];
  onUpdated: () => void;
}

export default function SpeakerMatrixModal({
  isOpen,
  onClose,
  projectId,
  speakers,
  relationships,
  onUpdated,
}: SpeakerMatrixModalProps) {
  const [activeTab, setActiveTab] = useState<'speakers' | 'relationships' | 'presets'>('speakers');
  const [editingSpeakers, setEditingSpeakers] = useState<SpeakerProfile[]>(speakers);
  const [editingRels, setEditingRels] = useState<RelationshipMatrix[]>(relationships);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isApplyingPreset, setIsApplyingPreset] = useState(false);
  const [isApplyingMatrix, setIsApplyingMatrix] = useState(false);
  const [matrixSuccessMsg, setMatrixSuccessMsg] = useState<string | null>(null);

  // New Speaker Form State
  const [showAddSpeaker, setShowAddSpeaker] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [newName, setNewName] = useState('');
  const [newOriginalName, setNewOriginalName] = useState('');
  const [newGender, setNewGender] = useState<'male' | 'female' | 'neutral' | 'unknown'>('male');
  const [newRole, setNewRole] = useState('');

  // New Relationship Form State
  const [showAddRel, setShowAddRel] = useState(false);
  const [newRelSource, setNewRelSource] = useState('');
  const [newRelTarget, setNewRelTarget] = useState('');
  const [newRelSelf, setNewRelSelf] = useState('');
  const [newRelTargetPronoun, setNewRelTargetPronoun] = useState('');
  const [newRelType, setNewRelType] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleSpeakerChange = (tag: string, field: keyof SpeakerProfile, value: any) => {
    setEditingSpeakers((prev) =>
      prev.map((s) => (s.speaker_tag === tag ? { ...s, [field]: value } : s))
    );
  };

  const handleRelChange = (source: string, target: string, field: keyof RelationshipMatrix, value: any) => {
    setEditingRels((prev) =>
      prev.map((r) =>
        r.source_speaker === source && r.target_speaker === target ? { ...r, [field]: value } : r
      )
    );
  };

  const handleAddSpeaker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTag.trim()) return;

    try {
      const created = await api.createSpeaker(projectId, {
        speaker_tag: newTag.trim().toUpperCase(),
        display_name: newName.trim() || newTag.trim(),
        original_name: newOriginalName.trim(),
        gender: newGender,
        role: newRole.trim(),
        tts_voice: newGender === 'female' ? 'vi-VN-HoaiMyNeural' : 'vi-VN-NamMinhNeural',
      });
      setEditingSpeakers((prev) => [...prev, created]);
      setNewTag('');
      setNewName('');
      setNewOriginalName('');
      setNewRole('');
      setShowAddSpeaker(false);
      onUpdated();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteSpeaker = async (tag: string) => {
    if (!confirm(`Bạn có chắc muốn xóa nhân vật ${tag}?`)) return;
    try {
      await api.deleteSpeaker(projectId, tag);
      setEditingSpeakers((prev) => prev.filter((s) => s.speaker_tag !== tag));
      setEditingRels((prev) =>
        prev.filter((r) => r.source_speaker !== tag && r.target_speaker !== tag)
      );
      onUpdated();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddRelationship = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRelSource || !newRelTarget || !newRelSelf || !newRelTargetPronoun) return;

    try {
      const created = await api.upsertRelationship(projectId, {
        source_speaker: newRelSource,
        target_speaker: newRelTarget,
        self_pronoun: newRelSelf.trim(),
        target_pronoun: newRelTargetPronoun.trim(),
        relationship_type: newRelType.trim() || 'Bạn bè',
      });
      setEditingRels((prev) => {
        const filtered = prev.filter(
          (r) => !(r.source_speaker === newRelSource && r.target_speaker === newRelTarget)
        );
        return [...filtered, created];
      });
      setShowAddRel(false);
      setNewRelSelf('');
      setNewRelTargetPronoun('');
      setNewRelType('');
      onUpdated();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteRelationship = async (relId?: string, src?: string, tgt?: string) => {
    try {
      if (relId) {
        await api.deleteRelationship(projectId, relId);
      }
      setEditingRels((prev) =>
        prev.filter((r) => !(r.source_speaker === src && r.target_speaker === tgt))
      );
      onUpdated();
    } catch (e) {
      console.error(e);
    }
  };

  // Auto-reverse pairing logic
  const handleAutoReversePair = async (rel: RelationshipMatrix) => {
    // Reverse pronouns smartly
    let reverseSelf = rel.target_pronoun;
    let reverseTarget = rel.self_pronoun;

    if (rel.self_pronoun.toLowerCase() === 'anh' && rel.target_pronoun.toLowerCase().includes('em')) {
      reverseSelf = 'Em';
      reverseTarget = 'Anh';
    } else if (rel.self_pronoun.toLowerCase() === 'thầy') {
      reverseSelf = 'Em / Con';
      reverseTarget = 'Thầy';
    } else if (rel.self_pronoun.toLowerCase() === 'sư phụ' || rel.self_pronoun.toLowerCase() === 'vi sư') {
      reverseSelf = 'Đồ nhi / Con';
      reverseTarget = 'Sư phụ';
    }

    try {
      const reversed = await api.upsertRelationship(projectId, {
        source_speaker: rel.target_speaker,
        target_speaker: rel.source_speaker,
        self_pronoun: reverseSelf,
        target_pronoun: reverseTarget,
        relationship_type: rel.relationship_type,
        honorific_notes: `Tự động đối xứng từ cặp ${rel.source_speaker} → ${rel.target_speaker}`,
      });

      setEditingRels((prev) => {
        const filtered = prev.filter(
          (r) => !(r.source_speaker === rel.target_speaker && r.target_speaker === rel.source_speaker)
        );
        return [...filtered, reversed];
      });
      onUpdated();
    } catch (e) {
      console.error(e);
    }
  };

  const handleApplyPreset = async (presetKey: string) => {
    setIsApplyingPreset(true);
    try {
      const res = await api.applySpeakerPreset(projectId, presetKey, false);
      setEditingSpeakers(res.speakers);
      setEditingRels(res.relationships);
      onUpdated();
      setActiveTab('speakers');
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
      if (file.name.endsWith('.json')) {
        const parsed = JSON.parse(text);
        const res = await api.importSpeakers(projectId, {
          speakers: parsed.speakers || [],
          relationships: parsed.relationships || [],
          override_existing: false,
        });
        setEditingSpeakers(res.speakers);
        setEditingRels(res.relationships);
        onUpdated();
      }
    } catch (err) {
      console.error('Failed to import speakers:', err);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSaveAll = async () => {
    setIsSaving(true);
    try {
      for (const spk of editingSpeakers) {
        await api.updateSpeaker(projectId, spk.speaker_tag, {
          display_name: spk.display_name,
          original_name: spk.original_name,
          aliases: spk.aliases,
          avatar_color: spk.avatar_color,
          gender: spk.gender,
          age_group: spk.age_group,
          role: spk.role,
          tone: spk.tone,
          tts_voice: spk.tts_voice,
          tts_speed: spk.tts_speed,
          notes: spk.notes,
        });
      }

      for (const rel of editingRels) {
        await api.upsertRelationship(projectId, {
          source_speaker: rel.source_speaker,
          target_speaker: rel.target_speaker,
          self_pronoun: rel.self_pronoun,
          target_pronoun: rel.target_pronoun,
          relationship_type: rel.relationship_type,
          honorific_notes: rel.honorific_notes,
        });
      }

      onUpdated();
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  };

  const handleApplyMatrixToSubtitles = async () => {
    setIsApplyingMatrix(true);
    setMatrixSuccessMsg(null);
    try {
      for (const spk of editingSpeakers) {
        await api.updateSpeaker(projectId, spk.speaker_tag, {
          display_name: spk.display_name,
          original_name: spk.original_name,
          aliases: spk.aliases,
          avatar_color: spk.avatar_color,
          gender: spk.gender,
          age_group: spk.age_group,
          role: spk.role,
          tone: spk.tone,
          tts_voice: spk.tts_voice,
          tts_speed: spk.tts_speed,
          notes: spk.notes,
        });
      }

      for (const rel of editingRels) {
        await api.upsertRelationship(projectId, {
          source_speaker: rel.source_speaker,
          target_speaker: rel.target_speaker,
          self_pronoun: rel.self_pronoun,
          target_pronoun: rel.target_pronoun,
          relationship_type: rel.relationship_type,
          honorific_notes: rel.honorific_notes,
        });
      }

      // Trigger re-translation with all cues using the new matrix
      await api.retranslateCues(projectId, ['ALL']);
      setMatrixSuccessMsg('Đã cập nhật ma trận xưng hô và dịch lại phụ đề thành công!');
      onUpdated();
      setTimeout(() => setMatrixSuccessMsg(null), 4000);
    } catch (e) {
      console.error('Failed to apply matrix to subtitles', e);
      alert('Không thể áp dụng ma trận vào phụ đề: ' + (e instanceof Error ? e.message : String(e)));
    } finally {
      setIsApplyingMatrix(false);
    }
  };

  const filteredSpeakers = editingSpeakers.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.speaker_tag.toLowerCase().includes(q) ||
      (s.display_name && s.display_name.toLowerCase().includes(q)) ||
      (s.original_name && s.original_name.toLowerCase().includes(q)) ||
      (s.role && s.role.toLowerCase().includes(q))
    );
  });

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
            <div className="w-11 h-11 rounded-2xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600 shadow-xs">
              <Users className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-heading font-bold text-xl text-slate-900">
                  Hồ Sơ Nhân Vật & Ma Trận Xưng Hô
                </h2>
                <span className="px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold border border-indigo-200">
                  {editingSpeakers.length} Nhân vật • {editingRels.length} Cặp xưng hô
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Kiểm soát đại từ xưng hô 2 chiều nhất quán và cấu hình giọng lồng tiếng cho từng nhân vật.
              </p>
            </div>
          </div>
        </div>

        {/* Tabs & Quick Actions */}
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2 p-1 rounded-xl bg-slate-100 border border-slate-200">
            <button
              onClick={() => setActiveTab('speakers')}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'speakers'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Hồ Sơ Nhân Vật ({editingSpeakers.length})
            </button>
            <button
              onClick={() => setActiveTab('relationships')}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'relationships'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Ma Trận Xưng Hô 2 Chiều ({editingRels.length})
            </button>
            <button
              onClick={() => setActiveTab('presets')}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'presets'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Thư Viện Mẫu & Xuất/Nhập
            </button>
          </div>

          <div className="flex items-center gap-2">
            {activeTab === 'speakers' && (
              <button
                type="button"
                onClick={() => setShowAddSpeaker(!showAddSpeaker)}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-colors shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Thêm Nhân Vật</span>
              </button>
            )}

            {activeTab === 'relationships' && (
              <button
                type="button"
                onClick={() => setShowAddRel(!showAddRel)}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-colors shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Thêm Cặp Xưng Hô</span>
              </button>
            )}
          </div>
        </div>

        {/* Tab 1: Speaker Profiles */}
        {activeTab === 'speakers' && (
          <div className="flex-1 overflow-y-auto pr-1 space-y-3">
            {/* Add Speaker Form */}
            {showAddSpeaker && (
              <form
                onSubmit={handleAddSpeaker}
                className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-200 space-y-3 mb-2 animate-in fade-in"
              >
                <div className="text-xs font-bold text-indigo-900">Tạo mới nhân vật</div>
                <div className="grid grid-cols-4 gap-2.5">
                  <input
                    type="text"
                    placeholder="Mã Tag (VD: SPEAKER_02)"
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    className="px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-500 shadow-xs"
                    required
                  />
                  <input
                    type="text"
                    placeholder="Tên tiếng Việt (VD: Mục Thần)"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none focus:border-indigo-500 shadow-xs"
                    required
                  />
                  <input
                    type="text"
                    placeholder="Tên gốc Hán tự (VD: 牧尘)"
                    value={newOriginalName}
                    onChange={(e) => setNewOriginalName(e.target.value)}
                    className="px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none focus:border-indigo-500 shadow-xs"
                  />
                  <select
                    value={newGender}
                    onChange={(e) => setNewGender(e.target.value as any)}
                    className="px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                  >
                    <option value="male">Nam (Male)</option>
                    <option value="female">Nữ (Female)</option>
                    <option value="neutral">AI / Robot</option>
                    <option value="unknown">Chưa rõ</option>
                  </select>
                </div>
                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setShowAddSpeaker(false)}
                    className="px-3 py-1.5 rounded-lg text-slate-500 hover:bg-slate-100 text-xs font-medium"
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold"
                  >
                    Tạo Nhân Vật
                  </button>
                </div>
              </form>
            )}

            {/* List of Characters */}
            {filteredSpeakers.map((spk) => (
              <div
                key={spk.speaker_tag}
                className="p-4 rounded-2xl bg-slate-50 border border-slate-200 hover:border-indigo-200 transition-all space-y-3 shadow-2xs"
              >
                {/* Row 1: Tag, Names, Avatar Color, Cue Count, Delete */}
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 flex-1">
                    <span
                      className="w-3.5 h-3.5 rounded-full shrink-0 shadow-xs"
                      style={{ backgroundColor: spk.avatar_color || '#6366f1' }}
                    />
                    <span className="px-2.5 py-0.5 rounded-md bg-indigo-100 text-indigo-800 text-xs font-extrabold border border-indigo-200">
                      {spk.speaker_tag}
                    </span>

                    <input
                      type="text"
                      placeholder="Tên tiếng Việt (VD: Mục Thần)"
                      value={spk.display_name || ''}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'display_name', e.target.value)}
                      className="w-48 px-3 py-1 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-500 shadow-xs"
                    />

                    <input
                      type="text"
                      placeholder="Tên gốc Hán tự / Anh (VD: 牧尘)"
                      value={spk.original_name || ''}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'original_name', e.target.value)}
                      className="w-44 px-3 py-1 rounded-xl bg-white border border-slate-200 text-xs text-slate-600 focus:outline-none focus:border-indigo-500 shadow-xs"
                    />

                    <input
                      type="text"
                      placeholder="Biệt danh (VD: Mục ca)"
                      value={spk.aliases || ''}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'aliases', e.target.value)}
                      className="flex-1 px-3 py-1 rounded-xl bg-white border border-slate-200 text-xs text-slate-500 focus:outline-none shadow-xs"
                    />
                  </div>

                  {spk.dialogue_count !== undefined && spk.dialogue_count > 0 && (
                    <span className="px-2 py-0.5 rounded-md bg-slate-200/80 text-slate-700 text-[10px] font-bold">
                      {spk.dialogue_count} câu thoại
                    </span>
                  )}

                  <button
                    type="button"
                    onClick={() => handleDeleteSpeaker(spk.speaker_tag)}
                    className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
                    title="Xóa nhân vật"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Row 2: Gender, Age, Role, Tone */}
                <div className="grid grid-cols-4 gap-2.5">
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">
                      Giới tính (Gender)
                    </label>
                    <select
                      value={spk.gender}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'gender', e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                    >
                      <option value="male">Nam (Male)</option>
                      <option value="female">Nữ (Female)</option>
                      <option value="neutral">AI / Robot</option>
                      <option value="unknown">Chưa rõ</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">
                      Nhóm tuổi
                    </label>
                    <select
                      value={spk.age_group || 'young_adult'}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'age_group', e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                    >
                      <option value="child">Thiếu nhi (Child)</option>
                      <option value="teen">Thiếu niên (Teen)</option>
                      <option value="young_adult">Thanh niên (Young Adult)</option>
                      <option value="adult">Trung niên (Adult)</option>
                      <option value="senior">Lão niên (Senior)</option>
                      <option value="immortal">Bất tử / AI (Immortal)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">
                      Thân phận / Vai trò
                    </label>
                    <input
                      type="text"
                      placeholder="VD: Nam chính, Sư phụ, Sát thủ"
                      value={spk.role || ''}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'role', e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">
                      Giọng điệu / Phong thái
                    </label>
                    <input
                      type="text"
                      placeholder="VD: Lạnh lùng, Hoạt bát, Điềm đạm"
                      value={spk.tone || ''}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'tone', e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                    />
                  </div>
                </div>

                {/* Row 3: Voice Selection & Notes */}
                <div className="grid grid-cols-12 gap-2.5 pt-1">
                  <div className="col-span-5">
                    <label className="block text-[10px] uppercase font-bold text-indigo-700 mb-1">
                      Giọng Lồng Tiếng AI (TTS Voice)
                    </label>
                    <select
                      value={spk.tts_voice || 'vi-VN-HoaiMyNeural'}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'tts_voice', e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-indigo-50/50 border border-indigo-200 text-xs font-semibold text-slate-900 focus:outline-none shadow-xs"
                    >
                      <option value="vi-VN-HoaiMyNeural">🌸 Hoài My (Nữ - Tự Nhiên & Truyền Cảm ⭐)</option>
                      <option value="vi-VN-HoaiMyAnime">✨ Hoài My Anime (Nữ - Ngọt Ngào & Trong Trẻo)</option>
                      <option value="vi-VN-HoaiMyNarrator">📖 Hoài My Thuyết Minh (Nữ - Sâu Lắng)</option>
                      <option value="vi-VN-NamMinhNeural">🌴 Nam Minh (Nam - Miền Bắc Đĩnh Đạc)</option>
                      <option value="nova">🌸 Nova (Nữ - OpenAI Chuẩn Điện Ảnh)</option>
                      <option value="shimmer">✨ Shimmer (Nữ - OpenAI Dịu Dàng)</option>
                      <option value="alloy">🎙️ Alloy (Nữ/Trung Tính - Hiện Đại)</option>
                      <option value="onyx">🎬 Onyx (Nam - Trầm Hùng & Uy Lực)</option>
                      <option value="gtts-female-vi">🌺 Mai Lan (Nữ - Google Voice)</option>
                    </select>
                  </div>

                  <div className="col-span-7">
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">
                      Ghi chú xuất thân & Cấm kỵ khi dịch đại từ
                    </label>
                    <input
                      type="text"
                      placeholder="VD: Con gái, cấm dịch là anh ta hay hắn. Xưng em/tôi, gọi anh/cậu."
                      value={spk.notes || ''}
                      onChange={(e) => handleSpeakerChange(spk.speaker_tag, 'notes', e.target.value)}
                      className="w-full px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-700 focus:outline-none shadow-xs"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tab 2: 2-Way Relationship Matrix */}
        {activeTab === 'relationships' && (
          <div className="flex-1 overflow-y-auto pr-1 space-y-4">
            {/* Guide Banner */}
            <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-50 via-purple-50/70 to-cyan-50 border border-indigo-200 space-y-2 shadow-2xs">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-base">🎯</span>
                  <h4 className="text-xs font-bold text-indigo-950 uppercase tracking-wider">
                    Ma Trận Xưng Hô & Cơ Chế Dịch Phim Sát Nghĩa
                  </h4>
                </div>
                <button
                  type="button"
                  onClick={handleApplyMatrixToSubtitles}
                  disabled={isApplyingMatrix}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm transition-all disabled:opacity-50"
                  title="Dịch lại phụ đề theo ma trận xưng hô ngay"
                >
                  {isApplyingMatrix ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang dịch lại...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>⚡ Áp Dụng Vào Phụ Đề Ngay</span>
                    </>
                  )}
                </button>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed">
                Trong tiếng Việt, xưng hô (<span className="font-bold text-indigo-700">Tôi - Cô</span>, <span className="font-bold text-indigo-700">Anh - Em</span>, <span className="font-bold text-indigo-700">Huynh - Muội</span>, <span className="font-bold text-indigo-700">Thầy - Trò</span>...) là <strong className="text-indigo-900">linh hồn của bộ phim</strong>. Ma trận này ép buộc động cơ dịch AI tuân thủ tuyệt đối từng cặp đại từ khi đối thoại, ngay cả khi các câu thoại cùng mang mã SPEAKER_00!
              </p>
              {matrixSuccessMsg && (
                <div className="flex items-center gap-2 text-xs font-bold text-emerald-800 bg-emerald-100/90 border border-emerald-300 px-3 py-1.5 rounded-xl">
                  <Check className="w-4 h-4 text-emerald-600" />
                  <span>{matrixSuccessMsg}</span>
                </div>
              )}
            </div>

            {/* Add Relationship Form */}
            {showAddRel && (
              <form
                onSubmit={handleAddRelationship}
                className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-200 space-y-3 animate-in fade-in"
              >
                <div className="text-xs font-bold text-indigo-900">Thêm mới cặp xưng hô đối thoại</div>
                <div className="grid grid-cols-4 gap-2.5">
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Người nói (Source)</label>
                    <select
                      value={newRelSource}
                      onChange={(e) => setNewRelSource(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                      required
                    >
                      <option value="">-- Chọn nhân vật --</option>
                      {editingSpeakers.map((s) => (
                        <option key={s.speaker_tag} value={s.speaker_tag}>
                          {s.display_name || s.speaker_tag} ({s.speaker_tag})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Đối tượng nghe (Target)</label>
                    <select
                      value={newRelTarget}
                      onChange={(e) => setNewRelTarget(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                      required
                    >
                      <option value="">-- Chọn nhân vật --</option>
                      {editingSpeakers.map((s) => (
                        <option key={s.speaker_tag} value={s.speaker_tag}>
                          {s.display_name || s.speaker_tag} ({s.speaker_tag})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Tự xưng (Self / '我')</label>
                    <input
                      type="text"
                      placeholder="VD: Anh / Tôi / Sư phụ"
                      value={newRelSelf}
                      onChange={(e) => setNewRelSelf(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Gọi đối phương (Target / '你')</label>
                    <input
                      type="text"
                      placeholder="VD: Em / Cô / Cậu / Đồ nhi"
                      value={newRelTargetPronoun}
                      onChange={(e) => setNewRelTargetPronoun(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-900 focus:outline-none shadow-xs"
                      required
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-slate-400 font-bold uppercase">Quan hệ:</span>
                    {['Bạn đồng hành', 'Anh em', 'Người yêu', 'Sư đồ', 'Kẻ thù'].map((suggest) => (
                      <button
                        key={suggest}
                        type="button"
                        onClick={() => setNewRelType(suggest)}
                        className={`px-2 py-0.5 rounded-lg text-[10px] font-medium border transition-colors ${
                          newRelType === suggest
                            ? 'bg-indigo-600 text-white border-indigo-600'
                            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        {suggest}
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowAddRel(false)}
                      className="px-3 py-1.5 rounded-lg text-slate-500 hover:bg-slate-100 text-xs font-medium"
                    >
                      Hủy
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold"
                    >
                      Thêm Cặp Xưng Hô
                    </button>
                  </div>
                </div>
              </form>
            )}

            {/* List of Relationship Pairs */}
            {editingRels.length === 0 ? (
              <div className="text-center py-12 text-slate-400 text-xs">
                Chưa có cặp xưng hô nào được cấu hình.
              </div>
            ) : (
              editingRels.map((rel, idx) => {
                const srcSpk = editingSpeakers.find((s) => s.speaker_tag === rel.source_speaker);
                const tgtSpk = editingSpeakers.find((s) => s.speaker_tag === rel.target_speaker);
                const srcName = srcSpk?.display_name || rel.source_speaker;
                const tgtName = tgtSpk?.display_name || rel.target_speaker;
                const srcColor = srcSpk?.avatar_color || '#6366f1';
                const tgtColor = tgtSpk?.avatar_color || '#ec4899';

                return (
                  <div
                    key={idx}
                    className="p-4 rounded-2xl bg-slate-50 border border-slate-200 hover:border-indigo-200 transition-all space-y-3 shadow-2xs"
                  >
                    {/* Header: Visual Characters Flow */}
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        {/* Source Character */}
                        <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-white border border-slate-200 shadow-2xs">
                          <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: srcColor }}
                          />
                          <span className="font-bold text-xs text-slate-900">{srcName}</span>
                          <span className="text-[10px] font-mono text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded font-bold">
                            {rel.source_speaker}
                          </span>
                          {srcSpk?.gender && (
                            <span
                              className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                                srcSpk.gender === 'female'
                                  ? 'bg-pink-100 text-pink-700'
                                  : srcSpk.gender === 'male'
                                  ? 'bg-blue-100 text-blue-700'
                                  : 'bg-slate-100 text-slate-700'
                              }`}
                            >
                              {srcSpk.gender === 'female' ? 'Nữ' : srcSpk.gender === 'male' ? 'Nam' : 'AI'}
                            </span>
                          )}
                        </div>

                        <ArrowRight className="w-4 h-4 text-indigo-500 shrink-0 stroke-[2.5]" />

                        {/* Target Character */}
                        <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-white border border-slate-200 shadow-2xs">
                          <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: tgtColor }}
                          />
                          <span className="font-bold text-xs text-slate-900">{tgtName}</span>
                          <span className="text-[10px] font-mono text-cyan-700 bg-cyan-50 px-1.5 py-0.5 rounded font-bold">
                            {rel.target_speaker}
                          </span>
                          {tgtSpk?.gender && (
                            <span
                              className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                                tgtSpk.gender === 'female'
                                  ? 'bg-pink-100 text-pink-700'
                                  : tgtSpk.gender === 'male'
                                  ? 'bg-blue-100 text-blue-700'
                                  : 'bg-slate-100 text-slate-700'
                              }`}
                            >
                              {tgtSpk.gender === 'female' ? 'Nữ' : tgtSpk.gender === 'male' ? 'Nam' : 'AI'}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="Mối quan hệ (VD: Bạn đồng hành)"
                          value={rel.relationship_type || ''}
                          onChange={(e) =>
                            handleRelChange(rel.source_speaker, rel.target_speaker, 'relationship_type', e.target.value)
                          }
                          className="w-44 px-3 py-1 rounded-lg bg-white border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 shadow-xs"
                        />

                        {/* Auto Reverse Pair Button */}
                        <button
                          type="button"
                          onClick={() => handleAutoReversePair(rel)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-[11px] font-bold transition-colors"
                          title="Tự động tạo chiều đối xứng ngược lại"
                        >
                          <RefreshCw className="w-3 h-3" />
                          <span>Tạo chiều ngược</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDeleteRelationship(rel.id, rel.source_speaker, rel.target_speaker)}
                          className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
                          title="Xóa cặp xưng hô"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Inputs for Self and Target Pronoun */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-600 mb-1">
                          {srcName} tự xưng khi nói (&ldquo;我&rdquo; / Ngôi 1)
                        </label>
                        <input
                          type="text"
                          value={rel.self_pronoun}
                          onChange={(e) =>
                            handleRelChange(rel.source_speaker, rel.target_speaker, 'self_pronoun', e.target.value)
                          }
                          placeholder="VD: Tôi / Anh / Sư phụ / Bổn thiếu gia"
                          className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-bold text-indigo-900 focus:outline-none focus:border-indigo-500 shadow-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-600 mb-1">
                          {srcName} gọi {tgtName} (&ldquo;你&rdquo; / Ngôi 2)
                        </label>
                        <input
                          type="text"
                          value={rel.target_pronoun}
                          onChange={(e) =>
                            handleRelChange(rel.source_speaker, rel.target_speaker, 'target_pronoun', e.target.value)
                          }
                          placeholder="VD: Em / Cô / Cậu / Cố tiểu thư / Đồ nhi"
                          className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-bold text-indigo-900 focus:outline-none focus:border-indigo-500 shadow-xs"
                        />
                      </div>
                    </div>

                    {/* Live Translation Preview Sentence */}
                    <div className="p-3 rounded-xl bg-indigo-50/70 border border-indigo-150 flex items-start gap-2.5 text-xs text-indigo-950">
                      <Sparkles className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                      <div className="space-y-0.5 flex-1">
                        <div className="text-[10px] uppercase font-bold text-indigo-800 tracking-wider">
                          Mô phỏng câu thoại dịch sát nghĩa theo Ma Trận:
                        </div>
                        <p className="italic text-slate-800">
                          <span className="font-bold not-italic text-indigo-900">{srcName}:</span> &ldquo;<span className="font-bold text-indigo-700 bg-indigo-100 px-1 rounded">[{rel.self_pronoun || 'Tôi'}]</span> nghĩ <span className="font-bold text-indigo-700 bg-indigo-100 px-1 rounded">[{rel.target_pronoun || 'cô'}]</span> không nên mạo hiểm ở khu vực này.&rdquo;
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Tab 3: Presets & Cross-Movie Reusability */}
        {activeTab === 'presets' && (
          <div className="flex-1 overflow-y-auto pr-1 space-y-4">
            {/* Genre Presets Section */}
            <div className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-200 space-y-3">
              <div>
                <h3 className="text-sm font-bold text-indigo-900">
                  Thư Viện Mẫu Nhân Vật Có Sẵn Theo Thể Loại
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Nạp nhanh danh sách nhân vật và xưng hô chuẩn của các thể loại phim vào dự án này với 1 click.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => handleApplyPreset('sci_fi_mecha')}
                  disabled={isApplyingPreset}
                  className="p-3.5 rounded-xl bg-white border border-indigo-200 hover:border-indigo-400 hover:shadow-md transition-all text-left flex items-start gap-3 group"
                >
                  <span className="text-2xl">🚀</span>
                  <div>
                    <div className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                      Khoa Huyễn & Cơ Giáp Không Gian
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1 line-clamp-2">
                      Nam chính cơ giáp, Nữ chính chỉ huy, Trợ lý AI chiến hạm, Thầy Lâm mentor.
                    </div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleApplyPreset('xianxia_cultivation')}
                  disabled={isApplyingPreset}
                  className="p-3.5 rounded-xl bg-white border border-indigo-200 hover:border-indigo-400 hover:shadow-md transition-all text-left flex items-start gap-3 group"
                >
                  <span className="text-2xl">⚔️</span>
                  <div>
                    <div className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                      Tiên Hiệp & Tu Chân Huyền Huyễn
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1 line-clamp-2">
                      Sư phụ Chưởng môn, Đồ nhi, Tiểu sư muội, xưng hô Vi sư - Đồ nhi chuẩn đạo.
                    </div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleApplyPreset('wuxia_ancient')}
                  disabled={isApplyingPreset}
                  className="p-3.5 rounded-xl bg-white border border-indigo-200 hover:border-indigo-400 hover:shadow-md transition-all text-left flex items-start gap-3 group"
                >
                  <span className="text-2xl">🗡️</span>
                  <div>
                    <div className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                      Kiếm Hiệp & Cổ Trang Giang Hồ
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1 line-clamp-2">
                      Hiệp khách giang hồ, Minh chủ võ lâm, xưng hô Tại hạ - Các hạ, Huynh đệ.
                    </div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleApplyPreset('anime_manga')}
                  disabled={isApplyingPreset}
                  className="p-3.5 rounded-xl bg-white border border-indigo-200 hover:border-indigo-400 hover:shadow-md transition-all text-left flex items-start gap-3 group"
                >
                  <span className="text-2xl">⛩️</span>
                  <div>
                    <div className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                      Anime, Manga & Dị Giới Isekai
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1 line-clamp-2">
                      Dũng giả, Tsundere ma pháp sư, Senpai - Kouhai tự nhiên.
                    </div>
                  </div>
                </button>
              </div>
            </div>

            {/* Export & Import Section */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Xuất / Nhập Dữ Liệu Nhân Vật Sang Phim Khác
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Lưu file cấu hình nhân vật của bộ phim này để nạp vào Season 2 hoặc phim khác trong cùng series.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <a
                  href={api.getSpeakerExportUrl(projectId, 'json')}
                  download
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-slate-200 hover:border-indigo-500 text-slate-700 text-xs font-bold transition-all shadow-xs"
                >
                  <Download className="w-4 h-4 text-indigo-600" />
                  <span>Xuất File JSON Toàn Diện</span>
                </a>

                <a
                  href={api.getSpeakerExportUrl(projectId, 'csv')}
                  download
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-slate-200 hover:border-indigo-500 text-slate-700 text-xs font-bold transition-all shadow-xs"
                >
                  <Download className="w-4 h-4 text-emerald-600" />
                  <span>Xuất File CSV (Excel)</span>
                </a>

                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".json"
                  className="hidden"
                />

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-bold transition-all shadow-xs"
                >
                  <Upload className="w-4 h-4" />
                  <span>Nhập Từ File JSON Đã Có</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-100 mt-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleApplyMatrixToSubtitles}
              disabled={isApplyingMatrix || isSaving}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-bold shadow-md shadow-emerald-500/20 transition-all cursor-pointer disabled:opacity-50"
              title="Lưu hồ sơ và dịch lại toàn bộ phụ đề theo ma trận xưng hô ngay"
            >
              {isApplyingMatrix ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Đang dịch lại phụ đề theo ma trận...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>⚡ Áp Dụng Ma Trận Vào Phụ Đề Ngay</span>
                </>
              )}
            </button>
            {matrixSuccessMsg && (
              <span className="text-xs font-bold text-emerald-700 flex items-center gap-1">
                <Check className="w-3.5 h-3.5 text-emerald-600" />
                {matrixSuccessMsg}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
            >
              Đóng
            </button>
            <button
              type="button"
              onClick={handleSaveAll}
              disabled={isSaving}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-md shadow-indigo-500/20"
            >
              <Save className="w-4 h-4" />
              <span>{isSaving ? 'Đang lưu...' : 'Lưu Hồ Sơ & Ma Trận'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
