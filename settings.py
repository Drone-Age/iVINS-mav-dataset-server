"""Runtime settings with one-major-release compatibility aliases."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

_WARNED: set[str] = set()


def value(name: str, default: object | None = None) -> object | None:
    """Return DSM_* first, then deprecated IVINS_*, then the default."""
    canonical = f"DSM_{name}"
    legacy = f"IVINS_{name}"
    if canonical in os.environ:
        return os.environ[canonical]
    if legacy in os.environ:
        if legacy not in _WARNED:
            warnings.warn(
                f"{legacy} is deprecated; use {canonical}. The alias is removed in Backend 5.0.",
                FutureWarning,
                stacklevel=2,
            )
            _WARNED.add(legacy)
        return os.environ[legacy]
    return default


def path(name: str, default: str | Path) -> Path:
    return Path(str(value(name, default))).resolve()


def integer(name: str, default: int) -> int:
    try:
        result = int(str(value(name, default)))
    except (TypeError, ValueError):
        return default
    return max(0, result)
