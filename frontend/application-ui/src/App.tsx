import { useCallback, useEffect, useReducer, useRef, useState, lazy, Suspense } from "react";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { useWebSocket } from "./hooks/useWebSocket";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useSessionManager } from "./hooks/useSessionManager";
import { sessionReducer, initialSessionState } from "./store/sessionReducer";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Menu, RotateCw, Settings as SettingsIcon, SlidersHorizontal } from "lucide-react";
import MessageList from "./components/MessageList";
import ChatInput from "./components/ChatInput";
import PermissionModal from "./components/PermissionModal";
import QuestionModal from "./components/QuestionModal";
import SelectModal from "./components/SelectModal";
import WelcomeCard from "./components/WelcomeCard";
import Sidebar from "./components/Sidebar";
import ExportChatButtons from "./components/ExportChatButtons";
import SettingsDialog from "./components/SettingsDialog";
import { FrontendRequestType, type ArtifactRef, type TranscriptItem } from "./types/protocol";

const ArtifactPanel = lazy(() => import("./components/ArtifactPanel"));

interface SessionOutputResponse {
  output_files?: ArtifactRef[];
  error?: string;
}

interface ArtifactPdfExportResponse {
  artifact?: ArtifactRef;
  error?: string;
}

export default function App() {
  const [state, dispatch] = useReducer(sessionReducer, initialSessionState);
  const { sendRequest, manualReconnect } = useWebSocket(dispatch);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarToolsOpen, setSidebarToolsOpen] = useState(false);

  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try { return localStorage.getItem("oh-sidebar") !== "closed"; } catch { return true; }
  });
  const toggleSidebar = useCallback(() => {
    setSidebarOpen((o) => {
      try { localStorage.setItem("oh-sidebar", o ? "closed" : "open"); } catch { /* noop */ }
      return !o;
    });
  }, []);

  const {
    fetchSessions,
    startNewSession,
    resumeSession,
    deleteSession,
    renameSession,
  } = useSessionManager({
    sendRequest,
    connectionStatus: state.connectionStatus,
  });

  const hasModal = state.modal !== null;
  const hasSelect = state.selectRequest !== null;
  const modalSessionId =
    typeof state.modal?._session_id === "string"
      ? state.modal._session_id
      : state.currentSessionId ?? undefined;

  useKeyboardShortcuts({
    dispatch,
    sendRequest,
    sessionId: state.currentSessionId,
    inputRef,
    hasModal,
    hasSelect,
  });

  const connected = state.connectionStatus === "connected";
  const showWelcome =
    state.transcript.length === 0 &&
    state.assistantBuffer.length === 0 &&
    !state.busy;

  const handleSendPrompt = useCallback(
    (prompt: string) => {
      sendRequest({ type: "submit_line", line: prompt, session_id: state.currentSessionId ?? undefined });
      dispatch({ type: "submit_line", line: prompt });
    },
    [sendRequest, dispatch, state.currentSessionId],
  );

  const handleStopSessionRun = useCallback(() => {
    if (!state.currentSessionId || !state.busy || state.stopping) return;
    sendRequest({
      type: "session_control",
      action: "stop",
      session_id: state.currentSessionId,
    });
    dispatch({ type: "session_stopping" });
  }, [dispatch, sendRequest, state.busy, state.currentSessionId, state.stopping]);

  const loadSessionOutputArtifacts = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`/api/session-output/${encodeURIComponent(sessionId)}`);
      const payload = (await res.json().catch(() => ({}))) as SessionOutputResponse;
      if (!res.ok) return;
      dispatch({
        type: "session_output_artifacts_loaded",
        sessionId,
        files: Array.isArray(payload.output_files) ? payload.output_files : [],
      });
    } catch {
      // Artifact discovery is a convenience path; keep chat usable if it fails.
    }
  }, [dispatch]);

  const handleOpenArtifact = useCallback(
    (id: string) => {
      dispatch({ type: "open_artifact", id });
      if (state.currentSessionId) void loadSessionOutputArtifacts(state.currentSessionId);
    },
    [dispatch, loadSessionOutputArtifacts, state.currentSessionId],
  );

  const handleExportArtifactPdf = useCallback(
    async (artifact: { filePath: string; contentUrl?: string }) => {
      if (!state.currentSessionId) throw new Error("No active session.");
      const res = await fetch("/api/artifacts/export-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.currentSessionId,
          content_url: artifact.contentUrl ?? "",
          file_path: artifact.filePath,
        }),
      });
      const payload = (await res.json().catch(() => ({}))) as ArtifactPdfExportResponse;
      if (!res.ok || !payload.artifact) {
        throw new Error(payload.error || "Failed to export PDF.");
      }
      dispatch({ type: "artifact_exported", artifact: payload.artifact });
      await loadSessionOutputArtifacts(state.currentSessionId);
    },
    [dispatch, loadSessionOutputArtifacts, state.currentSessionId],
  );

  const handleStepControl = useCallback(
    (action: "stop" | "skip" | "wait", item: TranscriptItem) => {
      if (!state.currentSessionId || !item.tool_use_id) return;
      sendRequest({
        type: "step_control",
        action,
        tool_use_id: item.tool_use_id,
        session_id: state.currentSessionId,
      });
    },
    [sendRequest, state.currentSessionId],
  );

  const handleCloseArtifactPanel = useCallback(
    () => dispatch({ type: "close_artifact_panel" }),
    [dispatch],
  );

  const handleSettingsApply = useCallback(
    (options?: { reconnect?: boolean }) => {
      if (options?.reconnect) {
        manualReconnect();
        return;
      }
      sendRequest({
        type: FrontendRequestType.RefreshSettings,
        session_id: state.currentSessionId ?? undefined,
      });
    },
    [manualReconnect, sendRequest, state.currentSessionId],
  );

  const statusDotColor =
    state.connectionStatus === "connected"
      ? "bg-accent-green"
      : state.connectionStatus === "connecting" || state.connectionStatus === "reconnecting"
        ? "bg-accent-yellow"
        : "bg-accent-red";

  const hasArtifacts = state.artifacts.length > 0;
  const showArtifactPanel = state.artifactPanelOpen && hasArtifacts;

  useEffect(() => {
    if (!connected || !state.currentSessionId || state.busy) return;
    void loadSessionOutputArtifacts(state.currentSessionId);
  }, [connected, loadSessionOutputArtifacts, state.busy, state.currentSessionId, state.transcript.length]);

  useEffect(() => {
    if (!connected || !state.currentSessionId || !state.artifactPanelOpen) return;
    void loadSessionOutputArtifacts(state.currentSessionId);
  }, [connected, loadSessionOutputArtifacts, state.artifactPanelOpen, state.currentSessionId]);

  return (
    <div className="flex h-screen bg-bg-page text-text-primary font-sans">
      <Sidebar
        open={sidebarOpen}
        onToggle={toggleSidebar}
        sessions={state.sessions}
        currentSessionId={state.currentSessionId}
        onNewSession={startNewSession}
        onResumeSession={resumeSession}
        onDeleteSession={deleteSession}
        onRenameSession={renameSession}
        onRefresh={fetchSessions}
        footer={
          <div className="relative flex justify-start">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setSidebarToolsOpen((open) => !open)}
              title="Tools"
              aria-haspopup="menu"
              aria-expanded={sidebarToolsOpen}
              className="text-text-muted hover:bg-bg-tertiary hover:text-text-secondary"
            >
              <SettingsIcon className="size-4" />
            </Button>
            {sidebarToolsOpen && (
              <div
                className="absolute bottom-9 left-0 z-50 min-w-32 rounded-md border border-border-subtle bg-bg-elevated py-1 shadow-lg"
                role="menu"
              >
                <button
                  type="button"
                  className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-[12px] text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                  role="menuitem"
                  onClick={() => {
                    setSidebarToolsOpen(false);
                    setSettingsOpen(true);
                  }}
                >
                  <SlidersHorizontal className="size-3.5" />
                  Settings
                </button>
              </div>
            )}
          </div>
        }
      />

      <PanelGroup orientation="horizontal" className="flex-1 min-w-0">
        <Panel defaultSize={showArtifactPanel ? 55 : 100} minSize={35}>
          <div className="flex flex-col h-full">
            <header className="flex items-center justify-between shrink-0 px-5 py-3 border-b border-border-header">
              <div className="flex min-w-0 items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={toggleSidebar}
                  title="Toggle sidebar"
                  className={cn(sidebarOpen && "md:hidden")}
                >
                  <Menu className="size-4" />
                </Button>
                <span className={cn("size-2 rounded-full inline-block", statusDotColor)} />
              </div>
              <div className="flex items-center gap-3">
                <ExportChatButtons state={state} />
              </div>
            </header>

            {state.connectionStatus === "reconnecting" && (
              <div className="px-5 py-2 bg-bg-warning text-accent-yellow-light text-[13px] shrink-0">
                Reconnecting… (attempt {state.reconnectAttempt}/20)
              </div>
            )}

            {state.connectionStatus === "disconnected" && (
              <div className="flex items-center gap-3 px-5 py-2 bg-bg-error text-accent-red-light text-[13px] shrink-0">
                <span>Disconnected from server.</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={manualReconnect}
                  className="border-accent-red-light text-accent-red-light hover:bg-accent-red/20"
                >
                  <RotateCw className="size-3" />
                  Reconnect
                </Button>
              </div>
            )}

            {state.error && state.connectionStatus === "connected" && (
              <div className="px-5 py-2 bg-bg-warning text-accent-yellow-light text-[13px] shrink-0">
                {state.error}
              </div>
            )}

            {showWelcome ? (
              <WelcomeCard
                connectionStatus={state.connectionStatus}
                model={state.appState?.model ?? null}
                onSendPrompt={handleSendPrompt}
              />
            ) : (
              <MessageList
                transcript={state.transcript}
                streamingText={state.assistantBuffer}
                busy={state.busy}
                stopping={state.stopping}
                streamStartedAt={state.streamStartedAt}
                artifacts={state.artifacts}
                artifactIdsByIndex={state.artifactIdsByIndex}
                onOpenArtifact={handleOpenArtifact}
                onStepControl={handleStepControl}
                currentSessionId={state.currentSessionId}
                connected={connected}
              />
            )}

            <ChatInput
              disabled={!connected}
              busy={state.busy}
              stopping={state.stopping}
              sessionId={state.currentSessionId}
              onSend={sendRequest}
              onSubmitLine={(line) => dispatch({ type: "submit_line", line })}
              onStopSession={handleStopSessionRun}
              inputRef={inputRef}
            />
          </div>
        </Panel>

        {showArtifactPanel && (
          <>
            <PanelResizeHandle className="w-1 bg-border-subtle hover:bg-accent-blue/40 transition-colors cursor-col-resize" />
            <Panel defaultSize={45} minSize={25}>
              <Suspense fallback={
                <div className="flex items-center justify-center h-full bg-bg-secondary text-text-muted text-sm">
                  Loading…
                </div>
              }>
                <ArtifactPanel
                  artifacts={state.artifacts}
                  activeId={state.activeArtifactId}
                  onSelectArtifact={handleOpenArtifact}
                  onExportPdf={handleExportArtifactPdf}
                  onClose={handleCloseArtifactPanel}
                />
              </Suspense>
            </Panel>
          </>
        )}
      </PanelGroup>

      {state.modal && (state.modal as Record<string, unknown>).kind === "permission" && (
        <PermissionModal
          requestId={String((state.modal as Record<string, unknown>).request_id ?? "")}
          toolName={String((state.modal as Record<string, unknown>).tool_name ?? "unknown")}
          reason={String((state.modal as Record<string, unknown>).reason ?? "")}
          onSend={(req) =>
            sendRequest({
              ...req,
              session_id: modalSessionId,
            })
          }
          onDismiss={() => dispatch({ type: "dismiss_modal" })}
        />
      )}

      {state.modal && (state.modal as Record<string, unknown>).kind === "question" && (
        <QuestionModal
          requestId={String((state.modal as Record<string, unknown>).request_id ?? "")}
          question={String((state.modal as Record<string, unknown>).question ?? "")}
          onSend={(req) =>
            sendRequest({
              ...req,
              session_id: modalSessionId,
            })
          }
          onDismiss={() => dispatch({ type: "dismiss_modal" })}
        />
      )}

      {state.selectRequest && (
        <SelectModal
          title={state.selectRequest.title}
          submitPrefix={state.selectRequest.submitPrefix}
          options={state.selectRequest.options}
          sessionId={state.selectRequest.sessionId}
          onSend={sendRequest}
          onDismiss={() => dispatch({ type: "dismiss_select" })}
        />
      )}

      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        appState={state.appState}
        onApply={handleSettingsApply}
      />
    </div>
  );
}
