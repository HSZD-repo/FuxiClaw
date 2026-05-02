import { AlertCircle, ArrowRight } from "lucide-react";
import type { ConnectionStatus } from "../store/sessionReducer";
import { EXAMPLE_PROMPTS } from "../lib/mockData";

interface WelcomeCardProps {
  connectionStatus: ConnectionStatus;
  model: string | null;
  onSendPrompt: (prompt: string) => void;
}

export default function WelcomeCard({
  connectionStatus,
  model,
  onSendPrompt,
}: WelcomeCardProps) {
  if (connectionStatus === "connecting" || connectionStatus === "reconnecting") {
    return <ConnectingState />;
  }

  if (connectionStatus === "disconnected") {
    return <DisconnectedState />;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-8 p-8 overflow-y-auto">
      <div className="text-center">
        <div className="text-3xl font-extrabold tracking-tight text-text-primary mb-1.5">
          FuxiClaw
        </div>
        <div className="text-sm text-text-muted">
          {model ? `Connected · ${model}` : "Connected"}
        </div>
      </div>

      <div className="w-full max-w-[720px]">
        <div className="text-[11px] uppercase tracking-wide text-text-dimmed mb-3 px-1">
          Try an example
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {EXAMPLE_PROMPTS.map(({ title, description, prompt, icon: Icon }) => (
            <button
              key={title}
              type="button"
              onClick={() => onSendPrompt(prompt)}
              className="group flex items-start gap-3 rounded-xl border border-border-secondary bg-bg-tertiary p-4 text-left transition-all hover:-translate-y-0.5 hover:border-accent-blue hover:bg-bg-elevated hover:shadow-lg"
            >
              <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-bg-elevated text-text-muted transition-colors group-hover:bg-accent-blue/15 group-hover:text-accent-blue">
                <Icon className="size-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 text-[13px] font-semibold text-text-primary">
                  {title}
                  <ArrowRight className="size-3 text-text-faint opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100 group-hover:text-accent-blue" />
                </div>
                <div className="mt-1 text-[12px] leading-snug text-text-muted">
                  {description}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="text-xs text-text-faint text-center max-w-[400px]">
        Pick an example above, or type a message below to get started.
      </div>
    </div>
  );
}

function ConnectingState() {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4">
      <div className="spinner" />
      <div className="text-sm text-text-muted">
        Connecting to FuxiClaw…
      </div>
    </div>
  );
}

function DisconnectedState() {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 overflow-y-auto p-8">
      <div className="size-12 rounded-full bg-bg-error flex items-center justify-center">
        <AlertCircle className="size-6 text-accent-red-light" />
      </div>
      <div className="text-base font-semibold text-text-primary">
        Unable to Connect
      </div>
      <div className="text-[13px] text-text-muted text-center max-w-[360px] leading-relaxed">
        Start the backend first, then it will reconnect automatically:
      </div>
      <code className="block px-4 py-2 rounded-md bg-bg-code border border-border-primary text-role-tool text-[13px] font-mono">
        oh web
      </code>
      <div className="text-xs text-text-faint text-center max-w-[400px] leading-normal">
        Or without installing:{" "}
        <code className="rounded bg-bg-code px-1">
          PYTHONPATH=src python -m openharness.web
        </code>
      </div>
    </div>
  );
}
