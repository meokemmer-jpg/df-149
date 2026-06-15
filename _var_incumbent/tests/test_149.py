import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib

# Direkte Syntax `from 149 import ...` ist in Python ungueltig; das Modul `149.py`
# wird hier testbar per importlib geladen.
m149 = importlib.import_module("149")
calculate_fx_snapshot = m149.calculate_fx_snapshot
write_report = m149.write_report


def test_calculate_fx_snapshot_and_write_report(tmp_path):
    exposures = [
        {"currency": "EUR", "amount": 100_000},
        {"currency": "USD", "amount": 25_000},
    ]
    hedges = [
        {"currency_pair": "EUR/USD", "notional_usd": 60_000},
    ]

    snapshot = calculate_fx_snapshot(
        exposures=exposures,
        hedges=hedges,
        current_eur_usd=1.20,
        previous_eur_usd=1.10,
    )

    assert snapshot.exposed_eur == 100_000
    assert snapshot.exposed_usd == 25_000
    assert snapshot.gross_usd_exposure == 120_000
    assert snapshot.hedge_notional_usd == 60_000
    assert snapshot.hedge_coverage_pct == 50.0
    assert round(snapshot.fx_pnl_rolling_usd, 2) == 10_000.00

    report_path = write_report(snapshot, report_date=__import__("datetime").date(2026, 6, 14), base_dir=str(tmp_path))
    assert report_path.exists()

    content = report_path.read_text(encoding="utf-8")
    assert '"tracker": "df-149"' in content
    assert '"auto_hedge_execution": false' in content
    assert '"hedge_coverage_pct": 50.0' in content

