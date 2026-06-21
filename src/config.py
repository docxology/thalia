"""Configuration object shared by the harness and its compilers.

:class:`HarnessConfig` is the tunable parameter vector the MIPRO-style and
GEPA-style compilers search over. It is a frozen dataclass so a candidate config
is hashable and reproducible, and :func:`dataclasses.replace` produces mutated
variants without aliasing.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Callable

RERANK_STRATEGIES = ("rrf", "mmr")


def _parse_bool(value: str) -> bool:
    """Parse a truthy/falsey string to bool (raises ValueError on anything else)."""
    lowered = value.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{value!r} is not a boolean")


# Environment variable -> (field name, parser) for runtime overrides.
_ENV_OVERRIDES: dict[str, tuple[str, Callable[[str], Any]]] = {
    "ATLAS_TOP_K": ("top_k", int),
    "ATLAS_MAX_WINDOWS": ("max_windows", int),
    "ATLAS_MAX_EVIDENCE": ("max_evidence", int),
    "ATLAS_RRF_K": ("rrf_k", int),
    "ATLAS_CONTEXT_BUDGET_TOKENS": ("context_budget_tokens", int),
    "ATLAS_LEXICAL_WEIGHT": ("lexical_weight", float),
    "ATLAS_SEMANTIC_WEIGHT": ("semantic_weight", float),
    "ATLAS_RERANK": ("rerank", str),
    "ATLAS_MMR_LAMBDA": ("mmr_lambda", float),
    "ATLAS_VERIFY": ("verify", _parse_bool),
    "ATLAS_GROUNDING_THRESHOLD": ("grounding_threshold", float),
    "ATLAS_PARTITION_THRESHOLD": ("partition_threshold", int),
    "ATLAS_PARTITION_SIZE": ("partition_size", int),
    "ATLAS_QUERY_EXPANSION": ("query_expansion", _parse_bool),
    "ATLAS_EXPANSION_TERMS": ("expansion_terms", int),
    "ATLAS_RECENCY_WEIGHT": ("recency_weight", float),
    "ATLAS_RECALL_MEMORY": ("recall_memory", _parse_bool),
    "ATLAS_RECALL_LIMIT": ("recall_limit", int),
    "ATLAS_ADAPTIVE_WINDOWS": ("adaptive_windows", _parse_bool),
    "ATLAS_ADAPTIVE_WINDOW_RATIO": ("adaptive_window_ratio", int),
}


@dataclass(frozen=True)
class HarnessConfig:
    """Tunable parameters for the full ATLAS pipeline.

    Attributes:
        max_windows: Inspector cap on emitted evidence windows.
        top_k: Retriever cap on ranked evidence returned.
        rrf_k: RRF damping constant.
        lexical_weight: Lexical lane weight (None -> per-category default).
        semantic_weight: Semantic lane weight (None -> per-category default).
        context_budget_tokens: Inline delivery token budget.
        max_evidence: Reasoner cap on evidence windows considered.
        rerank: Retriever re-ranking strategy after fusion: "rrf" or "mmr".
        mmr_lambda: MMR relevance/diversity tradeoff in [0, 1] (1 = pure relevance).
        verify: Run a Reasoner grounding-verification pass (re-answer if weak).
        grounding_threshold: Minimum answer-in-evidence support before re-answering.
        partition_threshold: Inspector line count above which recursive partitioning runs.
        partition_size: Block size (in records) for recursive partitioning.
        query_expansion: Pseudo-relevance-feedback query expansion in the Retriever.
        expansion_terms: Number of feedback terms to append when expanding.
        recency_weight: Recency bonus in [0, 1] favouring later session turns.
        recall_memory: Consult the episodic store + MEMORY.md for evidence at inference.
        recall_limit: Maximum recalled evidence windows.
        adaptive_windows: Inspector scales max_windows with input size instead of capping flat.
        adaptive_window_ratio: Windows-per-record divisor when adaptive_windows is on.
    """

    max_windows: int = 15
    top_k: int = 8
    rrf_k: int = 60
    lexical_weight: float | None = None
    semantic_weight: float | None = None
    context_budget_tokens: int = 2048
    max_evidence: int = 5
    rerank: str = "rrf"
    mmr_lambda: float = 0.7
    verify: bool = False
    grounding_threshold: float = 0.3
    partition_threshold: int = 40
    partition_size: int = 10
    query_expansion: bool = False
    expansion_terms: int = 5
    recency_weight: float = 0.0
    recall_memory: bool = False
    recall_limit: int = 3
    adaptive_windows: bool = False
    adaptive_window_ratio: int = 5

    def __post_init__(self) -> None:
        if self.adaptive_window_ratio <= 0:
            raise ValueError("adaptive_window_ratio must be positive")
        if self.max_windows <= 0:
            raise ValueError("max_windows must be positive")
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if self.rrf_k < 0:
            raise ValueError("rrf_k must be non-negative")
        if self.max_evidence <= 0:
            raise ValueError("max_evidence must be positive")
        if self.context_budget_tokens <= 0:
            raise ValueError("context_budget_tokens must be positive")
        lw, sw = self.lexical_weight, self.semantic_weight
        if (lw is None) ^ (sw is None):
            raise ValueError("lexical_weight and semantic_weight must both be set or both None")
        if lw is not None and (lw < 0 or (sw is not None and sw < 0)):
            raise ValueError("lane weights must be non-negative")
        if self.rerank not in RERANK_STRATEGIES:
            raise ValueError(f"rerank must be one of {RERANK_STRATEGIES}, got {self.rerank!r}")
        if not 0.0 <= self.mmr_lambda <= 1.0:
            raise ValueError("mmr_lambda must be in [0, 1]")
        if not 0.0 <= self.grounding_threshold <= 1.0:
            raise ValueError("grounding_threshold must be in [0, 1]")
        if self.partition_threshold <= 0:
            raise ValueError("partition_threshold must be positive")
        if self.partition_size <= 0:
            raise ValueError("partition_size must be positive")
        if self.expansion_terms <= 0:
            raise ValueError("expansion_terms must be positive")
        if not 0.0 <= self.recency_weight <= 1.0:
            raise ValueError("recency_weight must be in [0, 1]")
        if self.recall_limit <= 0:
            raise ValueError("recall_limit must be positive")

    def with_(self, **changes: Any) -> "HarnessConfig":
        """Return a copy with the given fields replaced (validated)."""
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict view of the configuration (YAML/JSON-friendly)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HarnessConfig":
        """Build a config from a dict, ignoring unrecognised keys (validated)."""
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def default_config() -> HarnessConfig:
    """Return the default harness configuration."""
    return HarnessConfig()


def apply_env_overrides(config: HarnessConfig) -> HarnessConfig:
    """Return ``config`` with any ``ATLAS_*`` environment overrides applied.

    Recognised variables map to config fields (see ``_ENV_OVERRIDES``); values are
    parsed to the field type. Weight overrides still obey the both-or-neither
    invariant — setting only one weight env var against an unset pair raises.

    Raises:
        ValueError: If an override value cannot be parsed, or violates validation.
    """
    changes: dict[str, Any] = {}
    for env_name, (field_name, parser) in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_name)
        if raw is None:
            continue
        try:
            changes[field_name] = parser(raw)
        except ValueError as exc:
            raise ValueError(f"{env_name}={raw!r} is not a valid {parser.__name__}") from exc
    return config.with_(**changes) if changes else config


def load_config(path: str | Path, apply_env: bool = True) -> HarnessConfig:
    """Load a :class:`HarnessConfig` from a YAML file, then apply env overrides.

    The YAML may be a flat mapping of fields, or carry the fields under a top-level
    ``harness:`` key (so a manuscript ``config.yaml`` can double as a source).

    Args:
        path: Path to the YAML config file.
        apply_env: Apply ``ATLAS_*`` environment overrides after loading (default True).

    Returns:
        A validated :class:`HarnessConfig`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file does not contain a mapping.
    """
    import yaml

    text = Path(path).read_text()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"config file {path} must contain a mapping, got {type(data).__name__}")
    if "harness" in data and isinstance(data["harness"], dict):
        data = data["harness"]
    config = HarnessConfig.from_dict(data)
    return apply_env_overrides(config) if apply_env else config


def save_config(config: HarnessConfig, path: str | Path) -> Path:
    """Write ``config`` to ``path`` as YAML and return the path."""
    import yaml

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(config.to_dict(), sort_keys=True))
    return out


__all__ = [
    "HarnessConfig",
    "RERANK_STRATEGIES",
    "default_config",
    "apply_env_overrides",
    "load_config",
    "save_config",
]
