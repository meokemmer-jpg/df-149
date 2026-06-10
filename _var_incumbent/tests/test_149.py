import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib
import json

m149 = importlib.import_module("149")
compute_fx_snapshot = m149.compute_fx_snapshot
write_report = m149.write_report


def test_df149_core_snapshot_and_report(tmp_path):
    snapshot = compute_fx_snapshot(
        eur_balance=100000,
        usd_balance=50000,
        eurusd_rate=1.10,
        hedge_usd_notional=20000,
        previous_eurusd_rate=1.00,
    )

    assert snapshot.base_currency == "EUR"
    assert snapshot.pair == "EUR/USD"
    assert snapshot.usd_exposure_gross == 50000
    assert snapshot.usd_exposure_open == 30000
    assert snapshot.hedge_coverage_pct == 40.0
    assert snapshot.auto_hedge_execution is False
    assert round(snapshot.fx_pnl_eur_rolling, 6) == round(30000 * ((1 / 1.10) - 1.0), 6)
    assert round(snapshot.fx_pnl_usd_rolling, 6) == round(snapshot.fx_pnl_eur_rolling * 1.10, 6)

    report_path = write_report(snapshot, tmp_path / "reports")
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path.name == f"df-149-{snapshot.as_of}.json"
    assert payload["mission"] == "DF-149 KPM-Currency-Hedge-Tracker"
    assert payload["policy"] == "NIEMALS Auto-Hedge-Execution."
    assert payload["status"] == "monitor_only"
    assert payload["usd_exposure_open"] == 30000
    assert payload["hedge_coverage_pct"] == 40.0
    assert payload["auto_hedge_execution"] is False

