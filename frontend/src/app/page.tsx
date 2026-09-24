'use client';

import { useEffect, useState } from 'react';
import { Plus, Video, Sparkles, Filter, Search, Loader2, PlayCircle, Zap, ShieldCheck, Cpu } from 'lucide-react';
import { Project } from '@/lib/types';
import { api } from '@/lib/api';
import ProjectCard from '@/components/ProjectCard';
import CreateProjectModal from '@/components/CreateProjectModal';

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const fetchProjects = async () => {
    try {
      const data = await api.listProjects();
      setProjects(data.items);
    } catch (e) {
      console.error('Failed to load projects', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
    const hasActiveProjects = projects.some(p => ['PROCESSING', 'INGESTING', 'ASR_PROCESSING', 'SPEAKER_PROFILING', 'TRANSLATING', 'BURNING', 'DUBBING'].includes(p.status));
    const intervalTime = hasActiveProjects ? 1500 : 5000;
    const interval = setInterval(fetchProjects, intervalTime);
    return () => clearInterval(interval);
  }, [projects]);

  const handleDeleteProject = async (id: string) => {
    if (!confirm('Are you sure you want to delete this project?')) return;
    try {
      await api.deleteProject(id);
      fetchProjects();
    } catch (e) {
      console.error(e);
    }
  };

  const filteredProjects = projects.filter(p => {
    const matchesSearch = p.title.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch) return false;
    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'PROCESSING') return ['PROCESSING', 'INGESTING', 'ASR_PROCESSING', 'TRANSLATING', 'BURNING'].includes(p.status);
    if (statusFilter === 'REVIEW') return p.status === 'WAITING_REVIEW';
    if (statusFilter === 'COMPLETED') return p.status === 'COMPLETED';
    return true;
  });

  const totalCount = projects.length;
  const processingCount = projects.filter(p => ['PROCESSING', 'INGESTING', 'ASR_PROCESSING', 'SPEAKER_PROFILING', 'TRANSLATING', 'BURNING', 'DUBBING'].includes(p.status)).length;
  const reviewCount = projects.filter(p => p.status === 'WAITING_REVIEW').length;
  const completedCount = projects.filter(p => p.status === 'COMPLETED').length;

  const [quickUrl, setQuickUrl] = useState('');
  const [isQuickSubmitting, setIsQuickSubmitting] = useState(false);

  const handleQuickBilibiliSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickUrl.trim()) return;
    setIsQuickSubmitting(true);
    try {
      const project = await api.createProjectFromUrl({
        url: quickUrl.trim(),
        source_language: 'zh',
        target_language: 'vi',
        auto_start_pipeline: true,
      });
      setQuickUrl('');
      fetchProjects();
    } catch (err: any) {
      alert(err.message || 'Lỗi khi tải video Bilibili');
    } finally {
      setIsQuickSubmitting(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in pb-12">
      {/* Hero Header & Quick Bilibili Bar */}
      <div className="relative rounded-3xl p-7 lg:p-9 overflow-hidden bg-white border border-slate-200/90 shadow-sm">
        <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-indigo-100/50 via-cyan-50/40 to-transparent rounded-full blur-3xl pointer-events-none -z-0" />

        <div className="relative z-10 max-w-4xl space-y-4">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-semibold shadow-2xs">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>Dual-Engine AI: Google Gemini 2.5 Flash + OpenAI GPT-4o & TTS Nova</span>
          </div>

          <h1 className="font-heading font-extrabold text-3xl sm:text-4xl lg:text-5xl text-slate-900 tracking-tight leading-tight">
            Phòng Thu Dịch & <span className="text-gradient">Lồng Tiếng Video AI</span>
          </h1>

          <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-2xl font-normal">
            Tự động tải video từ Bilibili, phân tích giọng nói (WhisperX + Diarization), dịch thuật ngữ cảnh với ma trận xưng hô nhân vật và lồng tiếng tự nhiên bằng giọng <strong>🌸 Nova</strong>.
          </p>

          {/* Instant Bilibili URL Bar & Primary Action */}
          <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-3 max-w-3xl">
            <form onSubmit={handleQuickBilibiliSubmit} className="flex-1 relative flex items-center">
              <input
                type="url"
                value={quickUrl}
                onChange={(e) => setQuickUrl(e.target.value)}
                placeholder="Dán link Bilibili (https://www.bilibili.com/video/BV... hoặc b23.tv)..."
                className="w-full pl-4 pr-32 py-3 rounded-2xl bg-slate-50 hover:bg-slate-100/70 focus:bg-white border border-slate-200 focus:border-indigo-500 text-slate-900 placeholder:text-slate-400 text-xs sm:text-sm focus:outline-none shadow-2xs transition-all font-medium"
              />
              <button
                type="submit"
                disabled={isQuickSubmitting || !quickUrl.trim()}
                className="absolute right-1.5 top-1.5 bottom-1.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-xs font-bold transition-all disabled:opacity-50 flex items-center gap-1.5 shadow-xs cursor-pointer"
              >
                {isQuickSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Đang tải...</span>
                  </>
                ) : (
                  <>
                    <span>🚀 Dịch Ngay</span>
                  </>
                )}
              </button>
            </form>

            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-5 py-3 rounded-2xl bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-2xs hover:border-slate-300 transition-all cursor-pointer shrink-0"
            >
              <Plus className="w-4 h-4 text-indigo-600" />
              <span>Tải File Từ Máy</span>
            </button>
          </div>
        </div>

        {/* 4 Metric Counter Cards */}
        <div className="mt-7 pt-6 border-t border-slate-100 grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-200/70 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Tổng Dự Án</p>
              <p className="text-xl font-bold text-slate-900 mt-0.5">{totalCount}</p>
            </div>
            <div className="w-9 h-9 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-sm">
              🎬
            </div>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-200/70 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Đang Xử Lý</p>
              <p className="text-xl font-bold text-indigo-600 mt-0.5">{processingCount}</p>
            </div>
            <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-sm">
              ⚡
            </div>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-200/70 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Chờ Duyệt Phụ Đề</p>
              <p className="text-xl font-bold text-cyan-600 mt-0.5">{reviewCount}</p>
            </div>
            <div className="w-9 h-9 rounded-xl bg-cyan-100 text-cyan-700 flex items-center justify-center font-bold text-sm">
              📝
            </div>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-200/70 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Đã Hoàn Tất</p>
              <p className="text-xl font-bold text-emerald-600 mt-0.5">{completedCount}</p>
            </div>
            <div className="w-9 h-9 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-sm">
              ✅
            </div>
          </div>
        </div>
      </div>

      {/* Projects Section */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="font-heading font-bold text-2xl text-slate-900">Translation Projects</h2>
            <p className="text-xs text-slate-500">Quản lý, biên tập và xuất bản video phụ đề của bạn.</p>
          </div>

          {/* Search & Status Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search projects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400 text-xs focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-xs transition-colors"
              />
            </div>

            <div className="flex items-center p-1 rounded-xl bg-slate-100 border border-slate-200 text-xs font-semibold">
              {['ALL', 'PROCESSING', 'REVIEW', 'COMPLETED'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setStatusFilter(tab)}
                  className={`px-3 py-1.5 rounded-lg transition-all ${
                    statusFilter === tab
                      ? 'bg-white text-indigo-700 shadow-xs border border-slate-200/60'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {tab === 'ALL' ? 'All' : tab === 'REVIEW' ? 'Waiting Review' : tab}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Project Grid */}
        {isLoading ? (
          <div className="text-center py-16 text-slate-400">
            <Loader2 className="w-8 h-8 mx-auto animate-spin mb-3 text-indigo-600" />
            <p className="text-sm font-medium">Loading projects from database...</p>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="bg-white rounded-3xl p-12 text-center border border-slate-200 shadow-sm space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 mx-auto flex items-center justify-center text-slate-400">
              <Video className="w-8 h-8" />
            </div>
            <div>
              <h3 className="font-heading font-bold text-lg text-slate-900">No projects found</h3>
              <p className="text-xs text-slate-500 mt-1">Get started by creating your first video translation project.</p>
            </div>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-colors shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>Create Project</span>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredProjects.map((project) => (
              <ProjectCard key={project.id} project={project} onDelete={handleDeleteProject} />
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      <CreateProjectModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={() => {
          fetchProjects();
        }}
      />
    </div>
  );
}
