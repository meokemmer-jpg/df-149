from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class ExposureLot:
    currency: str
    amount: float


@dataclass(frozen=True)
class HedgePosition:
    currency_pair: str
    notional_usd: float


@dataclass(frozen=True)
class FxSnapshot:
    eur_usd: float
    exposed_eur: float
    exposed_usd: float
    gross_usd_exposure: float
    hedge_notional_usd: float
    hedge_coverage_pct: float
    fx_pnl_rolling_usd: float


def _sum_amounts(items: Iterable[Mapping[str, float]], currency: str) -> float:
    total = 0.0
    for item in items:
        if item["currency"].upper() == currency.upper():
            total += float(item["amount"])
    return total


def _sum_hedges_usd(hedges: Iterable[Mapping[str, float]]) -> float:
    total = 0.0
    for hedge in hedges:
        if hedge["currency_pair"].upper() != "EUR/USD":
            raise ValueError("Only EUR/USD hedges are supported")
        total += abs(float(hedge["notional_usd"]))
    return total


def calculate_fx_snapshot(
    exposures: Iterable[Mapping[str, float]],
    hedges: Iterable[Mapping[str, float]],
    current_eur_usd: float,
    previous_eur_usd: Optional[float] = None,
) -> FxSnapshot:
    if current_eur_usd <= 0:
        raise ValueError("current_eur_usd must be positive")
    if previous_eur_usd is not None and previous_eur_usd <= 0:
        raise ValueError("previous_eur_usd must be positive")

    exposed_eur = _sum_amounts(exposures, "EUR")
    exposed_usd = _sum_amounts(exposures, "USD")
    gross_usd_exposure = abs(exposed_eur * current_eur_usd)
    hedge_notional_usd = _sum_hedges_usd(hedges)

    hedge_coverage_pct = 0.0
    if gross_usd_exposure > 0:
        hedge_coverage_pct = min(hedge_notional_usd / gross_usd_exposure, 1.0) * 100.0

    fx_pnl_rolling_usd = 0.0
    if previous_eur_usd is not None:
        fx_pnl_rolling_usd = exposed_eur * (current_eur_usd - previous_eur_usd)

    return FxSnapshot(
        eur_usd=float(current_eur_usd),
        exposed_eur=float(exposed_eur),
        exposed_usd=float(exposed_usd),
        gross_usd_exposure=float(gross_usd_exposure),
        hedge_notional_usd=float(hedge_notional_usd),
        hedge_coverage_pct=float(hedge_coverage_pct),
        fx_pnl_rolling_usd=float(fx_pnl_rolling_usd),
    )


def write_report(snapshot: FxSnapshot, report_date: Optional[date] = None, base_dir: str = ".") -> Path:
    report_date = report_date or date.today()
    reports_dir = Path(base_dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    target = reports_dir / f"df-149-{report_date.isoformat()}.json"
    payload = {
        "tracker": "df-149",
        "date": report_date.isoformat(),
        "auto_hedge_execution": False,
        "metrics": asdict(snapshot),
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target
# [CRUX-MK]
