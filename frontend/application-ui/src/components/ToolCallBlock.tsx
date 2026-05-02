import { useEffect, useState, type KeyboardEvent } from "react";
import {
  ChevronRight,
  Check,
  X,
  FileCode,
  Loader2,
  Square,
  SkipForward,
  Clock3,
  Container,
  Terminal,
  FileOutput,
  Image as ImageIcon,
  FileSpreadsheet,
  File,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolStatus, TranscriptItem } from "../types/protocol";

const SANDBOX_TOOLS = new Set(["sandbox_exec", "sandbox_cancel"]);

export function getToolCardPhase(item: TranscriptItem): ToolStatus {
  const s = item.tool_status;
  if (s) return s;
  if (item.role === "tool") return "running";
  if (item.role === "tool_result") return item.is_error ? "error" : "success";
  return "success";
}

interface SandboxOutputFile {
  name: string;
  size: number;
  mime_type: string;
  url: string;
}

interface ToolCallBlockProps {
  item: TranscriptItem;
  artifactIds?: string[];
  sandboxArtifactIds?: Record<string, string>;
  onOpenArtifact?: (id: string) => void;
  onStepControl?: (action: "stop" | "skip" | "wait", item: TranscriptItem) => void;
}

export default function ToolCallBlock({
  item,
  artifactIds,
  sandboxArtifactIds,
  onOpenArtifact,
  onStepControl,
}: ToolCallBlockProps) {
  const toolName = item.tool_name ?? "unknown tool";

  if (SANDBOX_TOOLS.has(toolName)) {
    return (
      <SandboxToolBlock
        item={item}
        artifactIds={artifactIds}
        sandboxArtifactIds={sandboxArtifactIds}
        onOpenArtifact={onOpenArtifact}
        onStepControl={onStepControl}
      />
    );
  }

  return (
    <GenericToolBlock
      item={item}
      artifactIds={artifactIds}
      onOpenArtifact={onOpenArtifact}
      onStepControl={onStepControl}
    />
  );
}

