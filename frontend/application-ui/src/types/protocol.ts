/**
 * Protocol types for the OpenHarness web UI.
 *
 * Mirrors the reference project (frontend/web/src/types/protocol.ts) which in
 * turn mirrors the Python backend contract in src/openharness/ui/protocol.py.
 *
 * The real backend is NOT wired up in this project — see hooks/useWebSocket
 * and lib/mockData for the stubbed implementations.
 */

// ---------------------------------------------------------------------------
// Upstream → Frontend  (BackendEvent)
// ---------------------------------------------------------------------------

export const BackendEventType = {
  Ready: "ready",
  StateSnapshot: "state_snapshot",
  TasksSnapshot: "tasks_snapshot",
  TranscriptItem: "transcript_item",
  AssistantDelta: "assistant_delta",
  AssistantComplete: "assistant_complete",
  LineComplete: "line_complete",
  ToolStarted: "tool_started",
  ToolHeartbeat: "tool_heartbeat",
  ToolCompleted: "tool_completed",
  ClearTranscript: "clear_transcript",
  ModalRequest: "modal_request",
  SelectRequest: "select_request",
  SessionCreated: "session_created",
  SessionLoaded: "session_loaded",
  SessionList: "session_list",
  SessionDeleted: "session_deleted",
  Error: "error",
  Shutdown: "shutdown",
} as const;

export type BackendEventType =
  (typeof BackendEventType)[keyof typeof BackendEventType];

export type ToolStatus =
  | "running"
  | "waiting_permission"
  | "waiting_output"
  | "stalled"
  | "success"
  | "error"
  | "cancelled"
  | "skipped";

export interface ArtifactRef {
  path: string;
  label?: string;
  mime_type?: string;
  url?: string;
  /** Legacy backend field; prefer size_bytes for new code. */
  size?: number;
  /** Byte size when known (e.g. session output); used for download-only UX. */
  size_bytes?: number;
  /** Human-readable version line (e.g. Turn 3 · tool · file.csv). */
  version_label?: string;
}

export interface TranscriptItem {
  role: "system" | "user" | "assistant" | "tool" | "tool_result" | "log";
  text: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  is_error?: boolean;
  metadata?: Record<string, unknown>;
  artifacts?: ArtifactRef[];
  tool_use_id?: string;
  tool_status?: ToolStatus;
  /**
   * Unix milliseconds. Backends may populate this; the frontend reducer
   * stamps Date.now() for any item that arrives without one, so UI code can
   * treat this field as effectively-always-present.
   */
  timestamp?: number;
}

export interface TaskSnapshot {
  id: string;
  type: string;
  status: string;
  description: string;
  metadata: Record<string, string>;
}

export interface McpServerSnapshot {
  name: string;
  state: string;
  detail?: string;
  transport?: string;
  auth_configured?: boolean;
  tool_count?: number;
  resource_count?: number;
}

export interface BridgeSessionSnapshot {
  session_id: string;
  command: string;
  cwd: string;
  pid: number;
  status: string;
  started_at: number;
  output_path: string;
}

export interface SelectOptionPayload {
  value: string;
  label: string;
  description?: string;
}

export interface AppStateSnapshot {
  model: string;
  cwd: string;
  provider: string;
  auth_status: string;
  base_url: string;
  permission_mode: string;
  theme: string;
  vim_enabled: boolean;
  voice_enabled: boolean;
  voice_available: boolean;
  voice_reason: string;
  fast_mode: boolean;
  effort: string;
  passes: number;
  mcp_connected: boolean;
  mcp_failed: boolean;
  bridge_sessions: number;
  output_style: string;
  keybindings: Record<string, string>;
}

export interface SessionSummaryPayload {
  session_id: string;
  summary: string;
  message_count: number;
  model: string;
  created_at: number;
}

export interface BackendEvent {
  type: BackendEventType;
  message?: string | null;
  item?: TranscriptItem | null;
  state?: AppStateSnapshot | null;
  tasks?: TaskSnapshot[] | null;
  mcp_servers?: McpServerSnapshot[] | null;
  bridge_sessions?: BridgeSessionSnapshot[] | null;
  commands?: string[] | null;
  modal?: Record<string, unknown> | null;
  select_options?: SelectOptionPayload[] | null;
  tool_name?: string | null;
  tool_input?: Record<string, unknown> | null;
  output?: string | null;
  is_error?: boolean | null;
  session_id?: string | null;
  sessions?: SessionSummaryPayload[] | null;
  transcript?: TranscriptItem[] | null;
}

// ---------------------------------------------------------------------------
// Frontend → Upstream  (FrontendRequest)
// ---------------------------------------------------------------------------

export const FrontendRequestType = {
  SubmitLine: "submit_line",
  PermissionResponse: "permission_response",
  QuestionResponse: "question_response",
  SessionControl: "session_control",
  StepControl: "step_control",
  NewSession: "new_session",
  LoadSession: "load_session",
  ListSessions: "list_sessions",
  DeleteSession: "delete_session",
  RenameSession: "rename_session",
  RefreshSettings: "refresh_settings",
  Shutdown: "shutdown",
} as const;

export type FrontendRequestType =
  (typeof FrontendRequestType)[keyof typeof FrontendRequestType];

export interface AttachmentRef {
  filename: string;
  path: string;
  size: number;
  mime_type: string;
}

export interface FrontendRequest {
  type: FrontendRequestType;
  line?: string;
  action?: "stop" | "skip" | "wait";
  request_id?: string;
  allowed?: boolean;
  trust_session?: boolean;
  answer?: string;
  attachments?: AttachmentRef[];
  session_id?: string;
  summary?: string;
  tool_use_id?: string;
}
