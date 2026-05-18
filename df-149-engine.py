
# K16: Concurrent-Spawn-Mutex (fcntl-based, Trinity-CONSERVATIVE 2026-05-17)
def k16_lock_or_exit(df_name: str):
    """Acquire exclusive lock or exit(3). Prevents concurrent DF runs."""
    import fcntl, os, sys
    lock_path = f"/tmp/df-trinity-{df_name}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        sys.exit(3)


# K13: External-Anchor-Mock-RFC3161 (Trinity-CONSERVATIVE 2026-05-17)
def k13_anchor(payload_hash: str) -> dict:
    """Mock RFC3161-style timestamp anchor."""
    from datetime import datetime, timezone
    return {
        "anchor_type": "rfc3161-mock",
        "iso_ts": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
    }


# K12: HMAC-SHA256-Provenance (Trinity-CONSERVATIVE 2026-05-17)
def k12_provenance(payload: bytes, key: bytes = b"df-trinity-conservative-v1") -> dict:
    """Returns payload_hash + HMAC-SHA256 signature."""
    import hashlib, hmac
    return {
        "payload_hash": hashlib.sha256(payload).hexdigest(),
        "hmac_sha256": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }

"""KPM-Currency-Hedge-Tracker DF-149 engine."""

import re
import os
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timezone

DF_DIR = Path(__file__).parent
LOCK_DIR = Path("/tmp/df-149.lock")
DF_ID = "149"
DECISION_KEYWORDS_REGEX = re.compile(
    r"\b(entscheid[a-z]*|empfehl(?:e|en|t|st)|sollt(?:e|en|est)|recommend[a-z]*|decid[a-z]*|advis[a-z]*|propos[a-z]*)\b",
    re.IGNORECASE,
)


@dataclass
class TrackerOutput:
    welle: str = "25"
    df: str = "DF-149"
    iso_timestamp: str = ""
    source: str = "mock"
    usd_exposure_eur: float = 0
    eur_exposure_eur: float = 0
    hedge_coverage_pct: float = 0
    currency_pl_unrealized_eur: float = 0
    hedge_instruments: list = field(default_factory=list)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_stable(path, min_age_sec=300) -> bool:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return False
    try:
        first = p.stat()
        if time.time() - first.st_mtime < min_age_sec:
            return False
        time.sleep(0.05)
        second = p.stat()
        return first.st_size == second.st_size and first.st_mtime == second.st_mtime
    except OSError:
        return False


def _remove_lock_dir() -> None:
    if not LOCK_DIR.exists():
        return
    for child in LOCK_DIR.iterdir():
        try:
            if child.is_file() or child.is_symlink():
                child.unlink()
        except OSError:
            pass
    try:
        LOCK_DIR.rmdir()
    except OSError:
        pass


def acquire_lock_with_identity() -> bool:
    stale_after_sec = 6 * 60 * 60
    try:
        LOCK_DIR.mkdir(mode=0o700)
        identity = {
            "pid": os.getpid(),
            "created_at": iso_now(),
            "df": DF_ID,
        }
        (LOCK_DIR / "identity.json").write_text(
            json.dumps(identity, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return True
    except FileExistsError:
        try:
            age = time.time() - LOCK_DIR.stat().st_mtime
        except OSError:
            return False
        if age <= stale_after_sec:
            return False
        _remove_lock_dir()
        try:
            LOCK_DIR.mkdir(mode=0o700)
            identity = {
                "pid": os.getpid(),
                "created_at": iso_now(),
                "df": DF_ID,
                "recovered_stale": True,
            }
            (LOCK_DIR / "identity.json").write_text(
                json.dumps(identity, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False
    except OSError:
        return False


def release_lock() -> None:
    _remove_lock_dir()


def k17_pre_action_verification(anchors) -> dict:
    missing = []
    env_tag = os.environ.get("DF_149_ENV_TAG", "real" if _is_real_api_enabled() else "mock")

    for anchor in anchors or []:
        value = str(anchor)
        if value.startswith("env:"):
            env_name = value[4:]
            if not os.environ.get(env_name):
                missing.append(value)
            continue

        path = Path(value)
        if not path.is_absolute():
            path = DF_DIR / path
        if not path.exists():
            missing.append(value)

    return {
        "ok": len(missing) == 0,
        "missing_anchors": missing,
        "env_tag": env_tag,
    }


def _is_real_api_enabled() -> bool:
    value = os.environ.get("DF_149_REAL_API_ENABLED", "false").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def scan_output_for_decision_keywords(text) -> list:
    if text is None:
        return []
    found = []
    for match in DECISION_KEYWORDS_REGEX.finditer(str(text)):
        token = match.group(0)
        if token.lower() not in {item.lower() for item in found}:
            found.append(token)
    return found


def assert_no_decision_keywords(output) -> None:
    hits = scan_output_for_decision_keywords(output)
    if hits:
        raise ValueError("Q_0/K_0 keyword block triggered: " + ", ".join(hits))


def _float_env(name: str, default: float = 0) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _list_env(name: str) -> list:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        return [part.strip() for part in raw.split(",") if part.strip()]


def collect_tracker_output() -> TrackerOutput:
    output = TrackerOutput()
    output.iso_timestamp = iso_now()

    if _is_real_api_enabled():
        output.source = "real"
        output.usd_exposure_eur = _float_env("DF_149_USD_EXPOSURE_EUR")
        output.eur_exposure_eur = _float_env("DF_149_EUR_EXPOSURE_EUR")
        output.hedge_coverage_pct = _float_env("DF_149_HEDGE_COVERAGE_PCT")
        output.currency_pl_unrealized_eur = _float_env("DF_149_CURRENCY_PL_UNREALIZED_EUR")
        output.hedge_instruments = _list_env("DF_149_HEDGE_INSTRUMENTS")

    return output


def _report_path(now_iso: str) -> Path:
    date_part = now_iso[:10]
    return DF_DIR / "reports" / f"df-149-{date_part}.json"


def _write_report(payload: dict) -> None:
    report_file = _report_path(payload.get("iso_timestamp") or iso_now())
    report_file.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
    assert_no_decision_keywords(text)
    report_file.write_text(text + "\n", encoding="utf-8")


def main() -> int:
    if not acquire_lock_with_identity():
        return 3

    try:
        pav = k17_pre_action_verification([])
        if not pav.get("ok"):
            payload = {
                "welle": "25",
                "df": "DF-149",
                "iso_timestamp": iso_now(),
                "source": "mock",
                "status": "blocked",
                "k17_pre_action_verification": pav,
            }
            _write_report(payload)
            return 3

        tracker_output = collect_tracker_output()
        payload = asdict(tracker_output)
        payload["k17_pre_action_verification"] = pav
        _write_report(payload)
        return 0
    except Exception as exc:
        payload = {
            "welle": "25",
            "df": "DF-149",
            "iso_timestamp": iso_now(),
            "source": "mock",
            "status": "error",
            "error_type": exc.__class__.__name__,
        }
        try:
            _write_report(payload)
        except Exception:
            pass
        return 3
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())