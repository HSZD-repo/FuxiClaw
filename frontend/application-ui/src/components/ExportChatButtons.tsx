import { FileJson } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SessionState } from "@/store/sessionReducer";
import {
  buildExportJson,
  exportFilename,
  triggerDownload,
} from "@/lib/exportTranscript";

interface ExportChatButtonsProps {
  state: SessionState;
}

export default function ExportChatButtons({ state }: ExportChatButtonsProps) {
  const canExport =
    state.transcript.length > 0 || state.assistantBuffer.trim().length > 0;

  const onExportJson = () => {
    if (!canExport) return;
    const body = buildExportJson(state);
    triggerDownload(exportFilename("med-claw-chat", "json"), body, "application/json;charset=utf-8");
  };

  return (
    <div className="flex items-center gap-0.5">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={!canExport}
        onClick={onExportJson}
        title="Download this chat as JSON"
        className="text-text-muted hover:text-text-secondary"
      >
        <FileJson className="size-3.5" />
        <span className="hidden lg:inline ml-1 text-[11px]">Log</span>
      </Button>
    </div>
  );
}
