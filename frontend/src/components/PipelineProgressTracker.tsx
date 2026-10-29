'use client';

import { api } from '@/lib/api';
import { Project } from '@/lib/types';
import { getDubbingRecovery, isProjectBusy } from '@/lib/projectView';
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  FileAudio,
  Film,
  Flame,
  Headphones,
  Languages,
  Loader2,
  Mic,
  Play,
  RefreshCw,
  Sliders,
  Sparkles,
  Square,
  Terminal,
  Trash2,
  Users
} from 'lucide-react';
import React, { useRef, useState } from 'react';

export interface StepItem {
  id: string;
  name: string;
  shortDesc: string;
  detailedDesc: string;
  icon: React.ReactNode;
  status: 'completed' | 'current' | 'pending' | 'failed';
  completedSummary?: string;
}

export interface WorkflowInfo {
  type: 'DUBBING' | 'TRANSLATION' | 'BURNING' | 'DOWNLOAD' | 'QUEUED' | 'ASR';
  title: string;
  badge: string;
  badgeColor: string;
  steps: StepItem[];
  currentStepIndex: number;
}

export function getFriendlyStageName(stage?: string): string {
  if (!stage) return 'Đang xử lý';
  switch (stage) {
    case 'DOWNLOADING_URL':
      return 'Tải video về máy chủ';
    case 'INGESTING':
      return 'Trích xuất âm thanh (16kHz)';
    case 'ASR_PROCESSING':
      return 'Nhận diện giọng nói (Whisper AI)';
    case 'ASR_COMPLETE':
      return 'Đã nhận diện thoại; chờ dịch phụ đề';
    case 'SPEAKER_PROFILING':
      return 'Phân tích nhân vật & Xưng hô';
    case 'TRANSLATING':
      return 'Dịch thuật AI đa ngữ cảnh';
    case 'WAITING_REVIEW':
      return 'Sẵn sàng kiểm duyệt (Studio)';
    case 'DUBBING_PREPARE':
      return 'Chuẩn bị phụ đề & Giọng đọc';
    case 'DUBBING_VOICE_SYNTHESIS':
      return 'Tổng hợp giọng nói AI (TTS)';
    case 'DUBBING_VIDEO_MIXING':
      return 'Đồng bộ & Hòa trộn Video';
    case 'BURNING':
      return 'Render & Gắn phụ đề cứng (GPU NVENC)';
    case 'COMPLETED':
      return 'Hoàn tất thành công';
    case 'FAILED':
      return 'Xử lý thất bại';
    default:
      return stage;
  }
}

export function getFriendlyVoiceName(voiceId?: string | null): string {
  if (!voiceId) return 'Ngọc Huyền';
  const voiceMap: Record<string, string> = {
    'vieneu-truc-ly': 'Trúc Ly',
    'vieneu-mai-anh': 'Mai Anh',
    'vieneu-thuy-dung': 'Thùy Dung',
    'vieneu-ngoc-huyen': 'Ngọc Huyền',
    'vieneu-ngoc-tran': 'Ngọc Trân',
    'vieneu-ngoc-linh': 'Ngọc Linh',
    'vieneu-thuc-doan': 'Thục Đoan',
    'vieneu-my-duyen': 'Mỹ Duyên',
    'vieneu-minh-quan': 'Minh Quân',
    'vieneu-anh-khoi': 'Anh Khôi',
    'vieneu-minh-duc': 'Minh Đức',
    'vieneu-xuan-vinh': 'Xuân Vĩnh',
    'vieneu-thanh-binh': 'Thanh Bình',
    'vi-VN-HoaiMyNeural': 'Hoài My',
    'vi-VN-HoaiMyAnime': 'Hoài My',
    'vi-VN-HoaiMyNarrator': 'Hoài My',
    'vi-VN-NamMinhNeural': 'Nam Minh',
    'nova': 'Nova',
    'onyx': 'Onyx',
    'gtts-female-vi': 'Mai Lan',
  };
  return voiceMap[voiceId] || voiceId;
}

