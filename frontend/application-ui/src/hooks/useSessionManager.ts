/**
 * Session manager backed by the WebSocket server.
 *
 * Sends `new_session`, `list_sessions`, and `delete_session` messages over
 * the existing WS connection. The server persists sessions to disk and
 * replies with `session_created`, `session_list`, and `session_deleted`
 * events that the reducer handles automatically.
 */

import { useCallback, useEffect } from "react";
import type { FrontendRequest } from "../types/protocol";

interface UseSessionManagerOpts {
  sendRequest: (req: FrontendRequest) => void;
  connectionStatus: string;
}

export function useSessionManager({ sendRequest, connectionStatus }: UseSessionManagerOpts) {
  const fetchSessions = useCallback(() => {
    sendRequest({ type: "list_sessions" });
  }, [sendRequest]);

  useEffect(() => {
    if (connectionStatus === "connected") {
      const timer = setTimeout(fetchSessions, 200);
      return () => clearTimeout(timer);
    }
  }, [connectionStatus, fetchSessions]);

  const startNewSession = useCallback(() => {
    sendRequest({ type: "new_session" });
  }, [sendRequest]);

  const resumeSession = useCallback(
    (sessionId: string) => {
      sendRequest({ type: "load_session", session_id: sessionId });
    },
    [sendRequest],
  );

  const deleteSession = useCallback(
    (sessionId: string) => {
      sendRequest({ type: "delete_session", session_id: sessionId });
    },
    [sendRequest],
  );

  const renameSession = useCallback(
    (sessionId: string, summary: string) => {
      sendRequest({ type: "rename_session", session_id: sessionId, summary });
    },
    [sendRequest],
  );

  return {
    fetchSessions,
    startNewSession,
    resumeSession,
    deleteSession,
    renameSession,
  };
}
