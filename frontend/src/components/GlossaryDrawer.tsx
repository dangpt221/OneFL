'use client';

import { useState } from 'react';
import { X, BookOpen, Trash2, Sparkles, Loader2 } from 'lucide-react';
import { GlossaryTerm } from '@/lib/types';
import { api } from '@/lib/api';

interface GlossaryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  terms: GlossaryTerm[];
  onUpdated: () => void;
}

export default function GlossaryDrawer({
  isOpen,
  onClose,
  projectId,
  terms,
  onUpdated,
}: GlossaryDrawerProps) {
  const [sourceTerm, setSourceTerm] = useState('');
  const [targetTerm, setTargetTerm] = useState('');
  const [category, setCategory] = useState('tech');
  const [contextNote, setContextNote] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);

  if (!isOpen) return null;

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

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-white border-l border-slate-200 shadow-2xl p-6 flex flex-col justify-between animate-slide-left">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-pink-50 border border-pink-200 flex items-center justify-center text-pink-600">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-heading font-bold text-lg text-slate-900">Terminology Glossary</h3>
              <p className="text-xs text-slate-500">Strict keyword enforcement during translation.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* AI Auto-extract button */}
        <button
          onClick={handleAutoExtract}
          disabled={isExtracting}
          className="w-full mb-4 flex items-center justify-center gap-2 p-2.5 rounded-xl bg-gradient-to-r from-pink-50 to-indigo-50 hover:from-pink-100 hover:to-indigo-100 text-pink-700 border border-pink-200 text-xs font-bold transition-all disabled:opacity-50"
        >
          {isExtracting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Auto-extracting keywords...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 text-pink-600" /> Auto-Extract Terms with AI
            </>
          )}
        </button>

        {/* Add Term Form */}
        <form onSubmit={handleAdd} className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5 mb-4">
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Source term (e.g. Throughput)"
              value={sourceTerm}
              onChange={(e) => setSourceTerm(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-pink-500 shadow-xs"
              required
            />
            <input
              type="text"
              placeholder="Target term (e.g. Thông lượng)"
              value={targetTerm}
              onChange={(e) => setTargetTerm(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-pink-500 shadow-xs"
              required
            />
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Context note (optional)"
              value={contextNote}
              onChange={(e) => setContextNote(e.target.value)}
              className="flex-1 px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none shadow-xs"
            />
            <button
              type="submit"
              disabled={isAdding}
              className="px-3 py-1.5 rounded-lg bg-pink-600 hover:bg-pink-700 text-white text-xs font-bold transition-colors disabled:opacity-50 shadow-xs"
            >
              Add
            </button>
          </div>
        </form>

        {/* Term List */}
        <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
          {terms.length === 0 ? (
            <div className="text-center py-8 text-slate-400 text-xs font-medium">
              No glossary terms added yet.
            </div>
          ) : (
            terms.map((term) => (
              <div
                key={term.id}
                className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200 hover:border-pink-300 transition-colors shadow-2xs"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-900">{term.source_term}</span>
                    <span className="text-[10px] text-slate-400 font-bold">→</span>
                    <span className="text-xs font-bold text-pink-600">{term.target_term}</span>
                  </div>
                  {term.context_note && (
                    <p className="text-[10px] text-slate-500 mt-0.5">{term.context_note}</p>
                  )}
                </div>

                <button
                  onClick={() => handleDelete(term.id)}
                  className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="pt-4 border-t border-slate-100">
        <button
          onClick={onClose}
          className="w-full py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
        >
          Done
        </button>
      </div>
    </div>
  );
}
