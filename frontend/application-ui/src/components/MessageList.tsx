import { useEffect, useRef, useMemo, useState, type ReactNode } from "react";
import { Download, FileCode, ImageIcon, Loader2 } from "lucide-react";
import type { TranscriptItem } from "../types/protocol";
import { cn } from "@/lib/utils";
import { getFileName } from "@/lib/language";
import type { ArtifactEntry } from "@/store/sessionReducer";
import ToolCallBlock from "./ToolCallBlock";
import MarkdownRenderer from "./MarkdownRenderer";

const ROLE_CONFIG: Record<string, { color: string; label: string }> = {
  user:        { color: "text-text-secondary", label: "You" },
  assistant:   { color: "text-role-assistant", label: "Assistant" },
  system:      { color: "text-role-system", label: "System" },
  tool:        { color: "text-role-tool", label: "Tool" },
  tool_result: { color: "text-role-result", label: "Result" },
  log:         { color: "text-role-log", label: "Log" },
};

function getRoleConfig(role: string) {
  return ROLE_CONFIG[role] ?? ROLE_CONFIG.log!;
}

function bubbleAlignRole(
  role: string,
): "user" | "assistant" | "system" | "log" {
  if (role === "user") return "user";
  if (role === "assistant") return "assistant";
  if (role === "system") return "system";
  return "log";
}

/**
 * Render a unix-millis timestamp as a short "HH:MM" label with a tooltip
 * showing the full locale string. Returns null for nullish / non-finite
 * inputs so callers can unconditionally pass their value in.
 */
function formatBubbleTime(ts: number | null | undefined): {
  short: string;
  full: string;
} | null {
  if (ts == null || !Number.isFinite(ts)) return null;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return null;
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  return { short: `${hh}:${mm}`, full: d.toLocaleString() };
}

function BubbleTimestamp({
  timestamp,
  align,
}: {
  timestamp: number | null | undefined;
  align: "left" | "right";
}) {
  const formatted = formatBubbleTime(timestamp);
  if (!formatted) return null;
  return (
    <div
      className={cn(
        "mt-1.5 text-[10px] leading-none text-text-dimmed select-none",
        align === "right" ? "text-right" : "text-left",
      )}
    >
      <time dateTime={new Date(timestamp!).toISOString()} title={formatted.full}>
        {formatted.short}
      </time>
    </div>
  );
}

function MessageBubbleShell({
  role,
  className,
  children,
  timestamp,
  trailingAside,
}: {
  role: "user" | "assistant" | "system" | "log";
  className?: string;
  children: ReactNode;
  timestamp?: number | null;
  /** Shown to the right of the bubble, bottom-aligned (e.g. session export). */
  trailingAside?: ReactNode;
}) {
  const isUser = role === "user";
  return (
    <div
      className={cn(
        "flex w-full shrink-0",
        isUser ? "justify-end" : "justify-start items-end gap-1.5 md:gap-2",
      )}
    >
      <div
        className={cn(
          "min-w-0 w-fit max-w-[85%] px-3.5 py-2.5",
          isUser
            ? "rounded-2xl border-2 border-msg-user-border bg-bg-msg-user shadow-[0_1px_4px_rgba(0,0,0,0.4)]"
            : "rounded-xl border border-border-primary bg-bg-secondary/50",
          className,
        )}
      >
        {children}
        <BubbleTimestamp timestamp={timestamp} align={isUser ? "right" : "left"} />
      </div>
      {!isUser && trailingAside}
    </div>
  );
}

function SessionDownloadAllButton({
  sessionId,
  disabled,
}: {
  sessionId: string;
  disabled: boolean;
}) {
  const [pending, setPending] = useState(false);

  const handleClick = () => {
    if (disabled || pending) return;
    setPending(true);
    const url = `/api/session-export/${encodeURIComponent(sessionId)}`;
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => setPending(false), 1200);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || pending}
      title="Download session snapshot, uploads, and output as a ZIP"
      className={cn(
        "shrink-0 rounded-md border border-border-subtle bg-bg-tertiary/80 px-2 py-1",
        "text-[10px] font-medium leading-none text-text-muted whitespace-nowrap",
        "inline-flex flex-row items-center gap-1 transition-colors",
        "hover:border-accent-blue hover:text-text-secondary hover:bg-bg-elevated",
        "disabled:pointer-events-none disabled:opacity-40",
      )}
    >
      <Download className="size-3 shrink-0" aria-hidden />
      <span>Download All</span>
    </button>
  );
}

