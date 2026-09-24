'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Video, Settings, Sparkles, Layers } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function Navbar() {
  const pathname = usePathname();
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch('/api/v1/health');
        setIsBackendHealthy(res.ok);
      } catch (e) {
        setIsBackendHealthy(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-50 w-full bg-white/90 backdrop-blur-md border-b border-slate-200/80 px-6 py-3.5 shadow-sm">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-500 flex items-center justify-center shadow-md shadow-indigo-500/20 group-hover:scale-105 transition-transform">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-heading font-bold text-xl tracking-tight text-slate-900">One<span className="text-gradient">FL</span></span>
              <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">Studio</span>
            </div>
            <p className="text-[11px] text-slate-500">10h+ Multi-LLM Video Translator</p>
          </div>
        </Link>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200/60">
          <Link
            href="/"
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              pathname === '/'
                ? 'bg-white text-indigo-600 shadow-sm border border-slate-200/50'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Layers className="w-4 h-4" />
            Projects
          </Link>
          <Link
            href="/settings"
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              pathname === '/settings'
                ? 'bg-white text-indigo-600 shadow-sm border border-slate-200/50'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Settings className="w-4 h-4" />
            AI & Engines
          </Link>
        </nav>

        {/* Backend & AI Status Badges */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200 text-xs font-medium text-slate-700 shadow-xs">
            <span className={`w-2 h-2 rounded-full ${isBackendHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
            <span>FastAPI: {isBackendHealthy ? 'Online' : 'Connecting...'}</span>
          </div>

          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-200/80 text-xs font-medium text-indigo-700">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>Gemini 2.5 Flash + GPT-4o</span>
          </div>
        </div>
      </div>
    </header>
  );
}
