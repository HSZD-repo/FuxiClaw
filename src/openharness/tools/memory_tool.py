"""Tool for persistent project environment memory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from openharness.memory import (
    add_structured_memory_entry,
    find_relevant_memories,
    get_project_memory_dir,
    list_memory_files,
    remove_memory_entry,
    scan_memory_files,
)
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


MemoryAction = Literal["add", "search", "list", "remove"]
MemoryType = Literal[
    "environment_fact",
    "known_failure",
    "working_command",
    "bio_tool",
    "user_preference",
    "workflow",
]


class MemoryToolInput(BaseModel):
    """Arguments for persistent memory access."""

    action: MemoryAction = Field(description="Memory action: add, search, list, or remove.")
    query: str | None = Field(default=None, description="Search query for action=search.")
    title: str | None = Field(default=None, description="Short title for action=add.")
    content: str | None = Field(default=None, description="Compact durable lesson or fact for action=add.")
    memory_type: MemoryType = Field(
        default="environment_fact",
        description=(
            "Memory category. Use known_failure for stable failed commands, working_command for "
            "verified command patterns, bio_tool for package/tool availability, environment_fact "
            "for Docker/OpenSandbox/path/version facts, workflow for project conventions, and "
            "user_preference for stable user preferences."
        ),
    )
    scope: str = Field(default="project", description="Scope such as project, docker, opensandbox, host, or bioinformatics.")
    keywords: list[str] = Field(default_factory=list, description="Search keywords that should recall this memory.")
    priority: Literal["normal", "high"] = Field(
        default="normal",
        description="Use high only for critical facts that should be shown in the compact memory index.",
    )
    name: str | None = Field(default=None, description="File name or stem for action=remove.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum results for search/list.")


class MemoryTool(BaseTool):
    """Read and write persistent project environment memory."""

    name = "memory"
    description = (
        "Search or save persistent project environment memory that survives future sessions. "
        "Use this before running environment-sensitive commands to avoid repeating known failures. "
        "Save only durable facts: known failed commands and their lessons, verified working command "
        "patterns, Docker/OpenSandbox details, bioinformatics tool availability, stable workflow "
        "conventions, and durable user preferences. Do not save temporary task progress, raw logs, "
        "large outputs, secrets, or facts that are easy to rediscover. Prefer short lessons over "
        "complete stderr. If a command fails because of this user's stable environment, add a "
        "known_failure memory with the failed command pattern and the working alternative."
    )
    input_model = MemoryToolInput

    def is_read_only(self, arguments: BaseModel) -> bool:
        return isinstance(arguments, MemoryToolInput) and arguments.action in {"search", "list"}

    async def execute(self, arguments: MemoryToolInput, context: ToolExecutionContext) -> ToolResult:
        if arguments.action == "add":
            if not arguments.title or not arguments.content:
                return ToolResult(output="title and content are required for action=add", is_error=True)
            path = add_structured_memory_entry(
                context.cwd,
                title=arguments.title,
                content=arguments.content,
                memory_type=arguments.memory_type,
                scope=arguments.scope,
                keywords=arguments.keywords,
                priority=arguments.priority,
            )
            return ToolResult(output=json.dumps({"saved": str(path), "name": path.name}, indent=2))

        if arguments.action == "search":
            query = (arguments.query or "").strip()
            if not query:
                return ToolResult(output="query is required for action=search", is_error=True)
            results = []
            for header in find_relevant_memories(query, context.cwd, max_results=arguments.limit):
                content = header.path.read_text(encoding="utf-8", errors="replace").strip()
                results.append(
                    {
                        "name": header.path.name,
                        "title": header.title,
                        "type": header.memory_type,
                        "priority": header.priority,
                        "description": header.description,
                        "keywords": list(header.keywords),
                        "content": content[:2000],
                    }
                )
            return ToolResult(output=json.dumps({"results": results}, indent=2, ensure_ascii=False))

        if arguments.action == "list":
            headers = scan_memory_files(context.cwd, max_files=arguments.limit)
            files = [
                {
                    "name": header.path.name,
                    "title": header.title,
                    "type": header.memory_type,
                    "priority": header.priority,
                    "description": header.description,
                    "keywords": list(header.keywords),
                }
                for header in headers
            ]
            if not files:
                files = [{"name": path.name} for path in list_memory_files(context.cwd)[: arguments.limit]]
            return ToolResult(
                output=json.dumps(
                    {"memory_dir": str(get_project_memory_dir(context.cwd)), "files": files},
                    indent=2,
                    ensure_ascii=False,
                )
            )

        if arguments.action == "remove":
            target = (arguments.name or "").strip()
            if not target:
                return ToolResult(output="name is required for action=remove", is_error=True)
            ok = remove_memory_entry(context.cwd, Path(target).name)
            return ToolResult(output=json.dumps({"removed": ok, "name": target}, indent=2), is_error=not ok)

        return ToolResult(output=f"Unknown memory action: {arguments.action}", is_error=True)
