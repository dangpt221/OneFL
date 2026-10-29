"use client";
import { useEffect, useState } from 'react';
export interface WebSocketMessage { type: string; project_id: string; data: any; }
interface ProjectSocketState {
  projectId?: string;
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
}

export function useProjectWebSocket(projectId?: string) {
  const [state, setState] = useState<ProjectSocketState>({isConnected: false, lastMessage: null});
  useEffect(() => {
    setState({projectId, isConnected: false, lastMessage: null});
    if (!projectId) return;
    let disposed = false;
    let activeSocket: WebSocket | null = null;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;

    function connect() {
      if (disposed) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/${projectId}`);
      activeSocket = socket;
      socket.onopen = () => {
        if (disposed || activeSocket !== socket) return;
        attempt = 0;
        setState(previous => ({...previous, isConnected: true}));
      };
      socket.onmessage = event => {
        if (disposed || activeSocket !== socket || event.data === 'pong') return;
        try {
          const message: WebSocketMessage | null = JSON.parse(event.data);
          if (message && message.project_id === projectId && typeof message.type === 'string') {
            setState(previous => ({...previous, lastMessage: message}));
          }
        } catch (error) {
          console.error('Invalid live event', error);
        }
      };
      socket.onclose = event => {
        if (disposed || activeSocket !== socket) return;
        activeSocket = null;
        setState(previous => ({...previous, isConnected: false}));
        if (event.code === 4401) { window.location.assign('/login'); return; }
        if (event.code === 4404) { window.location.assign('/'); return; }
        if (event.code === 4403) return;
        reconnect = setTimeout(connect, Math.min(30000, 1000 * 2 ** attempt));
        attempt = Math.min(attempt + 1, 5);
      };
      // Native connection failures emit close after error; closing here aborts a pending handshake.
    }

    // React can discard an effect immediately during development or quick navigation.
    reconnect = setTimeout(connect, 0);
    const ping = setInterval(() => {
      if (activeSocket?.readyState === WebSocket.OPEN) activeSocket.send('ping');
    }, 15000);
    return () => {
      disposed = true;
      clearInterval(ping);
      clearTimeout(reconnect);
      const socket = activeSocket;
      activeSocket = null;
      if (!socket) return;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onopen = null;
      if (socket.readyState === WebSocket.CONNECTING) {
        // The browser API has no silent handshake cancellation. Retire it once open.
        socket.onopen = () => {
          socket.onopen = null;
          socket.close(1000);
        };
      } else if (socket.readyState === WebSocket.OPEN) {
        socket.close(1000);
      }
    };
  }, [projectId]);
  // Mask the previous project even in the render before the new effect runs.
  return state.projectId === projectId
    ? {isConnected: state.isConnected, lastMessage: state.lastMessage}
    : {isConnected: false, lastMessage: null};
}
