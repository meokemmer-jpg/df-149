from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class CashFlow:
    amount: float
    currency: str


@dataclass(frozen=True)
class HedgePosition:
    notional_usd: float


@dataclass(frozen=True)
class TrackerSnapshot:
    eur_amount: float
    usd_amount: float
    spot_eur_usd: float
    hedge_notional_usd: float
    gross_usd_exposure: float
    net_usd_exposure: float
    hedge_coverage_pct: float
    fx_pnl_rolling: float

    def to_dict(self) -> dict:
        return {
            "eur_amount": self.eur_amount,
            "usd_amount": self.usd_amount,
            "spot_eur_usd": self.spot_eur_usd,
            "hedge_notional_usd": self.hedge_notional_usd,
            "gross_usd_exposure": self.gross_usd_exposure,
            "net_usd_exposure": self.net_usd_exposure,
            "hedge_coverage_pct": self.hedge_coverage_pct,
            "fx_pnl_rolling": self.fx_pnl_rolling,
        }


def _round2(value: float) -> float:
    return round(value, 2)


def calculate_currency_hedge_tracker(
    cashflows: Iterable[CashFlow],
    spot_eur_usd: float,
    hedge_positions: Optional[Iterable[HedgePosition]] = None,
    previous_spot_eur_usd: Optional[float] = None,
) -> TrackerSnapshot:
    if spot_eur_usd <= 0:
        raise ValueError("spot_eur_usd must be > 0")
    if previous_spot_eur_usd is not None and previous_spot_eur_usd <= 0:
        raise ValueError("previous_spot_eur_usd must be > 0")

    eur_amount = 0.0
    usd_amount = 0.0

    for flow in cashflows:
        currency = flow.currency.upper()
        if currency == "EUR":
            eur_amount += flow.amount
        elif currency == "USD":
            usd_amount += flow.amount
        else:
            raise ValueError(f"unsupported currency: {flow.currency}")

    hedge_notional_usd = sum(
        position.notional_usd for position in (hedge_positions or [])
    )

    gross_usd_exposure = eur_amount * spot_eur_usd + usd_amount
    net_usd_exposure = gross_usd_exposure - hedge_notional_usd

    if gross_usd_exposure == 0:
        hedge_coverage_pct = 0.0
    else:
        hedge_coverage_pct = max(
            0.0, min(100.0, (hedge_notional_usd / gross_usd_exposure) * 100.0)
        )

    fx_pnl_rolling = 0.0
    if previous_spot_eur_usd is not None:
        fx_pnl_rolling = eur_amount * (spot_eur_usd - previous_spot_eur_usd)

    return TrackerSnapshot(
        eur_amount=_round2(eur_amount),
        usd_amount=_round2(usd_amount),
        spot_eur_usd=_round2(spot_eur_usd),
        hedge_notional_usd=_round2(hedge_notional_usd),
        gross_usd_exposure=_round2(gross_usd_exposure),
        net_usd_exposure=_round2(net_usd_exposure),
        hedge_coverage_pct=_round2(hedge_coverage_pct),
        fx_pnl_rolling=_round2(fx_pnl_rolling),
    )


def build_report(
    cashflows: Iterable[CashFlow],
    spot_eur_usd: float,
    hedge_positions: Optional[Iterable[HedgePosition]] = None,
    previous_spot_eur_usd: Optional[float] = None,
    as_of: Optional[date] = None,
) -> dict:
    snapshot = calculate_currency_hedge_tracker(
        cashflows=cashflows,
        spot_eur_usd=spot_eur_usd,
        hedge_positions=hedge_positions,
        previous_spot_eur_usd=previous_spot_eur_usd,
    )
    report_date = (as_of or date.today()).isoformat()
    return {
        "mission": "DF-149 KPM-Currency-Hedge-Tracker",
        "as_of": report_date,
        "auto_hedge_execution": False,
        "metrics": snapshot.to_dict(),
    }


def write_report(
    cashflows: Iterable[CashFlow],
    spot_eur_usd: float,
    hedge_positions: Optional[Iterable[HedgePosition]] = None,
    previous_spot_eur_usd: Optional[float] = None,
    reports_dir: str = "reports",
    as_of: Optional[date] = None,
) -> Path:
    report = build_report(
        cashflows=cashflows,
        spot_eur_usd=spot_eur_usd,
        hedge_positions=hedge_positions,
        previous_spot_eur_usd=previous_spot_eur_usd,
        as_of=as_of,
    )
    report_date = report["as_of"]
    target_dir = Path(reports_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"df-149-{report_date}.json"
    target_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return target_path
# [CRUX-MK]
