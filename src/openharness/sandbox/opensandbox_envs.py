"""Load OpenSandbox image definitions from packaged defaults plus optional overlays."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from openharness.sandbox.opensandbox_models import EnvConfig

logger = logging.getLogger(__name__)

_BUILTIN_PATH = Path(__file__).resolve().parent / "default_envs.yaml"
_USER_ENVS_PATH = Path.home() / ".openharness" / "sandboxes" / "envs.yaml"


def _load_yaml(path: Path) -> dict[str, EnvConfig]:
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        logger.warning("Failed to parse %s", path, exc_info=True)
        return {}

    raw_envs = data.get("environments", {})
    result: dict[str, EnvConfig] = {}
    for name, cfg in raw_envs.items():
        try:
            result[name] = EnvConfig(**cfg)
        except Exception:
            logger.warning("Skipping invalid environment %r in %s", name, path, exc_info=True)
    return result


def load_environments() -> dict[str, EnvConfig]:
    """Builtin defaults, optional project cwd overlay, then user overlay."""
    envs = _load_yaml(_BUILTIN_PATH)
    for cfg in envs.values():
        cfg.builtin = True

    cwd_yaml = Path.cwd() / "sandboxes" / "envs.yaml"
    if cwd_yaml.is_file():
        proj = _load_yaml(cwd_yaml.resolve())
        for name, cfg in proj.items():
            cfg.builtin = True
            envs[name] = cfg

    user_envs = _load_yaml(_USER_ENVS_PATH)
    for name, cfg in user_envs.items():
        cfg.builtin = False
        envs[name] = cfg

    return envs


def get_environment(name: str) -> EnvConfig | None:
    return load_environments().get(name)
