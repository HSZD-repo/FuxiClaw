"""List OpenSandbox environments from sandboxes/envs.yaml."""

from __future__ import annotations

import json
import subprocess

from pydantic import BaseModel

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class SandboxListEnvsInput(BaseModel):
    pass


class SandboxListEnvsTool(BaseTool):
    name = "sandbox_list_envs"
    description = (
        "List OpenSandbox environments (Docker images) from sandboxes/envs.yaml. "
        "Use before sandbox_exec to choose the environment name."
    )
    input_model = SandboxListEnvsInput

    def is_read_only(self, arguments: BaseModel) -> bool:
        return True

    async def execute(self, arguments: SandboxListEnvsInput, context: ToolExecutionContext) -> ToolResult:
        from openharness.sandbox.opensandbox_envs import load_environments

        envs = load_environments()
        if not envs:
            return ToolResult(output="No sandbox environments configured (see sandboxes/envs.yaml).")

        local_images = _get_local_images()

        result = []
        for name, cfg in envs.items():
            available = cfg.image in local_images
            result.append({
                "name": name,
                "description": cfg.description.strip(),
                "tags": cfg.tags,
                "image": cfg.image,
                "resources": cfg.resources.model_dump(),
                "network_enabled": cfg.network_enabled,
                "available": available,
            })

        return ToolResult(output=json.dumps(result, indent=2, ensure_ascii=False))


def _get_local_images() -> set[str]:
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
