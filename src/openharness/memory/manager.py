"""Helpers for managing memory files."""

from __future__ import annotations

from pathlib import Path
from re import sub
from time import time

from openharness.memory.paths import get_memory_entrypoint, get_project_memory_dir
from openharness.utils.file_lock import exclusive_file_lock
from openharness.utils.fs import atomic_write_text


def _memory_lock_path(cwd: str | Path) -> Path:
    return get_project_memory_dir(cwd) / ".memory.lock"


def list_memory_files(cwd: str | Path) -> list[Path]:
    """List memory markdown files for the project."""
    memory_dir = get_project_memory_dir(cwd)
    return sorted(path for path in memory_dir.glob("*.md"))


def add_memory_entry(cwd: str | Path, title: str, content: str) -> Path:
    """Create a memory file and append it to MEMORY.md."""
    memory_dir = get_project_memory_dir(cwd)
    slug = sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_") or "memory"
    path = memory_dir / f"{slug}.md"
    with exclusive_file_lock(_memory_lock_path(cwd)):
        atomic_write_text(path, content.strip() + "\n")

        entrypoint = get_memory_entrypoint(cwd)
        existing = entrypoint.read_text(encoding="utf-8") if entrypoint.exists() else "# Memory Index\n"
        if path.name not in existing:
            existing = existing.rstrip() + f"\n- [{title}]({path.name})\n"
            atomic_write_text(entrypoint, existing)
    return path


def add_structured_memory_entry(
    cwd: str | Path,
    *,
    title: str,
    content: str,
    memory_type: str = "environment_fact",
    scope: str = "project",
    keywords: list[str] | tuple[str, ...] | None = None,
    priority: str = "normal",
) -> Path:
    """Create a structured memory file with lightweight frontmatter."""
    clean_title = title.strip() or "memory"
    clean_content = content.strip()
    clean_type = memory_type.strip() or "environment_fact"
    clean_scope = scope.strip() or "project"
    clean_priority = priority.strip().lower() or "normal"
    keyword_line = ", ".join(item.strip() for item in (keywords or []) if item.strip())
    frontmatter = [
        "---",
        f"name: {clean_title}",
        f"description: {clean_content.splitlines()[0][:180] if clean_content else clean_title}",
        f"type: {clean_type}",
        f"scope: {clean_scope}",
        f"priority: {clean_priority}",
        f"created_at: {int(time())}",
    ]
    if keyword_line:
        frontmatter.append(f"keywords: {keyword_line}")
    frontmatter.extend(["---", "", clean_content])
    return add_memory_entry(cwd, clean_title, "\n".join(frontmatter))


def remove_memory_entry(cwd: str | Path, name: str) -> bool:
    """Delete a memory file and remove its index entry."""
    memory_dir = get_project_memory_dir(cwd)
    matches = [path for path in memory_dir.glob("*.md") if path.stem == name or path.name == name]
    if not matches:
        return False
    path = matches[0]
    with exclusive_file_lock(_memory_lock_path(cwd)):
        if path.exists():
            path.unlink()

        entrypoint = get_memory_entrypoint(cwd)
        if entrypoint.exists():
            lines = [
                line
                for line in entrypoint.read_text(encoding="utf-8").splitlines()
                if path.name not in line
            ]
            atomic_write_text(entrypoint, "\n".join(lines).rstrip() + "\n")
    return True
