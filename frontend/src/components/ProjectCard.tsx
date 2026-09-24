'use client';

import Link from 'next/link';
import { Clock, MessageSquare, Users, BookOpen, ChevronRight, Trash2, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Project } from '@/lib/types';
import { getFriendlyStageName, getFriendlyVoiceName } from '@/components/PipelineProgressTracker';

interface ProjectCardProps {
  project: Project;
  onDelete: (id: string) => void;
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const formatDuration = (seconds: number) => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const hrs = Math.floor(mins / 60);
    if (hrs > 0) {
      return `${hrs}h ${mins % 60}m`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusBadge = () => {
    switch (project.status) {
      case 'COMPLETED':
        return (
          <span className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" /> Completed
          </span>
        );
      case 'WAITING_REVIEW':
        return (
          <span className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">
            Ready for Review
          </span>
        );
      case 'PROCESSING':
      case 'INGESTING':
      case 'ASR_PROCESSING':
      case 'SPEAKER_PROFILING':
      case 'TRANSLATING':
      case 'BURNING':
      case 'DUBBING':
        const stageName = getFriendlyStageName(project.current_stage);

        return (
          <span className="flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-2xs">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600 shrink-0" />
            <span>{stageName} ({project.progress_percentage}%)</span>
          </span>
        );
      case 'FAILED':
        return (
          <span className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3.5 h-3.5" /> Failed
          </span>
        );
      default:
        return (
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
            Created
          </span>
        );
    }
  };

  return (
    <div className="glass-card rounded-2xl p-5 flex flex-col justify-between group relative overflow-hidden bg-white border border-slate-200 shadow-sm hover:shadow-md hover:border-slate-300 transition-all">
      {/* Background Subtle Gradient Glow */}
      <div className="absolute -right-12 -top-12 w-32 h-32 bg-indigo-50 rounded-full blur-2xl group-hover:bg-indigo-100 transition-all pointer-events-none" />

      <div>
        {/* Header Badges */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200">
              {project.source_language.toUpperCase()} → {project.target_language.toUpperCase()}
            </span>
            {project.original_video_url?.includes('bilibili') && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-pink-50 text-pink-700 border border-pink-200">
                🇨🇳 Bilibili
              </span>
            )}
            {project.dubbed_video_url && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-violet-50 text-violet-700 border border-violet-200">
                🌸 {getFriendlyVoiceName(project.default_voice)}
              </span>
            )}
            <div className="flex items-center gap-1 text-xs text-slate-500 font-medium">
              <Clock className="w-3.5 h-3.5" />
              <span>{formatDuration(project.video_duration_seconds)}</span>
            </div>
          </div>
          {getStatusBadge()}
        </div>

        {/* Title */}
        <Link href={`/projects/${project.id}`}>
          <h3 className="font-heading font-bold text-lg text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-1 mb-1">
            {project.title}
          </h3>
        </Link>
        <p className="text-xs text-slate-500 line-clamp-2 mb-4 leading-relaxed">
          {project.description || 'Auto-translated video with AI Context Window & Guardrails.'}
        </p>

        {/* Real Progress Bar */}
        {project.status !== 'COMPLETED' && project.status !== 'FAILED' && project.status !== 'CREATED' && (
          <div className="mb-4 p-3 rounded-xl bg-slate-50/80 border border-slate-200/80 space-y-1.5">
            <div className="flex justify-between items-center text-[11px] font-medium text-slate-600">
              <span className="truncate max-w-[240px] text-slate-700">
                {project.error_message && !project.error_message.includes('Traceback') && !project.error_message.includes('Error')
                  ? project.error_message
                  : `Giai đoạn: ${getFriendlyStageName(project.current_stage)}`}
              </span>
              <span className="font-bold text-indigo-600 shrink-0">{project.progress_percentage}%</span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-indigo-500 via-cyan-500 to-emerald-500 h-full rounded-full transition-all duration-300 shadow-sm"
                style={{ width: `${Math.min(100, Math.max(0, project.progress_percentage))}%` }}
              />
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-2 py-2.5 px-3 rounded-xl bg-slate-50 border border-slate-200/70 text-xs text-slate-700 mb-4 font-medium">
          <div className="flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-cyan-600" />
            <span>{project.cue_count || 0} Cues</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5 text-indigo-600" />
            <span>{project.speaker_count || 0} Speakers</span>
          </div>
          <div className="flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5 text-pink-600" />
            <span>{project.glossary_count || 0} Terms</span>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-3 border-t border-slate-100">
        <button
          onClick={() => onDelete(project.id)}
          className="p-2 text-slate-400 hover:text-rose-600 transition-colors rounded-lg hover:bg-rose-50"
          title="Delete Project"
        >
          <Trash2 className="w-4 h-4" />
        </button>

        <Link
          href={`/projects/${project.id}`}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-600 text-indigo-700 hover:text-white border border-indigo-200/80 hover:border-indigo-600 text-xs font-bold transition-all shadow-xs group/btn"
        >
          <span>Open Studio</span>
          <ChevronRight className="w-3.5 h-3.5 group-hover/btn:translate-x-0.5 transition-transform" />
        </Link>
      </div>
    </div>
  );
}