function SandboxToolBlock({
  item,
  artifactIds,
  sandboxArtifactIds,
  onOpenArtifact,
  onStepControl,
}: {
  item: TranscriptItem;
  artifactIds?: string[];
  sandboxArtifactIds?: Record<string, string>;
  onOpenArtifact?: (id: string) => void;
  onStepControl?: (action: "stop" | "skip" | "wait", item: TranscriptItem) => void;
}) {
  const phase = getToolCardPhase(item);
  const [expanded, setExpanded] = useState(!isToolRunning(phase));

  useEffect(() => {
    if (!isToolRunning(phase)) setExpanded(true);
  }, [phase]);

  const isRunning = isToolRunning(phase);
  const isError = phase === "error";

  const env = item.tool_input?.environment as string | undefined;
  const command = item.tool_input?.command as string | undefined;
  const exitCode =
    !isRunning ? (item.metadata?.exit_code as number | undefined) : undefined;
  const outputFiles = !isRunning
    ? ((item.metadata?.output_files ?? []) as SandboxOutputFile[])
    : [];

  const statusLabel = getStatusLabel(phase, item);
  const exitOk = exitCode === 0;
  const primaryArtifactId = artifactIds?.[0];
  const artifactCount = artifactIds?.length ?? 0;

  const commandPreview = command
    ? command.length > 80
      ? `${command.slice(0, 77)}...`
      : command
    : "";

  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border text-[12px]",
        phase === "waiting_permission" || phase === "stalled"
          ? "border-accent-yellow/40 bg-bg-warning/40"
          : isError
            ? "border-border-error/70 bg-bg-error/35"
            : isRunning
              ? "border-border-subtle border-l-2 border-l-[var(--color-accent-blue)] bg-bg-tertiary/90"
              : "border-border-subtle bg-bg-secondary/90",
      )}
    >
      <div className="flex w-full min-w-0 items-center gap-1.5 px-2 py-1.5 text-left text-text-primary">
        <span
          className={cn(
            "shrink-0",
            phase === "waiting_permission" || phase === "stalled"
              ? "text-accent-yellow-light"
              : isError
                ? "text-accent-red-light"
                : isRunning
                  ? "text-accent-blue"
                  : "text-text-muted",
          )}
        >
          <ToolPhaseIcon phase={phase} />
        </span>

        <Container className="size-3 shrink-0 text-text-secondary" aria-hidden />
        <span className="shrink-0 font-medium text-text-secondary">sandbox_exec</span>

        {env && (
          <span className="shrink-0 rounded-full bg-role-assistant/10 px-1.5 py-px text-[10px] font-normal text-role-assistant/85">
            {env}
          </span>
        )}

        <span className={getStatusBadgeClass(phase)}>
          {statusLabel}
        </span>

        {!isRunning && exitCode !== undefined && (
          <span
            className={cn(
              "shrink-0 rounded px-1 py-px font-mono text-[10px]",
              exitOk
                ? "bg-accent-green/15 text-accent-green"
                : "bg-bg-error/50 text-accent-red-light",
            )}
          >
            exit {exitCode}
          </span>
        )}

        {!expanded && commandPreview && (
          <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-text-faint">
            - {commandPreview}
          </span>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-0.5">
          {supportsStepControl(item) && onStepControl && (
            <ToolControlButtons item={item} onStepControl={onStepControl} />
          )}

          {primaryArtifactId && onOpenArtifact && (
            <span
              role="button"
              tabIndex={0}
              className="flex items-center gap-0.5 rounded px-1 py-0.5 text-[10px] text-text-muted transition-colors hover:bg-bg-elevated hover:text-role-assistant"
              onClick={(e) => {
                e.stopPropagation();
                onOpenArtifact(primaryArtifactId);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onOpenArtifact(primaryArtifactId);
                }
              }}
              title="View in Artifact Panel"
            >
              <FileCode className="size-2.5" />
              {artifactCount > 1 ? `View ${artifactCount} files` : "View"}
            </span>
          )}

          <span
            role="button"
            tabIndex={0}
            className="inline-flex items-center rounded p-0.5 text-text-faint transition-colors hover:bg-bg-elevated hover:text-text-primary"
            onClick={() => setExpanded(!expanded)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setExpanded(!expanded);
              }
            }}
            title={expanded ? "Collapse" : "Expand"}
          >
            <ChevronRight
              className={cn(
                "size-3 shrink-0 transition-transform duration-150",
                expanded && "rotate-90",
              )}
              aria-hidden
            />
          </span>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border-subtle/80 px-2 pb-2 pt-1.5">
          {command && (
            <div className="mb-2">
              <div className="mb-1 flex items-center gap-1 text-[10px] font-medium text-text-dimmed">
                <Terminal className="size-2.5" aria-hidden />
                Command
              </div>
              <pre className="m-0 overflow-x-auto whitespace-pre-wrap break-all rounded-sm bg-bg-code p-1.5 font-mono text-[11px] text-text-tertiary">
                {command}
              </pre>
            </div>
          )}

          {!isRunning && item.text && (
            <div className="mb-2">
              <div className="mb-1 flex items-center gap-1 text-[10px] font-medium text-text-dimmed">
                <FileOutput className="size-2.5" aria-hidden />
                {isError ? "Error output" : "Execution log"}
              </div>
              <pre
                className={cn(
                  "m-0 max-h-[320px] overflow-x-auto overflow-y-auto whitespace-pre-wrap break-all rounded-sm p-1.5 font-mono text-[11px]",
                  isError ? "bg-bg-error-deep text-accent-red-light" : "bg-bg-code text-text-tertiary",
                )}
              >
                {item.text}
              </pre>
            </div>
          )}

          {isRunning && (
            <div className="text-[10px] text-text-faint italic">
              {String(item.metadata?.status_message ?? "Executing...")}
            </div>
          )}

          {outputFiles.length > 0 && (
            <div>
              <div className="mb-1 text-[10px] text-text-dimmed">Output files</div>
              <div className="flex flex-wrap gap-1">
                {outputFiles.map((f) => {
                  const aid = sandboxArtifactIds?.[f.name];
                  return (
                    <button
                      key={f.name}
                      type="button"
                      className={cn(
                        "flex items-center gap-1 rounded-md border border-border-subtle bg-bg-elevated px-1.5 py-0.5 text-[10px] transition-colors",
                        aid && onOpenArtifact
                          ? "cursor-pointer hover:border-role-assistant/50 hover:bg-role-assistant/10"
                          : "cursor-default",
                      )}
                      onClick={() => {
                        if (aid && onOpenArtifact) onOpenArtifact(aid);
                      }}
                    >
                      <SandboxFileIcon mimeType={f.mime_type} />
                      <span className="font-medium text-text-secondary">{f.name}</span>
                      <span className="text-text-faint">{formatBytes(f.size)}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {isRunning &&
            item.tool_input &&
            Object.keys(item.tool_input).length > 0 &&
            !command && (
              <div className="mb-2 mt-1.5">
                <div className="mb-1 text-[10px] text-text-dimmed">Input</div>
                <pre className="m-0 max-h-[160px] overflow-x-auto overflow-y-auto whitespace-pre-wrap break-all rounded-sm bg-bg-code p-1.5 font-mono text-[11px] text-text-tertiary">
                  {JSON.stringify(item.tool_input, null, 2)}
                </pre>
              </div>
            )}
        </div>
      )}
    </div>
  );
}

function SandboxFileIcon({ mimeType }: { mimeType: string }) {
  if (mimeType.startsWith("image/")) return <ImageIcon className="size-2.5 text-role-assistant" />;
  if (mimeType === "text/csv" || mimeType === "text/tab-separated-values") {
    return <FileSpreadsheet className="size-2.5 text-accent-green" />;
  }
  return <File className="size-2.5 text-text-muted" />;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function GenericToolBlock({
  item,
  artifactIds,
  onOpenArtifact,
  onStepControl,
}: {
  item: TranscriptItem;
  artifactIds?: string[];
  onOpenArtifact?: (id: string) => void;
  onStepControl?: (action: "stop" | "skip" | "wait", item: TranscriptItem) => void;
}) {
  const phase = getToolCardPhase(item);
  const [expanded, setExpanded] = useState(!isToolRunning(phase));

  useEffect(() => {
    if (!isToolRunning(phase)) setExpanded(true);
  }, [phase]);

  const isRunning = isToolRunning(phase);
  const isError = phase === "error";

  const toolName = item.tool_name ?? "unknown tool";
  const hasInput = Boolean(item.tool_input && Object.keys(item.tool_input).length > 0);
  const statusLabel = getStatusLabel(phase, item);
  const contentPreview = getPreview(item, phase);
  const primaryArtifactId = artifactIds?.[0];
  const artifactCount = artifactIds?.length ?? 0;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border text-[12px]",
        phase === "waiting_permission" || phase === "stalled"
          ? "border-accent-yellow/40 bg-bg-warning/40"
          : isError
            ? "border-border-error/70 bg-bg-error/35"
            : isRunning
              ? "border-border-subtle border-l-2 border-l-[var(--color-accent-blue)] bg-bg-tertiary/90"
              : "border-border-subtle bg-bg-secondary/90",
      )}
    >
      <div className="flex w-full min-w-0 items-center gap-1.5 px-2 py-1.5 text-left text-text-primary">
        <span
          className={cn(
            "shrink-0",
            phase === "waiting_permission" || phase === "stalled"
              ? "text-accent-yellow-light"
              : isError
                ? "text-accent-red-light"
                : isRunning
                  ? "text-accent-blue"
                  : "text-text-muted",
          )}
        >
          <ToolPhaseIcon phase={phase} />
        </span>
        <span
          className={cn(
            "shrink-0 font-medium",
            isError ? "text-accent-red-light" : "text-text-secondary",
          )}
        >
          {toolName}
        </span>
        <span className={getStatusBadgeClass(phase)}>
          {statusLabel}
        </span>

        {!expanded && contentPreview && (
          <span className="min-w-0 flex-1 truncate text-[11px] text-text-faint">
            - {contentPreview}
          </span>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-0.5">
          {supportsStepControl(item) && onStepControl && (
            <ToolControlButtons item={item} onStepControl={onStepControl} />
          )}

          {primaryArtifactId && onOpenArtifact && (
            <span
              role="button"
              tabIndex={0}
              className="flex items-center gap-0.5 rounded px-1 py-0.5 text-[10px] text-text-muted transition-colors hover:bg-bg-elevated hover:text-role-assistant"
              onClick={(e) => {
                e.stopPropagation();
                onOpenArtifact(primaryArtifactId);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onOpenArtifact(primaryArtifactId);
                }
              }}
              title="View in Artifact Panel"
            >
              <FileCode className="size-2.5" />
              {artifactCount > 1 ? `View ${artifactCount} files` : "View"}
            </span>
          )}

          <span
            role="button"
            tabIndex={0}
            className="inline-flex items-center rounded p-0.5 text-text-faint transition-colors hover:bg-bg-elevated hover:text-text-primary"
            onClick={() => setExpanded(!expanded)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setExpanded(!expanded);
              }
            }}
            title={expanded ? "Collapse" : "Expand"}
          >
            <ChevronRight
              className={cn(
                "size-3 shrink-0 transition-transform duration-150",
                expanded && "rotate-90",
              )}
              aria-hidden
            />
          </span>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border-subtle/80 px-2 pb-2 pt-0 font-mono text-[11px]">
          {hasInput && (
            <div className="mb-2 mt-1.5">
              <div className="mb-1 text-[10px] font-medium text-text-dimmed">Input</div>
              <pre className="m-0 max-h-[160px] overflow-x-auto overflow-y-auto whitespace-pre-wrap break-all rounded-sm bg-bg-code p-1.5 text-text-tertiary">
                {JSON.stringify(item.tool_input, null, 2)}
              </pre>
            </div>
          )}

          {!isRunning && (
            <div className="mt-1.5">
              <div className="mb-1 text-[10px] font-medium text-text-dimmed">
                {isError ? "Error output" : "Output"}
              </div>
              <pre
                className={cn(
                  "m-0 max-h-[240px] overflow-x-auto overflow-y-auto whitespace-pre-wrap break-all rounded-sm p-1.5",
                  isError ? "bg-bg-error-deep text-accent-red-light" : "bg-bg-code text-text-tertiary",
                )}
              >
                {item.text}
              </pre>
            </div>
          )}

          {isRunning && !hasInput && (
            <div className="mt-1.5 text-text-faint italic">
              {String(item.metadata?.status_message ?? "Running...")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolPhaseIcon({ phase }: { phase: ToolStatus }) {
  if (
    phase === "running" ||
    phase === "waiting_permission" ||
    phase === "waiting_output" ||
    phase === "stalled"
  ) {
    return <Loader2 className="size-3 animate-spin" aria-hidden />;
  }
  if (phase === "cancelled" || phase === "skipped") {
    return <Square className="size-3" aria-hidden />;
  }
  if (phase === "error") {
    return <X className="size-3" aria-hidden />;
  }
  return <Check className="size-3" aria-hidden />;
}

function isToolRunning(status: ToolStatus): boolean {
  return (
    status === "running" ||
    status === "waiting_permission" ||
    status === "waiting_output" ||
    status === "stalled"
  );
}

function supportsStepControl(item: TranscriptItem): boolean {
  return Boolean(
    item.tool_use_id &&
      isToolRunning(getToolCardPhase(item)) &&
      (item.metadata?.supports_step_control ?? true),
  );
}

function getStatusLabel(status: ToolStatus, item: TranscriptItem): string {
  if (status === "waiting_permission") return "Waiting for permission";
  if (status === "waiting_output") return "Waiting";
  if (status === "stalled") return "Stalled";
  if (status === "cancelled") return "Stopped";
  if (status === "skipped") return "Skipped";
  if (status === "running") return String(item.metadata?.status_message ?? "Running");
  if (status === "error") return "Error";
  return "Done";
}

function getStatusBadgeClass(status: ToolStatus): string {
  return cn(
    "shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
    status === "waiting_permission"
      ? "bg-accent-yellow/20 text-accent-yellow-light ring-1 ring-accent-yellow/35"
      : status === "stalled"
      ? "bg-accent-yellow/20 text-accent-yellow-light ring-1 ring-accent-yellow/35"
      : status === "error"
        ? "bg-accent-red-light/20 text-accent-red-light ring-1 ring-accent-red-light/35"
        : isToolRunning(status)
          ? "bg-accent-blue/20 text-accent-blue ring-1 ring-accent-blue/30"
          : status === "cancelled" || status === "skipped"
            ? "bg-bg-tertiary text-text-secondary ring-1 ring-border-subtle"
            : "bg-accent-green/20 text-accent-green ring-1 ring-accent-green/35",
  );
}

function ToolControlButtons({
  item,
  onStepControl,
}: {
  item: TranscriptItem;
  onStepControl: (action: "stop" | "skip" | "wait", item: TranscriptItem) => void;
}) {
  const handleKey = (
    e: KeyboardEvent<HTMLSpanElement>,
    action: "stop" | "skip" | "wait",
  ) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      e.stopPropagation();
      onStepControl(action, item);
    }
  };

  return (
    <div className="mr-1 flex shrink-0 items-center gap-1">
      <span
        role="button"
        tabIndex={0}
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-[10px] text-text-muted transition-colors hover:bg-bg-elevated hover:text-accent-red-light"
        onClick={(e) => {
          e.stopPropagation();
          onStepControl("stop", item);
        }}
        onKeyDown={(e) => handleKey(e, "stop")}
        title="Stop this step"
      >
        <Square className="size-2.5" />
        Stop
      </span>
      <span
        role="button"
        tabIndex={0}
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-[10px] text-text-muted transition-colors hover:bg-bg-elevated hover:text-text-secondary"
        onClick={(e) => {
          e.stopPropagation();
          onStepControl("skip", item);
        }}
        onKeyDown={(e) => handleKey(e, "skip")}
        title="Skip this step"
      >
        <SkipForward className="size-2.5" />
        Skip
      </span>
      <span
        role="button"
        tabIndex={0}
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-[10px] text-text-muted transition-colors hover:bg-bg-elevated hover:text-accent-blue"
        onClick={(e) => {
          e.stopPropagation();
          onStepControl("wait", item);
        }}
        onKeyDown={(e) => handleKey(e, "wait")}
        title="Keep waiting"
      >
        <Clock3 className="size-2.5" />
        Wait
      </span>
    </div>
  );
}

function getPreview(item: TranscriptItem, phase: ToolStatus): string {
  if (isToolRunning(phase) && item.tool_input) {
    const keys = Object.keys(item.tool_input);
    if (keys.length === 0) return "";
    const firstKey = keys[0]!;
    const firstVal = item.tool_input[firstKey];
    const valStr = typeof firstVal === "string" ? firstVal : JSON.stringify(firstVal);
    return `${firstKey}: ${valStr}`.slice(0, 80);
  }
  if (!isToolRunning(phase) && item.text) {
    return item.text.slice(0, 80);
  }
  return "";
}
