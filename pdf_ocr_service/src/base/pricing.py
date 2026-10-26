from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

DEFAULT_INPUT_COST_USD_PER_1M_TOKENS = 1.50
DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS = 9.00


def load_project_pricing() -> tuple[float, float]:
    config = _load_project_config()
    if config is None:
        return DEFAULT_INPUT_COST_USD_PER_1M_TOKENS, DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS

    input_cost = _as_non_negative_float(
        getattr(config, "ARABIC_PDF_MD_INPUT_TOKEN_PRICE_PER_1M_USD", None),
        DEFAULT_INPUT_COST_USD_PER_1M_TOKENS,
    )
    output_cost = _as_non_negative_float(
        getattr(config, "ARABIC_PDF_MD_OUTPUT_TOKEN_PRICE_PER_1M_USD", None),
        DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS,
    )
    return input_cost, output_cost


def _load_project_config() -> ModuleType | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "config.py"
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("_examy_project_config", candidate)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


def _as_non_negative_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    return parsed
