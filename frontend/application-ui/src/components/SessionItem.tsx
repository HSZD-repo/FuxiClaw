import { useEffect, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SessionSummary {
  session_id: string;
  summary: string;
  message_count: number;
  model: string;
  created_at: number;
}

interface SessionItemProps {
  session: SessionSummary;
  active: boolean;
  onResume: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, summary: string) => void;
}

export default function SessionItem({ session, active, onResume, onDelete, onRename }: SessionItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState(session.summary || "");
  const inputRef = useRef<HTMLInputElement>(null);
  const renameFinishedRef = useRef(false);

  const closeMenu = () => setMenuOpen(false);
  const displayTitle = session.summary || "(empty session)";

  useEffect(() => {
    if (!renaming) {
      setDraftTitle(session.summary || "");
    }
  }, [renaming, session.summary]);

  useEffect(() => {
    if (!renaming) return;
    inputRef.current?.focus();
    inputRef.current?.select();
  }, [renaming]);

  const beginRename = () => {
    closeMenu();
    renameFinishedRef.current = false;
    setDraftTitle(session.summary || "");
    setRenaming(true);
  };

  const cancelRename = () => {
    renameFinishedRef.current = true;
    setDraftTitle(session.summary || "");
    setRenaming(false);
  };

  const saveRename = () => {
    if (renameFinishedRef.current) return;
    renameFinishedRef.current = true;
    const nextTitle = draftTitle.trim();
    if (!nextTitle || nextTitle === session.summary) {
      cancelRename();
      return;
    }
    onRename(session.session_id, nextTitle);
    setRenaming(false);
  };

  return (
    <div
      className={cn(
        "group relative mb-0.5 w-full min-w-0 max-w-full cursor-pointer rounded-md px-2.5 py-2 transition-colors",
        active
          ? "bg-bg-tertiary text-text-primary"
          : "text-text-tertiary hover:bg-bg-tertiary/70 hover:text-text-secondary",
      )}
      onClick={() => {
        if (!renaming) onResume(session.session_id);
      }}
      onMouseLeave={() => {
        if (!renaming) closeMenu();
      }}
      role="button"
      tabIndex={0}
      aria-current={active ? "page" : undefined}
      onKeyDown={(e) => {
        if (e.key === "Enter" && !renaming) onResume(session.session_id);
      }}
    >
      {renaming ? (
        <input
          ref={inputRef}
          className="block h-5 w-full min-w-0 rounded-sm border border-border-primary bg-bg-input px-1.5 pr-8 text-[13px] leading-snug text-text-primary outline-none focus:border-accent-blue"
          value={draftTitle}
          aria-label="Rename chat"
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setDraftTitle(e.target.value)}
          onBlur={saveRename}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter") {
              e.preventDefault();
              saveRename();
            }
            if (e.key === "Escape") {
              e.preventDefault();
              cancelRename();
            }
          }}
        />
      ) : (
        <div
          className={cn(
            "block min-w-0 max-w-full truncate pr-8 text-[13px] leading-snug",
            active ? "font-medium text-text-primary" : "font-normal",
          )}
          title={displayTitle}
        >
          {displayTitle}
        </div>
      )}
      <div className="mt-1 flex min-h-4 min-w-0 max-w-full items-center gap-2 overflow-hidden pr-8 text-[11px] text-text-faint">
        <span className="shrink-0">{formatRelativeTime(session.created_at)}</span>
        {session.message_count > 0 && (
          <span className="truncate" title={`${session.message_count} messages`}>
            {session.message_count} msg
          </span>
        )}
      </div>

      <button
        type="button"
        className={cn(
          "absolute right-1.5 top-1.5 z-10 rounded-sm bg-bg-secondary/80 p-1 transition-all hover:bg-bg-elevated hover:text-text-primary",
          active || menuOpen
            ? "text-text-muted opacity-70 hover:opacity-100"
            : "text-text-muted opacity-0 group-hover:opacity-100",
        )}
        title="More actions"
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        onClick={(e) => {
          e.stopPropagation();
          setMenuOpen((open) => !open);
        }}
      >
        <MoreHorizontal className="size-3.5" />
        <span className="sr-only">More actions</span>
      </button>
      {menuOpen && (
        <div
          className="absolute right-1.5 top-7 z-50 min-w-24 rounded-md border border-border-subtle bg-bg-elevated py-1 shadow-lg"
          role="menu"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="flex w-full items-center px-2.5 py-1.5 text-left text-[12px] text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
            role="menuitem"
            onClick={beginRename}
          >
            Rename
          </button>
          <button
            type="button"
            className="flex w-full items-center px-2.5 py-1.5 text-left text-[12px] text-accent-red-light hover:bg-bg-error"
            role="menuitem"
            onClick={() => {
              closeMenu();
              onDelete(session.session_id);
            }}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(unixSeconds: number): string {
  const diff = Math.floor(Date.now() / 1000 - unixSeconds);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(unixSeconds * 1000).toLocaleDateString();
}
