import { useEffect, useRef } from 'react';

interface SSEMessage {
  event: string;
  data: unknown;
}

export function useSSE(onEvent?: (msg: SSEMessage) => void) {
  const cbRef = useRef(onEvent);
  // eslint-disable-next-line react-hooks/refs -- intentional: keep latest callback in ref for event handlers
  cbRef.current = onEvent;

  useEffect(() => {
    const source = new EventSource('/events');

    source.onmessage = (e) => {
      try { cbRef.current?.({ event: 'message', data: JSON.parse(e.data) }); }
      catch { /* ignore */ }
    };

    const listeners: [string, (e: MessageEvent) => void][] = [];

    const add = (event: string) => {
      const handler = (e: MessageEvent) => {
        try { cbRef.current?.({ event, data: JSON.parse(e.data) }); }
        catch { /* ignore */ }
      };
      source.addEventListener(event, handler);
      listeners.push([event, handler]);
    };

    add('daemon_status');
    add('audit_progress');
    add('audit_complete');
    add('feedback_received');

    source.onerror = () => {
      console.warn('SSE reconnecting...');
    };

    return () => {
      listeners.forEach(([ev, h]) => source.removeEventListener(ev, h));
      source.close();
    };
  }, []);

  return {};
}
