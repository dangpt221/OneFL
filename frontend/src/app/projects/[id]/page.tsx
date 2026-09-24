'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Users,
  BookOpen,
  Flame,
  Download,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { Project, SubtitleCue, SpeakerProfile, RelationshipMatrix, GlossaryTerm } from '@/lib/types';
import { api } from '@/lib/api';
import { useProjectWebSocket } from '@/lib/useWebSocket';
import VideoPlayer from '@/components/VideoPlayer';
import SubtitleEditor from '@/components/SubtitleEditor';
import SpeakerMatrixModal from '@/components/SpeakerMatrixModal';
import GlossaryModal from '@/components/GlossaryModal';
import BurnProgressModal from '@/components/BurnProgressModal';
import DubbingModal from '@/components/DubbingModal';
import PipelineProgressTracker, { getFriendlyStageName, getFriendlyVoiceName } from '@/components/PipelineProgressTracker';

export default function ProjectStudioPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [cues, setCues] = useState<SubtitleCue[]>([]);
  const [speakers, setSpeakers] = useState<SpeakerProfile[]>([]);
  const [relationships, setRelationships] = useState<RelationshipMatrix[]>([]);
  const [glossaryTerms, setGlossaryTerms] = useState<GlossaryTerm[]>([]);

  const [currentTime, setCurrentTime] = useState(0);
  const [seekTarget, setSeekTarget] = useState<number | null>(null);
  const [activeVideoSource, setActiveVideoSource] = useState<'auto' | 'burned' | 'dubbed' | 'original'>('auto');

  // Modals
  const [isSpeakerModalOpen, setIsSpeakerModalOpen] = useState(false);
  const [isGlossaryDrawerOpen, setIsGlossaryDrawerOpen] = useState(false);
  const [isBurnModalOpen, setIsBurnModalOpen] = useState(false);
  const [isDubModalOpen, setIsDubModalOpen] = useState(false);

  // WebSocket Live Updates
  const { isConnected, lastMessage } = useProjectWebSocket(projectId);

  const loadAllData = useCallback(async () => {
    try {
      const [projData, subData, spkData, gloData] = await Promise.all([
        api.getProject(projectId),
        api.getSubtitles(projectId),
        api.getSpeakerMatrix(projectId),
        api.getGlossary(projectId),
      ]);
      setProject(projData);
      setCues(subData.items);
      setSpeakers(spkData.speakers);
      setRelationships(spkData.relationships);
      setGlossaryTerms(gloData.items);
    } catch (e) {
      console.error('Failed to load project studio data', e);
    }
  }, [projectId]);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  // Handle live WebSocket events
  useEffect(() => {
    if (!lastMessage) return;

    const msgType = (lastMessage.type || '').toUpperCase();
    if (msgType === 'STAGE_CHANGED' || msgType === 'STATUS_UPDATE' || lastMessage.type === 'stage_changed') {
      const status = lastMessage.data?.status;
      const stage = lastMessage.data?.stage || lastMessage.data?.current_stage;
      const progress = lastMessage.data?.progress ?? lastMessage.data?.progress_percentage;
      const message = lastMessage.data?.message;
      const dubbed_audio_url = lastMessage.data?.dubbed_audio_url;
      const dubbed_video_url = lastMessage.data?.dubbed_video_url;
      const burned_video_url = lastMessage.data?.burned_video_url;
      setProject(prev => prev ? {
        ...prev,
        ...(status ? { status } : {}),
        ...(stage ? { current_stage: stage } : {}),
        ...(progress !== undefined ? { progress_percentage: progress } : {}),
        ...(message ? { error_message: message } : {}),
        ...(dubbed_audio_url ? { dubbed_audio_url } : {}),
        ...(dubbed_video_url ? { dubbed_video_url } : {}),
        ...(burned_video_url ? { burned_video_url } : {})
      } : null);
      loadAllData();
    } else if (msgType === 'PROGRESS_UPDATE' || lastMessage.type === 'progress_update') {
      const pct = lastMessage.data?.progress ?? lastMessage.data?.percentage;
      const msg = lastMessage.data?.message;
      const stage = lastMessage.data?.stage;
      setProject(prev => prev ? { 
        ...prev, 
        progress_percentage: pct !== undefined ? pct : prev.progress_percentage,
        error_message: msg || prev.error_message,
        current_stage: stage || prev.current_stage
      } : null);
    } else if (msgType === 'TRANSLATION_PROGRESS') {
      setProject(prev => prev ? { 
        ...prev, 
        progress_percentage: lastMessage.data.percentage,
        error_message: lastMessage.data.message || prev.error_message 
      } : null);
    } else if (msgType === 'CUE_UPDATED') {
      const updatedCue = lastMessage.data as SubtitleCue;
      setCues(prev => prev.map(c => c.id === updatedCue.id ? updatedCue : c));
    }
  }, [lastMessage, projectId, loadAllData]);

  const handleSeek = (time: number) => {
    setSeekTarget(time);
    setCurrentTime(time);
  };

  const handleCueUpdated = (updatedCue: SubtitleCue) => {
    setCues(prev => prev.map(c => c.id === updatedCue.id ? updatedCue : c));
  };

  const handleRetranslateRequested = async (cueIds: string[]) => {
    try {
      const updated = await api.retranslateCues(projectId, cueIds);
      const updatedMap = new Map(updated.map(u => [u.id, u]));
      setCues(prev => prev.map(c => updatedMap.get(c.id) || c));
    } catch (e) {
      console.error(e);
    }
  };

  const handleBurnStarted = async (options?: { subtitle_preset?: string; bilingual?: boolean; mask_original_sub?: boolean }) => {
    try {
      await api.startBurning(projectId, options);
      loadAllData();
    } catch (e) {
      console.error(e);
    }
  };

  const [isPipelineRunning, setIsPipelineRunning] = useState(false);

  const handleStartPipeline = async () => {
    try {
      setIsPipelineRunning(true);
      await api.triggerPipeline(projectId, 'INGESTING');
      loadAllData();
    } catch (e) {
      console.error('Failed to trigger pipeline', e);
    } finally {
      setTimeout(() => setIsPipelineRunning(false), 2000);
    }
  };

  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-400 space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        <p className="text-sm font-semibold text-slate-600">Loading OneFL Studio Workspace...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in pb-10">
      {/* Studio Top Action Bar */}
      <div className="bg-white rounded-3xl p-4 lg:p-5 border border-slate-200 shadow-sm flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Left: Navigation & Project Info */}
        <div className="flex items-center gap-3.5 min-w-0">
          <Link
            href="/"
            className="p-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-700 hover:text-slate-900 transition-colors border border-slate-200/60 shrink-0"
            title="Quay lại danh sách dự án"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="font-heading font-bold text-lg sm:text-xl text-slate-900 truncate max-w-[280px] sm:max-w-md">
                {project.title}
              </h1>
              <span className="text-xs uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200 shrink-0">
                {project.source_language.toUpperCase()} → {project.target_language.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500 font-medium">
              <span>Trạng thái: <strong className="text-indigo-600">{project.status}</strong></span>
              <span>•</span>
              <span>{cues.length} câu thoại</span>
              {project.default_voice && (
                <>
                  <span>•</span>
                  <span className="text-violet-600 font-semibold">Giọng: {getFriendlyVoiceName(project.default_voice)}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Right: Studio Toolbars & Primary Actions */}
        <div className="flex flex-wrap items-center gap-2 justify-end">
          {/* Group 1: Configuration Tools */}
          <div className="flex items-center gap-1.5 p-1 bg-slate-100/80 rounded-2xl border border-slate-200/60">
            <button
              onClick={() => setIsSpeakerModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl hover:bg-white text-slate-700 hover:text-slate-900 text-xs font-semibold transition-all"
              title="Cấu hình xưng hô nhân vật"
            >
              <Users className="w-3.5 h-3.5 text-indigo-600" />
              <span>Nhân Vật ({speakers.length})</span>
            </button>

            <button
              onClick={() => setIsGlossaryDrawerOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl hover:bg-white text-slate-700 hover:text-slate-900 text-xs font-semibold transition-all"
              title="Từ điển thuật ngữ dịch"
            >
              <BookOpen className="w-3.5 h-3.5 text-pink-600" />
              <span>Thuật Ngữ ({glossaryTerms.length})</span>
            </button>

            {/* Export Dropdown */}
            <div className="relative group">
              <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl hover:bg-white text-slate-700 hover:text-slate-900 text-xs font-semibold transition-all">
                <Download className="w-3.5 h-3.5 text-cyan-600" />
                <span>Xuất Sub</span>
              </button>
              <div className="absolute right-0 top-full mt-1.5 w-48 bg-white rounded-xl border border-slate-200 p-1.5 hidden group-hover:block z-30 shadow-xl animate-in fade-in">
                <a
                  href={api.getExportUrl(projectId, 'ass', { preset: 'cinema' })}
                  download
                  className="block px-3 py-2 rounded-lg text-xs font-medium text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 transition-colors"
                >
                  Phụ đề Cinema (.ass)
                </a>
                <a
                  href={api.getExportUrl(projectId, 'ass', { bilingual: true })}
                  download
                  className="block px-3 py-2 rounded-lg text-xs font-bold text-indigo-700 hover:bg-indigo-50 transition-colors"
                >
                  🌐 Phụ đề Song Ngữ (.ass)
                </a>
                <a
                  href={api.getExportUrl(projectId, 'srt')}
                  download
                  className="block px-3 py-2 rounded-lg text-xs font-medium text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 transition-colors"
                >
                  Phổ thông (.srt)
                </a>
                <a
                  href={api.getExportUrl(projectId, 'vtt')}
                  download
                  className="block px-3 py-2 rounded-lg text-xs font-medium text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 transition-colors"
                >
                  Trình duyệt web (.vtt)
                </a>
              </div>
            </div>
          </div>

          {/* Group 2: Production Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleStartPipeline}
              disabled={isPipelineRunning || project.status === 'PROCESSING'}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-bold shadow-sm shadow-emerald-600/20 transition-all cursor-pointer hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
              title="Khởi chạy nhận diện giọng nói và dịch phụ đề AI"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isPipelineRunning || project.status === 'PROCESSING' ? 'Đang Xử Lý Pipeline...' : (cues.length === 0 ? '🚀 Nhận diện & Dịch AI' : '🔄 Dịch Lại Toàn Bộ')}</span>
            </button>

            <button
              onClick={() => setIsDubModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-xs font-bold shadow-sm shadow-indigo-600/20 transition-all cursor-pointer hover:scale-[1.02] active:scale-[0.98]"
            >
              <span>🎙️ Lồng Tiếng AI (Nova)</span>
            </button>

            <button
              onClick={() => setIsBurnModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-600 hover:to-rose-600 text-white text-xs font-bold shadow-sm shadow-rose-500/20 transition-all cursor-pointer hover:scale-[1.02] active:scale-[0.98]"
            >
              <Flame className="w-3.5 h-3.5" />
              <span>Burn Video</span>
            </button>
          </div>
        </div>
      </div>

      {/* Live Pipeline Stepper / Progress Tracker */}
      <PipelineProgressTracker
        project={project}
        cuesCount={cues.length}
        translatedCuesCount={cues.filter(c => !!c.translated_text).length}
        onRetry={handleStartPipeline}
      />

      {/* Main Studio Grid: Video Player on Left (Sticky), Subtitle Grid on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Video Player & Sticky Media Panel */}
        <div className="lg:col-span-5 space-y-3 lg:sticky lg:top-20">
          {/* Video Track Selector Tabs */}
          {(project.burned_video_url || project.dubbed_video_url) && (
            <div className="flex items-center gap-1.5 p-1 bg-slate-100/90 rounded-2xl border border-slate-200 text-xs font-medium">
              {project.dubbed_video_url && (
                <button
                  type="button"
                  onClick={() => setActiveVideoSource('dubbed')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition-all cursor-pointer ${
                    (activeVideoSource === 'dubbed' || (activeVideoSource === 'auto' && project.dubbed_video_url))
                      ? 'bg-white text-slate-900 font-bold shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <span>🎙️ Lồng Tiếng AI (Có Giọng Đọc)</span>
                </button>
              )}

              {project.burned_video_url && (
                <button
                  type="button"
                  onClick={() => setActiveVideoSource('burned')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition-all cursor-pointer ${
                    (activeVideoSource === 'burned' || (activeVideoSource === 'auto' && !project.dubbed_video_url && project.burned_video_url))
                      ? 'bg-white text-slate-900 font-bold shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <span>🎬 Video Gắn Sub Cứng</span>
                </button>
              )}

              {project.original_video_url && (
                <button
                  type="button"
                  onClick={() => setActiveVideoSource('original')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition-all cursor-pointer ${
                    activeVideoSource === 'original'
                      ? 'bg-white text-slate-900 font-bold shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <span>📹 Video Gốc</span>
                </button>
              )}
            </div>
          )}

          <VideoPlayer
            videoUrl={
              activeVideoSource === 'burned' && project.burned_video_url ? project.burned_video_url :
              activeVideoSource === 'dubbed' && project.dubbed_video_url ? project.dubbed_video_url :
              activeVideoSource === 'original' && project.original_video_url ? project.original_video_url :
              (project.dubbed_video_url || project.burned_video_url || project.original_video_url)
            }
            isBurnedVideo={
              activeVideoSource === 'burned' ||
              (activeVideoSource === 'auto' && !project.dubbed_video_url && !!project.burned_video_url)
            }
            cues={cues}
            currentTime={currentTime}
            onTimeUpdate={setCurrentTime}
            seekTime={seekTarget}
          />

          {/* Dubbed Media Download & Status Box */}
          {(project.dubbed_video_url || project.dubbed_audio_url) && (
            <div className="bg-gradient-to-br from-indigo-50/80 to-violet-50/80 rounded-2xl p-4 border border-indigo-200/80 space-y-2.5 shadow-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-base">✨</span>
                  <span className="text-xs font-bold text-indigo-950 uppercase tracking-wider">
                    Bản Lồng Tiếng AI ({getFriendlyVoiceName(project.default_voice)})
                  </span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                  Hoàn tất
                </span>
              </div>
              <p className="text-[11px] text-indigo-900/80 leading-relaxed">
                Video và giọng lồng tiếng chất lượng cao đã sẵn sàng để tải về hoặc đăng tải.
              </p>
              <div className="grid grid-cols-2 gap-2 pt-1">
                {project.dubbed_video_url && (
                  <a
                    href={project.dubbed_video_url}
                    download
                    className="px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold text-center flex items-center justify-center space-x-1.5 shadow-xs transition-colors"
                  >
                    <span>🎬 Video (.mp4)</span>
                  </a>
                )}
                {project.dubbed_audio_url && (
                  <a
                    href={project.dubbed_audio_url}
                    download
                    className="px-3 py-2 rounded-xl bg-white hover:bg-slate-50 border border-indigo-200 text-indigo-900 text-xs font-bold text-center flex items-center justify-center space-x-1.5 shadow-2xs transition-colors"
                  >
                    <span>🎵 Âm thanh (.mp3)</span>
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Real-time Project Pipeline Status */}
          <div className="bg-white rounded-2xl p-4 border border-slate-200 space-y-2.5 shadow-sm">
            <div className="flex items-center justify-between text-xs font-bold">
              <span className="text-slate-500">Tiến Trình Xử Lý:</span>
              <span className="text-indigo-600 font-extrabold">{getFriendlyStageName(project.current_stage)}</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-indigo-500 via-cyan-500 to-emerald-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, project.progress_percentage))}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500 font-semibold">
              <span className="truncate max-w-[200px]">
                {project.error_message && !project.error_message.includes('Traceback') && !project.error_message.includes('Error')
                  ? project.error_message
                  : getFriendlyStageName(project.current_stage)}
              </span>
              <span className="text-indigo-600 font-bold shrink-0">{project.progress_percentage}%</span>
            </div>
          </div>
        </div>

        {/* Right: Dual-view Subtitle Editor */}
        <div className="lg:col-span-7 h-[calc(100vh-140px)] min-h-[620px]">
          <SubtitleEditor
            projectId={projectId}
            cues={cues}
            speakers={speakers}
            currentTime={currentTime}
            onSeek={handleSeek}
            onCueUpdated={handleCueUpdated}
            onRetranslateRequested={handleRetranslateRequested}
          />
        </div>
      </div>

      {/* Modals */}
      <DubbingModal
        project={project}
        isOpen={isDubModalOpen}
        onClose={() => setIsDubModalOpen(false)}
        onDubbingStarted={loadAllData}
        cuesCount={cues.length}
      />

      <SpeakerMatrixModal
        isOpen={isSpeakerModalOpen}
        onClose={() => setIsSpeakerModalOpen(false)}
        projectId={projectId}
        speakers={speakers}
        relationships={relationships}
        onUpdated={loadAllData}
      />

      <GlossaryModal
        isOpen={isGlossaryDrawerOpen}
        onClose={() => setIsGlossaryDrawerOpen(false)}
        projectId={projectId}
        terms={glossaryTerms}
        onUpdated={loadAllData}
      />

      <BurnProgressModal
        isOpen={isBurnModalOpen}
        onClose={() => setIsBurnModalOpen(false)}
        project={project}
        onBurnStarted={handleBurnStarted}
        cuesCount={cues.length}
      />
    </div>
  );
}
