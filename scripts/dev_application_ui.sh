#!/usr/bin/env bash
# One-shot dev runner for the Application UI.
#
# Starts:
#   1. The WebSocket backend defined in src/openharness/web (via PYTHONPATH,
#      so it works even if another `oh` is shadowing this repo).
#   2. The Vite dev server in frontend/application-ui.
#
# Usage (from repo root):
#   scripts/dev_application_ui.sh              # backend on :8765, frontend on :5173
#   OH_WEB_PORT=8766 scripts/dev_application_ui.sh
#
# Env vars honoured by the backend (all optional):
#   OPENAI_API_KEY       upstream key (required before you send a message)
#   OPENAI_BASE_URL      OpenAI-compatible base URL, e.g. https://api.moonshot.cn/v1
#   OPENHARNESS_MODEL    model name (fallback: OPENAI_MODEL)
#   OPENHARNESS_PROVIDER label shown in the UI
#
# These can be exported in your shell, or written into a git-ignored `.env`
# at the repo root — the script auto-sources `.env` on startup. See
# `.env.example` for a copy-paste template.
#
# Ctrl-C stops both processes.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log() { printf '\033[1;36m[dev]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[dev]\033[0m %s\n' "$*" >&2; }

# Auto-load .env at repo root, if present. Values already exported in the
# caller's shell take precedence, which keeps one-off overrides like
#   OPENAI_API_KEY=foo scripts/dev_application_ui.sh
# working even when .env has a different value.
if [ -f "$REPO_ROOT/.env" ]; then
  log "Loading env from $REPO_ROOT/.env"
  while IFS= read -r line || [ -n "$line" ]; do
    # skip blanks and comments
    case "$line" in
      ''|\#*) continue ;;
    esac
    # allow "export FOO=bar" style too
    line="${line#export }"
    # only accept KEY=VALUE
    case "$line" in
      *=*) ;;
      *) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    # strip one layer of matching quotes on the value
    case "$val" in
      \"*\") val="${val#\"}"; val="${val%\"}" ;;
      \'*\') val="${val#\'}"; val="${val%\'}" ;;
    esac
    # shell-exported values win
    if [ -z "${!key:-}" ]; then
      export "$key"="$val"
    fi
  done < "$REPO_ROOT/.env"
fi

: "${OH_WEB_HOST:=127.0.0.1}"
: "${OH_WEB_PORT:=8765}"
: "${VITE_PORT:=5173}"

# Pick a Python that has the backend deps. Priority:
#   1. $OH_PYTHON explicit override
#   2. $VIRTUAL_ENV/bin/python  (activated python -m venv)
#   3. $CONDA_PREFIX/bin/python (active conda env — only if no venv on top)
#   4. `python`                 (PATH shim; usually same as #2 or #3)
#   5. `python3`                (system fallback)
has_deps() { "$1" -c 'import websockets, openai, starlette, uvicorn' >/dev/null 2>&1; }

pick_python() {
  local candidates=()
  [ -n "${OH_PYTHON:-}" ] && candidates+=("$OH_PYTHON")
  [ -n "${VIRTUAL_ENV:-}" ] && candidates+=("$VIRTUAL_ENV/bin/python")
  [ -n "${CONDA_PREFIX:-}" ] && candidates+=("$CONDA_PREFIX/bin/python")
  candidates+=("python" "python3")

  for candidate in "${candidates[@]}"; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if has_deps "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if ! OH_PYTHON=$(pick_python); then
  # No interpreter on PATH has the deps. Pick the first available python so
  # the error message points at a real binary the user can paste into.
  for candidate in "${OH_PYTHON:-}" "${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}" python python3; do
    [ -z "$candidate" ] && continue
    if command -v "$candidate" >/dev/null 2>&1; then OH_PYTHON="$candidate"; break; fi
  done
  err "None of the Python interpreters I tried have the backend deps installed."
  err "Install them into the one you want, e.g.:"
  err "    $OH_PYTHON -m pip install 'websockets>=12' 'openai>=1' 'starlette>=0.38' 'uvicorn>=0.30'"
  err "Or point the script at a specific Python:"
  err "    OH_PYTHON=/path/to/python scripts/dev_application_ui.sh"
  exit 1
fi

log "Using python: $OH_PYTHON ($("$OH_PYTHON" --version 2>&1))"

if [ ! -d "frontend/application-ui/node_modules" ]; then
  log "Installing frontend deps (first run)…"
  npm --prefix frontend/application-ui install
fi

BACKEND_PID=""
FRONTEND_PID=""

# Kill a pid tree (parent + descendants). Needed because `npm run dev` is an
# intermediate process — signalling npm does not always cascade to the vite
# node child; we walk the process tree to make sure everything goes down.
kill_tree() {
  local root=$1
  [ -z "$root" ] && return 0
  kill -0 "$root" 2>/dev/null || return 0
  local children
  children=$(pgrep -P "$root" 2>/dev/null || true)
  for c in $children; do kill_tree "$c"; done
  kill -TERM "$root" 2>/dev/null || true
}

cleanup() {
  trap - EXIT INT TERM
  log "Shutting down…"
  kill_tree "$FRONTEND_PID"
  kill_tree "$BACKEND_PID"
  # Give them a moment, then force.
  sleep 0.5
  kill_tree "$FRONTEND_PID"
  kill_tree "$BACKEND_PID"
  sleep 0.3
  [ -n "$FRONTEND_PID" ] && kill -9 "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ]  && kill -9 "$BACKEND_PID"  2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "Starting backend: http://$OH_WEB_HOST:$OH_WEB_PORT/ (WS /ws, API /api/*)"
PYTHONPATH="$REPO_ROOT/src" "$OH_PYTHON" -m openharness.web \
  --host "$OH_WEB_HOST" --port "$OH_WEB_PORT" &
BACKEND_PID=$!

# Let the backend print its startup line before Vite takes over.
sleep 0.5

log "Starting frontend: http://localhost:$VITE_PORT/"
VITE_OH_BACKEND_URL="http://$OH_WEB_HOST:$OH_WEB_PORT" \
  npm --prefix frontend/application-ui run dev -- --port "$VITE_PORT" &
FRONTEND_PID=$!

log "Both processes running. Press Ctrl-C to stop."

# Exit as soon as either child dies so the trap tears down the other.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  err "Backend exited."
fi
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
  err "Frontend exited."
fi
exit 1
