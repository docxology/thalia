"""Load THALIA-local research overlays without widening generic template schemas.

The sibling template owns the generic ``domain_profile.yaml`` and
``experiment_plan.yaml`` contracts.  THALIA's model-quality, campaign, and
production-readiness protocols are deliberately kept in ``thalia_overlay.yaml``
so the local evidence gates remain expressive without pretending that those
fields are part of the generic template schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
THALIA_OVERLAY_PATH = PROJECT_ROOT / "thalia_overlay.yaml"


def load_thalia_overlay(path: str | Path | None = None) -> dict[str, Any]:
    """Load and minimally validate the THALIA-owned research overlay."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - project dependency is pinned
        raise ValueError("PyYAML is required to load thalia_overlay.yaml") from exc
    source = Path(path) if path is not None else THALIA_OVERLAY_PATH
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"THALIA overlay unreadable: {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("thalia_overlay.yaml must contain a mapping")
    return payload


def load_thalia_overlay_section(section: str, path: str | Path | None = None) -> dict[str, Any]:
    """Return one required mapping from the THALIA-local overlay."""
    payload = load_thalia_overlay(path)
    value = payload.get(section)
    if not isinstance(value, dict):
        raise ValueError(f"thalia_overlay.yaml must contain a {section!r} mapping")
    return value


__all__ = ["PROJECT_ROOT", "THALIA_OVERLAY_PATH", "load_thalia_overlay", "load_thalia_overlay_section"]
