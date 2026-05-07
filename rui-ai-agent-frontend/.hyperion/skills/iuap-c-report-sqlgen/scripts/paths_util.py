"""
Resolve paths for skill assets (under SKILL_DIR) vs writable outputs (under workspace).
Outputs must not default into the skill folder — see config paths.workspace_root.
"""
from __future__ import annotations

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
_ENV_WORKSPACE = "YONBIP_REPORT_SQL_WORKSPACE"


def infer_workspace_root() -> Path:
    """
    Best-effort project root: directory containing .hyperion or .git, else
    parent of the path segment before .../skills/<name>/..., else cwd.
    """
    cwd = Path.cwd().resolve()
    for p in [cwd, *cwd.parents]:
        if (p / ".hyperion").is_dir():
            return p
        if (p / ".git").is_dir():
            return p
    parts = cwd.parts
    if "skills" in parts:
        i = parts.index("skills")
        if i > 0:
            return Path(*parts[:i]).parent
    return cwd


def workspace_base(cfg: dict) -> Path:
    """
    Directory for output_dir / report_deliverable_dir and other generated files.
    Precedence: env YONBIP_REPORT_SQL_WORKSPACE > paths.workspace_root > infer_workspace_root().
    """
    env = os.environ.get(_ENV_WORKSPACE, "").strip()
    if env:
        p = Path(env).expanduser()
        return p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()

    paths = cfg.get("paths") or {}
    raw = paths.get("workspace_root")
    if raw is not None and str(raw).strip():
        p = Path(str(raw).strip()).expanduser()
        return p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()

    return infer_workspace_root()


def resolve_skill_path(relative: str) -> Path:
    """Bundled files shipped with the skill (reference/, scheme json, etc.)."""
    p = Path(relative)
    if p.is_absolute():
        return p.resolve()
    return (SKILL_DIR / p).resolve()


def resolve_workspace_path(relative: str, cfg: dict) -> Path:
    """User-generated outputs: relative to workspace_base(cfg), not the skill directory."""
    p = Path(relative)
    if p.is_absolute():
        return p.resolve()
    return (workspace_base(cfg) / p).resolve()
