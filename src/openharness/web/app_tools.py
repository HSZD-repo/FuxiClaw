"""Session-scoped output files + whitelisted tools for the Application UI web server.

See docs/application-ui-session-io.md for naming, versioning, and download policy.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("openharness.web.tools")

# Match docs / frontend: artifacts at or above this size are download-only.
ARTIFACT_PREVIEW_MAX_BYTES = 50 * 1024 * 1024

MAX_WRITE_SESSION_BYTES = 8 * 1024 * 1024
MAX_PYTHON_SNIPPET_CHARS = 96_000
PYTHON_RUN_TIMEOUT_SEC = 90


def session_output_dir(project_session_dir: Path, session_id: str) -> Path:
    d = project_session_dir / "output" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def session_upload_dir(project_session_dir: Path, session_id: str) -> Path:
    d = project_session_dir / "uploads" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize_output_basename(name: str) -> str:
    base = Path(name).name.strip()
    if not base or base in (".", ".."):
        return "output.txt"
    cleaned = "".join(c if c.isalnum() or c in "._-" else "_" for c in base)
    return cleaned[:180] or "output.txt"


def allocate_output_path(output_root: Path, logical_filename: str) -> tuple[Path, str]:
    """Pick a path under output_root; if basename exists, append ``_YYYYMMDD-HHMMSS``."""
    base = _sanitize_output_basename(logical_filename)
    stem = Path(base).stem
    suffix = Path(base).suffix
    candidate = output_root / base
    if not candidate.exists():
        return candidate, base
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    alt = f"{stem}_{ts}{suffix}"
    n = 0
    while (output_root / alt).exists():
        n += 1
        alt = f"{stem}_{ts}_{n}{suffix}"
    return output_root / alt, alt


def _output_dir_snapshot(output_root: Path) -> dict[str, int]:
    if not output_root.is_dir():
        return {}
    out: dict[str, int] = {}
    for p in output_root.iterdir():
        if p.is_file():
            try:
                out[p.name] = p.stat().st_size
            except OSError:
                continue
    return out


def _diff_output_files(
    before: dict[str, int], after: dict[str, int], output_root: Path,
) -> list[str]:
    """Names of files that are new or changed size (treat as new version)."""

    def _mtime(name: str) -> float:
        p = output_root / name
        try:
            return p.stat().st_mtime if p.is_file() else 0.0
        except OSError:
            return 0.0

    names: list[str] = []
    for name, sz in after.items():
        if name not in before or before[name] != sz:
            names.append(name)
    names.sort(key=_mtime)
    return names


def build_output_file_refs(
    session_id: str,
    output_root: Path,
    basenames: list[str],
    *,
    turn: int,
    tool_label: str,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for bn in basenames:
        p = output_root / bn
        if not p.is_file():
            continue
        try:
            sz = p.stat().st_size
        except OSError:
            continue
        mime, _ = mimetypes.guess_type(bn)
        try:
            mt = p.stat().st_mtime
        except OSError:
            mt = 0.0
        refs.append(
            (
                mt,
                {
                    "name": bn,
                    "path": bn,
                    "size": sz,
                    "size_bytes": sz,
                    "mime_type": mime or "application/octet-stream",
                    "url": f"/api/session-output/{session_id}/{bn}",
                    "version_label": f"Turn {turn} · {tool_label} · {bn}",
                },
            )
        )
    refs.sort(key=lambda x: x[0])
    return [r[1] for r in refs]


def run_write_session_output(
    output_root: Path,
    session_id: str,
    filename: str,
    content: str,
    *,
    turn: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Write text to session output with timestamp anti-collision."""
    if not isinstance(content, str):
        return {"ok": False, "error": "content must be a string"}, []
    raw = content.encode("utf-8")
    if len(raw) > MAX_WRITE_SESSION_BYTES:
        return {"ok": False, "error": f"content exceeds {MAX_WRITE_SESSION_BYTES // (1024 * 1024)} MB"}, []

    dest, final_name = allocate_output_path(output_root, filename)
    try:
        dest.write_bytes(raw)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}, []

    refs = build_output_file_refs(
        session_id, output_root, [final_name], turn=turn, tool_label="write_session_output"
    )
    return (
        {
            "ok": True,
            "path": str(dest),
            "filename": final_name,
            "bytes_written": len(raw),
        },
        refs,
    )