interface MessageListProps {
  transcript: TranscriptItem[];
  streamingText: string;
  busy: boolean;
  stopping: boolean;
  /** Unix millis of when the current turn started, for the streaming bubble. */
  streamStartedAt?: number | null;
  artifacts?: ArtifactEntry[];
  artifactIdsByIndex?: Record<number, string[]>;
  onOpenArtifact?: (id: string) => void;
  onStepControl?: (action: "stop" | "skip" | "wait", item: TranscriptItem) => void;
  currentSessionId: string | null;
  connected: boolean;
}

export default function MessageList({
  transcript,
  streamingText,
  busy,
  stopping,
  streamStartedAt,
  artifacts,
  artifactIdsByIndex,
  onOpenArtifact,
  onStepControl,
  currentSessionId,
  connected,
}: MessageListProps) {
  const sandboxArtifactsByIndex = new Map<number, Record<string, string>>();
  if (artifacts) {
    for (const a of artifacts) {
      const idx = a.transcriptIndex;
      if (Number.isNaN(idx)) continue;

      let map = sandboxArtifactsByIndex.get(idx);
      if (!map) {
        map = {};
        sandboxArtifactsByIndex.set(idx, map);
      }
      const filename = getFileName(a.filePath);
      map[filename] = a.id;
    }
  }
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, streamingText]);

  const hasStreaming = streamingText.length > 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
      <div className="mx-auto flex w-full min-w-0 max-w-full flex-col gap-2 md:max-w-[52.8rem] lg:max-w-[61.6rem]">
      {transcript.map((item, i) => {
        if (item.role === "tool" || item.role === "tool_result") {
          return (
            <div
              key={i}
              className="flex w-full shrink-0 justify-start pl-2 md:pl-3"
            >
              <div className="min-w-0 w-full max-w-[72%]">
                <ToolCallBlock
                  item={item}
                  artifactIds={artifactIdsByIndex?.[i]}
                  sandboxArtifactIds={sandboxArtifactsByIndex.get(i)}
                  onOpenArtifact={onOpenArtifact}
                  onStepControl={onStepControl}
                />
              </div>
            </div>
          );
        }

        const cfg = getRoleConfig(item.role);
        const align = bubbleAlignRole(item.role);
        const linkedArtifactIds = artifactIdsByIndex?.[i] ?? [];
        const primaryArtifactId = linkedArtifactIds[0];
        const fileArtifactByName = sandboxArtifactsByIndex.get(i);
        const exportAside =
          item.role === "assistant" && currentSessionId ? (
            <SessionDownloadAllButton
              sessionId={currentSessionId}
              disabled={!connected}
            />
          ) : undefined;

        return (
          <MessageBubbleShell
            key={i}
            role={align}
            timestamp={item.timestamp}
            trailingAside={exportAside}
          >
            <div className="mb-1 flex items-center gap-2">
              <div className={cn("text-[11px] font-semibold", cfg.color)}>
                {cfg.label}
              </div>
              {(item.role === "assistant" || item.role === "user") &&
                primaryArtifactId &&
                onOpenArtifact && (
                <button
                  type="button"
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-text-muted transition-colors hover:bg-bg-elevated",
                    item.role === "assistant" ? "hover:text-role-assistant" : "hover:text-msg-user-border",
                  )}
                  onClick={() => onOpenArtifact(primaryArtifactId)}
                  title="View in Artifact Panel"
                >
                  <FileCode className="size-3" />
                  {linkedArtifactIds.length > 1 ? `View ${linkedArtifactIds.length} files` : "View"}
                </button>
              )}
            </div>
            {item.role === "assistant" || item.role === "system" ? (
              <MarkdownRenderer content={item.text} />
            ) : (
              <UserMessageContent
                text={item.text}
                fileArtifactByName={fileArtifactByName}
                onOpenArtifact={onOpenArtifact}
              />
            )}
          </MessageBubbleShell>
        );
      })}

      {hasStreaming && (
        <MessageBubbleShell role="assistant" timestamp={streamStartedAt}>
          <div className="text-[11px] mb-1 font-semibold text-role-assistant">
            Assistant
          </div>
          <MarkdownRenderer content={streamingText} />
          <span className="animate-blink text-role-assistant">▊</span>
        </MessageBubbleShell>
      )}

      {busy && !hasStreaming && (
        <div className="flex w-full shrink-0 justify-start pl-2 md:pl-3">
          <div className="inline-flex max-w-[85%] items-center gap-2 px-0.5 py-1 text-[11px] text-text-dimmed">
            <Loader2 className="size-3 animate-spin text-text-faint" />
            <span>{stopping ? "Stopping current run..." : "Session still running"}</span>
            <BubbleTimestamp timestamp={streamStartedAt} align="left" />
          </div>
        </div>
      )}

      <div ref={bottomRef} className="h-0 shrink-0" />
      </div>
    </div>
  );
}

