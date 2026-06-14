"""HTTP + WebSocket server for the Application UI.

Protocol (WebSocket ``/ws``)
----------------------------
JSON messages match ``frontend/application-ui/src/types/protocol.ts``.

    Client → Server    { "type": "submit_line", "line": "hello", "attachments": [...] }
    Client → Server    { "type": "new_session" }
    ...

REST (``/api``)
---------------
    POST /api/upload   multipart: ``file``, ``session_id`` (must match an active WS session)
    GET  /api/uploads/{session_id}/{filename}   serve file from that session's upload dir
    GET  /api/session-export/{session_id}     ZIP: session.json + uploads/ + output/
    GET  /api/sandbox-output/{session_id}/{filename}  files from OpenSandbox mirror (~/.openharness/sandbox-workspace/...)

Uploads are stored under
``<project_session_dir>/uploads/<session_id>/`` so files never mix across sessions.

Configuration: CLI flags and OPENAI_API_KEY, OPENAI_BASE_URL, OPENHARNESS_MODEL, etc.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import mimetypes
import os
import shutil
import tempfile
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

import anyio
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from openharness.auth.manager import AuthManager
from openharness.config import load_settings, save_settings
from openharness.api.client import ApiMessageCompleteEvent, ApiMessageRequest
from openharness.engine.messages import ConversationMessage, TextBlock
from openharness.services import session_storage
from openharness.ui.backend_host import BackendHostConfig
from openharness.ui.protocol import FrontendRequest
from openharness.sandbox.opensandbox_bridge import cleanup_shared_session
from openharness.web.app_tools import (
    APPLICATION_UI_TOOLS,
    ARTIFACT_PREVIEW_MAX_BYTES,
    dispatch_tool,
)
from openharness.web.host import WebBackendHost

logger = logging.getLogger("openharness.web")


# ---------------------------------------------------------------------------
# Upload policy (bioinformatics + general dev files)
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE = 600 * 1024 * 1024  # 600 MB
MAX_INLINE_SIZE = 200_000  # 200 KB — inline read for model context

IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
})

ALLOWED_EXTENSIONS = frozenset({
    ".csv", ".tsv", ".txt", ".md", ".json", ".xml", ".xlsx", ".xls", ".pdf",
    ".zip", ".tar", ".gz", ".py", ".r", ".sh", ".mtx", ".h5", ".h5ad", ".rds",
    ".rdata",
    ".m", ".mlx", ".pdb", ".mol2", ".xyz", ".gro", ".fasta", ".fa", ".fastq",
    ".fq", ".gff", ".gtf", ".bed", ".vcf", ".maf", ".sam", ".bam",
    ".js", ".ts", ".jsx", ".tsx", ".yaml", ".yml", ".toml", ".html", ".htm",
    ".css", ".svg", ".rs", ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".rb",
    ".php", ".sql", ".swift", ".kt", ".scala", ".lua", ".pl", ".ex", ".exs",
    ".log", ".ini", ".cfg", ".conf", ".gmt", ".gff3", ".tab", ".doc", ".docx",
    ".pptx", ".env",
})


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


DEFAULT_SYSTEM_PROMPT = (
    "You are MedClaw, a helpful coding assistant running inside the "
    "Application UI. Respond in Markdown when it improves readability."
)


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    provider: str = "openai-compatible"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    extra_model_params: dict[str, Any] = field(default_factory=dict)


def _app_state(cfg: ServerConfig) -> dict[str, Any]:
    """Matches the `AppStateSnapshot` TypeScript interface."""
    return {
        "model": cfg.model or "",
        "cwd": str(Path.cwd()),
        "provider": cfg.provider,
        "auth_status": "ok" if cfg.api_key else "missing",
        "base_url": cfg.base_url or "",
        "permission_mode": "default",
        "theme": "dark",
        "vim_enabled": False,
        "voice_enabled": False,
        "voice_available": False,
        "voice_reason": "",
        "fast_mode": False,
        "effort": "medium",
        "passes": 1,
        "mcp_connected": False,
        "mcp_failed": False,
        "bridge_sessions": 0,
        "output_style": "default",
        "keybindings": {},
    }


async def _ws_send(websocket: WebSocket, event: dict[str, Any]) -> None:
    await websocket.send_text(json.dumps(event))


# ---------------------------------------------------------------------------
# Session persistence + per-session uploads directory
# ---------------------------------------------------------------------------


def _sessions_dir() -> Path:
    base = Path.home() / ".openharness" / "data" / "web_sessions"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _project_session_dir(cwd: str) -> Path:
    from hashlib import sha1

    path = Path(cwd).resolve()
    digest = sha1(str(path).encode("utf-8")).hexdigest()[:12]
    d = _sessions_dir() / f"{path.name}-{digest}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_upload_dir(cwd: str, session_id: str) -> Path:
    d = _project_session_dir(cwd) / "uploads" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _list_web_sessions(cwd: str, limit: int = 20) -> list[dict[str, Any]]:
    return session_storage.list_session_snapshots(cwd, limit=limit)


def _delete_uploads_for_session(cwd: str, session_id: str) -> None:
    udir = _project_session_dir(cwd) / "uploads" / session_id
    if udir.is_dir():
        shutil.rmtree(udir, ignore_errors=True)


def _delete_output_for_session(cwd: str, session_id: str) -> None:
    odir = _project_session_dir(cwd) / "output" / session_id
    if odir.is_dir():
        shutil.rmtree(odir, ignore_errors=True)


def _delete_web_session(cwd: str, session_id: str) -> bool:
    session_dir = session_storage.get_project_session_dir(cwd)
    path = session_dir / f"session-{session_id}.json"
    deleted = False
    if path.exists():
        path.unlink()
        deleted = True
    latest = session_dir / "latest.json"
    if latest.exists():
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        if data.get("session_id") == session_id:
            latest.unlink(missing_ok=True)
    _delete_uploads_for_session(cwd, session_id)
    _delete_output_for_session(cwd, session_id)
    shutil.rmtree(Path.home() / ".openharness" / "sandbox-workspace" / session_id, ignore_errors=True)
    return deleted


def _rename_web_session(cwd: str, session_id: str, summary: str) -> bool:
    return session_storage.rename_session_snapshot(cwd, session_id, summary)


def _load_web_session(cwd: str, session_id: str) -> dict[str, Any] | None:
    return session_storage.load_session_by_id(cwd, session_id)


def _settings_payload() -> dict[str, Any]:
    settings = load_settings()
    active_profile, _ = settings.resolve_profile()
    statuses = AuthManager(settings).get_profile_statuses()
    profiles = settings.merged_profiles()
    payload_profiles: list[dict[str, Any]] = []
    for name, profile in profiles.items():
        info = statuses.get(name, {})
        payload_profiles.append(
            {
                "name": name,
                "label": info.get("label", profile.label),
                "provider": profile.provider,
                "api_format": profile.api_format,
                "auth_source": profile.auth_source,
                "configured": bool(info.get("configured")),
                "auth_state": str(info.get("auth_state", "missing")),
                "auth_origin": str(info.get("auth_origin", "missing")),
                "active": name == active_profile,
                "base_url": profile.base_url or "",
                "model": info.get("model") or profile.resolved_model,
                "default_model": profile.default_model,
                "allowed_models": list(profile.allowed_models),
            }
        )
    return {
        "active_profile": active_profile,
        "profiles": payload_profiles,
        "current": {
            "model": settings.model,
            "provider": settings.provider,
            "base_url": settings.base_url or "",
            "auth_status": AuthManager(settings).get_profile_statuses()
            .get(active_profile, {})
            .get("auth_state", "missing"),
        },
    }


def _apply_settings_payload(payload: dict[str, Any]) -> dict[str, Any]:
    settings, _profile_name = _settings_from_payload(payload)
    save_settings(settings)

    api_key = str(payload.get("api_key") or "").strip()
    if api_key:
        AuthManager(load_settings()).store_profile_credential(_profile_name, "api_key", api_key)

    saved = settings
    os.environ["OPENHARNESS_MODEL"] = saved.model
    os.environ["OPENHARNESS_PROVIDER"] = saved.provider
    os.environ["OPENHARNESS_API_FORMAT"] = saved.api_format
    if saved.base_url:
        os.environ["OPENHARNESS_BASE_URL"] = saved.base_url
    else:
        os.environ.pop("OPENHARNESS_BASE_URL", None)

    return _settings_payload()


def _settings_from_payload(payload: dict[str, Any]) -> tuple[Any, str]:
    settings = load_settings()
    profiles = settings.merged_profiles()
    profile_name = str(payload.get("active_profile") or settings.active_profile or "").strip()
    if not profile_name:
        profile_name = settings.resolve_profile()[0]
    if profile_name not in profiles:
        raise ValueError(f"Unknown provider profile: {profile_name}")

    profile = profiles[profile_name]
    updates: dict[str, Any] = {}
    if "model" in payload:
        model_name = str(payload.get("model") or "").strip()
        if model_name:
            if (
                profile.allowed_models
                and model_name.lower() != "default"
                and model_name not in profile.allowed_models
            ):
                allowed = ", ".join(profile.allowed_models)
                raise ValueError(f"Model '{model_name}' is not allowed for {profile.label}. Allowed models: {allowed}")
            updates["last_model"] = "" if model_name.lower() == "default" else model_name

    if "base_url" in payload:
        raw_base_url = str(payload.get("base_url") or "").strip()
        updates["base_url"] = raw_base_url or None

    if updates:
        profiles[profile_name] = profile.model_copy(update=updates)

    settings = settings.model_copy(
        update={
            "active_profile": profile_name,
            "profiles": profiles,
        }
    ).materialize_active_profile()
    return settings, profile_name


async def _test_settings_payload(payload: dict[str, Any]) -> dict[str, Any]:
    settings, profile_name = _settings_from_payload(payload)
    _, profile = settings.resolve_profile(profile_name)
    api_key = str(payload.get("api_key") or "").strip()
    if api_key:
        auth_value = api_key
        auth_source = "form"
    else:
        resolved = settings.resolve_auth()
        auth_value = resolved.value
        auth_source = resolved.source

    if profile.api_format in {"openai", "openai_compat"}:
        from openharness.api.openai_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            api_key=auth_value,
            base_url=settings.base_url,
            timeout=min(settings.timeout, 15.0),
        )
    elif profile.api_format == "anthropic":
        from openharness.api.client import AnthropicApiClient

        client = AnthropicApiClient(api_key=auth_value, base_url=settings.base_url)
    else:
        raise ValueError(f"Test connection is not available for api format '{profile.api_format}'.")

    request = ApiMessageRequest(
        model=settings.model,
        messages=[ConversationMessage(role="user", content=[TextBlock(text="Reply with OK.")])],
        max_tokens=8,
    )
    saw_complete = False
    async for event in client.stream_message(request):
        if isinstance(event, ApiMessageCompleteEvent):
            saw_complete = True
            break

    return {
        "ok": saw_complete,
        "profile": profile_name,
        "provider": profile.provider,
        "model": settings.model,
        "base_url": settings.base_url or "",
        "auth_source": auth_source,
        "message": "Connection succeeded." if saw_complete else "Connection completed without a final model response.",
    }


async def _refresh_idle_hosts(hosts: dict[str, WebBackendHost]) -> dict[str, Any]:
    refreshed: list[str] = []
    busy: list[str] = []
    for session_id, host in hosts.items():
        if host.is_busy:
            busy.append(session_id)
            continue
        try:
            if await host.refresh_runtime_settings():
                refreshed.append(session_id)
        except SystemExit as exc:
            logger.warning("Runtime refresh failed for session %s: %s", session_id, exc)
        except Exception:
            logger.exception("Runtime refresh failed for session %s", session_id)
    return {"refreshed_sessions": refreshed, "busy_sessions": busy}


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _zip_tree_under_prefix(
    zf: zipfile.ZipFile,
    disk_root: Path,
    arc_prefix: str,
) -> None:
    """Add all regular files under ``disk_root`` as ``arc_prefix/relative`` paths."""
    if not disk_root.is_dir():
        return
    root = disk_root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        arc = f"{arc_prefix}/{rel.as_posix()}" if arc_prefix else rel.as_posix()
        zf.write(resolved, arc)


def _write_session_export_zip(cwd: str, session_id: str, dest: Path) -> None:
    upload_root = (_project_session_dir(cwd) / "uploads" / session_id).resolve()
    output_root = (_project_session_dir(cwd) / "output" / session_id).resolve()
    sandbox_output_root = _sandbox_output_dir(session_id)
    legacy_output_root = _legacy_runtime_output_dir(cwd, session_id)
    snapshot = session_storage.load_session_by_id(cwd, session_id)

    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if snapshot is not None:
            zf.writestr("session.json", json.dumps(snapshot, indent=2) + "\n")
        else:
            zf.writestr(
                "session.json",
                json.dumps(
                    {
                        "note": "No session snapshot file on disk yet.",
                        "session_id": session_id,
                    },
                    indent=2,
                )
                + "\n",
            )
        _zip_tree_under_prefix(zf, upload_root, "uploads")
        _zip_tree_under_prefix(zf, output_root, "output")
        _zip_tree_under_prefix(zf, legacy_output_root, "output")
        _zip_tree_under_prefix(zf, sandbox_output_root, "sandbox-output")


# ---------------------------------------------------------------------------
# Attachment expansion (user message text for model + transcript)
# ---------------------------------------------------------------------------


def _expand_attachments(
    attachments: list[dict[str, Any]] | None,
    line: str,
    session_id: str,
) -> str:
    """Build the full user message string from optional attachments and line."""
    user_text = (line or "").strip()
    if not attachments:
        return user_text

    parts: list[str] = []
    for att in attachments:
        filename = str(att.get("filename") or "file")
        path_str = str(att.get("path") or "")
        try:
            size = int(att.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        ext = Path(filename).suffix.lower()

        if ext in IMAGE_EXTENSIONS:
            basename = Path(path_str).name if path_str else ""
            api_url = f"/api/uploads/{session_id}/{basename}" if basename else ""
            parts.append(f"[Attached image: {filename} ({size} bytes) at {api_url}]")
        else:
            parts.append(f"[Attached file: {filename} ({size} bytes) at {path_str}]")

    attachment_context = "\n\n".join(parts)
    if user_text:
        return f"{attachment_context}\n\n{user_text}"
    return attachment_context


def _artifact_refs_for_uploads(
    session_id: str,
    attachments: list[Any] | None,
) -> list[dict[str, Any]]:
    """Build ArtifactRef-shaped dicts for the UI artifact panel (path + url)."""
    if not attachments:
        return []
    out: list[dict[str, str]] = []
    for att in attachments:
        if not isinstance(att, dict):
            continue
        filename = str(att.get("filename") or "file").strip() or "file"
        host_path = str(att.get("path") or "").strip()
        if not host_path:
            continue
        basename = Path(host_path).name
        if not basename:
            continue
        mime = str(att.get("mime_type") or "application/octet-stream")
        try:
            size = int(att.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        out.append(
            {
                "path": filename,
                "label": filename,
                "mime_type": mime,
                "url": f"/api/uploads/{session_id}/{basename}",
                "size_bytes": size,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Model call
# ---------------------------------------------------------------------------


def _ensure_kimi_assistant_reasoning(messages: list[dict[str, Any]]) -> None:
    """Moonshot/Kimi with thinking requires ``reasoning_content`` on assistant+tool_calls.

    See ``openharness.api.openai_client._convert_assistant_message`` — same contract.
    """
    for m in messages:
        if m.get("role") != "assistant":
            continue
        if not m.get("tool_calls"):
            continue
        if m.get("reasoning_content") is None:
            m["reasoning_content"] = ""


async def _stream_completion(
    cfg: ServerConfig,
    history: list[dict[str, Any]],
) -> AsyncIterator[str]:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The `openai` package is required. Install openharness[dev] or `pip install openai`."
        ) from exc

    client_kwargs: dict[str, Any] = {}
    if cfg.api_key:
        client_kwargs["api_key"] = cfg.api_key
    if cfg.base_url:
        client_kwargs["base_url"] = cfg.base_url

    client = AsyncOpenAI(**client_kwargs)
    try:
        _ensure_kimi_assistant_reasoning(history)
        stream = await client.chat.completions.create(
            model=cfg.model,
            messages=history,
            stream=True,
            **cfg.extra_model_params,
        )
        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except (IndexError, AttributeError):
                continue
            if delta:
                yield delta
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Model + tools (session output)
# ---------------------------------------------------------------------------


async def _complete_turn_with_tools(
    websocket: WebSocket,
    cfg: ServerConfig,
    history: list[dict[str, Any]],
    session_id: str,
    cwd: str,
    turn: int,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    """Non-streaming tool loop; falls back to plain streaming if the API rejects tools."""
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The `openai` package is required. Install openharness[dev] or `pip install openai`."
        ) from exc

    project_root = _project_session_dir(cwd)
    extra_tools = (
        "\n\n[Tools] You may call write_session_output, run_python_snippet, "
        "sandbox_list_envs, sandbox_exec, sandbox_status, or sandbox_cancel. "
        "Outputs go to this session's output folder; duplicate names get a timestamp suffix. "
        "run_python_snippet uses that folder as cwd; uploaded files are under "
        "OPENHARNESS_SESSION_UPLOAD_DIR. sandbox_exec runs commands in an OpenSandbox "
        "container and mirrors /workspace/output files back to the session artifacts."
    )
    api_msgs: list[dict[str, Any]] = []
    for m in history:
        api_msgs.append(dict(m))
    if api_msgs and api_msgs[0].get("role") == "system":
        c0 = str(api_msgs[0].get("content") or "")
        api_msgs[0] = {**api_msgs[0], "content": c0 + extra_tools}

    client_kwargs: dict[str, Any] = {}
    if cfg.api_key:
        client_kwargs["api_key"] = cfg.api_key
    if cfg.base_url:
        client_kwargs["base_url"] = cfg.base_url

    client = AsyncOpenAI(**client_kwargs)
    try:
        for _ in range(12):
            _ensure_kimi_assistant_reasoning(api_msgs)
            try:
                resp = await client.chat.completions.create(
                    model=cfg.model,
                    messages=api_msgs,
                    tools=APPLICATION_UI_TOOLS,
                    tool_choice="auto",
                    **cfg.extra_model_params,
                )
            except Exception as first_exc:
                logger.info("tool-enabled chat unavailable, using plain streaming: %s", first_exc)
                assembled = ""
                async for delta in _stream_completion(cfg, history):
                    assembled += delta
                    await _ws_send(websocket, {"type": "assistant_delta", "message": delta})
                history.append({"role": "assistant", "content": assembled})
                await _ws_send(websocket, {"type": "assistant_complete", "message": assembled})
                return

            msg = resp.choices[0].message
            tcalls = getattr(msg, "tool_calls", None) or []

            if tcalls:
                asst_payload: dict[str, Any] = {"role": "assistant", "content": msg.content}
                serial_calls: list[dict[str, Any]] = []
                for tc in tcalls:
                    fn = getattr(tc.function, "name", "") or ""
                    arg = getattr(tc.function, "arguments", "") or ""
                    cid = getattr(tc, "id", "") or ""
                    serial_calls.append(
                        {
                            "id": cid,
                            "type": "function",
                            "function": {"name": fn, "arguments": arg},
                        }
                    )
                asst_payload["tool_calls"] = serial_calls
                rc = getattr(msg, "reasoning_content", None)
                asst_payload["reasoning_content"] = rc if isinstance(rc, str) else (rc or "")
                api_msgs.append(asst_payload)
                history.append(dict(asst_payload))

                for tc in tcalls:
                    cid = getattr(tc, "id", "") or ""
                    fn = getattr(tc.function, "name", "") or ""
                    arg = getattr(tc.function, "arguments", "") or ""
                    try:
                        parsed: dict[str, Any] = json.loads(arg) if arg else {}
                    except json.JSONDecodeError:
                        parsed = {"_raw": arg}

                    await _ws_send(
                        websocket,
                        {
                            "type": "tool_started",
                            "tool_name": fn,
                            "item": {
                                "role": "tool",
                                "tool_name": fn,
                                "tool_use_id": cid,
                                "tool_status": "running",
                                "text": f"Running {fn}…",
                                "tool_input": parsed,
                            },
                        },
                    )

                    result_dict, refs, is_err = await dispatch_tool(
                        fn,
                        arg,
                        project_session_dir=project_root,
                        session_id=session_id,
                        turn=turn,
                        attachments=attachments,
                    )

                    tail = (result_dict.get("stderr_tail") or "")[-1200:]
                    completed_item: dict[str, Any] = {
                        "role": "tool",
                        "tool_name": fn,
                        "tool_use_id": cid,
                        "tool_status": "error" if is_err else "success",
                        "is_error": is_err,
                        "text": json.dumps(result_dict, ensure_ascii=False)[:12_000],
                        "tool_input": parsed,
                        "metadata": {
                            "output_files": refs,
                            "exit_code": result_dict.get("exit_code"),
                            "stderr_tail": tail,
                        },
                    }
                    await _ws_send(
                        websocket,
                        {
                            "type": "tool_completed",
                            "tool_name": fn,
                            "item": completed_item,
                        },
                    )

                    content_json = json.dumps(result_dict, ensure_ascii=False)
                    tool_msg = {"role": "tool", "tool_call_id": cid, "content": content_json}
                    api_msgs.append(tool_msg)
                    history.append(dict(tool_msg))

                continue

            text = msg.content or ""
            if not str(text).strip():
                text = "(no response)"
            api_msgs.append({"role": "assistant", "content": text})
            history.append({"role": "assistant", "content": text})
            step = 120
            for i in range(0, len(text), step):
                chunk = text[i : i + step]
                await _ws_send(websocket, {"type": "assistant_delta", "message": chunk})
            await _ws_send(websocket, {"type": "assistant_complete", "message": text})
            return

        await _ws_send(
            websocket,
            {"type": "error", "message": "Too many tool rounds; stopped."},
        )
    except Exception as exc:
        logger.exception("model call failed")
        await _ws_send(websocket, {"type": "error", "message": f"model error: {exc}"})
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# submit_line
# ---------------------------------------------------------------------------


async def _handle_submit_line(
    websocket: WebSocket,
    cfg: ServerConfig,
    history: list[dict[str, Any]],
    session_id: str,
    cwd: str,
    turn: int,
    req: dict[str, Any],
) -> None:
    raw_line = req.get("line")
    line = (raw_line or "").strip() if isinstance(raw_line, str) else ""
    attachments = req.get("attachments")
    if not isinstance(attachments, list):
        attachments = None

    combined = _expand_attachments(attachments, line, session_id)
    if not combined:
        await _ws_send(websocket, {"type": "line_complete"})
        return

    history.append({"role": "user", "content": combined})
    user_item: dict[str, Any] = {"role": "user", "text": combined}
    upload_refs = _artifact_refs_for_uploads(session_id, attachments)
    if upload_refs:
        user_item["artifacts"] = upload_refs
    await _ws_send(
        websocket,
        {
            "type": "transcript_item",
            "item": user_item,
        },
    )

    if not cfg.api_key:
        await _ws_send(
            websocket,
            {
                "type": "error",
                "message": (
                    "No API key configured. Set OPENAI_API_KEY or pass "
                    "--api-key to `oh web`."
                ),
            },
        )
        return

    await _complete_turn_with_tools(
        websocket,
        cfg,
        history,
        session_id,
        cwd,
        turn,
        attachments=attachments,
    )


# ---------------------------------------------------------------------------
# WebSocket connection
# ---------------------------------------------------------------------------


async def _handle_ws_connection(
    websocket: WebSocket,
    cfg: ServerConfig,
    active_upload_sessions: set[str],
) -> None:
    peer = websocket.client
    logger.info("client connected from %s", peer)

    cwd = str(Path.cwd())
    hosts: dict[str, WebBackendHost] = {}
    host_tasks: dict[str, asyncio.Task[int]] = {}
    current_view_session_id = ""
    ws_write_lock = asyncio.Lock()

    async def send_ws(event: dict[str, Any]) -> None:
        async with ws_write_lock:
            await _ws_send(websocket, event)

    async def create_host(
        *,
        session_id: str | None = None,
        snapshot: dict[str, Any] | None = None,
        wait_until_ready: bool = False,
    ) -> str:
        restore_messages = None
        restore_tool_metadata = None
        if snapshot is not None:
            restore_messages = snapshot.get("messages") if isinstance(snapshot.get("messages"), list) else None
            metadata = snapshot.get("tool_metadata")
            restore_tool_metadata = metadata if isinstance(metadata, dict) else None

        sid = session_id or uuid.uuid4().hex[:12]
        host = WebBackendHost(
            BackendHostConfig(
                model=cfg.model,
                base_url=cfg.base_url,
                api_key=cfg.api_key,
                system_prompt=cfg.system_prompt,
                cwd=cwd,
                restore_messages=restore_messages,
                restore_tool_metadata=restore_tool_metadata,
            ),
            websocket,
            session_id_override=sid,
            write_lock=ws_write_lock,
        )
        task = asyncio.create_task(host.run())
        hosts[sid] = host
        host_tasks[sid] = task
        active_upload_sessions.add(sid)

        if wait_until_ready:
            for _ in range(100):
                if host._bundle is not None:
                    host.apply_session_id(sid)
                    break
                if task.done():
                    break
                await asyncio.sleep(0.01)

            if host._bundle is None:
                raise RuntimeError("web runtime failed to start")

        return sid

    async def close_host(session_id: str) -> None:
        host = hosts.pop(session_id, None)
        task = host_tasks.pop(session_id, None)
        active_upload_sessions.discard(session_id)
        if host is not None:
            _save_host_session(host)
            with contextlib.suppress(Exception):
                await host.stop()
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=2)
            except asyncio.TimeoutError:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        with contextlib.suppress(Exception):
            await cleanup_shared_session(session_id)

    try:
        try:
            current_view_session_id = await create_host(wait_until_ready=True)
        except RuntimeError:
            await send_ws({"type": "error", "message": "web runtime failed to start"})
            return

        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                await send_ws({"type": "error", "message": "invalid JSON"})
                continue

            if not isinstance(req, dict):
                continue

            req_type = str(req.get("type") or "")
            if req_type == "new_session":
                current_view_session_id = await create_host()
                await send_ws({"type": "session_created", "session_id": current_view_session_id})
                await send_ws({"type": "session_list", "sessions": _list_web_sessions(cwd)})
                continue

            if req_type == "load_session":
                target_id = str(req.get("session_id") or "").strip()
                if target_id in hosts:
                    current_view_session_id = target_id
                    await send_ws(
                        {
                            "type": "session_loaded",
                            "session_id": target_id,
                            "transcript": [],
                        },
                    )
                    continue
                loaded = _load_web_session(cwd, target_id)
                if loaded is None:
                    await send_ws({"type": "error", "message": f"Session {target_id} not found"})
                    continue
                current_view_session_id = await create_host(session_id=target_id, snapshot=loaded)
                await send_ws(
                    {
                        "type": "session_loaded",
                        "session_id": current_view_session_id,
                        "transcript": _snapshot_messages_to_transcript(loaded),
                    },
                )
                continue

            if req_type == "list_sessions":
                await send_ws({"type": "session_list", "sessions": _list_web_sessions(cwd)})
                continue

            if req_type == "delete_session":
                target_id = str(req.get("session_id") or "").strip()
                if target_id in hosts:
                    await close_host(target_id)
                _delete_web_session(cwd, target_id)
                await send_ws({"type": "session_deleted", "session_id": target_id})
                await send_ws({"type": "session_list", "sessions": _list_web_sessions(cwd)})
                continue

            if req_type == "rename_session":
                target_id = str(req.get("session_id") or "").strip()
                summary = str(req.get("summary") or "").strip()
                if not target_id or not summary:
                    await send_ws({"type": "error", "message": "Missing session id or title"})
                    continue
                if not _rename_web_session(cwd, target_id, summary):
                    await send_ws({"type": "error", "message": f"Session {target_id} not found"})
                    continue
                await send_ws({"type": "session_list", "sessions": _list_web_sessions(cwd)})
                continue

            request = FrontendRequest.model_validate(req)
            target_id = request.session_id or current_view_session_id
            if not target_id:
                target_id = await create_host()
                current_view_session_id = target_id
            target_host = hosts.get(target_id)
            if target_host is None:
                loaded = _load_web_session(cwd, target_id)
                target_id = await create_host(session_id=target_id, snapshot=loaded)
                target_host = hosts[target_id]
            current_view_session_id = target_id
            await target_host.receive(request)
            if req_type == "shutdown":
                logger.info("shutdown requested by client %s", peer)
                return
    except Exception:  # pragma: no cover
        logger.exception("connection handler crashed")
    finally:
        for sid in list(hosts):
            await close_host(sid)
        logger.info("client disconnected: %s", peer)


# ---------------------------------------------------------------------------
# REST: upload + serve
# ---------------------------------------------------------------------------


async def api_upload(request: Request) -> JSONResponse:
    from starlette.datastructures import UploadFile

    active: set[str] = request.app.state.active_upload_sessions
    cwd = str(Path.cwd())

    form = await request.form()
    session_field = form.get("session_id")
    session_id = session_field.strip() if isinstance(session_field, str) else ""
    if not session_id:
        return JSONResponse({"error": "Missing session_id"}, status_code=400)
    if session_id not in active:
        return JSONResponse({"error": "Invalid or inactive session_id"}, status_code=403)

    results: list[dict[str, Any]] = []

    for _, upload in form.multi_items():
        if not isinstance(upload, UploadFile):
            continue
        filename = upload.filename or "unnamed"
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return JSONResponse(
                {"error": f"File type '{ext or '(none)'}' is not allowed"},
                status_code=400,
            )

        content = await upload.read()
        if len(content) > MAX_UPLOAD_SIZE:
            return JSONResponse(
                {
                    "error": (
                        f"File '{filename}' exceeds {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit"
                    ),
                },
                status_code=400,
            )

        upload_dir = _session_upload_dir(cwd, session_id)
        safe_name = f"{uuid.uuid4().hex[:8]}_{Path(filename).name}"
        dest = upload_dir / safe_name
        dest.write_bytes(content)

        mime, _ = mimetypes.guess_type(filename)
        results.append(
            {
                "filename": filename,
                "path": str(dest.resolve()),
                "size": len(content),
                "mime_type": mime or "application/octet-stream",
            }
        )

    if not results:
        return JSONResponse({"error": "No files uploaded"}, status_code=400)

    return JSONResponse(results)


async def api_get_settings(request: Request) -> JSONResponse:
    del request
    return JSONResponse(_settings_payload())


async def api_update_settings(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "Expected JSON object"}, status_code=400)
    try:
        updated = _apply_settings_payload(payload)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("settings update failed")
        return JSONResponse({"error": f"Settings update failed: {exc}"}, status_code=500)
    return JSONResponse(updated)


async def api_test_settings(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"ok": False, "error": "Expected JSON object"}, status_code=400)
    try:
        result = await _test_settings_payload(payload)
        return JSONResponse(result)
    except Exception as exc:
        logger.info("settings test connection failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=200)


async def api_serve_upload(request: Request) -> FileResponse | JSONResponse:
    cwd = str(Path.cwd())
    session_id = request.path_params["session_id"]
    filename = request.path_params["filename"]

    if not session_id or not filename or filename != Path(filename).name:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    if ".." in filename or "/" in filename or "\\" in filename:
        return JSONResponse({"error": "Invalid filename"}, status_code=400)

    base = (_project_session_dir(cwd) / "uploads" / session_id).resolve()
    target = (base / filename).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    if not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    if _is_excel_preview_request(request):
        return _excel_preview_response(target)

    filename = target.name
    download = _is_download_request(request)
    too_large = _artifact_is_too_large_for_preview(target)
    if too_large and not download:
        return _artifact_too_large_response(
            f"/api/uploads/{session_id}/{quote(filename, safe='')}?download=1"
        )

    headers: dict[str, str] = {}
    if download or too_large:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return FileResponse(str(target), headers=headers)


async def api_serve_artifact_file(request: Request) -> FileResponse | JSONResponse:
    """GET /api/artifacts/file?path=... — serve a generated local artifact."""
    raw_path = (request.query_params.get("path") or "").strip()
    if not raw_path:
        return JSONResponse({"error": "Missing path"}, status_code=400)

    cwd = str(Path.cwd())
    target = _resolve_allowed_artifact_file(cwd, raw_path)

    if target is None:
        return JSONResponse({"error": "File not found"}, status_code=404)

    if _is_excel_preview_request(request):
        return _excel_preview_response(target)

    download = _is_download_request(request)
    too_large = _artifact_is_too_large_for_preview(target)
    if too_large and not download:
        return _artifact_too_large_response(
            f"/api/artifacts/file?path={quote(str(target), safe='')}&download=1"
        )

    headers: dict[str, str] = {}
    if download or too_large:
        headers["Content-Disposition"] = f'attachment; filename="{target.name}"'

    return FileResponse(str(target), headers=headers)


async def api_serve_session_output(request: Request) -> FileResponse | JSONResponse:
    """GET /api/session-output/{session_id}/{file_path} — session agent output files."""
    cwd = str(Path.cwd())
    session_id = request.path_params["session_id"]
    file_path = request.path_params["file_path"]

    if not session_id or not file_path:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    if "\\" in file_path:
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    target = _resolve_session_output_file(cwd, session_id, file_path)
    if target is None:
        return JSONResponse({"error": "File not found"}, status_code=404)

    try:
        size = target.stat().st_size
    except OSError:
        return JSONResponse({"error": "File not found"}, status_code=404)

    if _is_excel_preview_request(request):
        return _excel_preview_response(target)

    download = _is_download_request(request)
    too_large = size >= ARTIFACT_PREVIEW_MAX_BYTES
    if too_large and not download:
        return _artifact_too_large_response(
            f"/api/session-output/{session_id}/{quote(file_path, safe='/')}?download=1"
        )

    headers: dict[str, str] = {}
    if download or too_large:
        headers["Content-Disposition"] = f'attachment; filename="{target.name}"'

    return FileResponse(str(target), headers=headers)


async def api_export_artifact_pdf(request: Request) -> JSONResponse:
    """POST /api/artifacts/export-pdf — render an HTML artifact into session output PDF."""
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "Expected JSON object"}, status_code=400)

    active: set[str] = request.app.state.active_upload_sessions
    cwd = str(Path.cwd())
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id or session_id != Path(session_id).name:
        return JSONResponse({"error": "Invalid session_id"}, status_code=400)
    if session_id not in active:
        return JSONResponse({"error": "Invalid or inactive session_id"}, status_code=403)

    source = _resolve_pdf_export_source(
        cwd,
        session_id,
        content_url=str(payload.get("content_url") or ""),
        file_path=str(payload.get("file_path") or ""),
    )
    if source is None:
        return JSONResponse({"error": "HTML artifact not found"}, status_code=404)
    if source.suffix.lower() not in (".html", ".htm"):
        return JSONResponse({"error": "Only HTML artifacts can be exported to PDF"}, status_code=400)

    output_dir = (_project_session_dir(cwd) / "output" / session_id).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = _allocate_unique_output_file(output_dir, f"{source.stem or 'report'}.pdf")

    try:
        await _render_html_file_to_pdf(source, output_path)
    except RuntimeError as exc:
        _unlink_quietly(output_path)
        return JSONResponse({"error": str(exc)}, status_code=501)
    except Exception:
        logger.exception("artifact PDF export failed")
        _unlink_quietly(output_path)
        return JSONResponse({"error": "Failed to export HTML as PDF"}, status_code=500)

    artifact = _session_output_artifact_ref(
        session_id,
        output_path,
        output_path.relative_to(output_dir).as_posix(),
        version_label=f"Exported PDF - {output_path.name}",
    )
    return JSONResponse({"artifact": artifact})


def _is_download_request(request: Request) -> bool:
    return (request.query_params.get("download") or "").lower() in ("1", "true", "yes")


def _is_excel_preview_request(request: Request) -> bool:
    return (request.query_params.get("preview") or "").lower() == "excel"


def _artifact_is_too_large_for_preview(path: Path) -> bool:
    try:
        return path.stat().st_size >= ARTIFACT_PREVIEW_MAX_BYTES
    except OSError:
        return False


def _allowed_artifact_bases(cwd: str) -> list[Path]:
    workspace_dir = Path(cwd).resolve()
    return [
        workspace_dir,
        _project_session_dir(cwd).resolve(),
        session_storage.get_project_session_dir(cwd).resolve(),
        (Path.home() / ".openharness" / "sandbox-workspace").resolve(),
    ]


def _resolve_allowed_artifact_file(cwd: str, raw_path: str) -> Path | None:
    workspace_dir = Path(cwd).resolve()
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = workspace_dir / target
    target = target.resolve(strict=False)

    if not target.exists() or not target.is_file():
        return None

    for base in _allowed_artifact_bases(cwd):
        try:
            target.relative_to(base)
            return target
        except ValueError:
            continue
    return None


def _resolve_pdf_export_source(
    cwd: str,
    session_id: str,
    *,
    content_url: str,
    file_path: str,
) -> Path | None:
    if content_url:
        parsed = urlparse(content_url)
        path = unquote(parsed.path)

        session_prefix = f"/api/session-output/{session_id}/"
        if path.startswith(session_prefix):
            return _resolve_session_output_file(cwd, session_id, path[len(session_prefix):])

        if path == "/api/artifacts/file":
            raw_paths = parse_qs(parsed.query).get("path")
            if raw_paths:
                return _resolve_allowed_artifact_file(cwd, raw_paths[0])

    if file_path:
        if file_path.startswith("/api/"):
            return _resolve_pdf_export_source(
                cwd,
                session_id,
                content_url=file_path,
                file_path="",
            )
        return _resolve_allowed_artifact_file(cwd, file_path)

    return None


def _allocate_unique_output_file(output_dir: Path, filename: str) -> Path:
    base = Path(filename).name.strip() or "artifact.pdf"
    if Path(base).suffix.lower() != ".pdf":
        base = f"{Path(base).stem}.pdf"
    candidate = output_dir / base
    if not candidate.exists():
        return candidate
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    stem = Path(base).stem
    suffix = Path(base).suffix
    for i in range(100):
        suffix_part = f"_{stamp}" if i == 0 else f"_{stamp}_{i}"
        candidate = output_dir / f"{stem}{suffix_part}{suffix}"
        if not candidate.exists():
            return candidate
    return output_dir / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


def _session_output_artifact_ref(
    session_id: str,
    path: Path,
    relative_path: str,
    *,
    version_label: str,
) -> dict[str, Any]:
    mime, _ = mimetypes.guess_type(relative_path)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {
        "name": path.name,
        "path": relative_path,
        "size": size,
        "size_bytes": size,
        "mime_type": mime or "application/octet-stream",
        "url": f"/api/session-output/{session_id}/{quote(relative_path, safe='/')}",
        "version_label": version_label,
    }


async def _render_html_file_to_pdf(source: Path, output_path: Path) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install the Python package and run "
            "`python -m playwright install chromium` to export PDFs."
        ) from exc

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(source.resolve().as_uri(), wait_until="networkidle")
                await page.pdf(
                    path=str(output_path),
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                )
            finally:
                await browser.close()
    except Exception as exc:
        raise RuntimeError(f"Playwright failed to export PDF: {exc}") from exc


def _artifact_too_large_response(download_url: str) -> JSONResponse:
    return JSONResponse(
        {
            "error": "file_too_large_for_preview",
            "max_bytes": ARTIFACT_PREVIEW_MAX_BYTES,
            "download_url": download_url,
        },
        status_code=413,
    )


def _excel_preview_response(path: Path) -> JSONResponse:
    if path.suffix.lower() != ".xlsx":
        return JSONResponse({"error": "excel_preview_unsupported"}, status_code=415)
    if _artifact_is_too_large_for_preview(path):
        return _artifact_too_large_response("")
    try:
        preview = _read_xlsx_preview(path)
    except Exception as exc:
        logger.info("failed to read xlsx preview for %s: %s", path, exc)
        return JSONResponse({"error": "excel_preview_failed"}, status_code=422)
    return JSONResponse(preview)


def _read_xlsx_preview(path: Path, *, max_rows: int = 500, max_cols: int = 80) -> dict[str, Any]:
    ns = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
        "officeRel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with zipfile.ZipFile(path) as zf:
        shared_strings = _xlsx_shared_strings(zf, ns)
        sheet_path, sheet_name = _xlsx_first_sheet(zf, ns)
        root = ET.fromstring(zf.read(sheet_path))
        rows: list[list[str]] = []
        max_seen_col = 0
        total_rows = 0
        for row in root.findall(".//main:sheetData/main:row", ns):
            total_rows += 1
            cells: dict[int, str] = {}
            for cell in row.findall("main:c", ns):
                col_idx = _xlsx_col_index(cell.attrib.get("r", ""))
                if col_idx is None or col_idx >= max_cols:
                    continue
                value = _xlsx_cell_text(cell, shared_strings, ns)
                cells[col_idx] = value
                max_seen_col = max(max_seen_col, col_idx + 1)
            if len(rows) < max_rows:
                row_width = min(max(max_seen_col, len(cells)), max_cols)
                rows.append([cells.get(i, "") for i in range(row_width)])
        width = max((len(row) for row in rows), default=0)
        normalized = [row + [""] * (width - len(row)) for row in rows]
        return {
            "sheet_name": sheet_name,
            "rows": normalized,
            "total_rows": total_rows,
            "total_cols": max_seen_col,
            "truncated": total_rows > max_rows or max_seen_col > max_cols,
            "max_rows": max_rows,
            "max_cols": max_cols,
        }


def _xlsx_shared_strings(zf: zipfile.ZipFile, ns: dict[str, str]) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for item in root.findall("main:si", ns):
        parts = [node.text or "" for node in item.findall(".//main:t", ns)]
        values.append("".join(parts))
    return values


def _xlsx_first_sheet(zf: zipfile.ZipFile, ns: dict[str, str]) -> tuple[str, str]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    sheet = workbook.find(".//main:sheets/main:sheet", ns)
    if sheet is None:
        return "xl/worksheets/sheet1.xml", "Sheet1"
    sheet_name = sheet.attrib.get("name") or "Sheet1"
    rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    if not rel_id:
        return "xl/worksheets/sheet1.xml", sheet_name
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall("rel:Relationship", ns):
        if rel.attrib.get("Id") != rel_id:
            continue
        target = rel.attrib.get("Target") or "worksheets/sheet1.xml"
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        return target, sheet_name
    return "xl/worksheets/sheet1.xml", sheet_name


def _xlsx_col_index(cell_ref: str) -> int | None:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    if not letters:
        return None
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value - 1


def _xlsx_cell_text(cell: ET.Element, shared_strings: list[str], ns: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", ns))
    value = cell.find("main:v", ns)
    raw = value.text if value is not None and value.text is not None else ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw
    return raw


def _sandbox_output_dir(session_id: str) -> Path:
    return (Path.home() / ".openharness" / "sandbox-workspace" / session_id / "output").resolve()


def _legacy_runtime_output_dir(cwd: str, session_id: str) -> Path:
    return (session_storage.get_project_session_dir(cwd) / "output" / session_id).resolve()


def _resolve_session_output_file(cwd: str, session_id: str, relative_path: str) -> Path | None:
    """Resolve output files across current web path, legacy runtime path, and sandbox mirror path.

    This keeps `View` working for artifacts created before the output-path unification,
    where sandbox files could be published under `sessions/.../output` or only mirrored
    under `~/.openharness/sandbox-workspace/<session_id>/output`.
    """
    rel = Path(relative_path)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        return None

    for base in _session_output_roots(cwd, session_id):
        target = (base / rel).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            continue
        if target.is_file():
            return target
    return None


def _session_output_roots(cwd: str, session_id: str) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for root in (
        (_project_session_dir(cwd) / "output" / session_id).resolve(),
        _legacy_runtime_output_dir(cwd, session_id),
        _sandbox_output_dir(session_id),
    ):
        if root in seen:
            continue
        seen.add(root)
        roots.append(root)
    return roots


def _list_session_output_file_refs(cwd: str, session_id: str) -> list[dict[str, Any]]:
    refs: list[tuple[float, dict[str, Any]]] = []
    seen_paths: set[str] = set()
    for root in _session_output_roots(cwd, session_id):
        if not root.is_dir():
            continue
        try:
            children = list(root.rglob("*"))
        except OSError:
            continue
        for child in children:
            if not child.is_file():
                continue
            try:
                rel_path = child.relative_to(root).as_posix()
            except ValueError:
                continue
            if rel_path in seen_paths:
                continue
            seen_paths.add(rel_path)
            try:
                stat = child.stat()
            except OSError:
                continue
            mime, _ = mimetypes.guess_type(rel_path)
            refs.append(
                (
                    stat.st_mtime,
                    {
                        "name": child.name,
                        "path": rel_path,
                        "size": stat.st_size,
                        "size_bytes": stat.st_size,
                        "mime_type": mime or "application/octet-stream",
                        "url": f"/api/session-output/{session_id}/{quote(rel_path, safe='/')}",
                        "version_label": f"Session output - {rel_path}",
                    },
                )
            )
    refs.sort(key=lambda item: (item[0], item[1]["name"]))
    return [item[1] for item in refs]


async def api_list_session_output(request: Request) -> JSONResponse:
    """GET /api/session-output/{session_id} — list current session output artifacts."""
    cwd = str(Path.cwd())
    session_id = request.path_params["session_id"]
    if not session_id:
        return JSONResponse({"error": "Invalid session_id"}, status_code=400)
    return JSONResponse({"output_files": _list_session_output_file_refs(cwd, session_id)})


def _snapshot_messages_to_transcript(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    transcript: list[dict[str, Any]] = []
    raw_messages = snapshot.get("messages", [])
    if not isinstance(raw_messages, list):
        return transcript
    for raw in raw_messages:
        try:
            msg = ConversationMessage.model_validate(raw)
        except Exception:
            continue
        if msg.role == "user":
            text = msg.text.strip()
            if text:
                transcript.append({"role": "user", "text": text})
        elif msg.role == "assistant":
            text = msg.text.strip()
            if text:
                transcript.append({"role": "assistant", "text": text})
    return transcript


def _save_host_session(host: WebBackendHost | None) -> None:
    if host is None:
        return
    try:
        host.save_snapshot()
    except Exception:
        logger.warning("Failed to save host session snapshot", exc_info=True)


async def api_serve_sandbox_output(request: Request) -> FileResponse | JSONResponse:
    """GET /api/sandbox-output/{session_id}/{filename} — OpenSandbox mirrored output files."""
    active: set[str] = request.app.state.active_upload_sessions
    session_id = request.path_params["session_id"]
    filename = request.path_params["filename"]

    if not session_id or not filename or filename != Path(filename).name:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    if ".." in filename or "/" in filename or "\\" in filename:
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    if session_id not in active:
        return JSONResponse({"error": "Invalid or inactive session_id"}, status_code=403)

    base = _sandbox_output_dir(session_id)
    if not base.is_dir():
        return JSONResponse({"error": "File not found"}, status_code=404)
    target = (base / filename).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    if not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    return FileResponse(str(target))


async def api_download_session_export(request: Request) -> FileResponse | JSONResponse:
    """GET /api/session-export/{session_id} — ZIP of transcript snapshot, uploads, output."""
    active: set[str] = request.app.state.active_upload_sessions
    cwd = str(Path.cwd())
    session_id = request.path_params["session_id"]
    if not session_id or session_id != Path(session_id).name:
        return JSONResponse({"error": "Invalid session_id"}, status_code=400)
    if session_id not in active:
        return JSONResponse({"error": "Invalid or inactive session_id"}, status_code=403)

    tmp = tempfile.NamedTemporaryFile(
        prefix="med-claw-export-",
        suffix=".zip",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    tmp.close()
    try:

        def _build() -> None:
            _write_session_export_zip(cwd, session_id, tmp_path)

        await anyio.to_thread.run_sync(_build)
    except Exception:
        logger.exception("session export failed")
        _unlink_quietly(tmp_path)
        return JSONResponse({"error": "Failed to build export archive"}, status_code=500)

    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    filename = f"med-claw-session-{session_id}-{stamp}.zip"
    return FileResponse(
        str(tmp_path),
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(_unlink_quietly, tmp_path),
    )


# ---------------------------------------------------------------------------
# ASGI app factory + entry point
# ---------------------------------------------------------------------------


def create_app(cfg: ServerConfig) -> Starlette:
    active_upload_sessions: set[str] = set()

    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        await _handle_ws_connection(websocket, cfg, active_upload_sessions)

    api_routes = [
        Route("/settings", api_get_settings, methods=["GET"]),
        Route("/settings", api_update_settings, methods=["POST"]),
        Route("/settings/test", api_test_settings, methods=["POST"]),
        Route("/upload", api_upload, methods=["POST"]),
        Route("/uploads/{session_id}/{filename}", api_serve_upload, methods=["GET"]),
        Route("/artifacts/file", api_serve_artifact_file, methods=["GET"]),
        Route("/artifacts/export-pdf", api_export_artifact_pdf, methods=["POST"]),
        Route(
            "/session-output/{session_id}",
            api_list_session_output,
            methods=["GET"],
        ),
        Route(
            "/session-output/{session_id}/{file_path:path}",
            api_serve_session_output,
            methods=["GET"],
        ),
        Route(
            "/session-export/{session_id}",
            api_download_session_export,
            methods=["GET"],
        ),
        Route(
            "/sandbox-output/{session_id}/{filename}",
            api_serve_sandbox_output,
            methods=["GET"],
        ),
    ]

    app = Starlette(
        routes=[
            WebSocketRoute("/ws", ws_endpoint),
            Mount("/api", routes=api_routes),
        ],
    )
    app.state.active_upload_sessions = active_upload_sessions
    return app


def _load_config(
    host: str,
    port: int,
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    provider: Optional[str],
    system_prompt: Optional[str],
) -> ServerConfig:
    if model is None:
        os.environ.pop("OPENHARNESS_MODEL", None)
        os.environ.pop("OPENAI_MODEL", None)
    if base_url is None:
        os.environ.pop("OPENHARNESS_BASE_URL", None)
        os.environ.pop("OPENAI_BASE_URL", None)
    if provider is None:
        os.environ.pop("OPENHARNESS_PROVIDER", None)
        os.environ.pop("OPENHARNESS_API_FORMAT", None)

    return ServerConfig(
        host=host,
        port=port,
        model=model,
        base_url=base_url,
        api_key=api_key,
        provider=(
            provider
            or os.getenv("OPENHARNESS_PROVIDER")
            or "openai-compatible"
        ),
        system_prompt=(
            system_prompt
            or os.getenv("OPENHARNESS_SYSTEM_PROMPT")
            or DEFAULT_SYSTEM_PROMPT
        ),
    )


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> None:
    """Synchronous entry point used by the CLI."""
    import uvicorn

    cfg = _load_config(host, port, model, base_url, api_key, provider, system_prompt)
    app = create_app(cfg)

    logging.basicConfig(
        level=os.getenv("OPENHARNESS_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    current_settings = load_settings()
    active_profile = current_settings.resolve_profile()[0]
    active_status = AuthManager(current_settings).get_profile_statuses().get(active_profile, {})
    if not cfg.api_key and not active_status.get("configured"):
        logger.warning(
            "No API key configured. Set OPENAI_API_KEY or pass --api-key; "
            "the UI will show an error on first message."
        )

    logger.info(
        "MedClaw Application UI server at http://%s:%s/ (WS /ws, API /api/*, model=%s)",
        cfg.host,
        cfg.port,
        cfg.model or current_settings.model,
    )

    try:
        uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
    except KeyboardInterrupt:
        logger.info("shutting down")
