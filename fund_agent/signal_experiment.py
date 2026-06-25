from __future__ import annotations

import json
from pathlib import Path


DISPLAY_ONLY_FIELDS = ("fund_manager", "fund_company", "inception_date")
REQUIRED_REGRESSION_TESTS = (
    "AKShare/fixture daily reports remain stable.",
    "Missing Tiantian fields never improve score.",
    "Stale Tiantian cache never silently improves score.",
    "Degraded NAV windows are excluded.",
    "Short-sample annualized return is excluded.",
    "Snapshot deltas explain any future score/risk behavior change.",
)


def evaluate_tiantian_signals(report_payload: dict) -> dict:
    eligible: list[dict] = []
    excluded: list[dict] = []
    warnings: list[dict] = []
    for code, summary in (report_payload.get("nav_history_summary") or {}).items():
        for window, item in (summary.get("windows") or {}).items():
            metadata = item.get("metadata") or {}
            grade = item.get("data_quality_grade")
            actual_points = int(metadata.get("actual_points") or item.get("count") or 0)
            required_points = int(metadata.get("required_points") or actual_points or 0)
            if grade == "degraded":
                excluded.append(_excluded(code, f"nav_window.{window}", "degraded_window"))
                continue
            if grade == "warning" and not metadata.get("experiment_allow_partial"):
                excluded.append(_excluded(code, f"nav_window.{window}", "warning_window_requires_explicit_partial_allowance"))
                continue
            if actual_points < required_points:
                excluded.append(_excluded(code, f"nav_window.{window}", "insufficient_sample_points"))
                continue
            for field in ("total_return", "max_drawdown", "volatility"):
                if item.get(field) is None:
                    excluded.append(_excluded(code, f"nav_window.{window}.{field}", "missing_signal_value"))
                else:
                    eligible.append(
                        {
                            "code": code,
                            "signal": f"nav_window.{window}.{field}",
                            "window": window,
                            "value": item.get(field),
                        }
                    )
            if metadata.get("annualized_return_unstable"):
                excluded.append(_excluded(code, f"nav_window.{window}.annualized_return", "annualized_return_unstable"))
            elif item.get("annualized_return") is not None:
                eligible.append(
                    {
                        "code": code,
                        "signal": f"nav_window.{window}.annualized_return",
                        "window": window,
                        "value": item.get("annualized_return"),
                    }
                )
    display_only = []
    for detail in report_payload.get("fund_details") or []:
        code = detail.get("code")
        for field in DISPLAY_ONLY_FIELDS:
            if detail.get(field):
                display_only.append({"code": code, "field": field, "value": detail.get(field)})
        for field in ("scale", "rating"):
            if detail.get(field) is None:
                excluded.append(_excluded(code, f"fund_detail.{field}", "missing_tiantian_field"))
            else:
                warnings.append(
                    {
                        "code": code,
                        "field": field,
                        "message": "Detail field is a future candidate only; not connected to main scoring.",
                    }
                )
    return {
        "eligible_signals": eligible,
        "excluded_signals": excluded,
        "exclusion_reasons": sorted({item["reason"] for item in excluded}),
        "display_only_fields": display_only,
        "required_regression_tests": list(REQUIRED_REGRESSION_TESTS),
        "warnings": warnings,
    }


def evaluate_tiantian_signals_file(input_path: Path | str, output_path: Path | str) -> Path:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    result = evaluate_tiantian_signals(payload)
    resolved_output = Path(output_path)
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return resolved_output


def _excluded(code: str | None, signal: str, reason: str) -> dict:
    return {"code": code, "signal": signal, "reason": reason}