const ATTACHED_IMAGE_RE = /\[Attached image: (.+?) \(\d+ bytes\) at (.+?)\]/g;
const ATTACHED_FILE_RE = /\[Attached file: (.+?) \(\d+ bytes\)(?:\s+at .+?)?\]/g;

function UserMessageContent({
  text,
  fileArtifactByName,
  onOpenArtifact,
}: {
  text: string;
  fileArtifactByName?: Record<string, string>;
  onOpenArtifact?: (id: string) => void;
}) {
  const { images, files, cleanText } = useMemo(() => {
    const imgs: { name: string; path: string }[] = [];
    const fls: { name: string }[] = [];

    let cleaned = text;
    for (const match of text.matchAll(ATTACHED_IMAGE_RE)) {
      const name = match[1]!;
      const rawPath = match[2]!;
      const path =
        rawPath.startsWith("/api/") ? rawPath : `/api/uploads/${rawPath.split("/").pop() ?? name}`;
      imgs.push({ name, path });
    }
    cleaned = cleaned.replace(ATTACHED_IMAGE_RE, "").trim();

    for (const match of cleaned.matchAll(ATTACHED_FILE_RE)) {
      fls.push({ name: match[1]! });
    }
    cleaned = cleaned.replace(ATTACHED_FILE_RE, "");
    cleaned = cleaned.replace(/^```[\s\S]*?```$/gm, "").trim();

    return { images: imgs, files: fls, cleanText: cleaned };
  }, [text]);

  return (
    <div>
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {images.map((img, i) => {
            const artifactId = fileArtifactByName?.[img.name];
            const imgEl = (
              <img
                src={img.path}
                alt={img.name}
                className="max-w-[200px] max-h-[150px] object-cover"
                loading="lazy"
              />
            );
            const frameClass =
              "block rounded-md overflow-hidden border border-border-subtle hover:border-accent-blue transition-colors";
            if (artifactId && onOpenArtifact) {
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => onOpenArtifact(artifactId)}
                  className={cn(frameClass, "text-left cursor-pointer")}
                  title={`Open ${img.name} in Artifacts`}
                >
                  {imgEl}
                </button>
              );
            }
            return (
              <a
                key={i}
                href={img.path}
                target="_blank"
                rel="noopener noreferrer"
                className={frameClass}
              >
                {imgEl}
              </a>
            );
          })}
        </div>
      )}

      {files.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {files.map((f, i) => {
            const artifactId = fileArtifactByName?.[f.name];
            const chipClass =
              "inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-xs border-border-subtle";
            if (artifactId && onOpenArtifact) {
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => onOpenArtifact(artifactId)}
                  className={cn(
                    chipClass,
                    "bg-bg-tertiary text-text-secondary cursor-pointer hover:bg-bg-elevated hover:border-accent-blue transition-colors text-left",
                  )}
                  title="Open in Artifact Panel"
                >
                  <FileCode className="size-3 shrink-0" />
                  <span className="truncate max-w-[220px]">{f.name}</span>
                </button>
              );
            }
            return (
              <span
                key={i}
                className={cn(chipClass, "bg-bg-tertiary text-text-muted")}
              >
                <ImageIcon className="size-3" />
                {f.name}
              </span>
            );
          })}
        </div>
      )}

      {cleanText && (
        <div className="whitespace-pre-wrap leading-relaxed">{cleanText}</div>
      )}
    </div>
  );
}
