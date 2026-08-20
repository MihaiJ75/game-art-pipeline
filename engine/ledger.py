"""Prompt Fingerprint Ledger & Staleness Tracking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def prompt_hash(prompt_text: str) -> str:
    """Return 12-char SHA-256 fingerprint of prompt text."""
    normalized = " ".join(prompt_text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def load_ledger(ledger_path: Path) -> dict[str, Any]:
    if not ledger_path.exists():
        return {}
    try:
        return json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def record_ledger(ledger_path: Path, records: dict[str, dict[str, Any]]) -> None:
    ledger = load_ledger(ledger_path)
    ledger.update(records)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
