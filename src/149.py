from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any


def _require_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _require_positive(name: str, value: float) -> float:
    value = _require_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


@dataclass(frozen=True)
class FXSnapshot:
    as_of: str
    base_currency: str
    pair: str
    eur_balance: float
    usd_balance: float
    eurusd_rate: float
    previous_eurusd_rate: float | None
    hedge_usd_notional: float
    usd_exposure_gross: float
    usd_exposure_open: float
    hedge_coverage_pct: float
    fx_pnl_eur_rolling: float
    fx_pnl_usd_rolling: float
    auto_hedge_execution: bool
    real_api_enabled: bool


def calculate_rolling_fx_pnl(
    open_usd_exposure: float,
    previous_eurusd_rate: float | None,
    current_eurusd_rate: float,
) -> tuple[float, float]:
    open_usd_exposure = _require_finite("open_usd_exposure", open_usd_exposure)
    current_eurusd_rate = _require_positive("current_eurusd_rate", current_eurusd_rate)

    if previous_eurusd_rate is None:
        return 0.0, 0.0

    previous_eurusd_rate = _require_positive("previous_eurusd_rate", previous_eurusd_rate)
    pnl_eur = open_usd_exposure * ((1.0 / current_eurusd_rate) - (1.0 / previous_eurusd_rate))
    pnl_usd = pnl_eur * current_eurusd_rate
    return pnl_eur, pnl_usd


def compute_fx_snapshot(
    *,
    eur_balance: float,
    usd_balance: float,
    eurusd_rate: float,
    hedge_usd_notional: float = 0.0,
    previous_eurusd_rate: float | None = None,
    as_of: date | None = None,
) -> FXSnapshot:
    eur_balance = _require_finite("eur_balance", eur_balance)
    usd_balance = _require_finite("usd_balance", usd_balance)
    hedge_usd_notional = _require_finite("hedge_usd_notional", hedge_usd_notional)
    eurusd_rate = _require_positive("eurusd_rate", eurusd_rate)

    if previous_eurusd_rate is not None:
        previous_eurusd_rate = _require_positive("previous_eurusd_rate", previous_eurusd_rate)

    gross_usd_exposure = abs(usd_balance)
    open_usd_exposure = usd_balance - hedge_usd_notional
    hedge_coverage_pct = 0.0 if gross_usd_exposure == 0 else (abs(hedge_usd_notional) / gross_usd_exposure) * 100.0
    pnl_eur, pnl_usd = calculate_rolling_fx_pnl(open_usd_exposure, previous_eurusd_rate, eurusd_rate)

    return FXSnapshot(
        as_of=(as_of or date.today()).isoformat(),
        base_currency="EUR",
        pair="EUR/USD",
        eur_balance=eur_balance,
        usd_balance=usd_balance,
        eurusd_rate=eurusd_rate,
        previous_eurusd_rate=previous_eurusd_rate,
        hedge_usd_notional=hedge_usd_notional,
        usd_exposure_gross=usd_balance,
        usd_exposure_open=open_usd_exposure,
        hedge_coverage_pct=hedge_coverage_pct,
        fx_pnl_eur_rolling=pnl_eur,
        fx_pnl_usd_rolling=pnl_usd,
        auto_hedge_execution=False,
        real_api_enabled=os.getenv("DF_149_REAL_API_ENABLED", "").lower() == "true",
    )


def snapshot_to_report(snapshot: FXSnapshot) -> dict[str, Any]:
    report = asdict(snapshot)
    report["mission"] = "DF-149 KPM-Currency-Hedge-Tracker"
    report["status"] = "monitor_only"
    report["policy"] = "NIEMALS Auto-Hedge-Execution."
    return report


def write_report(snapshot: FXSnapshot, reports_dir: str | Path = "reports") -> Path:
    report = snapshot_to_report(snapshot)
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    output_path = reports_path / f"df-149-{snapshot.as_of}.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def main() -> Path:
    snapshot = compute_fx_snapshot(
        eur_balance=0.0,
        usd_balance=0.0,
        eurusd_rate=1.10,
        hedge_usd_notional=0.0,
        previous_eurusd_rate=None,
    )
    return write_report(snapshot)


if __name__ == "__main__":
    path = main()
    print(path)
# [CRUX-MK]
