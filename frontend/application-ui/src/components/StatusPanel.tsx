import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Settings2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AppStateSnapshot, TaskSnapshot, McpServerSnapshot } from "../types/protocol";

type ProviderId =
  | "kimi"
  | "deepseek"
  | "minimax"
  | "glm"
  | "mimo"
  | "openai"
  | "anthropic"
  | "gemini"
  | "grok"
  | "custom";
type PermissionMode = "default" | "plan" | "full_auto";

const PROVIDERS: Array<{ value: Exclude<ProviderId, "custom">; label: string }> = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Claude (Anthropic)" },
  { value: "gemini", label: "Gemini (Google)" },
  { value: "grok", label: "Grok (xAI)" },
  { value: "kimi", label: "Kimi (Moonshot)" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "minimax", label: "MiniMax" },
  { value: "glm", label: "GLM (Zhipu)" },
  { value: "mimo", label: "MiMo (Xiaomi)" },
];

interface StatusPanelProps {
  appState: AppStateSnapshot | null;
  tasks: TaskSnapshot[];
  mcpServers: McpServerSnapshot[];
  commands: string[];
  open: boolean;
  onToggle: () => void;
  onReconnect: () => void;
  triggerClassName?: string;
  hideTrigger?: boolean;
}

/**
 * Mocked settings store — replaces the real `/api/settings` GET/PATCH.
 *
 * The state lives in React only (no persistence); switching provider or saving
 * still behaves correctly in the UI, and the runtime Row section below keeps
 * rendering the backend-provided AppStateSnapshot.
 */
