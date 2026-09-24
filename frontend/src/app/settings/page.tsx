'use client';

import { useEffect, useState } from 'react';
import { Settings, Sparkles, CheckCircle2, AlertCircle, Loader2, Cpu } from 'lucide-react';
import { SystemInfo } from '@/lib/types';
import { api } from '@/lib/api';

export default function SettingsPage() {
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Key testing states
  const [geminiKeyInput, setGeminiKeyInput] = useState('');
  const [geminiTestStatus, setGeminiTestStatus] = useState<{ testing: boolean; success?: boolean; error?: string; raw?: any } | null>(null);

  const [openaiKeyInput, setOpenaiKeyInput] = useState('');
  const [openaiTestStatus, setOpenaiTestStatus] = useState<{ testing: boolean; success?: boolean; error?: string; raw?: any } | null>(null);

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const info = await api.getSystemSettings();
        setSystemInfo(info);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    };
    fetchInfo();
  }, []);

  const handleTestGemini = async () => {
    setGeminiTestStatus({ testing: true });
    try {
      const res = await api.testApiKey('gemini', geminiKeyInput || undefined);
      setGeminiTestStatus({
        testing: false,
        success: res.success,
        error: res.error,
        raw: res.raw_response,
      });
    } catch (e: any) {
      setGeminiTestStatus({ testing: false, success: false, error: e.message });
    }
  };

  const handleTestOpenAI = async () => {
    setOpenaiTestStatus({ testing: true });
    try {
      const res = await api.testApiKey('openai', openaiKeyInput || undefined);
      setOpenaiTestStatus({
        testing: false,
        success: res.success,
        error: res.error,
        raw: res.raw_response,
      });
    } catch (e: any) {
      setOpenaiTestStatus({ testing: false, success: false, error: e.message });
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm flex items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
          <Settings className="w-6 h-6" />
        </div>
        <div>
          <h1 className="font-heading font-bold text-2xl text-slate-900">System Diagnostics & AI Providers</h1>
          <p className="text-xs text-slate-500 font-medium">Multi-LLM configuration, API connectivity test, and engine guardrails.</p>
        </div>
      </div>

      {/* AI Key Test Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Gemini Provider */}
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-cyan-50 border border-cyan-200 text-cyan-700 flex items-center justify-center">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-heading font-bold text-base text-slate-900">Google Gemini</h3>
                <p className="text-[11px] text-slate-500 font-medium">Động cơ dịch chính ({systemInfo?.gemini_model || 'gemini-2.5-flash'})</p>
              </div>
            </div>
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
              Primary
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
            <div className="flex items-center justify-between font-semibold text-slate-700">
              <span>Định dạng Key:</span>
              <span className="font-mono text-indigo-600 text-[11px]">AIzaSy...</span>
            </div>
            <p className="text-[11px] leading-relaxed text-slate-500">
              Lấy API Key chính thức tại{' '}
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noreferrer"
                className="text-indigo-600 font-bold hover:underline"
              >
                Google AI Studio ↗
              </a>
              . (Lưu ý: Không dùng access token OAuth dạng AQ.Ab8...).
            </p>
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700">
              Gemini API Key (Nhập để thử nghiệm hoặc ghi đè)
            </label>
            <input
              type="password"
              placeholder="AIzaSy... (Mặc định dùng key từ file .env)"
              value={geminiKeyInput}
              onChange={(e) => setGeminiKeyInput(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white shadow-2xs transition-colors font-mono"
            />
          </div>

          {geminiTestStatus && (
            <div
              className={`p-3 rounded-xl border text-xs ${
                geminiTestStatus.success
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800 font-medium'
                  : 'bg-rose-50 border-rose-200 text-rose-800'
              }`}
            >
              {geminiTestStatus.success ? (
                <div className="flex items-center gap-2 font-bold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Kết nối Gemini thành công! Sẵn sàng dịch thuật.</span>
                </div>
              ) : (
                <div>
                  <div className="flex items-center gap-2 font-bold text-rose-700">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>Kiểm tra thất bại:</span>
                  </div>
                  <p className="text-[11px] mt-1 opacity-90 leading-snug">{geminiTestStatus.error}</p>
                </div>
              )}
            </div>
          )}

          <button
            onClick={handleTestGemini}
            disabled={geminiTestStatus?.testing}
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-colors flex items-center justify-center gap-2 disabled:opacity-50 shadow-sm cursor-pointer"
          >
            {geminiTestStatus?.testing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Đang kiểm tra kết nối Gemini...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Kiểm Tra Kết Nối Gemini
              </>
            )}
          </button>
        </div>

        {/* OpenAI Provider */}
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-pink-50 border border-pink-200 text-pink-700 flex items-center justify-center">
                <Cpu className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-heading font-bold text-base text-slate-900">OpenAI (GPT & TTS Nova)</h3>
                <p className="text-[11px] text-slate-500 font-medium">Dự phòng & Lồng tiếng Nova ({systemInfo?.openai_model || 'gpt-4o-mini'})</p>
              </div>
            </div>
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200">
              TTS & Fallback
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
            <div className="flex items-center justify-between font-semibold text-slate-700">
              <span>Định dạng Key:</span>
              <span className="font-mono text-indigo-600 text-[11px]">sk-proj-... hoặc sk-...</span>
            </div>
            <p className="text-[11px] leading-relaxed text-slate-500">
              Lấy API Key tại{' '}
              <a
                href="https://platform.openai.com/api-keys"
                target="_blank"
                rel="noreferrer"
                className="text-indigo-600 font-bold hover:underline"
              >
                OpenAI Platform ↗
              </a>
              . Dùng cho dịch dự phòng và giọng lồng tiếng <strong>🌸 Nova</strong>.
            </p>
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700">
              OpenAI API Key (Nhập để thử nghiệm hoặc ghi đè)
            </label>
            <input
              type="password"
              placeholder="sk-... (Mặc định dùng key từ file .env)"
              value={openaiKeyInput}
              onChange={(e) => setOpenaiKeyInput(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white shadow-2xs transition-colors font-mono"
            />
          </div>

          {openaiTestStatus && (
            <div
              className={`p-3 rounded-xl border text-xs ${
                openaiTestStatus.success
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800 font-medium'
                  : 'bg-rose-50 border-rose-200 text-rose-800'
              }`}
            >
              {openaiTestStatus.success ? (
                <div className="flex items-center gap-2 font-bold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>OpenAI API connection OK! JSON Mode verified.</span>
                </div>
              ) : (
                <div>
                  <div className="flex items-center gap-2 font-bold text-rose-700">
                    <AlertCircle className="w-4 h-4" />
                    <span>OpenAI Test Failed:</span>
                  </div>
                  <p className="text-[11px] mt-1 opacity-90">{openaiTestStatus.error}</p>
                </div>
              )}
            </div>
          )}

          <button
            onClick={handleTestOpenAI}
            disabled={openaiTestStatus?.testing}
            className="w-full py-2.5 rounded-xl bg-pink-600 hover:bg-pink-700 text-white text-xs font-bold transition-colors flex items-center justify-center gap-2 disabled:opacity-50 shadow-sm"
          >
            {openaiTestStatus?.testing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Testing OpenAI API...
              </>
            ) : (
              <>
                <Cpu className="w-4 h-4" /> Test OpenAI Connectivity
              </>
            )}
          </button>
        </div>
      </div>

      {/* Engine & Guardrails Specs */}
      <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm space-y-4">
        <h3 className="font-heading font-bold text-lg text-slate-900">4-Tier Guardrail Specification</h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-1.5">
            <span className="text-[10px] uppercase font-bold text-indigo-700">Physical Limit</span>
            <p className="font-bold text-slate-900 text-sm">Max {systemInfo?.max_line_length || 40} chars/line</p>
            <p className="text-slate-500 text-[11px]">Auto-balanced 2-line break algorithm</p>
          </div>

          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-1.5">
            <span className="text-[10px] uppercase font-bold text-cyan-700">Reading Speed</span>
            <p className="font-bold text-slate-900 text-sm">Max {systemInfo?.max_cps || 20} CPS</p>
            <p className="text-slate-500 text-[11px]">Characters Per Second speed gauge</p>
          </div>

          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-1.5">
            <span className="text-[10px] uppercase font-bold text-pink-700">Reflexion Loop</span>
            <p className="font-bold text-slate-900 text-sm">Fast-Fix Enabled</p>
            <p className="text-slate-500 text-[11px]">Self-corrects only violated subtitle lines</p>
          </div>
        </div>
      </div>
    </div>
  );
}
