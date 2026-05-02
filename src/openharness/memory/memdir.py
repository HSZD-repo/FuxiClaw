"""Memory prompt helpers."""

from __future__ import annotations

from pathlib import Path

from openharness.memory.paths import get_memory_entrypoint, get_project_memory_dir
from openharness.memory.scan import scan_memory_files


def load_memory_prompt(
    cwd: str | Path,
    *,
    max_entrypoint_lines: int = 200,
    max_chars: int = 1200,
) -> str | None:
    """Return a compact memory prompt section for the current project."""
    memory_dir = get_project_memory_dir(cwd)
    entrypoint = get_memory_entrypoint(cwd)
    lines = [
        "# Persistent Environment Memory",
        f"- Persistent memory directory: {memory_dir}",
        "- Use the memory tool before environment-sensitive commands to avoid repeating known failures.",
        "- Save only durable environment facts, known failures, working command patterns, bioinformatics tool availability, and stable user workflow preferences.",
        "- Prefer short lessons over logs. Do not save temporary task progress.",
    ]

    if entrypoint.exists():
        content_lines = entrypoint.read_text(encoding="utf-8").splitlines()[:max_entrypoint_lines]
        if content_lines:
            lines.extend(["", "## MEMORY.md", "```md", *content_lines, "```"])
    else:
        lines.extend(
            [
                "",
                "## MEMORY.md",
                "(not created yet)",
            ]
        )

    critical = [header for header in scan_memory_files(cwd, max_files=20) if header.priority == "high"]
    if critical:
        lines.append("")
        lines.append("## Critical Memories")
        for header in critical[:5]:
            summary = header.description or header.body_preview or header.title
            lines.append(f"- {header.title}: {summary[:220]}")

    text = "\n".join(lines)
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n...(memory index truncated; use the memory tool to search details)"
    return text