export function getWorkflowDetails(
  project: Project,
  cuesCount: number = 0,
  translatedCuesCount: number = 0
): WorkflowInfo {
  const isFailed = project.status === 'FAILED';
  const isCompleted = project.status === 'COMPLETED' || project.current_stage === 'COMPLETED' || (project.last_job_kind === 'DUBBING' && project.status === 'WAITING_REVIEW' && !!project.dubbed_video_url);
  const stage = project.current_stage || '';
  const status = project.status || '';
  if (status === 'QUEUED') return {
    type: 'QUEUED', title: 'Đang chờ worker nhận tác vụ', badge: 'Hàng đợi', badgeColor: 'bg-indigo-50 text-indigo-700', currentStepIndex: 0,
    steps: [{ id: 'queue', name: 'Chờ xử lý', shortDesc: 'Tác vụ đã được lưu', detailedDesc: 'Giao diện cập nhật khi worker bắt đầu xử lý.', icon: <Loader2 className="w-4 h-4" />, status: 'current' }],
  };

  if (project.last_job_kind === 'TRANSCRIBE') {
    const done = stage === 'ASR_COMPLETE';
    const index = stage === 'INGESTING' || (isFailed && project.progress_percentage <= 10) ? 0 : 1;
    return {
      type: 'ASR', title: 'Trích xuất & Nhận diện thoại', badge: 'ASR',
      badgeColor: 'bg-indigo-50 text-indigo-700', currentStepIndex: index,
      steps: [
        { id: 'extract', name: 'Trích xuất âm thanh', shortDesc: 'Audio 16 kHz mono', detailedDesc: 'Chuẩn bị audio từ video của project.', icon: <FileAudio className="w-4 h-4" />, status: done || index > 0 ? 'completed' : isFailed ? 'failed' : 'current' },
        { id: 'asr', name: 'Nhận diện thoại', shortDesc: 'Lưu transcript vào Studio', detailedDesc: 'Có transcript để kiểm duyệt; chưa thực hiện dịch thuật hoặc lồng tiếng.', icon: <Mic className="w-4 h-4" />, status: done ? 'completed' : isFailed && index === 1 ? 'failed' : index === 1 ? 'current' : 'pending', completedSummary: `Đã nhận diện ${cuesCount} câu; chờ dịch phụ đề` },
      ],
    };
  }

  // 1. DUBBING WORKFLOW
  if (status === 'DUBBING' || stage.startsWith('DUBBING') || (project.last_job_kind === 'DUBBING' && (isCompleted || isFailed)) || (isCompleted && project.dubbed_video_url && !project.burned_video_url)) {
    const voiceDisplayName = getFriendlyVoiceName(project.default_voice);

    let currentIndex = 1; // Default is voice synthesis (Step 2)
    if (stage === 'DUBBING_PREPARE') currentIndex = 0;
    else if (stage === 'DUBBING_VOICE_SYNTHESIS') currentIndex = 1;
    else if (stage === 'DUBBING_VIDEO_MIXING') currentIndex = 2;
    if (isCompleted || stage === 'COMPLETED') currentIndex = 3;

    const steps: StepItem[] = [
      {
        id: 'dub-prep',
        name: 'Chuẩn bị phụ đề & Giọng đọc',
        shortDesc: 'Kiểm tra timeline & ánh xạ giọng',
        detailedDesc: 'Hệ thống chuẩn bị dữ liệu phụ đề tiếng Việt và cấu hình giọng đọc nhân vật.',
        icon: <Mic className="w-4 h-4" />,
        status: currentIndex >= 0 ? 'completed' : 'current',
        completedSummary: `✓ Đã cấu hình giọng đọc (${voiceDisplayName})`,
      },
      {
        id: 'dub-synthesis',
        name: 'Tổng hợp giọng nói AI (TTS)',
        shortDesc: 'Sinh audio từng câu thoại',
        detailedDesc: 'Mô hình Neural AI chuyển đổi từng câu phụ đề tiếng Việt thành file audio giọng đọc tự nhiên.',
        icon: <Sparkles className="w-4 h-4" />,
        status: isFailed && currentIndex === 1 ? 'failed' : (currentIndex > 1 || isCompleted) ? 'completed' : currentIndex === 1 ? 'current' : 'pending',
        completedSummary: `✓ Đã tạo giọng đọc cho ${cuesCount} câu thoại`,
      },
      {
        id: 'dub-mixing',
        name: 'Đồng bộ timeline & Ghép Video',
        shortDesc: 'Audio ducking & Muxing video (~2 phút)',
        detailedDesc: 'Tự động giảm âm thanh nền (ducking) và hòa trộn âm thanh lồng tiếng vào video gốc (thời gian ghép tùy thời lượng video).',
        icon: <Sliders className="w-4 h-4" />,
        status: isFailed && currentIndex === 2 ? 'failed' : (currentIndex > 2 || isCompleted) ? 'completed' : currentIndex === 2 ? 'current' : 'pending',
        completedSummary: '✓ Đã hòa trộn âm thanh lồng tiếng vào video gốc thành công',
      },
      {
        id: 'dub-completed',
        name: 'Hoàn tất video',
        shortDesc: 'Sẵn sàng xem và tải về',
        detailedDesc: 'Video lồng tiếng AI hoàn chỉnh độ nét cao đã sẵn sàng để phát hoặc tải về máy.',
        icon: <Film className="w-4 h-4" />,
        status: isCompleted || currentIndex === 3 ? 'completed' : 'pending',
        completedSummary: '✓ Video lồng tiếng AI sẵn sàng phát & tải về (.MP4)',
      },
    ];

    return {
      type: 'DUBBING',
      title: `🎙️ Quy Trình Lồng Tiếng AI (${voiceDisplayName})`,
      badge: 'Lồng tiếng AI',
      badgeColor: 'bg-violet-50 text-violet-700 border-violet-200',
      steps,
      currentStepIndex: currentIndex,
    };
  }

  // 2. BURNING WORKFLOW
  if (status === 'BURNING' || stage === 'BURNING' || (project.last_job_kind === 'BURN' && (isCompleted || isFailed)) || (isCompleted && project.burned_video_url)) {
    let currentIndex = 1;
    if (isCompleted) currentIndex = 2;

    const steps: StepItem[] = [
      {
        id: 'burn-prep',
        name: 'Chuẩn bị phụ đề ASS',
        shortDesc: 'Định dạng phụ đề điện ảnh',
        detailedDesc: 'Tạo tệp phụ đề kiểu dáng chuẩn điện ảnh với font chữ, màu sắc và viền chữ sắc nét.',
        icon: <Sparkles className="w-4 h-4" />,
        status: 'completed',
        completedSummary: '✓ Đã tạo file phụ đề kiểu dáng điện ảnh ASS',
      },
      {
        id: 'burn-render',
        name: 'Render & Gắn phụ đề vào Video',
        shortDesc: 'In cứng phụ đề vào từng khung hình',
        detailedDesc: 'Sử dụng FFmpeg tăng tốc phần cứng GPU NVENC để in phụ đề trực tiếp vào luồng video gốc.',
        icon: <Flame className="w-4 h-4" />,
        status: isFailed ? 'failed' : isCompleted ? 'completed' : 'current',
        completedSummary: '✓ Đã hoàn tất render phụ đề cứng vào video',
      },
      {
        id: 'burn-completed',
        name: 'Hoàn tất video',
        shortDesc: 'Sẵn sàng tải về',
        detailedDesc: 'Video MP4 kèm phụ đề cứng đã được đóng gói hoàn chỉnh, sẵn sàng tải về máy.',
        icon: <Film className="w-4 h-4" />,
        status: isCompleted ? 'completed' : 'pending',
        completedSummary: '✓ Video MP4 gắn phụ đề sẵn sàng tải về',
      },
    ];

    return {
      type: 'BURNING',
      title: '🔥 Quy Trình Gắn Phụ Đề Cứng (Burn Subtitle)',
      badge: 'Burn Video',
      badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
      steps,
      currentStepIndex: currentIndex,
    };
  }

  // 3. DOWNLOADING URL WORKFLOW
  if (stage === 'DOWNLOADING_URL') {
    const steps: StepItem[] = [
      {
        id: 'dl-connect',
        name: 'Kết nối nguồn video',
        shortDesc: 'Phân tích liên kết',
        detailedDesc: 'Kết nối đến Bilibili / YouTube và phân tích luồng phát tối ưu.',
        icon: <Download className="w-4 h-4" />,
        status: 'completed',
        completedSummary: '✓ Đã kết nối và lấy thông tin video',
      },
      {
        id: 'dl-downloading',
        name: 'Tải video gốc về máy chủ',
        shortDesc: `Đang tải (${project.progress_percentage}%)`,
        detailedDesc: 'Tải dữ liệu video và âm thanh chất lượng cao về hệ thống lưu trữ dự án.',
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
        status: isFailed ? 'failed' : 'current',
      },
      {
        id: 'dl-ready',
        name: 'Sẵn sàng xử lý',
        shortDesc: 'Chờ hoàn thành tải',
        detailedDesc: 'Video sẵn sàng để khởi chạy nhận diện giọng nói và dịch phụ đề AI.',
        icon: <CheckCircle2 className="w-4 h-4" />,
        status: 'pending',
      },
    ];

    return {
      type: 'DOWNLOAD',
      title: '📥 Quy Trình Tải Video Trực Tuyến',
      badge: 'Đang tải video',
      badgeColor: 'bg-pink-50 text-pink-700 border-pink-200',
      steps,
      currentStepIndex: 1,
    };
  }

  // 4. MAIN TRANSLATION & ASR PIPELINE
  const isIngestDone = ['ASR_PROCESSING', 'SPEAKER_PROFILING', 'TRANSLATING', 'WAITING_REVIEW', 'COMPLETED'].includes(stage) || cuesCount > 0;
  const isAsrDone = ['SPEAKER_PROFILING', 'TRANSLATING', 'WAITING_REVIEW', 'COMPLETED'].includes(stage) || cuesCount > 0;
  const isSpeakerDone = ['TRANSLATING', 'WAITING_REVIEW', 'COMPLETED'].includes(stage) || (project.speaker_count || 0) > 0;
  const isTranslateDone = ['WAITING_REVIEW', 'COMPLETED'].includes(stage) || (cuesCount > 0 && translatedCuesCount > 0 && stage !== 'TRANSLATING');
  const isStudioReady = stage === 'WAITING_REVIEW' || isCompleted;

  let currentIndex = 0;
  if (stage === 'ASR_PROCESSING') currentIndex = 1;
  else if (stage === 'SPEAKER_PROFILING') currentIndex = 2;
  else if (stage === 'TRANSLATING') currentIndex = 3;
  else if (isStudioReady) currentIndex = 4;

  const totalCues = cuesCount || project.cue_count || 0;
  const totalSpeakers = project.speaker_count || 0;

  const steps: StepItem[] = [
    {
      id: 'pipe-ingest',
      name: '1. Trích xuất âm thanh',
      shortDesc: 'Tách audio 16kHz mono',
      detailedDesc: 'Tách luồng âm thanh gốc độ phân giải cao từ tệp video để phục vụ nhận diện AI.',
      icon: <FileAudio className="w-4 h-4" />,
      status: isFailed && currentIndex === 0 ? 'failed' : isIngestDone ? 'completed' : 'current',
      completedSummary: '✓ Đã trích xuất file audio 16kHz mono',
    },
    {
      id: 'pipe-asr',
      name: '2. Nhận diện giọng nói AI (ASR)',
      shortDesc: 'Whisper tách câu & mốc thời gian',
      detailedDesc: 'Mô hình Whisper nhận diện lời thoại, tách từng câu và căn chỉnh mốc thời gian bắt đầu/kết thúc.',
      icon: <Headphones className="w-4 h-4" />,
      status: isFailed && currentIndex === 1 ? 'failed' : isAsrDone ? 'completed' : isIngestDone ? 'current' : 'pending',
      completedSummary: totalCues > 0 ? `✓ Đã nhận diện thành công ${totalCues} câu thoại` : '✓ Đã nhận diện lời thoại & timeline',
    },
    {
      id: 'pipe-speaker',
      name: '3. Phân tích nhân vật & Xưng hô',
      shortDesc: 'AI xây dựng ma trận xưng hô',
      detailedDesc: 'Phân tích người nói (diarization), nhận diện vai vế, quan hệ xã hội để tạo xưng hô tự nhiên.',
      icon: <Users className="w-4 h-4" />,
      status: isFailed && currentIndex === 2 ? 'failed' : isSpeakerDone ? 'completed' : isAsrDone ? 'current' : 'pending',
      completedSummary: totalSpeakers > 0 ? `✓ Đã xác định ${totalSpeakers} nhân vật & quan hệ xưng hô` : 'Chưa có hồ sơ nhân vật; sử dụng nhãn ASR',
    },
    {
      id: 'pipe-translate',
      name: '4. Dịch thuật AI đa ngữ cảnh',
      shortDesc: 'LLM dịch sát nghĩa & áp dụng thuật ngữ',
      detailedDesc: 'Dịch thuật phụ đề bằng AI ngữ cảnh cao, áp dụng thuật ngữ chuyên ngành và kiểm soát độ dài dòng phụ đề.',
      icon: <Languages className="w-4 h-4" />,
      status: isFailed && currentIndex === 3 ? 'failed' : isTranslateDone ? 'completed' : isSpeakerDone ? 'current' : 'pending',
      completedSummary: translatedCuesCount > 0 ? `✓ Đã dịch ${translatedCuesCount} câu sang tiếng Việt chuẩn` : '✓ Đã hoàn tất bản dịch tiếng Việt',
    },
    {
      id: 'pipe-review',
      name: '5. Sẵn sàng kiểm duyệt (Studio)',
      shortDesc: 'Xem video & tinh chỉnh phụ đề',
      detailedDesc: 'Dữ liệu đã sẵn sàng trên Studio Workspace để phát thử video, chỉnh sửa text và căn chỉnh timeline.',
      icon: <CheckCircle2 className="w-4 h-4" />,
      status: isStudioReady ? 'completed' : 'pending',
      completedSummary: '✓ Phụ đề đã sẵn sàng trong Studio để duyệt và xuất bản',
    },
  ];

  return {
    type: 'TRANSLATION',
    title: '🚀 Quy Trình Nhận Diện & Dịch Phụ Đề AI',
    badge: 'Dịch thuật AI',
    badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    steps,
    currentStepIndex: currentIndex,
  };
}

