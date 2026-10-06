#!/usr/bin/env python3
"""append_csv.py - Append one row to data/history.csv from `collect.sh` KEY=VALUE output.

Usage:
    bash scripts/collect.sh | python3 scripts/append_csv.py
    bash scripts/collect.sh | python3 scripts/append_csv.py --dry-run

Creates the CSV with a header on first run; idempotent per (date) is NOT enforced,
so only run once per day.
"""
import csv
import sys
from pathlib import Path

COLUMNS = [
    "date", "time", "uptime_days", "load_1m", "load_5m", "load_15m",
    "mem_used_gb", "mem_used_pct", "swap_used_mb",
    "battery_pct", "battery_cycles", "battery_maxcap_pct", "battery_cond", "battery_temp_c",
    "disk_used_gb", "disk_used_pct", "disk_free_gb", "ssd_smart",
    "thermal_warning", "panics", "jetsam_24h", "top_cpu", "top_mem",
]

# KEY=VALUE name  ->  CSV column
MAP = {
    "DATE": "date", "TIME": "time", "UPTIME_DAYS": "uptime_days",
    "LOAD_1M": "load_1m", "LOAD_5M": "load_5m", "LOAD_15M": "load_15m",
    "MEM_USED_GB": "mem_used_gb", "MEM_USED_PCT": "mem_used_pct", "SWAP_USED_MB": "swap_used_mb",
    "BATTERY_PCT": "battery_pct", "BATTERY_CYCLES": "battery_cycles",
    "BATTERY_MAXCAP_PCT": "battery_maxcap_pct", "BATTERY_CONDITION": "battery_cond",
    "BATTERY_TEMP_C": "battery_temp_c",
    "DISK_USED_GB": "disk_used_gb", "DISK_USED_PCT": "disk_used_pct", "DISK_FREE_GB": "disk_free_gb",
    "SSD_SMART": "ssd_smart", "THERMAL_WARNING": "thermal_warning",
    "PANIC_FILES": "panics", "JETSAM_24H": "jetsam_24h",
    "TOP_CPU": "top_cpu", "TOP_MEM": "top_mem",
}


def main() -> int:
    dry = "--dry-run" in sys.argv
    row = {c: "" for c in COLUMNS}
    for line in sys.stdin:
        if "=" not in line:
            continue
        k, v = line.rstrip("\n").split("=", 1)
        if k in MAP:
            row[MAP[k]] = v

    out = Path(__file__).resolve().parent.parent / "data" / "history.csv"
    if dry:
        print(",".join(row[c] for c in COLUMNS))
        return 0

    exists = out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        if not exists:
            w.writeheader()
        w.writerow(row)
    print(f"appended {row['date']} {row['time']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
