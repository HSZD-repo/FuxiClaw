/**
 * Real WebSocket client for the Application UI.
 *
 * Speaks the tiny chat-only protocol implemented by
 * `src/openharness/web/server.py`. The resolved server URL comes from
 * `lib/settings.ts` (UI override → VITE_OH_WS_URL → /ws via Vite proxy).
 *
 * Session management (history, new session) is still handled by the mock
 * `useSessionManager`; those buttons won't do anything meaningful until the
 * backend grows real session persistence.
 */

import { useCallback, useEffect, useRef } from "react";
import type { BackendEvent, FrontendRequest } from "../types/protocol";
import type { SessionAction } from "../store/sessionReducer";
import { getEffectiveWsUrl } from "../lib/settings";

const MAX_RECONNECT_ATTEMPTS = 20;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

type SendFn = (req: FrontendRequest) => void;

export function useWebSocket(dispatch: React.Dispatch<SessionAction>) {
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Connection generation; incremented on teardown so event handlers attached
  // to a stale WS are ignored. Keeps React 18 Strict Mode double-mount and
  // manual reconnects from stepping on each other.
  const genRef = useRef(0);
  const onReadyRef = useRef<((send: SendFn) => void) | null>(null);

  const sendRequest = useCallback((req: FrontendRequest) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(req));
    } else {
      console.warn("[oh-app-ui] sendRequest dropped, socket not open:", req.type);
    }
  }, []);

  const scheduleReconnectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    const gen = genRef.current;
    const url = getEffectiveWsUrl();
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch (err) {
      console.error("[oh-app-ui] failed to construct WebSocket:", err);
      scheduleReconnectRef.current();
      return;
    }
    wsRef.current = ws;

    ws.addEventListener("open", () => {
      if (gen !== genRef.current) {
        ws.close();
        return;
      }
      console.log("[oh-app-ui] WebSocket connected:", url);
      attemptRef.current = 0;
      dispatch({ type: "ws_connected" });
    });

    ws.addEventListener("message", (msg) => {
      if (gen !== genRef.current) return;
      try {
        const event: BackendEvent = JSON.parse(msg.data as string);
        dispatch({ type: "backend_event", event });

        if (event.type === "ready" && onReadyRef.current) {
          const cb = onReadyRef.current;
          onReadyRef.current = null;
          cb(sendRequest);
        }
      } catch {
        console.warn("[oh-app-ui] non-JSON message:", msg.data);
      }
    });

    ws.addEventListener("close", () => {
      if (gen !== genRef.current) return;
      console.log("[oh-app-ui] WebSocket disconnected");
      scheduleReconnectRef.current();
    });

    ws.addEventListener("error", (err) => {
      if (gen !== genRef.current) return;
      console.error("[oh-app-ui] WebSocket error:", err);
    });
  }, [dispatch, sendRequest]);

  const scheduleReconnect = useCallback(() => {
    const attempt = attemptRef.current + 1;
    if (attempt > MAX_RECONNECT_ATTEMPTS) {
      dispatch({ type: "ws_reconnect_failed" });
      return;
    }
    attemptRef.current = attempt;
    const delay = Math.min(BASE_DELAY_MS * 2 ** (attempt - 1), MAX_DELAY_MS);
    dispatch({ type: "ws_reconnecting", attempt });
    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect, dispatch]);

  useEffect(() => {
    scheduleReconnectRef.current = scheduleReconnect;
  }, [scheduleReconnect]);

  const teardown = useCallback(() => {
    genRef.current += 1;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {
        /* noop */
      }
      wsRef.current = null;
    }
  }, []);

  const manualReconnect = useCallback(() => {
    teardown();
    attemptRef.current = 0;
    dispatch({ type: "ws_reconnecting", attempt: 1 });
    connect();
  }, [teardown, connect, dispatch]);

  const resetAndReconnect = useCallback(
    (afterReady?: (send: SendFn) => void) => {
      onReadyRef.current = afterReady ?? null;
      teardown();
      attemptRef.current = 0;
      dispatch({ type: "reset_session" });
      connect();
    },
    [teardown, connect, dispatch],
  );

  useEffect(() => {
    connect();
    return teardown;
  }, [connect, teardown]);

  return { sendRequest, manualReconnect, resetAndReconnect };
}