def run_python_snippet(
    output_root: Path,
    upload_root: Path,
    session_id: str,
    code: str,
    *,
    turn: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """Run ``python -c <code>`` with cwd=output_root. Returns (result, output_files, is_error)."""
    if not isinstance(code, str):
        return {"ok": False, "error": "code must be a string"}, [], True
    if len(code) > MAX_PYTHON_SNIPPET_CHARS:
        return {"ok": False, "error": "code too long"}, [], True

    before = _output_dir_snapshot(output_root)
    env = {
        **dict(os.environ),
        "OPENHARNESS_SESSION_OUTPUT_DIR": str(output_root.resolve()),
        "OPENHARNESS_SESSION_UPLOAD_DIR": str(upload_root.resolve()),
    }
    is_error = False
    stderr_tail = ""
    stdout_tail = ""
    exit_code: int | None = None
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(output_root.resolve()),
            capture_output=True,
            text=True,
            timeout=PYTHON_RUN_TIMEOUT_SEC,
            env=env,
        )
        exit_code = proc.returncode
        stdout_tail = (proc.stdout or "")[-4000:]
        stderr_tail = (proc.stderr or "")[-4000:]
        if proc.returncode != 0:
            is_error = True
    except subprocess.TimeoutExpired:
        is_error = True
        exit_code = -1
        stderr_tail = f"timeout after {PYTHON_RUN_TIMEOUT_SEC}s"
    except Exception as exc:
        is_error = True
        exit_code = -1
        stderr_tail = str(exc)

    after = _output_dir_snapshot(output_root)
    changed = _diff_output_files(before, after, output_root)
    refs = build_output_file_refs(
        session_id, output_root, changed, turn=turn, tool_label="run_python_snippet"
    )

    result = {
        "ok": not is_error,
        "exit_code": exit_code,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "output_filenames": changed,
    }
    return result, refs, is_error


