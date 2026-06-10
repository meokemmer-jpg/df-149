import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib
import json


mod = importlib.import_module("149")
compute_currency_hedge_report = mod.compute_currency_hedge_report
write_report_file = mod.write_report_file


def test_currency_hedge_report_core_metrics_and_file_output(tmp_path, monkeypatch):
    monkeypatch.setenv("DF_149_REAL_API_ENABLED", "true")

    report = compute_currency_hedge_report(
        usd_assets=150_000,
        usd_liabilities=50_000,
        hedge_usd_notional=60_000,
        previous_eurusd=1.10,
        current_eurusd=1.00,
        previous_rolling_pnl_eur=1_000,
        as_of="2026-06-10",
    )

    assert report.net_usd_exposure == 100_000
    assert report.unhedged_usd_exposure == 40_000
    assert report.hedge_coverage_pct == 60.0
    assert round(report.exposure_pnl_eur, 2) == 9090.91
    assert round(report.hedge_pnl_eur, 2) == -5454.55
    assert round(report.total_fx_pnl_eur, 2) == 3636.36
    assert round(report.rolling_fx_pnl_eur, 2) == 4636.36
    assert report.auto_hedge_execution is False
    assert report.real_api_enabled is True

    path = write_report_file(report, directory=str(tmp_path))
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "df-149-2026-06-10.json"
    assert payload["net_usd_exposure"] == 100_000
    assert payload["hedge_coverage_pct"] == 60.0
    assert payload["auto_hedge_execution"] is False
