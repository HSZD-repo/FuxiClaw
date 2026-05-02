import { useRef, useState, useCallback } from "react";
import { Send, Square, Paperclip, X, FileText, ImageIcon, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { FrontendRequest } from "../types/protocol";
import type { PendingFile } from "../hooks/useFileUpload";
import { useFileUpload } from "../hooks/useFileUpload";

interface ChatInputProps {
  disabled: boolean;
  busy: boolean;
  stopping: boolean;
  sessionId: string | null;
  onSend: (req: FrontendRequest) => void;
  onSubmitLine: (line?: string) => void;
  onStopSession: () => void;
  inputRef: React.RefObject<HTMLTextAreaElement>;
}

const IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"]);

export default function ChatInput({
  disabled,
  busy,
  stopping,
  sessionId,
  onSend,
  onSubmitLine,
  onStopSession,
  inputRef,
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const { files, addFiles, removeFile, clearFiles, uploadAll, hasFiles, isUploading } =
    useFileUpload(sessionId);

  const handleSubmit = useCallback(async () => {
    const el = inputRef.current;
    if (!el) return;
    const line = el.value.trim();
    if (!line && !hasFiles) return;

    let attachments: FrontendRequest["attachments"];
    if (hasFiles) {
      const refs = await uploadAll();
      if (refs.length > 0) {
        attachments = refs;
      }
    }

    onSend({ type: "submit_line", line: line || undefined, attachments, session_id: sessionId ?? undefined });
    onSubmitLine(line || (hasFiles ? "Uploaded files" : undefined));
    el.value = "";
    el.style.height = "auto";
    clearFiles();
  }, [inputRef, hasFiles, uploadAll, onSend, onSubmitLine, clearFiles]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (!sessionId) return;
      if (e.dataTransfer.files.length > 0) {
        addFiles(e.dataTransfer.files);
      }
    },
    [addFiles, sessionId],
  );

  return (
    <div
      className={cn(
        "px-4 py-3 border-t border-border-secondary transition-colors",
        dragOver && "bg-accent-blue/5 border-accent-blue",
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {hasFiles && (
        <div className="flex flex-wrap gap-2 mb-2">
          {files.map((pf) => (
            <AttachmentChip key={pf.id} file={pf} onRemove={removeFile} />
          ))}
        </div>
      )}

      <div className="flex gap-2 items-center">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || busy || !sessionId}
          title={sessionId ? "Attach files" : "Waiting for session…"}
          className="shrink-0"
        >
          <Paperclip className="size-4" />
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              addFiles(e.target.files);
              e.target.value = "";
            }
          }}
        />

        <textarea
          ref={inputRef}
          placeholder={
            stopping
              ? "Stopping current run..."
              : busy
                ? "Agent is still running..."
                : "Type a message… (Enter to send)"
          }
          disabled={disabled || busy}
          rows={1}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          onInput={(e) => {
            const el = e.currentTarget;
            el.style.height = "auto";
            el.style.height = Math.min(Math.max(el.scrollHeight, 36), 160) + "px";
          }}
          className="flex-1 min-h-9 px-3.5 py-2 rounded-lg border border-border-primary bg-bg-input text-text-primary text-sm font-sans resize-none leading-5 outline-none focus:border-accent-blue transition-colors box-border"
        />
        <Button
          variant={busy ? "outline" : "accent"}
          onClick={busy ? onStopSession : handleSubmit}
          disabled={disabled || (!busy && isUploading)}
          size="default"
          className="shrink-0"
        >
          {stopping ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Stopping...
            </>
          ) : isUploading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : busy ? (
            <>
              <Square className="size-4" />
              Stop
            </>
          ) : (
            <>
              <Send className="size-4" />
              Send
            </>
          )}
        </Button>
      </div>
      <div className="hidden sm:flex flex-wrap items-center justify-center gap-x-3 gap-y-1 pt-1 text-center text-[11px] text-text-muted">
        <span><Kbd>Enter</Kbd> send</span>
        <span><Kbd>Shift+Enter</Kbd> newline</span>
        <span><Kbd>/</Kbd> focus</span>
        <span>Drag & drop files to attach</span>
      </div>
    </div>
  );
}

function AttachmentChip({ file: pf, onRemove }: { file: PendingFile; onRemove: (id: string) => void }) {
  const isImage = IMAGE_TYPES.has(pf.file.type);
  const previewUrl = isImage ? URL.createObjectURL(pf.file) : null;

  return (
    <div
      className={cn(
        "flex items-center gap-1.5 pl-2 pr-1 py-1 rounded-md border text-xs max-w-[200px]",
        pf.status === "error"
          ? "border-accent-red/40 bg-bg-error text-accent-red-light"
          : pf.status === "uploading"
            ? "border-accent-blue/40 bg-accent-blue/5 text-text-secondary"
            : "border-border-primary bg-bg-tertiary text-text-secondary",
      )}
    >
      {previewUrl ? (
        <img src={previewUrl} alt="" className="size-5 rounded-sm object-cover shrink-0" />
      ) : (
        isImage
          ? <ImageIcon className="size-3.5 shrink-0 text-text-muted" />
          : <FileText className="size-3.5 shrink-0 text-text-muted" />
      )}
      <span className="truncate">{pf.file.name}</span>
      <span className="text-text-faint shrink-0">
        {pf.status === "uploading" ? (
          <Loader2 className="size-3 animate-spin" />
        ) : pf.status === "error" ? (
          "!"
        ) : (
          formatSize(pf.file.size)
        )}
      </span>
      <button
        type="button"
        onClick={() => onRemove(pf.id)}
        className="p-0.5 rounded-sm hover:bg-bg-elevated text-text-muted hover:text-text-primary transition-colors shrink-0"
      >
        <X className="size-3" />
      </button>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-block px-1 text-[10px] font-mono bg-bg-code border border-border-primary rounded-sm leading-4">
      {children}
    </kbd>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}K`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}M`;
}