APPLICATION_UI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "write_session_output",
            "description": (
                "Write a text file into this session's output folder. "
                "If the filename already exists, a timestamp suffix is added automatically. "
                "Use for CSV, JSON, reports, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Desired file name (e.g. results.csv); basename only.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full UTF-8 text file body.",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_snippet",
            "description": (
                "Run a short Python snippet with working directory set to this session's output folder. "
                "Uploaded files for this session are readable from the directory in environment variable "
                "OPENHARNESS_SESSION_UPLOAD_DIR. Write new files to the current directory (output folder). "
                "Prefer small scripts; stdout/stderr tails are returned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python source passed to python -c.",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_list_envs",
            "description": (
                "List OpenSandbox environments configured for this project and whether their "
                "Docker images are available locally."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_exec",
            "description": (
                "Run a command inside an OpenSandbox Docker container. "
                "Use sandbox_list_envs first, then choose environment and command. "
                "Uploaded files are available under /workspace/uploads; write outputs to "
                "/workspace/output for host mirroring."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "description": "Environment name from sandbox_list_envs (e.g. bioinformatics).",
                    },
                    "command": {
                        "type": "string",
                        "description": "Shell command to run inside the sandbox.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (foreground mode).",
                    },
                    "background": {
                        "type": "boolean",
                        "description": "If true, run in background and return a task_id.",
                    },
                },
                "required": ["environment", "command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_status",
            "description": "Poll a background task started by sandbox_exec(background=true).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID returned by sandbox_exec.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_cancel",
            "description": "Cancel a running background sandbox task by task_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID returned by sandbox_exec.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
]


_SANDBOX_BRIDGES: dict[str, Any] = {}


def _docker_local_images() -> set[str]:
    try:
        proc = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            return set(proc.stdout.strip().splitlines())
    except Exception:
        pass
    return set()


def _collect_upload_paths(
    upload_root: Path,
    attachments: list[dict[str, Any]] | None,
) -> list[str]:
    # Prefer explicitly attached files for this turn, then include any persisted uploads
    # in this session so follow-up turns can still access earlier files.
    paths: list[str] = []
    if attachments:
        for a in attachments:
            if not isinstance(a, dict):
                continue
            p = str(a.get("path") or "").strip()
            if p:
                paths.append(p)
    if upload_root.is_dir():
        for p in sorted(upload_root.iterdir()):
            if p.is_file():
                paths.append(str(p.resolve()))
    dedup: list[str] = []
    seen: set[str] = set()
    for p in paths:
        if p in seen:
            continue
        dedup.append(p)
        seen.add(p)
    return dedup


def _sandbox_bridge_for_session(session_id: str) -> Any:
    bridge = _SANDBOX_BRIDGES.get(session_id)
    if bridge is not None:
        return bridge
    from openharness.sandbox.opensandbox_bridge import SandboxBridge, sdk_available

    if not sdk_available:
        raise RuntimeError(
            "opensandbox SDK is not installed. Install with: "
            "pip install 'openharness-ai[opensandbox]'"
        )
    bridge = SandboxBridge()
    _SANDBOX_BRIDGES[session_id] = bridge
    return bridge


async def dispatch_tool(
    name: str,
    arguments_json: str,
    *,
    project_session_dir: Path,
    session_id: str,
    turn: int,
    attachments: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """Execute one tool call. Returns (result_dict, output_file_refs, is_error_for_ui)."""
    out_root = session_output_dir(project_session_dir, session_id)
    up_root = session_upload_dir(project_session_dir, session_id)
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid JSON arguments"}, [], True

    if name == "write_session_output":
        fn = str(args.get("filename") or "output.txt")
        content = str(args.get("content") or "")
        res, refs = run_write_session_output(out_root, session_id, fn, content, turn=turn)
        return res, refs, (res.get("ok") is not True)

    if name == "run_python_snippet":
        code = str(args.get("code") or "")
        res, refs, err = run_python_snippet(out_root, up_root, session_id, code, turn=turn)
        return res, refs, err

    if name == "sandbox_list_envs":
        try:
            from openharness.sandbox.opensandbox_envs import load_environments
        except Exception as exc:
            return {"ok": False, "error": str(exc)}, [], True
        envs = load_environments()
        local_images = _docker_local_images()
        result = []
        for env_name, cfg in envs.items():
            result.append(
                {
                    "name": env_name,
                    "description": cfg.description.strip(),
                    "tags": cfg.tags,
                    "image": cfg.image,
                    "resources": cfg.resources.model_dump(),
                    "network_enabled": cfg.network_enabled,
                    "available": cfg.image in local_images,
                }
            )
        return {"ok": True, "environments": result}, [], False

    if name == "sandbox_exec":
        env_name = str(args.get("environment") or "").strip()
        command = str(args.get("command") or "").strip()
        if not env_name or not command:
            return {"ok": False, "error": "environment and command are required"}, [], True
        timeout = int(args.get("timeout") or 300)
        background = bool(args.get("background"))
        try:
            bridge = _sandbox_bridge_for_session(session_id)
            upload_paths = _collect_upload_paths(up_root, attachments)
            injected = await bridge.inject_files(env_name, session_id, upload_paths) if upload_paths else []

            if background:
                task_id = await bridge.exec_background(env_name, session_id, command)
                return {
                    "ok": True,
                    "task_id": task_id,
                    "status": "running",
                    "injected_files": injected,
                }, [], False

            result = await bridge.exec_command(env_name, session_id, command, timeout=timeout)
            refs: list[dict[str, Any]] = []
            for f in result.output_files:
                refs.append(
                    {
                        "name": f.name,
                        "path": f.name,
                        "size": f.size,
                        "size_bytes": f.size,
                        "mime_type": f.mime_type,
                        "url": f"/api/sandbox-output/{session_id}/{f.name}",
                        "version_label": f"Turn {turn} · sandbox_exec · {f.name}",
                    }
                )
            payload = {
                "ok": result.exit_code == 0,
                "exit_code": result.exit_code,
                "output": result.output[-12_000:],
                "environment": env_name,
                "injected_files": injected,
                "output_filenames": [f.name for f in result.output_files],
            }
            return payload, refs, (result.exit_code != 0)
        except Exception as exc:
            return {"ok": False, "error": f"sandbox_exec failed: {exc}"}, [], True

    if name == "sandbox_status":
        task_id = str(args.get("task_id") or "").strip()
        if not task_id:
            return {"ok": False, "error": "task_id is required"}, [], True
        try:
            bridge = _sandbox_bridge_for_session(session_id)
            info = await bridge.poll_task(task_id)
            refs: list[dict[str, Any]] = []
            for f in info.output_files:
                refs.append(
                    {
                        "name": f.name,
                        "path": f.name,
                        "size": f.size,
                        "size_bytes": f.size,
                        "mime_type": f.mime_type,
                        "url": f"/api/sandbox-output/{session_id}/{f.name}",
                        "version_label": f"Turn {turn} · sandbox_status · {f.name}",
                    }
                )
            return {
                "ok": info.status.value != "failed",
                "task_id": info.task_id,
                "status": info.status.value,
                "exit_code": info.exit_code,
                "output": info.output[-12_000:],
            }, refs, (info.status.value == "failed")
        except Exception as exc:
            return {"ok": False, "error": f"sandbox_status failed: {exc}"}, [], True

    if name == "sandbox_cancel":
        task_id = str(args.get("task_id") or "").strip()
        if not task_id:
            return {"ok": False, "error": "task_id is required"}, [], True
        try:
            bridge = _sandbox_bridge_for_session(session_id)
            ok = await bridge.cancel_task(task_id)
            return {"ok": ok, "task_id": task_id}, [], (not ok)
        except Exception as exc:
            return {"ok": False, "error": f"sandbox_cancel failed: {exc}"}, [], True

    return {"ok": False, "error": f"unknown tool {name!r}"}, [], True
