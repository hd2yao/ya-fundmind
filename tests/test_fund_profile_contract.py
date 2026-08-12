from __future__ import annotations

import json

import pytest

from fund_agent.contract import validate_contract_file


def _valid_payload() -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-07-28T00:00:00+00:00",
        "generator": "fund_agent",
        "code": "021511",
        "as_of": "2026-07-28",
        "catalog": {
            "code": "021511",
            "name": "示例混合A",
            "fund_type": "混合型",
        },
        "profile": {
            "code": "021511",
            "name": "示例混合A",
            "fund_company": "示例基金",
        },
        "trading_rule": {
            "code": "021511",
            "purchase_status": "开放申购",
            "redemption_status": "开放赎回",
        },
        "fees": [
            {
                "code": "021511",
                "fee_type": "申购费率（前端）",
                "condition": "小于100万元",
                "original_rate": "1.20%",
                "discounted_rate": "0.12%",
            }
        ],
        "data_status": "updated",
        "profile_status": "updated",
        "trading_status": "updated",
        "fee_status": "updated",
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def _write_payload(tmp_path, payload: dict):
    path = tmp_path / "fund-profile.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_fund_profile_contract_accepts_current_artifact_in_strict_mode(tmp_path):
    result = validate_contract_file(
        _write_payload(tmp_path, _valid_payload()),
        "fund_profile",
        strict=True,
    )

    assert result.ok is True
    assert result.errors == ()


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("code", "21511", "six-digit"),
        ("data_status", "healthy", "status"),
        ("fees", {}, "list"),
        ("not_production_model", False, "not_production_model"),
        ("main_score_changed", True, "main_score_changed"),
        ("main_risk_changed", True, "main_risk_changed"),
    ],
)
def test_fund_profile_contract_rejects_invalid_shape_status_or_boundary(
    tmp_path,
    field,
    value,
    expected_error,
):
    payload = _valid_payload()
    payload[field] = value

    result = validate_contract_file(
        _write_payload(tmp_path, payload),
        "fund_profile",
        strict=True,
    )

    assert result.ok is False
    assert any(expected_error in error for error in result.errors)


def test_fund_profile_contract_rejects_component_code_mismatch(tmp_path):
    payload = _valid_payload()
    payload["fees"][0]["code"] = "510300"

    result = validate_contract_file(
        _write_payload(tmp_path, payload),
        "fund_profile",
        strict=True,
    )

    assert result.ok is False
    assert any("fees[0].code" in error for error in result.errors)


def test_fund_profile_contract_accepts_explicitly_unavailable_components(tmp_path):
    payload = _valid_payload()
    payload.update(
        {
            "catalog": None,
            "profile": None,
            "trading_rule": None,
            "fees": [],
            "data_status": "unavailable",
            "profile_status": "unavailable",
            "trading_status": "unavailable",
            "fee_status": "unavailable",
        }
    )

    result = validate_contract_file(
        _write_payload(tmp_path, payload),
        "fund_profile",
        strict=True,
    )

    assert result.ok is True
