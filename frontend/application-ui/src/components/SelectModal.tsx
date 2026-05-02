import { List } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { FrontendRequest, SelectOptionPayload } from "../types/protocol";
import { Overlay } from "./PermissionModal";

interface SelectModalProps {
  title: string;
  submitPrefix: string;
  options: SelectOptionPayload[];
  sessionId: string | null;
  onSend: (req: FrontendRequest) => void;
  onDismiss: () => void;
}

export default function SelectModal({
  title,
  submitPrefix,
  options,
  sessionId,
  onSend,
  onDismiss,
}: SelectModalProps) {
  const select = (value: string) => {
    onSend({ type: "submit_line", line: submitPrefix + value, session_id: sessionId ?? undefined });
    onDismiss();
  };

  return (
    <Overlay>
      <div className="w-[min(440px,90vw)] max-h-[80vh] overflow-y-auto bg-bg-tertiary border border-border-primary rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <List className="size-5 text-role-assistant" />
          <span className="text-[15px] font-semibold text-role-assistant">
            {title}
          </span>
        </div>

        {options.length === 0 && (
          <div className="text-text-dimmed text-[13px] mb-4">No options available.</div>
        )}

        <div className="flex flex-col gap-1.5 mb-4">
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => select(opt.value)}
              className="block w-full text-left px-3.5 py-2.5 rounded-md border border-border-secondary bg-bg-secondary text-text-primary cursor-pointer text-[13px] transition-colors hover:bg-bg-elevated hover:border-border-primary"
            >
              <div className="font-medium">{opt.label}</div>
              {opt.description && (
                <div className="text-text-dimmed text-xs mt-0.5">{opt.description}</div>
              )}
            </button>
          ))}
        </div>

        <div className="flex justify-end">
          <Button variant="secondary" onClick={onDismiss}>
            Cancel
          </Button>
        </div>
      </div>
    </Overlay>
  );
}
