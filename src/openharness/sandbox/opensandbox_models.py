"""Pydantic models for OpenSandbox-backed execution (separate from OS-level docker sandbox)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ResourceConfig(BaseModel):
    """CPU and memory limits for a sandbox container."""

    cpu: int = Field(default=4, ge=1, description="Number of CPU cores")
    memory: str = Field(default="8g", description="Memory limit (e.g. '8g', '16g')")


class EnvConfig(BaseModel):
    """Configuration for a single OpenSandbox environment."""

    image: str = Field(description="Docker image name (e.g. 'openharness/sandbox-bioinformatics:latest')")
    description: str = Field(default="", description="Human-readable description")
    dockerfile: str = Field(default="", description="Path to Dockerfile (relative to project root)")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    resources: ResourceConfig = Field(default_factory=ResourceConfig)
    network_enabled: bool = Field(default=False, description="Whether network access is enabled by default")
    builtin: bool = Field(default=True, description="Whether this is a built-in environment")


class OutputFile(BaseModel):
    """A file produced by sandbox execution."""

    path: str = Field(description="Host-side path once mirrored, or container path before download")
    name: str = Field(description="Filename")
    size: int = Field(default=0, description="File size in bytes")
    mime_type: str = Field(default="application/octet-stream")


class TaskStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    output: str = Field(default="", description="Accumulated stdout/stderr so far")
    exit_code: int | None = Field(default=None, description="Exit code when completed")
    output_files: list[OutputFile] = Field(default_factory=list)


class ExecResult(BaseModel):
    output: str = Field(description="Combined stdout + stderr")
    exit_code: int = Field(description="Command exit code")
    output_files: list[OutputFile] = Field(default_factory=list)