export default function StatusPanel({
  appState,
  tasks,
  mcpServers,
  commands,
  open,
  onToggle,
  onReconnect,
  triggerClassName,
  hideTrigger = false,
}: StatusPanelProps) {
  const [providerId, setProviderId] = useState<ProviderId>("kimi");
  const [model, setModel] = useState("kimi-k2-turbo-preview");
  const [permissionMode, setPermissionMode] = useState<PermissionMode>("default");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [apiKeyConfigured, setApiKeyConfigured] = useState(true);
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");
  const [needsReconnect, setNeedsReconnect] = useState(false);

  const canEditProvider = providerId !== "custom";
  const providerHelp = useMemo(
    () =>
      providerId === "custom"
        ? "Current settings do not match a predefined provider. Select a provider preset to continue."
        : "Provider preset controls api_format + base_url.",
    [providerId],
  );

  const loadSettings = useCallback(async () => {
    setLoadingSettings(true);
    await new Promise((resolve) => setTimeout(resolve, 120));
    setSaveMessage("");
    setSaveError("");
    setNeedsReconnect(false);
    setLoadingSettings(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    void loadSettings();
  }, [open, loadSettings]);

  const onSaveSettings = useCallback(async () => {
    setSavingSettings(true);
    setSaveError("");
    setSaveMessage("");
    setNeedsReconnect(false);
    await new Promise((resolve) => setTimeout(resolve, 250));
    if (apiKeyInput.trim()) {
      setApiKeyConfigured(true);
      setApiKeyInput("");
    }
    setSaveMessage("Settings saved (mock — not persisted).");
    setSavingSettings(false);
  }, [apiKeyInput]);

  if (!appState) return null;

  return (
    <>
      {!hideTrigger && (
        <Button variant="outline" size="sm" onClick={onToggle} className={triggerClassName}>
          <Settings2 className="size-3.5" />
          Status
        </Button>
      )}

      {open && (
        <div className="fixed top-0 right-0 bottom-0 w-[min(360px,85vw)] bg-bg-secondary border-l border-border-subtle z-50 overflow-y-auto p-5 flex flex-col gap-5 max-md:w-screen max-md:border-l-0">
          <div className="flex justify-between items-center">
            <span className="font-bold text-[15px]">Status</span>
            <Button variant="ghost" size="icon-sm" onClick={onToggle}>
              <X className="size-4" />
            </Button>
          </div>

          <Section title="Settings">
            {loadingSettings && (
              <div className="flex items-center gap-2 text-xs text-text-muted pb-2">
                <Loader2 className="size-3 animate-spin" />
                Loading settings...
              </div>
            )}

            <div className="space-y-2.5">
              <Field label="Provider">
                <select
                  value={providerId}
                  onChange={(e) => setProviderId(e.target.value as ProviderId)}
                  className="w-full h-8 rounded-md border border-border-primary bg-bg-input text-text-primary text-xs px-2 outline-none focus:border-accent-blue disabled:opacity-60"
                  disabled={loadingSettings || savingSettings}
                >
                  {providerId === "custom" && (
                    <option value="custom">Custom (unsupported preset)</option>
                  )}
                  {PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <div className="text-[11px] text-text-faint mt-1">{providerHelp}</div>
              </Field>

              <Field label="Model">
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="e.g. gpt-4.1-mini"
                  className="w-full h-8 rounded-md border border-border-primary bg-bg-input text-text-primary text-xs px-2 outline-none focus:border-accent-blue disabled:opacity-60"
                  disabled={loadingSettings || savingSettings || !canEditProvider}
                />
              </Field>

              <Field label="API Key">
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder={apiKeyConfigured ? "Configured (enter to replace)" : "Enter API key"}
                  className="w-full h-8 rounded-md border border-border-primary bg-bg-input text-text-primary text-xs px-2 outline-none focus:border-accent-blue disabled:opacity-60"
                  disabled={loadingSettings || savingSettings || !canEditProvider}
                />
                <div className="text-[11px] text-text-faint mt-1">
                  {apiKeyConfigured ? "Current key is configured (masked)." : "No API key configured."}
                </div>
              </Field>

              <Field label="Permission Mode">
                <select
                  value={permissionMode}
                  onChange={(e) => setPermissionMode(e.target.value as PermissionMode)}
                  className="w-full h-8 rounded-md border border-border-primary bg-bg-input text-text-primary text-xs px-2 outline-none focus:border-accent-blue disabled:opacity-60"
                  disabled={loadingSettings || savingSettings}
                >
                  <option value="default">default</option>
                  <option value="plan">plan</option>
                  <option value="full_auto">full_auto</option>
                </select>
                <div className="text-[11px] text-text-faint mt-1">
                  This is the default mode saved to settings.json for future sessions. "Trust this session"
                  remains temporary and only applies to the current connection.
                </div>
                <div className="text-[11px] text-text-faint mt-1">
                  <span className="text-text-secondary">default</span>: mutating tools require confirmation.
                  {" "}
                  <span className="text-text-secondary">plan</span>: mutating tools are blocked until exiting plan mode.
                  {" "}
                  <span className="text-text-secondary">full_auto</span>: tools run without confirmation.
                </div>
              </Field>

              <Button
                variant="accent"
                size="sm"
                onClick={onSaveSettings}
                disabled={loadingSettings || savingSettings || !canEditProvider || !model.trim()}
                className="w-full"
              >
                {savingSettings ? (
                  <>
                    <Loader2 className="size-3 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save settings"
                )}
              </Button>

              {saveMessage && (
                <div className="text-xs text-accent-green">{saveMessage}</div>
              )}
              {saveError && (
                <div className="text-xs text-accent-red-light">{saveError}</div>
              )}
              {needsReconnect && (
                <Button variant="outline" size="sm" onClick={onReconnect} className="w-full">
                  Reconnect again
                </Button>
              )}
            </div>
          </Section>

          <Section title="Runtime">
            <Row label="Model" value={appState.model} />
            <Row label="Provider" value={appState.provider} />
            <Row label="CWD" value={appState.cwd} mono />
            <Row label="Permission" value={appState.permission_mode} />
            <Row label="Auth" value={appState.auth_status} />
            <Row label="Effort" value={appState.effort} />
            <Row label="Fast mode" value={appState.fast_mode ? "On" : "Off"} />
            <Row label="MCP" value={`${appState.mcp_connected} connected, ${appState.mcp_failed} failed`} />
          </Section>

          {mcpServers.length > 0 && (
            <Section title="MCP Servers">
              {mcpServers.map((s) => (
                <div key={s.name} className="mb-1.5">
                  <Row
                    label={s.name}
                    value={s.state}
                    valueColor={
                      s.state === "connected" ? "text-accent-green"
                        : s.state === "failed" ? "text-accent-red"
                          : "text-text-muted"
                    }
                  />
                  {s.tool_count != null && (
                    <div className="text-[11px] text-text-faint ml-3">
                      {s.tool_count} tools, {s.resource_count ?? 0} resources
                    </div>
                  )}
                </div>
              ))}
            </Section>
          )}

          {tasks.length > 0 && (
            <Section title={`Tasks (${tasks.length})`}>
              {tasks.map((t) => (
                <div
                  key={t.id}
                  className="p-1.5 px-2 bg-bg-tertiary rounded-sm mb-1 text-xs"
                >
                  <div className="flex justify-between items-center">
                    <span className="text-text-secondary">{t.description}</span>
                    <TaskBadge status={t.status} />
                  </div>
                </div>
              ))}
            </Section>
          )}

          {commands.length > 0 && (
            <Section title="Commands">
              <div className="flex flex-wrap gap-1">
                {commands.map((cmd) => (
                  <Badge key={cmd} variant="secondary" className="font-mono text-[11px]">
                    {cmd}
                  </Badge>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-[11px] text-text-dimmed mb-1">{label}</div>
      {children}
    </label>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] text-text-dimmed uppercase mb-2 tracking-wide">
        {title}
      </div>
      {children}
    </div>
  );
}

function Row({
  label,
  value,
  mono,
  valueColor,
}: {
  label: string;
  value: string;
  mono?: boolean;
  valueColor?: string;
}) {
  return (
    <div className="flex justify-between text-xs py-0.5">
      <span className="text-text-dimmed">{label}</span>
      <span
        className={cn(
          "max-w-[60%] truncate text-right",
          valueColor ?? "text-text-secondary",
          mono && "font-mono",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function TaskBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    running: "bg-accent-blue/15 text-accent-blue",
    completed: "bg-accent-green/15 text-accent-green",
    failed: "bg-accent-red/15 text-accent-red",
    pending: "bg-accent-yellow/15 text-accent-yellow",
  };
  return (
    <span
      className={cn(
        "text-[10px] px-1.5 py-px rounded font-semibold shrink-0",
        variants[status] ?? "bg-bg-tertiary text-text-muted",
      )}
    >
      {status}
    </span>
  );
}
