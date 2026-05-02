/**
 * Client-only export of the current chat (transcript + streaming buffer)
 * to Markdown / JSON. Pure function — works just as well against mock data.
 */

import type { TranscriptItem } from "../types/protocol";
import type { SessionState } from "../store/sessionReducer";

function makeFence(body: string): string {
  let len = 3;
  while (true) {
    const fence = "`".repeat(len);
    if (!body.includes(fence)) return fence;
    len++;
  }
}

function fencedBlock(lang: string, body: string): string {
  const fence = makeFence(body);
  const head = lang ? `${fence}${lang}\n` : `${fence}\n`;
  return `${head}${body}\n${fence}`;
}

function roleHeading(role: string): string {
  switch (role) {
    case "user":
      return "User";
    case "assistant":
      return "Assistant";
    case "system":
      return "System";
    case "tool":
      return "Tool";
    case "tool_result":
      return "Tool result";
    case "log":
      return "Log";
    default:
      return role;
  }
}

function formatTranscriptItemMd(item: TranscriptItem, index: number): string {
  const lines: string[] = [`### ${roleHeading(item.role)} (${index + 1})`];

  if (item.role === "tool" || item.role === "tool_result") {
    const name = item.tool_name ?? "unknown";
    lines.push("", `**${name}**${item.is_error ? " *(error)*" : ""}`, "");
    if (item.tool_input && Object.keys(item.tool_input).length > 0) {
      let inputStr: string;
      try {
        inputStr = JSON.stringify(item.tool_input, null, 2);
      } catch {
        inputStr = String(item.tool_input);
      }
      lines.push(fencedBlock("json", inputStr));
    }
    if (item.text?.trim()) {
      lines.push("", fencedBlock("", item.text));
    }
    return lines.join("\n");
  }

  if (item.text?.trim()) {
    lines.push("", item.text);
  } else {
    lines.push("", "*(empty)*");
  }
  return lines.join("\n");
}

export function buildExportMarkdown(state: SessionState): string {
  const parts: string[] = [];
  parts.push("# FuxiClaw transcript");
  parts.push("");
  parts.push(`Exported: ${new Date().toISOString()}`);

  if (state.appState) {
    parts.push("");
    parts.push("## Session");
    parts.push("");
    parts.push(`- **Model:** ${state.appState.model}`);
    parts.push(`- **CWD:** \`${state.appState.cwd}\``);
    parts.push(`- **Provider:** ${state.appState.provider}`);
  }

  parts.push("");
  parts.push("## Messages");
  parts.push("");

  if (state.transcript.length === 0 && !state.assistantBuffer.trim()) {
    parts.push("*(no messages)*");
  } else {
    state.transcript.forEach((item, i) => {
      parts.push(formatTranscriptItemMd(item, i));
      parts.push("");
    });
    if (state.assistantBuffer.trim()) {
      parts.push("### Assistant (streaming)");
      parts.push("");
      parts.push(
        "_The assistant reply was still streaming when you exported._",
        "",
        state.assistantBuffer,
        "",
      );
    }
  }

  if (state.artifacts.length > 0) {
    parts.push("## Artifacts");
    parts.push("");
    for (const a of state.artifacts) {
      parts.push(`- **${a.filePath}** (\`${a.toolName}\`, ${a.status})`);
    }
    parts.push("");
  }

  return parts.join("\n").trimEnd() + "\n";
}

export interface ExportedChatJson {
  version: 1;
  exportedAt: string;
  appState: Pick<
    NonNullable<SessionState["appState"]>,
    "model" | "cwd" | "provider" | "permission_mode"
  > | null;
  transcript: TranscriptItem[];
  assistantBuffer: string;
  artifacts: Array<{
    id: string;
    filePath: string;
    status: string;
    toolName: string;
  }>;
}

export function buildExportJson(state: SessionState): string {
  const payload: ExportedChatJson = {
    version: 1,
    exportedAt: new Date().toISOString(),
    appState: state.appState
      ? {
          model: state.appState.model,
          cwd: state.appState.cwd,
          provider: state.appState.provider,
          permission_mode: state.appState.permission_mode,
        }
      : null,
    transcript: state.transcript,
    assistantBuffer: state.assistantBuffer,
    artifacts: state.artifacts.map((a) => ({
      id: a.id,
      filePath: a.filePath,
      status: a.status,
      toolName: a.toolName,
    })),
  };
  return JSON.stringify(payload, null, 2) + "\n";
}

export function triggerDownload(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  a.click();
  URL.revokeObjectURL(url);
}

export function exportFilename(prefix: string, ext: string): string {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  return `${prefix}-${stamp}.${ext}`;
}
