import { useEffect } from "react";
import type { FrontendRequest } from "../types/protocol";
import type { SessionAction } from "../store/sessionReducer";

interface ShortcutDeps {
  dispatch: React.Dispatch<SessionAction>;
  sendRequest: (req: FrontendRequest) => void;
  sessionId: string | null;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  hasModal: boolean;
  hasSelect: boolean;
}

export function useKeyboardShortcuts({
  dispatch,
  sendRequest,
  sessionId,
  inputRef,
  hasModal,
  hasSelect,
}: ShortcutDeps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (hasModal) {
          dispatch({ type: "dismiss_modal" });
          e.preventDefault();
          return;
        }
        if (hasSelect) {
          dispatch({ type: "dismiss_select" });
          e.preventDefault();
          return;
        }
      }

      if (e.key === "l" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        sendRequest({ type: "submit_line", line: "/clear", session_id: sessionId ?? undefined });
        return;
      }

      if (e.key === "/" && !hasModal && !hasSelect) {
        const tag = (e.target as HTMLElement).tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA") {
          e.preventDefault();
          inputRef.current?.focus();
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [dispatch, sendRequest, sessionId, inputRef, hasModal, hasSelect]);
}
