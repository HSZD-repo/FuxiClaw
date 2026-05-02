/**
 * Client-side Application UI settings.
 *
 * Provider, model, and API keys are owned by the Python backend. This file
 * only stores the optional WebSocket URL override used by the UI.
 *
 * Resolution order for the WebSocket URL:
 *   1. UI override saved in localStorage (set via the Settings dialog)
 *   2. `VITE_OH_WS_URL` at build time
 *   3. `<location.protocol === "https:" ? "wss://" : "ws://">/ws`
 *      — the default, served via the Vite dev proxy.
 */

const LS_KEY = "oh-app-ui:ws-url";

export function getDefaultWsUrl(): string {
  const envUrl = (import.meta.env.VITE_OH_WS_URL as string | undefined)?.trim();
  if (envUrl) return envUrl;
  const scheme = typeof location !== "undefined" && location.protocol === "https:" ? "wss" : "ws";
  const host =
    typeof location !== "undefined" && location.host ? location.host : "localhost:5173";
  return `${scheme}://${host}/ws`;
}

export function getStoredWsUrl(): string | null {
  try {
    const value = localStorage.getItem(LS_KEY);
    return value && value.trim().length > 0 ? value.trim() : null;
  } catch {
    return null;
  }
}

export function setStoredWsUrl(value: string | null): void {
  try {
    if (value && value.trim().length > 0) {
      localStorage.setItem(LS_KEY, value.trim());
    } else {
      localStorage.removeItem(LS_KEY);
    }
  } catch {
    /* ignore quota / privacy-mode errors */
  }
}

export function getEffectiveWsUrl(): string {
  return getStoredWsUrl() ?? getDefaultWsUrl();
}
