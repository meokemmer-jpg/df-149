from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence


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
    net_usd_exposure: float
    hedge_notional_usd: float
    hedge_coverage_pct: float
    fx_pnl_rolling_usd: float
    risk_state: str


def _sum_amounts(items: Iterable[Mapping[str, object]], currency: str) -> float:
    total = 0.0
    for item in items:
        if str(item["currency"]).upper() == currency.upper():
            total += float(item["amount"])
    return total


def _sum_hedges_usd(hedges: Iterable[Mapping[str, object]]) -> float:
    total = 0.0
    for hedge in hedges:
        if str(hedge["currency_pair"]).upper() != "EUR/USD":
            raise ValueError("Only EUR/USD hedges are supported")
        total += abs(float(hedge["notional_usd"]))
    return total


def _risk_state(net_usd_exposure: float, hedge_coverage_pct: float, fx_pnl_rolling_usd: float) -> str:
    if net_usd_exposure == 0:
        return "flat"
    if hedge_coverage_pct >= 90.0 and fx_pnl_rolling_usd >= 0.0:
        return "contained"
    if fx_pnl_rolling_usd < 0.0 and hedge_coverage_pct < 50.0:
        return "adverse_unhedged"
    return "open"


def calculate_fx_snapshot(
    exposures: Iterable[Mapping[str, object]],
    hedges: Iterable[Mapping[str, object]],
    current_eur_usd: float,
    previous_eur_usd: Optional[float] = None,
) -> FxSnapshot:
    if current_eur_usd <= 0:
        raise ValueError("current_eur_usd must be positive")
    if previous_eur_usd is not None and previous_eur_usd <= 0:
        raise ValueError("previous_eur_usd must be positive")

    exposure_rows = list(exposures)
    hedge_rows = list(hedges)
    exposed_eur = _sum_amounts(exposure_rows, "EUR")
    exposed_usd = _sum_amounts(exposure_rows, "USD")
    eur_value_usd = exposed_eur * current_eur_usd
    gross_usd_exposure = abs(eur_value_usd) + abs(exposed_usd)
    hedge_notional_usd = _sum_hedges_usd(hedge_rows)
    signed_hedge = min(hedge_notional_usd, abs(eur_value_usd))
    if eur_value_usd > 0:
        signed_hedge *= -1.0
    net_usd_exposure = eur_value_usd + exposed_usd + signed_hedge

    hedge_coverage_pct = 0.0
    if abs(eur_value_usd) > 0:
        hedge_coverage_pct = min(hedge_notional_usd / abs(eur_value_usd), 1.0) * 100.0

    fx_pnl_rolling_usd = 0.0
    if previous_eur_usd is not None:
        fx_pnl_rolling_usd = exposed_eur * (current_eur_usd - previous_eur_usd)

    return FxSnapshot(
        eur_usd=float(current_eur_usd),
        exposed_eur=float(exposed_eur),
        exposed_usd=float(exposed_usd),
        gross_usd_exposure=float(gross_usd_exposure),
        net_usd_exposure=float(net_usd_exposure),
        hedge_notional_usd=float(hedge_notional_usd),
        hedge_coverage_pct=float(hedge_coverage_pct),
        fx_pnl_rolling_usd=float(fx_pnl_rolling_usd),
        risk_state=_risk_state(net_usd_exposure, hedge_coverage_pct, fx_pnl_rolling_usd),
    )


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ledger JSON must contain an object")
    return data


def _read_csv_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_ledger(path: str | Path) -> dict[str, object]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() == ".json":
        ledger = _read_json(source)
    elif source.suffix.lower() == ".csv":
        ledger = {"exposures": _read_csv_rows(source), "hedges": []}
    else:
        raise ValueError("ledger must be .json or .csv")

    ledger.setdefault("exposures", [])
    ledger.setdefault("hedges", [])
    if not isinstance(ledger["exposures"], Sequence) or isinstance(ledger["exposures"], (str, bytes)):
        raise ValueError("exposures must be a sequence")
    if not isinstance(ledger["hedges"], Sequence) or isinstance(ledger["hedges"], (str, bytes)):
        raise ValueError("hedges must be a sequence")
    return ledger


def snapshot_from_ledger(path: str | Path) -> FxSnapshot:
    ledger = load_ledger(path)
    return calculate_fx_snapshot(
        exposures=ledger["exposures"],
        hedges=ledger["hedges"],
        current_eur_usd=float(ledger["current_eur_usd"]),
        previous_eur_usd=float(ledger["previous_eur_usd"]) if ledger.get("previous_eur_usd") is not None else None,
    )


def write_report(snapshot: FxSnapshot, report_date: Optional[date] = None, base_dir: str | Path = ".") -> Path:
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


def build_report_from_ledger(ledger_path: str | Path, report_date: Optional[date] = None, base_dir: str | Path = ".") -> Path:
    return write_report(snapshot_from_ledger(ledger_path), report_date=report_date, base_dir=base_dir)
