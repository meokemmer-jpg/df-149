import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib

# Python erlaubt syntaktisch kein `from 149 import ...`, daher wird das Modul
# hier mit importlib geladen, obwohl es als `149.py` gespeichert ist.
m149 = importlib.import_module("149")
CashFlow = m149.CashFlow
HedgePosition = m149.HedgePosition
build_report = m149.build_report
calculate_currency_hedge_tracker = m149.calculate_currency_hedge_tracker
write_report = m149.write_report


def test_currency_hedge_tracker_core_and_report(tmp_path):
    cashflows = [
        CashFlow(amount=100_000, currency="EUR"),
        CashFlow(amount=20_000, currency="USD"),
    ]
    hedges = [HedgePosition(notional_usd=60_000)]

    snapshot = calculate_currency_hedge_tracker(
        cashflows=cashflows,
        spot_eur_usd=1.10,
        hedge_positions=hedges,
        previous_spot_eur_usd=1.05,
    )

    assert snapshot.eur_amount == 100_000.00
    assert snapshot.usd_amount == 20_000.00
    assert snapshot.gross_usd_exposure == 130_000.00
    assert snapshot.net_usd_exposure == 70_000.00
    assert snapshot.hedge_coverage_pct == 46.15
    assert snapshot.fx_pnl_rolling == 5_000.00

    report = build_report(
        cashflows=cashflows,
        spot_eur_usd=1.10,
        hedge_positions=hedges,
        previous_spot_eur_usd=1.05,
    )

    assert report["mission"] == "DF-149 KPM-Currency-Hedge-Tracker"
    assert report["auto_hedge_execution"] is False
    assert report["metrics"]["net_usd_exposure"] == 70_000.00

    output = write_report(
        cashflows=cashflows,
        spot_eur_usd=1.10,
        hedge_positions=hedges,
        previous_spot_eur_usd=1.05,
        reports_dir=str(tmp_path / "reports"),
    )

    assert output.exists()
    assert output.name.startswith("df-149-")
    content = output.read_text(encoding="utf-8")
    assert '"auto_hedge_execution": false' in content
    assert '"hedge_coverage_pct": 46.15' in content
