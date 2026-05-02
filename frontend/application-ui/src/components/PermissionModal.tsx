import { useEffect } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { FrontendRequest } from "../types/protocol";

interface PermissionModalProps {
  requestId: string;
  toolName: string;
  reason: string;
  onSend: (req: FrontendRequest) => void;
  onDismiss: () => void;
}

export default function PermissionModal({
  requestId,
  toolName,
  reason,
  onSend,
  onDismiss,
}: PermissionModalProps) {
  const respond = (allowed: boolean, trust?: boolean) => {
    onSend({
      type: "permission_response",
      request_id: requestId,
      allowed,
      trust_session: trust || undefined,
    });
    onDismiss();
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "y" || e.key === "Y") {
        e.preventDefault();
        respond(true);
      } else if (e.key === "n" || e.key === "N") {
        e.preventDefault();
        respond(false);
      } else if (e.key === "t" || e.key === "T") {
        e.preventDefault();
        respond(true, true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  return (
    <Overlay>
      <div className="w-[min(480px,90vw)] max-h-[80vh] overflow-y-auto bg-bg-tertiary border border-border-primary rounded-xl p-6">
        <div className="flex items-center gap-2 mb-3">
          <ShieldAlert className="size-5 text-accent-yellow-light" />
          <span className="text-[15px] font-semibold text-accent-yellow-light">
            Permission Request
          </span>
        </div>
        <div className="mb-2">
          <span className="text-text-muted text-xs">Tool: </span>
          <span className="text-role-tool font-semibold">{toolName}</span>
        </div>
        <div className="bg-bg-code p-2.5 rounded-md text-[13px] text-text-secondary whitespace-pre-wrap mb-4 max-h-[200px] overflow-y-auto">
          {reason}
        </div>
        <div className="flex flex-col gap-3">
          <div className="flex gap-2 justify-end items-center">
            <span className="text-[11px] text-text-muted mr-auto">
              <Kbd>Y</Kbd> allow · <Kbd>N</Kbd> deny · <Kbd>T</Kbd> trust session
            </span>
            <Button variant="secondary" onClick={() => respond(false)}>
              Deny
            </Button>
          <Button variant="accent" onClick={() => respond(true)} autoFocus>
            Allow
          </Button>
          </div>
          <button
            onClick={() => respond(true, true)}
            className="flex items-center justify-center gap-1.5 w-full py-1.5 text-[12px] text-text-muted hover:text-accent-green border border-border-primary hover:border-accent-green/40 rounded-lg transition-colors"
          >
            <ShieldCheck className="size-3.5" />
            Trust this session (temporary FULL_AUTO for this connection)
          </button>
          <div className="text-[11px] text-text-faint leading-relaxed">
            This only affects the current WebSocket session. To change the default mode for future sessions,
            update <span className="font-mono">Settings → Permission Mode</span>.
          </div>
        </div>
      </div>
    </Overlay>
  );
}

export function Overlay({ children }: { children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 bg-overlay flex items-center justify-center z-[100]">
      {children}
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-block px-1.5 py-px text-[11px] font-mono bg-bg-code border border-border-primary rounded-sm">
      {children}
    </kbd>
  );
}
