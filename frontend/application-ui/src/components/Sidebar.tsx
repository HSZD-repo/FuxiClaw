import { PanelLeftClose, Plus, RefreshCw, X } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import SessionItem from "./SessionItem";
import type { SessionSummary } from "./SessionItem";

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
  sessions: SessionSummary[];
  currentSessionId: string | null;
  onNewSession: () => void;
  onResumeSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, summary: string) => void;
  onRefresh: () => void;
  footer?: ReactNode;
}

export default function Sidebar({
  open,
  onToggle,
  sessions,
  currentSessionId,
  onNewSession,
  onResumeSession,
  onDeleteSession,
  onRenameSession,
  onRefresh,
  footer,
}: SidebarProps) {
  return (
    <>
      {open && (
        <div
          className="hidden max-md:block fixed inset-0 bg-overlay z-[55]"
          onClick={onToggle}
        />
      )}

      <aside
        className={cn(
          "w-[276px] shrink-0 bg-bg-secondary border-r border-border-subtle flex-col h-screen overflow-hidden",
          "max-md:fixed max-md:left-[-292px] max-md:top-0 max-md:bottom-0 max-md:z-[60] max-md:transition-[left] max-md:duration-200 max-md:ease-in-out max-md:flex",
          open ? "flex max-md:left-0" : "hidden",
        )}
      >
        <div className="shrink-0 px-3 pt-3 pb-2">
          <div className="flex h-8 items-center justify-between">
            <div className="min-w-0">
              <div className="truncate text-[13px] font-semibold text-text-primary">
                FuxiClaw
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={onToggle}
                title="Collapse sidebar"
                className="hidden text-text-muted hover:text-text-secondary md:inline-flex"
              >
                <PanelLeftClose className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-text-muted hover:text-text-secondary md:hidden"
                onClick={onToggle}
                title="Close sidebar"
              >
                <X className="size-4" />
              </Button>
            </div>
          </div>
        </div>

        <div className="shrink-0 px-3 pb-3">
          <Button
            variant="secondary"
            size="sm"
            className="h-9 w-full justify-start gap-2 bg-bg-tertiary text-text-primary shadow-none hover:bg-bg-elevated"
            onClick={onNewSession}
          >
            <Plus className="size-4" />
            New Chat
          </Button>
        </div>

        <div className="flex items-center justify-between px-3 pb-1.5 pt-1">
          <span className="text-[11px] font-medium text-text-muted">Chats</span>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onRefresh}
            title="Refresh session list"
            className="size-6 text-text-faint hover:text-text-secondary"
          >
            <RefreshCw className="size-3" />
          </Button>
        </div>

        <ScrollArea className="w-full min-w-0 flex-1 overflow-x-hidden">
          <div className="w-full min-w-0 max-w-full overflow-x-hidden px-2 pb-4 pt-1">
            {sessions.length === 0 && (
              <div className="px-2 py-4">
                <div className="rounded-md px-2 py-3 text-[12px] leading-relaxed text-text-faint">
                  No chats yet.
                  <button
                    type="button"
                    className="mt-2 block text-[12px] font-medium text-text-tertiary hover:text-text-primary"
                    onClick={onNewSession}
                  >
                    Start a new chat
                  </button>
                </div>
              </div>
            )}
            {sessions.map((s) => (
              <SessionItem
                key={s.session_id}
                session={s}
                active={s.session_id === currentSessionId}
                onResume={onResumeSession}
                onDelete={onDeleteSession}
                onRename={onRenameSession}
              />
            ))}
          </div>
        </ScrollArea>

        {footer && (
          <div className="shrink-0 border-t border-border-subtle px-2 py-2">
            {footer}
          </div>
        )}
      </aside>
    </>
  );
}
