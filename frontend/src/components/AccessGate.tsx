'use client';
import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

export default function AccessGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let disposed = false;
    if (pathname === '/login') { setReady(true); return; }
    setReady(false); setError('');
    fetch('/api/v1/auth/session', { credentials: 'same-origin', cache: 'no-store' })
      .then(async response => {
        if (!response.ok) throw new Error('Không kết nối được máy chủ');
        const session = await response.json();
        if (disposed) return;
        if (!session.authenticated) router.replace('/login');
        else setReady(true);
      }).catch(error => { if (!disposed) setError(error.message); });
    return () => { disposed = true; };
  }, [pathname, router]);
  if (!ready) return <p role="status" className="p-8 text-center">{error || 'Đang kiểm tra kết nối…'}</p>;
  return <>{children}</>;
}
