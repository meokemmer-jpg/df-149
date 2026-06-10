from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any, Dict


REAL_API_ENV = "DF_149_REAL_API_ENABLED"


@dataclass(frozen=True)
class HedgeReport:
    as_of: str
    base_ccy: str
    quote_ccy: str
    eurusd_previous: float
    eurusd_current: float
    usd_assets: float
    usd_liabilities: float
    net_usd_exposure: float
    hedge_usd_notional: float
    unhedged_usd_exposure: float
    hedge_coverage_pct: float
    exposure_pnl_eur: float
    hedge_pnl_eur: float
    total_fx_pnl_eur: float
    rolling_fx_pnl_eur: float
    auto_hedge_execution: bool
    real_api_enabled: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _require_positive_rate(rate: float, name: str) -> None:
    if rate <= 0:
        raise ValueError(f"{name} must be > 0")


def net_usd_exposure(usd_assets: float, usd_liabilities: float) -> float:
    return float(usd_assets) - float(usd_liabilities)


def hedge_coverage_pct(exposure_usd: float, hedge_usd_notional: float) -> float:
    if exposure_usd == 0:
        return 0.0 if hedge_usd_notional == 0 else 100.0
    return abs(float(hedge_usd_notional)) / abs(float(exposure_usd)) * 100.0


def fx_pnl_eur(usd_notional: float, previous_eurusd: float, current_eurusd: float) -> float:
    _require_positive_rate(previous_eurusd, "previous_eurusd")
    _require_positive_rate(current_eurusd, "current_eurusd")
    return float(usd_notional) * ((1.0 / current_eurusd) - (1.0 / previous_eurusd))


def compute_currency_hedge_report(
    *,
    usd_assets: float,
    usd_liabilities: float,
    hedge_usd_notional: float,
    previous_eurusd: float,
    current_eurusd: float,
    previous_rolling_pnl_eur: float = 0.0,
    as_of: str | None = None,
) -> HedgeReport:
    exposure_usd = net_usd_exposure(usd_assets, usd_liabilities)
    exposure_pnl = fx_pnl_eur(exposure_usd, previous_eurusd, current_eurusd)

    # Positive hedge_usd_notional means a hedge against long-USD exposure.
    hedge_pnl = fx_pnl_eur(-float(hedge_usd_notional), previous_eurusd, current_eurusd)
    total_pnl = exposure_pnl + hedge_pnl

    report = HedgeReport(
        as_of=as_of or date.today().isoformat(),
        base_ccy="EUR",
        quote_ccy="USD",
        eurusd_previous=float(previous_eurusd),
        eurusd_current=float(current_eurusd),
        usd_assets=float(usd_assets),
        usd_liabilities=float(usd_liabilities),
        net_usd_exposure=exposure_usd,
        hedge_usd_notional=float(hedge_usd_notional),
        unhedged_usd_exposure=exposure_usd - float(hedge_usd_notional),
        hedge_coverage_pct=hedge_coverage_pct(exposure_usd, hedge_usd_notional),
        exposure_pnl_eur=exposure_pnl,
        hedge_pnl_eur=hedge_pnl,
        total_fx_pnl_eur=total_pnl,
        rolling_fx_pnl_eur=float(previous_rolling_pnl_eur) + total_pnl,
        auto_hedge_execution=False,
        real_api_enabled=os.getenv(REAL_API_ENV, "").lower() == "true",
    )
    return report


def write_report_file(report: HedgeReport, directory: str = "reports") -> Path:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"df-149-{report.as_of}.json"
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def main() -> Path:
    report = compute_currency_hedge_report(
        usd_assets=0.0,
        usd_liabilities=0.0,
        hedge_usd_notional=0.0,
        previous_eurusd=1.0,
        current_eurusd=1.0,
    )
    return write_report_file(report)


if __name__ == "__main__":
    path = main()
    print(path)
# [CRUX-MK]