interface PipelineProgressTrackerProps {
  project: Project;
  cuesCount?: number;
  translatedCuesCount?: number;
  onRetry?: () => void;
  onResume?: () => void;
  onReset?: () => void;
  onRefresh?: () => void;
  liveLogs?: Array<{ time: string; text: string; level?: 'info' | 'warn' | 'success' | 'error' }>;
  className?: string;
  defaultExpanded?: boolean;
}

export default function PipelineProgressTracker({
  project,
  cuesCount = 0,
  translatedCuesCount = 0,
  onRetry,
  onResume,
  onReset,
  onRefresh,
  liveLogs = [],
  className = '',
  defaultExpanded = true,
}: PipelineProgressTrackerProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded);
  const [isActionLoading, setIsActionLoading] = useState<boolean>(false);
  const [showTerminal, setShowTerminal] = useState<boolean>(true);
  const [actionError, setActionError] = useState('');
  const actionPending = useRef(false);
  const recovery = getDubbingRecovery(project);
  const canResumeDubbing = recovery === 'resumable';

  const handleResume = async () => {
    if (actionPending.current || !canResumeDubbing) return;
    actionPending.current = true;
    try {
      setIsActionLoading(true);
      setActionError('');
      // A job may have started in another tab since this snapshot rendered.
      const latest = await api.getProject(project.id);
      if (getDubbingRecovery(latest) !== 'resumable') {
        await onRefresh?.();
        return;
      }
      if (onResume) {
        await onResume();
      } else {
        await api.resumeProjectDubbing(project.id);
      }
      await onRefresh?.();
    } catch (err: unknown) {
      setActionError('Không thể tiếp tục lồng tiếng: ' + (err instanceof Error ? err.message : String(err)));
      await onRefresh?.();
    } finally {
      actionPending.current = false;
      setIsActionLoading(false);
    }
  };

  const handleReset = async () => {
    if (actionPending.current) return;
    if (!confirm("Bạn có chắc chắn muốn đặt lại trạng thái về Studio để tiếp tục thao tác? Toàn bộ các câu đã lồng tiếng hoặc dịch sẽ KHÔNG bị mất.")) return;
    actionPending.current = true;
    try {
      setIsActionLoading(true);
      if (onReset) {
        await onReset();
      } else {
        await api.resetProjectStatus(project.id, 'WAITING_REVIEW');
        if (onRefresh) onRefresh();
      }
    } catch (err: any) {
      alert("Không thể đặt lại: " + (err.message || err));
    } finally {
      actionPending.current = false;
      setIsActionLoading(false);
    }
  };

  const workflow = getWorkflowDetails(project, cuesCount, translatedCuesCount);
  const isFailed = project.status === 'FAILED';
  const isCompleted = project.status === 'COMPLETED';
  const isWaitingReview = project.status === 'WAITING_REVIEW';
  const isCancelled = project.status === 'CANCELLED';
  const isProcessing = isProjectBusy(project);

  const currentStep = workflow.steps[workflow.currentStepIndex] || workflow.steps[0];
  const completedCount = workflow.steps.filter(s => s.status === 'completed').length;
  const totalSteps = workflow.steps.length;

  // Compute live descriptive message
  const liveMessage = (() => {
    if (isFailed) {
      return project.error_message || 'Có lỗi xảy ra trong quá trình xử lý.';
    }
    if (project.error_message && !project.error_message.includes('Traceback') && !project.error_message.includes('Error')) {
      return project.error_message;
    }
    return currentStep?.detailedDesc || 'Hệ thống đang xử lý tự động...';
  })();

  const nowStr = new Date().toLocaleTimeString('vi-VN', { hour12: false });
  const allLogs = [
    {
      time: nowStr,
      text: `[HỆ THỐNG] Dự án: "${project.title.slice(0, 45)}..." · Trạng thái: ${project.status} (${project.progress_percentage}%)`,
      level: 'info' as const
    },
    ...(project.error_message ? [{
      time: nowStr,
      text: project.error_message,
      level: isFailed ? ('error' as const) : ('info' as const)
    }] : []),
    ...liveLogs
  ];

  return (
    <div className={`rounded-3xl bg-white border border-indigo-100/90 shadow-sm overflow-hidden transition-all duration-300 ${className}`}>
      {/* Top Banner Header */}
      <div className="p-4 sm:p-5 bg-gradient-to-r from-indigo-50/70 via-slate-50 to-cyan-50/50 border-b border-indigo-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-indigo-600 text-white flex items-center justify-center shadow-md shadow-indigo-500/20 shrink-0">
            {isProcessing ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : isFailed ? (
              <AlertCircle className="w-5 h-5 text-rose-200" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-emerald-200" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-heading font-bold text-slate-900 text-base sm:text-lg">
                {workflow.title}
              </h3>
              <span className={`text-[11px] font-extrabold px-2.5 py-0.5 rounded-full border ${workflow.badgeColor}`}>
                {workflow.badge}
              </span>
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                Bước {completedCount}/{totalSteps} hoàn thành
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5 font-medium">
              {isProcessing
                ? `Đang thực thi: ${currentStep.name}`
                : isWaitingReview
                  ? 'Đã sẵn sàng kiểm duyệt phụ đề trên Studio Timeline'
                  : isCompleted
                    ? 'Tất cả các công đoạn đã hoàn tất thành công'
                    : 'Đã dừng do phát sinh lỗi'}
            </p>
          </div>
        </div>

        {/* Right side: Percentage & Expand Toggle */}
        <div className="flex items-center gap-3 self-end sm:self-center">
          <div className="text-right">
            <span className="text-xs font-semibold text-slate-400 block uppercase tracking-wider">Tiến độ</span>
            <span className="text-xl sm:text-2xl font-black bg-gradient-to-r from-indigo-600 to-cyan-600 bg-clip-text text-transparent">
              {project.progress_percentage}%
            </span>
          </div>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-700 hover:text-slate-900 border border-slate-200 text-xs font-bold transition-all shadow-2xs"
            title={isExpanded ? 'Thu gọn sơ đồ' : 'Xem chi tiết các bước'}
          >
            <span>{isExpanded ? 'Thu gọn' : 'Xem các bước'}</span>
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Main Master Progress Bar */}
      <div className="px-4 sm:px-5 pt-3 pb-1">
        <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden shadow-inner p-0.5">
          <div
            className={`h-full rounded-full transition-all duration-500 shadow-sm ${isFailed
              ? 'bg-rose-500'
              : isCompleted || isWaitingReview
                ? 'bg-gradient-to-r from-teal-500 to-emerald-500'
                : 'bg-gradient-to-r from-indigo-500 via-cyan-500 to-emerald-500 animate-pulse'
              }`}
            style={{ width: `${Math.min(100, Math.max(0, project.progress_percentage))}%` }}
          />
        </div>
      </div>

      {/* Current Live Activity Callout Box */}
      <div className="px-4 sm:px-5 py-3">
        <div className={`p-3.5 rounded-2xl border flex items-start gap-3 transition-colors ${isFailed
          ? 'bg-rose-50/80 border-rose-200 text-rose-900'
          : isCompleted || isWaitingReview
            ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
            : 'bg-indigo-50/70 border-indigo-200/80 text-indigo-950'
          }`}>
          <div className="mt-0.5 shrink-0">
            {isFailed ? (
              <AlertCircle className="w-4 h-4 text-rose-600" />
            ) : isCompleted || isWaitingReview ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            ) : (
              <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-wider">
                {isFailed
                  ? 'Lỗi xảy ra'
                  : isCompleted
                    ? 'Hoàn tất quy trình'
                    : isWaitingReview
                      ? 'Sẵn sàng kiểm duyệt'
                      : `Đang thực hiện: ${currentStep.name}`}
              </span>
              <div className="flex items-center gap-1.5 flex-wrap">
                {canResumeDubbing && (
                    <button
                      onClick={handleResume}
                      disabled={isActionLoading}
                      className="flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white transition-all shadow-xs cursor-pointer hover:scale-105 active:scale-95 disabled:opacity-50"
                      title="Chạy tiếp quy trình lồng tiếng (tự động bỏ qua các câu đã tạo sẵn)"
                    >
                      <Play className="w-3 h-3 fill-white" />
                      <span>{isActionLoading ? 'Đang gửi...' : 'Tiếp tục chạy'}</span>
                    </button>
                )}
                {isProcessing && (
                    <button
                      onClick={handleReset}
                      disabled={isActionLoading}
                      className="flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-xl bg-slate-200 hover:bg-rose-100 text-slate-700 hover:text-rose-700 transition-all border border-slate-300/80 cursor-pointer disabled:opacity-50"
                      title="Đặt lại trạng thái về Studio để tiếp tục thao tác"
                    >
                      <Square className="w-3 h-3" />
                      <span>Dừng / Đặt lại</span>
                    </button>
                )}
                {(isFailed || isCancelled) && !isProcessing && (
                  <>
                    {onRetry && workflow.type === 'TRANSLATION' && (
                      <button
                        onClick={onRetry}
                        className="flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-xl bg-rose-600 hover:bg-rose-700 text-white transition-colors cursor-pointer"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>Thử lại</span>
                      </button>
                    )}
                    <button
                      onClick={handleReset}
                      disabled={isActionLoading}
                      className="flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-xl bg-slate-200 hover:bg-slate-300 text-slate-700 transition-colors cursor-pointer"
                    >
                      <Square className="w-3 h-3" />
                      <span>Đặt lại Studio</span>
                    </button>
                  </>
                )}
                <button
                  onClick={() => setShowTerminal(!showTerminal)}
                  className={`flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-xl transition-all border cursor-pointer ${
                    showTerminal
                      ? 'bg-slate-900 text-emerald-400 border-slate-800'
                      : 'bg-white text-slate-700 hover:bg-slate-100 border-slate-200'
                  }`}
                  title="Bật/Tắt xem console log trực tiếp"
                >
                  <Terminal className="w-3 h-3 text-cyan-500" />
                  <span>{showTerminal ? 'Ẩn Console' : 'Xem Live Logs'}</span>
                </button>
              </div>
            </div>
            <p className="text-xs mt-1 leading-relaxed opacity-90 font-medium">
              {liveMessage}
            </p>
            {actionError && <p role="alert" className="mt-2 text-xs text-rose-700">{actionError}</p>}
            {recovery === 'configure' && <p className="mt-2 text-xs text-amber-800">
              Chưa có cấu hình lồng tiếng đã lưu. Mở Lồng Tiếng AI để chọn giọng và bắt đầu.
            </p>}
          </div>
        </div>
      </div>

      {/* Stepper Roadmap: Horizontal Connected Nodes */}
      <div className="px-4 sm:px-5 pb-5 pt-2">
        <div className="relative">
          {/* Connecting Line between steps */}
          <div className="hidden md:block absolute top-5 left-8 right-8 h-1 bg-slate-100 rounded-full z-0">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-indigo-500 rounded-full transition-all duration-500"
              style={{
                width: `${totalSteps > 1 ? (Math.min(completedCount, totalSteps - 1) / (totalSteps - 1)) * 100 : 100}%`
              }}
            />
          </div>

          {/* Steps Grid */}
          <div className={`grid gap-3 relative z-10 ${totalSteps === 3 ? 'grid-cols-1 md:grid-cols-3' :
            totalSteps === 4 ? 'grid-cols-1 md:grid-cols-4' :
              'grid-cols-1 md:grid-cols-5'
            }`}>
            {workflow.steps.map((step, idx) => {
              const isStepCompleted = step.status === 'completed';
              const isStepCurrent = step.status === 'current';
              const isStepFailed = step.status === 'failed';

              return (
                <div
                  key={step.id}
                  className={`p-3 rounded-2xl border transition-all ${isStepCurrent
                    ? 'bg-gradient-to-b from-indigo-50/90 to-white border-indigo-300 ring-2 ring-indigo-500/20 shadow-md shadow-indigo-100'
                    : isStepCompleted
                      ? 'bg-emerald-50/40 border-emerald-200/80'
                      : isStepFailed
                        ? 'bg-rose-50/50 border-rose-300 ring-2 ring-rose-500/20'
                        : 'bg-slate-50/60 border-slate-200/70 opacity-70'
                    }`}
                >
                  {/* Node Icon & Status Indicator */}
                  <div className="flex items-center justify-between mb-2">
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs shadow-xs transition-all ${isStepCompleted
                      ? 'bg-emerald-500 text-white shadow-emerald-500/20'
                      : isStepCurrent
                        ? 'bg-indigo-600 text-white ring-4 ring-indigo-100 shadow-indigo-500/30'
                        : isStepFailed
                          ? 'bg-rose-600 text-white'
                          : 'bg-slate-200 text-slate-500'
                      }`}>
                      {isStepCompleted ? (
                        <Check className="w-4 h-4 stroke-[3]" />
                      ) : isStepCurrent ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : isStepFailed ? (
                        <AlertCircle className="w-4 h-4" />
                      ) : (
                        <span>{idx + 1}</span>
                      )}
                    </div>

                    <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-md uppercase tracking-wider ${isStepCompleted
                      ? 'bg-emerald-100 text-emerald-800'
                      : isStepCurrent
                        ? 'bg-indigo-100 text-indigo-800 animate-pulse'
                        : isStepFailed
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-slate-200/70 text-slate-600'
                      }`}>
                      {isStepCompleted ? 'Đã xong' : isStepCurrent ? 'Đang chạy' : isStepFailed ? 'Lỗi' : 'Chờ'}
                    </span>
                  </div>

                  {/* Step Title & Details */}
                  <div>
                    <h4 className={`text-xs font-bold line-clamp-1 ${isStepCurrent ? 'text-indigo-950 font-extrabold' : isStepCompleted ? 'text-slate-800' : 'text-slate-600'
                      }`}>
                      {step.name}
                    </h4>
                    <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-2 leading-tight">
                      {isStepCompleted && step.completedSummary
                        ? step.completedSummary
                        : step.shortDesc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Collapsible Step-by-Step Detailed History / Checklist */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-slate-100 space-y-2.5 animate-fade-in">
            <div className="flex items-center justify-between text-xs font-bold text-slate-600 px-1">
              <span>Lịch sử chi tiết từng giai đoạn:</span>
              <span className="text-[11px] font-normal text-slate-400">Tự động cập nhật theo thời gian thực</span>
            </div>

            <div className="space-y-2">
              {workflow.steps.map((step, idx) => (
                <div
                  key={`detail-${step.id}`}
                  className="flex items-start gap-3 p-2.5 rounded-xl bg-slate-50/80 border border-slate-200/60 text-xs"
                >
                  <div className="mt-0.5 shrink-0">
                    {step.status === 'completed' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : step.status === 'current' ? (
                      <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />
                    ) : step.status === 'failed' ? (
                      <AlertCircle className="w-4 h-4 text-rose-600" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-slate-300 flex items-center justify-center text-[9px] text-slate-400 font-bold">
                        {idx + 1}
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-slate-800">
                        {step.name}
                      </span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${step.status === 'completed'
                        ? 'bg-emerald-100 text-emerald-800'
                        : step.status === 'current'
                          ? 'bg-indigo-100 text-indigo-800'
                          : step.status === 'failed'
                            ? 'bg-rose-100 text-rose-800'
                            : 'text-slate-400'
                        }`}>
                        {step.status === 'completed'
                          ? 'Đã hoàn thành'
                          : step.status === 'current'
                            ? 'Đang thực thi...'
                            : step.status === 'failed'
                              ? 'Gặp sự cố'
                              : 'Chưa thực hiện'}
                      </span>
                    </div>
                    <p className="text-slate-500 text-[11px] mt-0.5 leading-relaxed">
                      {step.status === 'completed' && step.completedSummary
                        ? step.completedSummary
                        : step.detailedDesc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Real-time Terminal Log Console Drawer */}
      {showTerminal && (
        <div className="border-t border-slate-200 bg-slate-950 p-4 font-mono text-xs text-slate-300">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-[11px]">
            <div className="flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-cyan-400" />
              <span className="font-bold text-slate-200">CONSOLE TRỰC TIẾP (LIVE EXECUTION LOGS)</span>
              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px]">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                <span>TRỰC TIẾP</span>
              </span>
            </div>
            <div className="flex items-center gap-2 text-[10px] text-slate-400">
              <span>Trạng thái: <strong className="text-indigo-400">{project.status}</strong></span>
              <span>•</span>
              <span>Tiến độ: <strong className="text-emerald-400">{project.progress_percentage}%</strong></span>
            </div>
          </div>

          <div className="mt-2.5 space-y-1.5 max-h-52 overflow-y-auto select-text font-mono text-[11px] leading-relaxed">
            {allLogs.map((log, index) => (
              <div key={index} className="flex items-start gap-2">
                <span className="text-slate-500 shrink-0 select-none">[{log.time}]</span>
                <span className={`shrink-0 font-bold ${
                  log.level === 'error' ? 'text-rose-400' :
                  log.level === 'warn' ? 'text-amber-400' :
                  log.level === 'success' ? 'text-emerald-400' :
                  'text-cyan-400'
                }`}>
                  {log.level === 'error' ? '✖ [ERROR]' :
                   log.level === 'warn' ? '⚠ [WARN]' :
                   log.level === 'success' ? '✓ [DONE]' :
                   '▶ [SYS]'}
                </span>
                <span className={`${
                  log.level === 'error' ? 'text-rose-300' :
                  log.level === 'warn' ? 'text-amber-200' :
                  log.level === 'success' ? 'text-emerald-200' :
                  'text-slate-300'
                }`}>
                  {log.text}
                </span>
              </div>
            ))}
          </div>

          {canResumeDubbing && (
            <div className="mt-3 pt-2 border-t border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5 text-amber-300/90 text-[11px]">
                <span>💡</span>
                <span>Nếu server từng bị tắt giữa chừng, các file audio đã tạo vẫn được lưu trên đĩa. Nhấn <strong>"Tiếp tục chạy"</strong> để làm tiếp câu còn lại.</span>
              </span>
              <button
                onClick={handleResume}
                disabled={isActionLoading}
                className="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-[10px] transition-colors shrink-0"
              >
                Tiếp tục từ điểm dừng
              </button>
            </div>
          )}
          {isProcessing && <p className="mt-3 border-t border-slate-800/80 pt-2 text-[11px] text-slate-400">
            Tác vụ đang chạy hoặc chờ worker. Sau khi khởi động lại server, worker tự khôi phục job đã lưu.
          </p>}
        </div>
      )}
    </div>
  );
}
