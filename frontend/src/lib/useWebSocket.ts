"use client";
import { useEffect, useRef, useState } from 'react';
export interface WebSocketMessage { type: string; project_id: string; data: any; }
export function useProjectWebSocket(projectId?: string) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    if (!projectId) return;
    let disposed = false;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    function connect() {
      if (disposed) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/${projectId}`);
      socketRef.current = socket;
      socket.onopen = () => { if (!disposed) { attempt = 0; setIsConnected(true); } };
      socket.onmessage = event => {
        if (disposed || event.data === 'pong') return;
        try { setLastMessage(JSON.parse(event.data)); } catch (error) { console.error('Invalid live event', error); }
      };
      socket.onclose = event => {
        if (disposed) return;
        setIsConnected(false);
        if (event.code === 4401) { window.location.assign('/login'); return; }
        if (event.code === 4404) { window.location.assign('/'); return; }
        if (event.code === 4403) return;
        reconnect = setTimeout(connect, Math.min(30000, 1000 * 2 ** attempt++));
      };
      socket.onerror = () => socket.close();
    }
    connect();
    const ping = setInterval(() => { if (socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send('ping'); }, 15000);
    return () => {
      disposed = true;
      clearInterval(ping);
      clearTimeout(reconnect);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [projectId]);
  return { isConnected, lastMessage };
}
