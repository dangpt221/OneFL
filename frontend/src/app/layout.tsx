import type { Metadata } from 'next';
import '@/styles/globals.css';
import Navbar from '@/components/Navbar';
import { Toaster } from 'react-hot-toast';

export const metadata: Metadata = {
  title: 'OneFL Studio - AI Video Translation & Subtitle Burner (10h+)',
  description: 'Automated video translation & subtitle burner system with Gemini 2.5 Flash, GPT-4o fallback, Speaker Profiling & 4-Tier Guardrails.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="min-h-screen bg-[#f8fafc] text-slate-900 antialiased selection:bg-indigo-500 selection:text-white relative">
        {/* Soft Ambient Background Elements */}
        <div className="fixed top-0 left-1/4 -translate-x-1/2 w-[600px] h-[350px] bg-indigo-200/40 rounded-full blur-[140px] pointer-events-none -z-10" />
        <div className="fixed top-0 right-1/4 translate-x-1/2 w-[600px] h-[350px] bg-cyan-200/40 rounded-full blur-[140px] pointer-events-none -z-10" />

        <Navbar />
        <main className="max-w-7xl mx-auto px-6 py-8">
          {children}
        </main>
        
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
