/**
 * Session state shape & reducer for the OpenHarness Application UI.
 *
 * This is a straight port of the reference project reducer. It is already
 * agnostic of whether events arrive from a real WebSocket or a mock dispatcher,
 * which makes the mock useWebSocket drop-in.
 */

import type {
  ArtifactRef,
  AppStateSnapshot,
  BackendEvent,
  BridgeSessionSnapshot,
  McpServerSnapshot,
  SelectOptionPayload,
  SessionSummaryPayload,
  TaskSnapshot,
  TranscriptItem,
  ToolStatus,
} from "../types/protocol";
import { BackendEventType } from "../types/protocol";

// ---------------------------------------------------------------------------
// Artifact tracking
// ---------------------------------------------------------------------------

export interface ArtifactEntry {
  id: string;
  transcriptIndex: number;
  filePath: string;
  content: string;
  contentUrl?: string;
  mimeType?: string;
  /** When set with contentUrl, skip inline fetch above this size (bytes). */
  sizeBytes?: number;
  /** Shown in artifact tabs / header when present. */
  versionLabel?: string;
  status: "writing" | "complete" | "error";
  toolName: string;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

export interface SelectRequest {
  title: string;
  submitPrefix: string;
  options: SelectOptionPayload[];
  sessionId: string | null;
}

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

interface SessionView {
  transcript: TranscriptItem[];
  artifactIdsByIndex: Record<number, string[]>;
  pendingAssistantArtifactIds: string[];
  assistantBuffer: string;
  streamStartedAt: number | null;
  busy: boolean;
  stopping: boolean;
  artifacts: ArtifactEntry[];
  activeArtifactId: string | null;
  artifactPanelOpen: boolean;
  error: string | null;
}

export interface SessionState {
  connectionStatus: ConnectionStatus;
  reconnectAttempt: number;
  currentSessionId: string | null;
  sessions: SessionSummaryPayload[];
  sessionViews: Record<string, SessionView>;
  transcript: TranscriptItem[];
  artifactIdsByIndex: Record<number, string[]>;
  pendingAssistantArtifactIds: string[];
  assistantBuffer: string;
  /**
   * Unix millis captured when the user submits a line. Used to timestamp the
   * ephemeral streaming / "thinking…" bubbles and the final assistant
   * message so it lines up with when the user actually asked. Cleared when
   * the turn ends.
   */
  streamStartedAt: number | null;
  appState: AppStateSnapshot | null;
  tasks: TaskSnapshot[];
  commands: string[];
  mcpServers: McpServerSnapshot[];
  bridgeSessions: BridgeSessionSnapshot[];
  modal: Record<string, unknown> | null;
  selectRequest: SelectRequest | null;
  busy: boolean;
  stopping: boolean;
  error: string | null;
  artifacts: ArtifactEntry[];
  activeArtifactId: string | null;
  artifactPanelOpen: boolean;
}

export const initialSessionState: SessionState = {
  connectionStatus: "connecting",
  reconnectAttempt: 0,
  currentSessionId: null,
  sessions: [],
  sessionViews: {},
  transcript: [],
  artifactIdsByIndex: {},
  pendingAssistantArtifactIds: [],
  assistantBuffer: "",
  streamStartedAt: null,
  appState: null,
  tasks: [],
  commands: [],
  mcpServers: [],
  bridgeSessions: [],
  modal: null,
  selectRequest: null,
  busy: false,
  stopping: false,
  error: null,
  artifacts: [],
  activeArtifactId: null,
  artifactPanelOpen: false,
};

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export type SessionAction =
  | { type: "ws_connected" }
  | { type: "ws_disconnected" }
  | { type: "ws_reconnecting"; attempt: number }
  | { type: "ws_reconnect_failed" }
  | { type: "reset_session" }
  | { type: "backend_event"; event: BackendEvent }
  | { type: "submit_line"; line?: string }
  | { type: "session_stopping" }
  | { type: "dismiss_modal" }
  | { type: "dismiss_select" }
  | { type: "open_artifact"; id: string }
  | { type: "close_artifact_panel" }
  | { type: "session_output_artifacts_loaded"; sessionId: string; files: ArtifactRef[] }
  | { type: "artifact_exported"; artifact: ArtifactRef };

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

export function sessionReducer(
  state: SessionState,
  action: SessionAction,
): SessionState {
  switch (action.type) {
    case "ws_connected":
      return { ...state, connectionStatus: "connected", reconnectAttempt: 0 };

    case "ws_disconnected":
      return { ...state, connectionStatus: "disconnected", busy: false, stopping: false };

    case "ws_reconnecting":
      return { ...state, connectionStatus: "reconnecting", reconnectAttempt: action.attempt };

    case "ws_reconnect_failed":
      return { ...state, connectionStatus: "disconnected", busy: false, stopping: false };

    case "reset_session":
      return { ...initialSessionState };

    case "submit_line":
      return cacheCurrentView(addOptimisticSession({
        ...state,
        busy: true,
        stopping: false,
        pendingAssistantArtifactIds: [],
        streamStartedAt: Date.now(),
      }, action.line));

    case "session_stopping":
      return cacheCurrentView({
        ...state,
        stopping: true,
      });

    case "dismiss_modal":
      return { ...state, modal: null };

    case "dismiss_select":
      return { ...state, selectRequest: null };

    case "open_artifact":
      return { ...state, activeArtifactId: action.id, artifactPanelOpen: true };

    case "close_artifact_panel":
      return { ...state, artifactPanelOpen: false };

    case "session_output_artifacts_loaded":
      if (state.currentSessionId && action.sessionId !== state.currentSessionId) return state;
      return cacheCurrentView(mergeSessionOutputArtifacts(state, action.files));

    case "artifact_exported":
      return cacheCurrentView(openExportedArtifact(state, action.artifact));

    case "backend_event":
      return applyBackendEvent(state, action.event);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Make sure an incoming transcript item has a `timestamp`. Backends that
 * populate it (unix millis) keep their value; anything missing gets stamped
 * with Date.now() so the UI can always render a time.
 */
function stampItem(item: TranscriptItem): TranscriptItem {
  if (typeof item.timestamp === "number") return item;
  return { ...item, timestamp: Date.now() };
}

// ---------------------------------------------------------------------------
// Merge tool_completed into the running row (single card)
// ---------------------------------------------------------------------------

function mergeToolCompletion(
  transcript: TranscriptItem[],
  completed: TranscriptItem,
): { transcript: TranscriptItem[]; index: number; mergedItem: TranscriptItem } {
  const id = completed.tool_use_id;
  if (id) {
    for (let i = transcript.length - 1; i >= 0; i--) {
      const row = transcript[i]!;
      if (
        row.role === "tool" &&
        row.tool_use_id === id &&
        isActiveToolStatus(row.tool_status)
      ) {
        const mergedItem: TranscriptItem = {
          ...row,
          text: completed.text ?? "",
          is_error: completed.is_error,
          metadata:
            completed.metadata !== undefined ? completed.metadata : row.metadata,
          tool_status:
            completed.tool_status ??
            (completed.is_error ? "error" : "success"),
          tool_name: completed.tool_name ?? row.tool_name,
        };
        const next = [...transcript];
        next[i] = mergedItem;
        return { transcript: next, index: i, mergedItem };
      }
    }
  }
  const legacy: TranscriptItem = {
    ...completed,
    role: "tool_result",
    tool_status: completed.tool_status ?? (completed.is_error ? "error" : "success"),
    timestamp: completed.timestamp ?? Date.now(),
  };
  const next = [...transcript, legacy];
  return {
    transcript: next,
    index: next.length - 1,
    mergedItem: legacy,
  };
}

function mergeToolHeartbeat(
  transcript: TranscriptItem[],
  heartbeat: TranscriptItem,
): TranscriptItem[] {
  const id = heartbeat.tool_use_id;
  if (!id) return transcript;
  for (let i = transcript.length - 1; i >= 0; i--) {
    const row = transcript[i]!;
    if (row.role !== "tool" || row.tool_use_id !== id || !isActiveToolStatus(row.tool_status)) {
      continue;
    }
    const next = [...transcript];
    next[i] = {
      ...row,
      tool_status: heartbeat.tool_status ?? row.tool_status,
      metadata: {
        ...(row.metadata ?? {}),
        ...(heartbeat.metadata ?? {}),
      },
      text: heartbeat.text || row.text,
    };
    return next;
  }
  return transcript;
}

function isActiveToolStatus(status: ToolStatus | undefined): boolean {
  return (
    status === "running" ||
    status === "waiting_permission" ||
    status === "waiting_output" ||
    status === "stalled"
  );
}

// ---------------------------------------------------------------------------
// Event → State mapping
// ---------------------------------------------------------------------------

function applyBackendEvent(
  state: SessionState,
  event: BackendEvent,
): SessionState {
  if (isViewScopedEvent(event) && !isCurrentSessionEvent(state, event) && event.session_id) {
    return applyBackgroundSessionEvent(state, event.session_id, event);
  }

  switch (event.type) {
    case BackendEventType.Ready:
      if (event.session_id && state.currentSessionId && event.session_id !== state.currentSessionId) {
        return state;
      }
      return {
        ...state,
        appState: (event.state as AppStateSnapshot) ?? state.appState,
        tasks: event.tasks ?? state.tasks,
        commands: event.commands ?? state.commands,
        mcpServers: event.mcp_servers ?? state.mcpServers,
        bridgeSessions: event.bridge_sessions ?? state.bridgeSessions,
        currentSessionId: event.session_id ?? state.currentSessionId,
      };

    case BackendEventType.StateSnapshot:
      if (event.session_id && state.currentSessionId && event.session_id !== state.currentSessionId) {
        return state;
      }
      return {
        ...state,
        appState: (event.state as AppStateSnapshot) ?? state.appState,
        mcpServers: event.mcp_servers ?? state.mcpServers,
        bridgeSessions: event.bridge_sessions ?? state.bridgeSessions,
      };

    case BackendEventType.TasksSnapshot:
      if (event.session_id && state.currentSessionId && event.session_id !== state.currentSessionId) {
        return state;
      }
      return {
        ...state,
        tasks: event.tasks ?? state.tasks,
      };

    case BackendEventType.TranscriptItem: {
      if (!isCurrentSessionEvent(state, event)) return state;
      if (!event.item) return state;
      const stamped = stampItem(event.item);
      const nextTranscript = [...state.transcript, stamped];
      const newIndex = nextTranscript.length - 1;
      let nextArtifacts = state.artifacts;
      let nextArtifactIdsByIndex = state.artifactIdsByIndex;
      if (
        stamped.role === "user" &&
        Array.isArray(stamped.artifacts) &&
        stamped.artifacts.length > 0
      ) {
        const refs = dedupeArtifactRefs(stamped.artifacts.filter(isArtifactRef));
        if (refs.length > 0) {
          const appended = appendArtifactsForTranscript(
            state.artifacts,
            refs,
            newIndex,
            "upload",
            "complete",
          );
          nextArtifacts = appended.artifacts;
          nextArtifactIdsByIndex = {
            ...state.artifactIdsByIndex,
            [newIndex]: appended.artifactIds,
          };
        }
      }
      return {
        ...state,
        transcript: nextTranscript,
        artifacts: nextArtifacts,
        artifactIdsByIndex: nextArtifactIdsByIndex,
      };
    }

    case BackendEventType.AssistantDelta:
      if (!isCurrentSessionEvent(state, event)) return state;
      return {
        ...state,
        assistantBuffer: state.assistantBuffer + (event.message ?? ""),
      };

    case BackendEventType.AssistantComplete: {
      if (!isCurrentSessionEvent(state, event)) {
        return { ...state };
      }
      const text = event.message || state.assistantBuffer;
      const assistantIndex = state.transcript.length;
      const assistantTextRefs = extractArtifactRefsFromText(text);
      const appended = appendArtifactsForTranscript(
        state.artifacts,
        assistantTextRefs,
        assistantIndex,
        "assistant",
      );
      const nextArtifactIdsByIndex = { ...state.artifactIdsByIndex };
      const assistantArtifactIds = mergeArtifactIdLists(
        state.pendingAssistantArtifactIds,
        appended.artifactIds,
      );
      if (assistantArtifactIds.length > 0) {
        nextArtifactIdsByIndex[assistantIndex] = assistantArtifactIds;
      }
      return {
        ...state,
        transcript: [
          ...state.transcript,
          {
            role: "assistant",
            text,
            timestamp: state.streamStartedAt ?? Date.now(),
          } as TranscriptItem,
        ],
        artifacts: appended.artifacts,
        artifactIdsByIndex: nextArtifactIdsByIndex,
        pendingAssistantArtifactIds: [],
        assistantBuffer: "",
        busy: true,
      };
    }

    case BackendEventType.LineComplete:
      return {
        ...state,
        assistantBuffer: "",
        busy: false,
        stopping: false,
        streamStartedAt: null,
      };

    case BackendEventType.ToolStarted: {
      if (!isCurrentSessionEvent(state, event)) return state;
      if (!event.item) return state;
      const toolItem: TranscriptItem = {
        ...event.item,
        tool_name: event.item.tool_name ?? event.tool_name ?? undefined,
        tool_input: event.item.tool_input ?? undefined,
        is_error: event.item.is_error ?? event.is_error ?? undefined,
        tool_status: (event.item.tool_status ?? "running") as ToolStatus,
        timestamp: event.item.timestamp ?? Date.now(),
      };
      const nextTranscript = [...state.transcript, toolItem];
      const nextArtifacts = extractArtifact(
        state.artifacts,
        toolItem,
        nextTranscript.length - 1,
        event.type,
      );
      return {
        ...state,
        transcript: nextTranscript,
        artifacts: nextArtifacts,
        artifactIdsByIndex: {
          ...state.artifactIdsByIndex,
          [nextTranscript.length - 1]: [],
        },
      };
    }

    case BackendEventType.ToolHeartbeat: {
      if (!isCurrentSessionEvent(state, event)) return state;
      if (!event.item) return state;
      return {
        ...state,
        transcript: mergeToolHeartbeat(
          state.transcript,
          stampItem({
            ...event.item,
            tool_status: (event.item.tool_status ?? "running") as ToolStatus,
          }),
        ),
      };
    }

    case BackendEventType.ToolCompleted: {
      if (!isCurrentSessionEvent(state, event)) return state;
      if (!event.item) return state;
      const completed: TranscriptItem = {
        ...event.item,
        tool_name: event.item.tool_name ?? event.tool_name ?? undefined,
        tool_input: event.item.tool_input ?? undefined,
        is_error: event.item.is_error ?? event.is_error ?? undefined,
        tool_status: (event.item.tool_status ??
          (event.item.is_error ? "error" : "success")) as ToolStatus,
      };
      const merged = mergeToolCompletion(state.transcript, completed);
      const nextArtifacts = extractArtifact(
        state.artifacts,
        merged.mergedItem,
        merged.index,
        event.type,
      );
      const artifactIds = getArtifactIdsForTranscript(nextArtifacts, merged.index);
      const nextArtifactIdsByIndex = {
        ...state.artifactIdsByIndex,
        [merged.index]: artifactIds,
      };
      return {
        ...state,
        transcript: merged.transcript,
        artifacts: nextArtifacts,
        artifactIdsByIndex: nextArtifactIdsByIndex,
        pendingAssistantArtifactIds: mergeArtifactIdLists(
          state.pendingAssistantArtifactIds,
          artifactIds,
        ),
      };
    }

    case BackendEventType.ClearTranscript:
      if (!isCurrentSessionEvent(state, event)) return state;
      return {
        ...state,
        transcript: [],
        artifactIdsByIndex: {},
        pendingAssistantArtifactIds: [],
        assistantBuffer: "",
        streamStartedAt: null,
      };

    case BackendEventType.SelectRequest: {
      const m = event.modal ?? {};
      return {
        ...state,
        selectRequest: {
          title: String(m.title ?? "Select"),
          submitPrefix: String(m.submit_prefix ?? ""),
          options: event.select_options ?? [],
          sessionId: event.session_id ?? state.currentSessionId,
        },
      };
    }

    case BackendEventType.ModalRequest:
      return {
        ...state,
        modal: event.modal
          ? { ...event.modal, _session_id: event.session_id ?? state.currentSessionId }
          : null,
      };

    case BackendEventType.SessionCreated:
      return {
        ...state,
        sessionViews: state.currentSessionId
          ? {
              ...state.sessionViews,
              [state.currentSessionId]: viewFromState(state),
            }
          : state.sessionViews,
        currentSessionId: event.session_id ?? null,
        transcript: [],
        artifactIdsByIndex: {},
        pendingAssistantArtifactIds: [],
        assistantBuffer: "",
        streamStartedAt: null,
        artifacts: [],
        activeArtifactId: null,
        artifactPanelOpen: false,
        busy: false,
        stopping: false,
        error: null,
      };

    case BackendEventType.SessionLoaded:
      return switchToSession(state, event.session_id ?? null, event.transcript ?? []);

    case BackendEventType.SessionList:
      return {
        ...state,
        sessions: mergeSessionList(state, event.sessions ?? []),
      };

    case BackendEventType.SessionDeleted:
      return {
        ...state,
        sessions: state.sessions.filter((s) => s.session_id !== event.session_id),
      };

    case BackendEventType.Error:
      return {
        ...state,
        transcript: [
          ...state.transcript,
          {
            role: "system",
            text: `error: ${event.message ?? "unknown error"}`,
            timestamp: Date.now(),
          } as TranscriptItem,
        ],
        pendingAssistantArtifactIds: [],
        streamStartedAt: null,
        busy: false,
        stopping: false,
        error: event.message ?? "unknown error",
      };

    case BackendEventType.Shutdown:
      return { ...state, connectionStatus: "disconnected", busy: false, stopping: false };

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Artifact extraction from tool events
// ---------------------------------------------------------------------------

function isCurrentSessionEvent(state: SessionState, event: BackendEvent): boolean {
  if (!event.session_id || !state.currentSessionId) return true;
  return event.session_id === state.currentSessionId;
}

function isViewScopedEvent(event: BackendEvent): boolean {
  return (
    event.type === BackendEventType.TranscriptItem ||
    event.type === BackendEventType.AssistantDelta ||
    event.type === BackendEventType.AssistantComplete ||
    event.type === BackendEventType.LineComplete ||
    event.type === BackendEventType.ToolStarted ||
    event.type === BackendEventType.ToolHeartbeat ||
    event.type === BackendEventType.ToolCompleted ||
    event.type === BackendEventType.ClearTranscript ||
    event.type === BackendEventType.Error
  );
}

function viewFromState(state: SessionState): SessionView {
  return {
    transcript: state.transcript,
    artifactIdsByIndex: state.artifactIdsByIndex,
    pendingAssistantArtifactIds: state.pendingAssistantArtifactIds,
    assistantBuffer: state.assistantBuffer,
    streamStartedAt: state.streamStartedAt,
    busy: state.busy,
    stopping: state.stopping,
    artifacts: state.artifacts,
    activeArtifactId: state.activeArtifactId,
    artifactPanelOpen: state.artifactPanelOpen,
    error: state.error,
  };
}

function stateWithView(state: SessionState, view: SessionView): SessionState {
  return {
    ...state,
    transcript: view.transcript,
    artifactIdsByIndex: view.artifactIdsByIndex,
    pendingAssistantArtifactIds: view.pendingAssistantArtifactIds,
    assistantBuffer: view.assistantBuffer,
    streamStartedAt: view.streamStartedAt,
    busy: view.busy,
    stopping: view.stopping,
    artifacts: view.artifacts,
    activeArtifactId: view.activeArtifactId,
    artifactPanelOpen: view.artifactPanelOpen,
    error: view.error,
  };
}

function cacheCurrentView(state: SessionState): SessionState {
  if (!state.currentSessionId) return state;
  return {
    ...state,
    sessionViews: {
      ...state.sessionViews,
      [state.currentSessionId]: viewFromState(state),
    },
  };
}

function viewFromTranscript(transcript: TranscriptItem[]): SessionView {
  return {
    transcript: transcript.map(stampItem),
    artifactIdsByIndex: {},
    pendingAssistantArtifactIds: [],
    assistantBuffer: "",
    streamStartedAt: null,
    busy: false,
    stopping: false,
    artifacts: [],
    activeArtifactId: null,
    artifactPanelOpen: false,
    error: null,
  };
}

function switchToSession(
  state: SessionState,
  sessionId: string | null,
  transcript: TranscriptItem[],
): SessionState {
  const cachedState = cacheCurrentView(state);
  if (!sessionId) {
    return stateWithView(cachedState, viewFromTranscript(transcript));
  }
  const hasTranscript = transcript.length > 0;
  const nextView = hasTranscript
    ? viewFromTranscript(transcript)
    : cachedState.sessionViews[sessionId] ?? viewFromTranscript([]);
  return {
    ...stateWithView(cachedState, nextView),
    currentSessionId: sessionId,
  };
}

function applyBackgroundSessionEvent(
  state: SessionState,
  sessionId: string,
  event: BackendEvent,
): SessionState {
  const view = state.sessionViews[sessionId] ?? viewFromTranscript([]);
  const temp = stateWithView(
    {
      ...state,
      currentSessionId: sessionId,
      sessionViews: {},
    },
    view,
  );
  const next = applyBackendEvent(temp, event);
  return {
    ...state,
    sessionViews: {
      ...state.sessionViews,
      [sessionId]: viewFromState(next),
    },
    busy: state.busy,
  };
}

function addOptimisticSession(state: SessionState, line?: string): SessionState {
  if (!state.currentSessionId) return state;
  const existing = state.sessions.some((s) => s.session_id === state.currentSessionId);
  if (existing) return state;
  const summary = line?.trim() || "Running session";
  return {
    ...state,
    sessions: [
      {
        session_id: state.currentSessionId,
        summary: summary.slice(0, 80),
        message_count: Math.max(1, state.transcript.length + 1),
        model: state.appState?.model ?? "",
        created_at: Math.floor(Date.now() / 1000),
      },
      ...state.sessions,
    ],
  };
}

function mergeSessionList(
  state: SessionState,
  persistedSessions: SessionSummaryPayload[],
): SessionSummaryPayload[] {
  const byId = new Map<string, SessionSummaryPayload>();
  for (const session of persistedSessions) {
    byId.set(session.session_id, session);
  }

  for (const session of state.sessions) {
    if (!byId.has(session.session_id) && shouldKeepLocalSession(state, session.session_id)) {
      byId.set(session.session_id, session);
    }
  }

  return Array.from(byId.values()).sort((a, b) => b.created_at - a.created_at);
}

function shouldKeepLocalSession(state: SessionState, sessionId: string): boolean {
  const view =
    sessionId === state.currentSessionId
      ? viewFromState(state)
      : state.sessionViews[sessionId];

  if (!view) return false;
  return (
    view.busy ||
    view.transcript.length > 0 ||
    view.assistantBuffer.length > 0 ||
    view.pendingAssistantArtifactIds.length > 0
  );
}

const LEGACY_FILE_TOOLS = new Set([
  "file_write", "write_file", "file_edit", "str_replace",
  "file_read", "read_file", "create_file",
]);

interface SandboxOutputFile {
  name: string;
  path: string;
  size: number;
  mime_type: string;
  url: string;
  version_label?: string;
}

function extractArtifact(
  existing: ArtifactEntry[],
  item: TranscriptItem,
  transcriptIndex: number,
  eventType: string,
): ArtifactEntry[] {
  if (eventType !== BackendEventType.ToolCompleted) return existing;

  const refs = extractArtifactRefs(item);
  if (refs.length === 0) return existing;
  return appendArtifactsForTranscript(
    existing,
    refs,
    transcriptIndex,
    item.tool_name ?? "",
    item.is_error ? "error" : "complete",
  ).artifacts;
}

function extractArtifactRefs(item: TranscriptItem): ArtifactRef[] {
  if (Array.isArray(item.artifacts) && item.artifacts.length > 0) {
    return dedupeArtifactRefs(item.artifacts.filter(isArtifactRef));
  }

  const refs: ArtifactRef[] = [];
  const meta = item.metadata as Record<string, unknown> | undefined;
  const outputFiles = (meta?.output_files ?? []) as SandboxOutputFile[];
  for (const file of outputFiles) {
    if (!file || typeof file.name !== "string" || typeof file.url !== "string") continue;
    const sz = typeof file.size === "number" ? file.size : undefined;
    refs.push({
      path: file.name,
      label: file.name,
      mime_type: typeof file.mime_type === "string" ? file.mime_type : undefined,
      url: file.url,
      size_bytes: sz,
      version_label: typeof file.version_label === "string" ? file.version_label : undefined,
    });
  }

  const outputPath = meta?.output_path;
  if (typeof outputPath === "string") {
    refs.push(buildLocalArtifactRef(outputPath));
  }

  const toolInput = item.tool_input;
  if (toolInput) {
    const explicitOutputPath = toolInput.output_path;
    if (typeof explicitOutputPath === "string") {
      refs.push(buildLocalArtifactRef(explicitOutputPath));
    }

    if (LEGACY_FILE_TOOLS.has(item.tool_name ?? "")) {
      const legacyPath = toolInput.file_path ?? toolInput.path ?? toolInput.filename;
      if (typeof legacyPath === "string") {
        refs.push(buildLocalArtifactRef(legacyPath));
      }
    }
  }

  return dedupeArtifactRefs(refs);
}

function isArtifactRef(value: unknown): value is ArtifactRef {
  if (!value || typeof value !== "object") return false;
  const candidate = value as ArtifactRef;
  return typeof candidate.path === "string";
}

function buildLocalArtifactRef(rawPath: string): ArtifactRef {
  const displayPath = rawPath.split(/[\\/]/).pop() || rawPath;
  return {
    path: rawPath,
    label: displayPath,
    url: `/api/artifacts/file?path=${encodeURIComponent(rawPath)}`,
  };
}

function dedupeArtifactRefs(refs: ArtifactRef[]): ArtifactRef[] {
  const seen = new Set<string>();
  const deduped: ArtifactRef[] = [];
  for (const ref of refs) {
    const key = `${ref.path}::${ref.url ?? ""}::${artifactRefSizeBytes(ref) ?? ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(ref);
  }
  return deduped;
}

function getArtifactIdsForTranscript(
  artifacts: ArtifactEntry[],
  transcriptIndex: number,
): string[] {
  return artifacts
    .filter((artifact) => artifact.transcriptIndex === transcriptIndex)
    .map((artifact) => artifact.id);
}

function mergeArtifactIdLists(existing: string[], incoming: string[]): string[] {
  if (incoming.length === 0) return existing;
  return Array.from(new Set([...existing, ...incoming]));
}

function appendArtifactsForTranscript(
  existing: ArtifactEntry[],
  refs: ArtifactRef[],
  transcriptIndex: number,
  toolName: string,
  status: ArtifactEntry["status"] = "complete",
): { artifacts: ArtifactEntry[]; artifactIds: string[] } {
  const nextArtifacts = existing.filter((artifact) => artifact.transcriptIndex !== transcriptIndex);
  const artifactIds: string[] = [];

  for (const ref of refs) {
    const reused = nextArtifacts.find((artifact) =>
      artifact.filePath === ref.path && artifact.contentUrl === ref.url,
    );
    if (reused) {
      artifactIds.push(reused.id);
      continue;
    }

    const artifactIndex = nextArtifacts.filter((artifact) => artifact.id.startsWith(`artifact-${transcriptIndex}-`)).length;
    const entry: ArtifactEntry = {
      id: `artifact-${transcriptIndex}-${artifactIndex}`,
      transcriptIndex,
      filePath: ref.path,
      content: "",
      contentUrl: ref.url,
      mimeType: ref.mime_type,
      sizeBytes: artifactRefSizeBytes(ref),
      versionLabel: ref.version_label,
      status,
      toolName,
    };
    nextArtifacts.push(entry);
    artifactIds.push(entry.id);
  }

  return { artifacts: nextArtifacts, artifactIds };
}

function mergeSessionOutputArtifacts(state: SessionState, refs: ArtifactRef[]): SessionState {
  const validRefs = dedupeArtifactRefs(refs.filter(isArtifactRef));
  if (validRefs.length === 0) return state;

  const anchorIndex = latestArtifactAnchorIndex(state.transcript);
  const nextArtifacts = [...state.artifacts];
  const artifactIds: string[] = [];
  const existingByKey = new Map<string, ArtifactEntry>();
  for (const artifact of nextArtifacts) {
    existingByKey.set(artifactKey(artifact.filePath, artifact.contentUrl), artifact);
  }

  for (const ref of validRefs) {
    const key = artifactKey(ref.path, ref.url);
    const existing = existingByKey.get(key);
    if (existing) {
      artifactIds.push(existing.id);
      continue;
    }

    const entry: ArtifactEntry = {
      id: `session-output-${hashArtifactKey(key)}`,
      transcriptIndex: anchorIndex,
      filePath: ref.path,
      content: "",
      contentUrl: ref.url,
      mimeType: ref.mime_type,
      sizeBytes: artifactRefSizeBytes(ref),
      versionLabel: ref.version_label,
      status: "complete",
      toolName: "session-output",
    };
    nextArtifacts.push(entry);
    existingByKey.set(key, entry);
    artifactIds.push(entry.id);
  }

  const nextArtifactIdsByIndex = { ...state.artifactIdsByIndex };
  if (anchorIndex >= 0 && artifactIds.length > 0) {
    nextArtifactIdsByIndex[anchorIndex] = mergeArtifactIdLists(
      nextArtifactIdsByIndex[anchorIndex] ?? [],
      artifactIds,
    );
  }

  return {
    ...state,
    artifacts: nextArtifacts,
    artifactIdsByIndex: nextArtifactIdsByIndex,
  };
}

function openExportedArtifact(state: SessionState, ref: ArtifactRef): SessionState {
  const merged = mergeSessionOutputArtifacts(state, [ref]);
  const key = artifactKey(ref.path, ref.url);
  const exported = merged.artifacts.find((artifact) =>
    artifactKey(artifact.filePath, artifact.contentUrl) === key,
  );
  return {
    ...merged,
    activeArtifactId: exported?.id ?? merged.activeArtifactId,
    artifactPanelOpen: true,
  };
}

function latestArtifactAnchorIndex(transcript: TranscriptItem[]): number {
  for (let i = transcript.length - 1; i >= 0; i -= 1) {
    const role = transcript[i]?.role;
    if (role === "assistant" || role === "tool" || role === "tool_result") return i;
  }
  return transcript.length - 1;
}

function artifactKey(path: string, url?: string): string {
  return `${path}::${url ?? ""}`;
}

function artifactRefSizeBytes(ref: ArtifactRef): number | undefined {
  if (typeof ref.size_bytes === "number") return ref.size_bytes;
  if (typeof ref.size === "number") return ref.size;
  return undefined;
}

function hashArtifactKey(value: string): string {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(36);
}

const ARTIFACT_PATH_EXTENSIONS = [
  "bmp",
  "c",
  "cfg",
  "conf",
  "cpp",
  "css",
  "csv",
  "doc",
  "docx",
  "env",
  "fa",
  "fasta",
  "fastq",
  "fq",
  "gif",
  "gff",
  "gff3",
  "gmt",
  "go",
  "gro",
  "gtf",
  "gz",
  "h",
  "h5",
  "h5ad",
  "hpp",
  "htm",
  "html",
  "ico",
  "ini",
  "java",
  "jpeg",
  "jpg",
  "js",
  "json",
  "jsx",
  "kt",
  "log",
  "lua",
  "m",
  "maf",
  "md",
  "mlx",
  "mol2",
  "mtx",
  "pdb",
  "pdf",
  "php",
  "pl",
  "png",
  "pptx",
  "py",
  "r",
  "rb",
  "rdata",
  "rds",
  "rs",
  "sam",
  "scala",
  "sh",
  "sql",
  "svg",
  "swift",
  "tab",
  "tar",
  "toml",
  "ts",
  "tsv",
  "tsx",
  "txt",
  "vcf",
  "webp",
  "xls",
  "xlsx",
  "xml",
  "xyz",
  "yaml",
  "yml",
  "zip",
] as const;

const ARTIFACT_PATH_EXTENSION_PATTERN = [...ARTIFACT_PATH_EXTENSIONS]
  .sort((a, b) => b.length - a.length)
  .join("|");

const ARTIFACT_PATH_PATTERN = new RegExp(
  `(?:/[^\\s"'\\\`<>]+?\\.(?:${ARTIFACT_PATH_EXTENSION_PATTERN})|(?:\\.\\.?/)?[A-Za-z0-9_./-]+?\\.(?:${ARTIFACT_PATH_EXTENSION_PATTERN}))`,
  "gi",
);

function extractArtifactRefsFromText(text: string): ArtifactRef[] {
  const refs: ArtifactRef[] = [];

  for (const match of text.matchAll(ARTIFACT_PATH_PATTERN)) {
    const raw = match[0]?.trim();
    if (!raw || /^https?:\/\//i.test(raw) || raw.startsWith("/api/")) continue;
    refs.push(buildLocalArtifactRef(raw.replace(/[),.;]+$/, "")));
  }

  return dedupeArtifactRefs(refs);
}
