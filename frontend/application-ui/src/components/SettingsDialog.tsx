import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  getDefaultWsUrl,
  getStoredWsUrl,
  setStoredWsUrl,
} from "@/lib/settings";
import type { AppStateSnapshot } from "../types/protocol";

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  appState: AppStateSnapshot | null;
  onApply: (options?: { reconnect?: boolean }) => void;
}

interface ProviderProfileOption {
  name: string;
  label: string;
  provider: string;
  api_format: string;
  auth_source: string;
  configured: boolean;
  auth_state: string;
  auth_origin: string;
  active: boolean;
  base_url: string;
  model: string;
  default_model: string;
  allowed_models: string[];
}

interface SettingsPayload {
  active_profile: string;
  profiles: ProviderProfileOption[];
  current: {
    model: string;
    provider: string;
    base_url: string;
    auth_status: string;
  };
}

export default function SettingsDialog({
  open,
  onOpenChange,
  appState,
  onApply,
}: SettingsDialogProps) {
  const defaultUrl = getDefaultWsUrl();
  const [wsUrl, setWsUrl] = useState<string>("");
  const [initialWsUrl, setInitialWsUrl] = useState<string>("");
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [profileName, setProfileName] = useState("");
  const [modelName, setModelName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [testOk, setTestOk] = useState<boolean | null>(null);

  useEffect(() => {
    if (!open) return;
    const storedWsUrl = getStoredWsUrl() ?? "";
    setWsUrl(storedWsUrl);
    setInitialWsUrl(storedWsUrl);
    setApiKey("");
    setAdvancedOpen(false);
    setError(null);
    setSaveMessage(null);
    setTestMessage(null);
    setTestOk(null);
    setLoading(true);
    fetch("/api/settings")
      .then(async (res) => {
        const payload = await res.json();
        if (!res.ok) throw new Error(String(payload?.error ?? "Failed to load settings"));
        return payload as SettingsPayload;
      })
      .then((payload) => {
        setSettings(payload);
        const active = payload.profiles.find((profile) => profile.name === payload.active_profile);
        setProfileName(payload.active_profile);
        setModelName(active?.model || active?.default_model || payload.current.model || "");
        setBaseUrl(active?.base_url || "");
      })
      .catch((err) => {
        setSettings(null);
        setError(err instanceof Error ? err.message : "Failed to load settings");
      })
      .finally(() => setLoading(false));
  }, [open]);

  const selectedProfile = useMemo(
    () => settings?.profiles.find((profile) => profile.name === profileName) ?? null,
    [profileName, settings],
  );

  const modelOptions = useMemo(() => {
    if (!selectedProfile) return [];
    const values = [
      selectedProfile.model,
      selectedProfile.default_model,
      ...selectedProfile.allowed_models,
    ].filter(Boolean);
    return Array.from(new Set(values));
  }, [selectedProfile]);

  const handleProfileChange = (nextProfile: string) => {
    setProfileName(nextProfile);
    const profile = settings?.profiles.find((item) => item.name === nextProfile);
    setModelName(profile?.model || profile?.default_model || "");
    setBaseUrl(profile?.base_url || "");
    setApiKey("");
    setSaveMessage(null);
    setTestMessage(null);
    setTestOk(null);
  };

  const buildSettingsPayload = () => {
    const payload: Record<string, string> = {
      active_profile: profileName,
      model: modelName,
      base_url: baseUrl.trim(),
    };
    if (apiKey.trim()) {
      payload.api_key = apiKey.trim();
    }
    return payload;
  };

  const handleSave = async () => {
    setError(null);
    setSaveMessage(null);
    setSaving(true);
    try {
      const trimmedWsUrl = wsUrl.trim();
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildSettingsPayload()),
      });
      const next = await res.json();
      if (!res.ok) throw new Error(String(next?.error ?? "Failed to save settings"));
      setStoredWsUrl(trimmedWsUrl.length > 0 ? trimmedWsUrl : null);
      setSettings(next as SettingsPayload);
      onApply({ reconnect: trimmedWsUrl !== initialWsUrl });
      setInitialWsUrl(trimmedWsUrl);
      setApiKey("");
      setSaveMessage(
        trimmedWsUrl !== initialWsUrl
          ? "Saved. Reconnecting to the selected backend."
          : "Saved. Current session refresh requested.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setError(null);
    setTestMessage(null);
    setTestOk(null);
    setTesting(true);
    try {
      const res = await fetch("/api/settings/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildSettingsPayload()),
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(String(payload?.error ?? "Connection test failed"));
      const ok = Boolean(payload?.ok);
      setTestOk(ok);
      setTestMessage(
        ok
          ? `Connection succeeded with ${payload?.model ?? modelName}.`
          : String(payload?.error ?? payload?.message ?? "Connection test failed"),
      );
    } catch (err) {
      setTestOk(false);
      setTestMessage(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setTesting(false);
    }
  };

  const handleResetConnection = () => {
    setWsUrl("");
    setStoredWsUrl(null);
    onApply({ reconnect: initialWsUrl !== "" });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Choose the provider, model, and credential used by new agent runs.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
          {error && (
            <div className="rounded-md border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-[12px] text-accent-red-light">
              {error}
            </div>
          )}
          {saveMessage && (
            <div className="rounded-md border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-[12px] text-accent-green">
              {saveMessage}
            </div>
          )}
          {testMessage && (
            <div
              className={
                testOk
                  ? "rounded-md border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-[12px] text-accent-green"
                  : "rounded-md border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-[12px] text-accent-red-light"
              }
            >
              {testMessage}
            </div>
          )}

          {loading ? (
            <div className="rounded-md border border-border-subtle bg-bg-secondary px-3 py-3 text-[12px] text-text-muted">
              Loading settings…
            </div>
          ) : (
            <>
              <Field label="Provider">
                <select
                  value={profileName}
                  onChange={(event) => handleProfileChange(event.target.value)}
                  className="w-full rounded-md border border-border-primary bg-bg-input px-3 py-2 text-[13px] text-text-primary outline-none transition-colors focus:border-accent-blue"
                >
                  {(settings?.profiles ?? []).map((profile) => (
                    <option key={profile.name} value={profile.name}>
                      {profile.label}{profile.configured ? "" : " · missing key"}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Model">
                {modelOptions.length > 0 ? (
                  <select
                  value={modelName}
                  onChange={(event) => {
                    setModelName(event.target.value);
                    setSaveMessage(null);
                    setTestMessage(null);
                    setTestOk(null);
                  }}
                    className="w-full rounded-md border border-border-primary bg-bg-input px-3 py-2 text-[13px] text-text-primary outline-none transition-colors focus:border-accent-blue"
                  >
                    {modelOptions.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={modelName}
                    onChange={(event) => {
                      setModelName(event.target.value);
                      setSaveMessage(null);
                      setTestMessage(null);
                      setTestOk(null);
                    }}
                    className="w-full rounded-md border border-border-primary bg-bg-input px-3 py-2 font-mono text-[13px] text-text-primary outline-none transition-colors focus:border-accent-blue"
                  />
                )}
              </Field>

              <Field label="API Key">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => {
                    setApiKey(event.target.value);
                    setSaveMessage(null);
                    setTestMessage(null);
                    setTestOk(null);
                  }}
                  placeholder={selectedProfile?.configured ? "Configured; enter a new key to replace" : "Paste API key"}
                  className="w-full rounded-md border border-border-primary bg-bg-input px-3 py-2 font-mono text-[13px] text-text-primary outline-none transition-colors focus:border-accent-blue"
                />
                <div className="mt-1 text-[11px] text-text-faint">
                  Source: {apiKey.trim() ? "new key in this form" : describeAuthOrigin(selectedProfile)}
                  {" · "}The raw key is never sent back to the UI.
                </div>
              </Field>

              <Field label="Base URL">
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(event) => {
                    setBaseUrl(event.target.value);
                    setSaveMessage(null);
                    setTestMessage(null);
                    setTestOk(null);
                  }}
                  placeholder="Provider default"
                  className="w-full rounded-md border border-border-primary bg-bg-input px-3 py-2 font-mono text-[13px] text-text-primary outline-none transition-colors focus:border-accent-blue"
                />
              </Field>

              <RuntimeSummary appState={appState} profile={selectedProfile} />

              <div>
                <button
                  type="button"
                  onClick={() => setAdvancedOpen((value) => !value)}
                  className="text-[12px] text-text-muted hover:text-text-primary"
                >
                  {advancedOpen ? "Hide" : "Show"} advanced connection
                </button>
                {advancedOpen && (
                  <div className="mt-3 rounded-md border border-border-subtle bg-bg-secondary p-3">
                    <label className="block text-[11px] uppercase text-text-dimmed mb-1.5">
                      Backend WebSocket URL
                    </label>
                    <input
                      type="text"
                      value={wsUrl}
                      onChange={(event) => setWsUrl(event.target.value)}
                      placeholder={defaultUrl}
                      className="w-full rounded-md border border-border-primary bg-bg-input px-3 py-2 font-mono text-[13px] text-text-primary outline-none transition-colors focus:border-accent-blue"
                    />
                    <div className="mt-2 flex items-center justify-between gap-3 text-[11px] text-text-faint">
                      <span className="truncate">Default: {defaultUrl}</span>
                      <Button variant="ghost" size="sm" onClick={handleResetConnection}>
                        Reset
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <DialogFooter className="mt-6">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleTestConnection}
            disabled={loading || saving || testing || !profileName || !modelName}
          >
            {testing ? "Testing…" : "Test connection"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="accent"
            size="sm"
            onClick={handleSave}
            disabled={loading || saving || !profileName || !modelName}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function describeAuthOrigin(profile: ProviderProfileOption | null): string {
  if (!profile) return "unknown";
  if (!profile.configured) return "missing";
  if (profile.auth_origin === "settings" || profile.auth_origin === "file") {
    return "saved in Settings";
  }
  if (profile.auth_origin === "env") {
    return "environment variable";
  }
  if (profile.auth_origin === "external") {
    return "external login";
  }
  return profile.auth_origin || profile.auth_state || "configured";
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1.5 text-[11px] uppercase text-text-dimmed">{label}</div>
      {children}
    </label>
  );
}

function RuntimeSummary({
  appState,
  profile,
}: {
  appState: AppStateSnapshot | null;
  profile: ProviderProfileOption | null;
}) {
  const model = profile?.model || appState?.model || "(unset)";
  const provider = profile?.provider || appState?.provider || "(unset)";
  const auth = profile
    ? profile.configured
      ? "configured"
      : profile.auth_state || "missing"
    : appState?.auth_status || "unknown";

  return (
    <div className="rounded-md bg-bg-secondary px-3 py-2 text-[12px] text-text-muted">
      <div className="flex min-w-0 items-center justify-between gap-3">
        <span className="truncate">
          Current: <span className="font-mono text-text-primary">{model}</span>
        </span>
        <span className="shrink-0 text-text-dimmed">{auth}</span>
      </div>
      <div className="mt-1 truncate text-[11px] text-text-faint">
        {provider}
      </div>
    </div>
  );
}
