'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const router = useRouter();
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      if (!response.ok) { const body = await response.json(); throw new Error(body.detail || 'Đăng nhập thất bại'); }
      setToken(''); router.replace('/'); router.refresh();
    } catch (error) { setError(error instanceof Error ? error.message : 'Đăng nhập thất bại'); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="mx-auto max-w-md space-y-4 rounded-2xl border bg-white p-6">
    <h1 className="text-xl font-bold">Đăng nhập OneFL</h1>
    <label htmlFor="access-token" className="block">Mã truy cập do người quản trị cung cấp</label>
    <input id="access-token" type="password" autoComplete="current-password" required value={token} onChange={e => setToken(e.target.value)} className="w-full rounded-lg border p-3" />
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <button disabled={busy} className="rounded-lg bg-indigo-600 px-4 py-2 text-white">{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}</button>
  </form>;
}
