from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SRC = Path(__file__).resolve().parents[1] / "src" / "149.py"


def _load():
    spec = importlib.util.spec_from_file_location("df_149", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["df_149"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_ledger(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_df149_report_discriminates_adversarial_real_ledger_input(tmp_path):
    mod = _load()
    normal_ledger = _write_ledger(
        tmp_path / "normal-ledger.json",
        {
            "current_eur_usd": 1.20,
            "previous_eur_usd": 1.10,
            "exposures": [
                {"currency": "EUR", "amount": 1000},
                {"currency": "USD", "amount": 100},
            ],
            "hedges": [{"currency_pair": "EUR/USD", "notional_usd": 1200}],
        },
    )
    adverse_ledger = _write_ledger(
        tmp_path / "adverse-ledger.json",
        {
            "current_eur_usd": 1.00,
            "previous_eur_usd": 1.20,
            "exposures": [
                {"currency": "EUR", "amount": 1000},
                {"currency": "USD", "amount": 100},
            ],
            "hedges": [],
        },
    )

    normal_snapshot = mod.snapshot_from_ledger(normal_ledger)
    adverse_snapshot = mod.snapshot_from_ledger(adverse_ledger)

    assert normal_snapshot.fx_pnl_rolling_usd > 0
    assert adverse_snapshot.fx_pnl_rolling_usd < 0
    assert normal_snapshot.hedge_coverage_pct > adverse_snapshot.hedge_coverage_pct
    assert normal_snapshot.risk_state != adverse_snapshot.risk_state
    assert adverse_snapshot.risk_state == "adverse_unhedged"

    normal_report = mod.write_report(normal_snapshot, report_date=date(2026, 7, 9), base_dir=tmp_path / "normal")
    adverse_report = mod.write_report(adverse_snapshot, report_date=date(2026, 7, 9), base_dir=tmp_path / "adverse")

    normal_payload = json.loads(normal_report.read_text(encoding="utf-8"))
    adverse_payload = json.loads(adverse_report.read_text(encoding="utf-8"))

    assert normal_report.exists()
    assert adverse_report.exists()
    assert normal_payload["tracker"] == "df-149"
    assert normal_payload["auto_hedge_execution"] is False
    assert normal_payload["metrics"] != adverse_payload["metrics"]
    assert normal_payload["metrics"]["risk_state"] == "contained"
    assert adverse_payload["metrics"]["risk_state"] == "adverse_unhedged"


def test_df149_rejects_unsupported_real_hedge_pair(tmp_path):
    mod = _load()
    ledger = _write_ledger(
        tmp_path / "bad-hedge.json",
        {
            "current_eur_usd": 1.08,
            "exposures": [{"currency": "EUR", "amount": 250}],
            "hedges": [{"currency_pair": "GBP/USD", "notional_usd": 100}],
        },
    )

    with pytest.raises(ValueError, match="Only EUR/USD"):
        mod.snapshot_from_ledger(ledger)
