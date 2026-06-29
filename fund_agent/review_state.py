from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_REVIEW_STATUSES = {
    "open",
    "approved_for_more_experiment",
    "rejected",
    "needs_more_data",
    "approved_for_main_candidate",
}


def update_review_state(
    *,
    state_path: Path | str,
    review_id: str,
    status: str,
    note: str = "",
    reviewer: str = "",
    signal_id: str | None = None,
    evidence_refs: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    normalized_status = _normalize_status(status)
    path = Path(state_path)
    payload = _load_state(path)
    items = payload.setdefault("items", [])
    existing = next((item for item in items if item.get("review_id") == review_id), None)
    if existing is None:
        existing = {
            "review_id": review_id,
            "signal_id": signal_id or review_id,
            "status": "open",
            "reviewer": "",
            "decision": "",
            "note": "",
            "updated_at": "",
            "evidence_refs": [],
        }
        items.append(existing)
    if signal_id:
        existing["signal_id"] = signal_id
    existing["status"] = normalized_status
    existing["decision"] = normalized_status
    existing["note"] = note
    existing["reviewer"] = reviewer
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    if evidence_refs is not None:
        existing["evidence_refs"] = list(evidence_refs)
    _write_state(path, payload)
    return dict(existing)


def list_review_state(state_path: Path | str) -> list[dict[str, Any]]:
    return list(_load_state(Path(state_path)).get("items") or [])


def summarize_review_state(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = Counter(str(item.get("status", "open")) for item in items)
    approved_count = by_status.get("approved_for_more_experiment", 0) + by_status.get(
        "approved_for_main_candidate", 0
    )
    rejected_count = by_status.get("rejected", 0)
    needs_more = by_status.get("needs_more_data", 0)
    unresolved = sum(
        count
        for status, count in by_status.items()
        if status in {"open", "needs_more_data", "approved_for_more_experiment"}
    )
    notes = sorted(
        str(item.get("signal_id"))
        for item in items
        if item.get("signal_id") and item.get("note")
    )
    return {
        "total_review_items": len(items),
        "by_status": dict(by_status),
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "needs_more_data_count": needs_more,
        "unresolved_count": unresolved,
        "signals_with_human_notes": notes,
    }


def write_review_state_summary(state_path: Path | str, output_path: Path | str) -> Path:
    summary = summarize_review_state(list_review_state(state_path))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return output


def _normalize_status(status: str) -> str:
    normalized = str(status).strip()
    if normalized not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")
    return normalized


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"items": payload}
    if not isinstance(payload, dict):
        return {"items": []}
    payload.setdefault("items", [])
    return payload


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
