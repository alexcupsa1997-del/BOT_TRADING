import { useEffect, useRef, useCallback, useState } from 'react';

export function useWebSocket<T>(
  path: string,
  onMessage: (data: T) => void,
  enabled = true
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef(1000);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (!enabled) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}${path}`);

    ws.onopen = () => {
      setConnected(true);
      reconnectTimeout.current = 1000;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setTimeout(() => {
        reconnectTimeout.current = Math.min(reconnectTimeout.current * 2, 30000);
        connect();
      }, reconnectTimeout.current);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [path, onMessage, enabled]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
