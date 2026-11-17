# MyComputerStatus

A daily health log for my MacBook Air — battery wear, RAM pressure, thermal state, disk
headroom, and anything abnormal (kernel panics, memory-pressure kills, crash reports).

One markdown snapshot per day in [`daily/`](daily/), plus a machine-readable row per day in
[`data/history.csv`](data/history.csv) so trends can be charted over time.

> **Machine:** MacBook Air `Mac16,12` · Apple M4 (10 cores) · 16 GB RAM · macOS 26.5 (25F71)
>
> Only generic hardware facts are published. **No computer name, no network addresses, no serial
> number and no software / process names** appear anywhere in this repository — see
> [Privacy](#privacy).
> Users can change this repo accordingly if they want to establish name, addresses, and so on.
---

## What gets recorded

| Metric | Source |
|---|---|
| Battery charge, source, cycle count, max capacity, condition, temperature | `pmset -g batt`, `ioreg AppleSmartBattery`, `system_profiler SPPowerDataType` |
| **Charging behaviour**: plug-ins, sessions, top-off level, floor, fastest ramp, time on AC vs battery, charger bounces | `log show --predicate 'process == "powerd"'` via `scripts/collect_charging.py` |
| RAM used / pressure / swap / compressor | `vm_stat`, `sysctl vm.swapusage` |
| Load average, core count | `sysctl vm.loadavg`, `hw.ncpu` |
| Thermal throttling warnings | `pmset -g therm` |
| Disk usage, SSD SMART status | `df`, `diskutil info disk0` |
| Anomalies: kernel panics, Jetsam events | `/Library/Logs/DiagnosticReports/` (counted, never named) |
| Top CPU / memory processes | **never recorded** — see [Privacy](#privacy) |

## Layout

```
daily/YYYY-MM-DD.md      Human-readable daily report
data/history.csv         One row per day, stable schema (see header)
scripts/collect.sh       Collects anonymous metrics as KEY=VALUE lines (no sudo needed)
scripts/collect_charging.py
                         Derives charging behaviour from the last N hours of the power log
scripts/append_csv.py    Pipes collect.sh (and optionally collect_charging.py) into history.csv
scripts/show_names.py    LOCAL-ONLY unredacted view — never used by the daily run
```

## Reproducing a run

```bash
# Print today's metrics (anonymous by design: no names, no IPs, no serials)
bash scripts/collect.sh

# Append today's row to data/history.csv, charging columns included
{ bash scripts/collect.sh; python3 scripts/collect_charging.py; } | python3 scripts/append_csv.py

# Preview without writing
{ bash scripts/collect.sh; python3 scripts/collect_charging.py; } | python3 scripts/append_csv.py --dry-run

# Charging behaviour on its own, over an exact window
python3 scripts/collect_charging.py --since '2026-11-16 11:14:03' --until '2026-11-17 11:38:44'
```

`collect.sh` is read-only — it never changes system state. It requires no `sudo`; the one thing
it cannot read without elevation is `powermetrics` sensor data, so thermal state is reported via
`pmset -g therm` instead.

`collect_charging.py` is likewise read-only and takes **2–4 minutes** on a 24-hour window,
because `log show` has to walk the whole unified log. Run it in the background rather than
chaining it behind `collect.sh` inside a timed script. Passing a pre-dumped log with
`--from-file` makes re-runs instant and keeps the numbers reproducible.

## Seeing the full detail locally (`show_names.py`)

The published log is anonymous **on purpose**, so it deliberately leaves out everything that
could identify the machine. If you want that detail for yourself — for troubleshooting, or just
to know what is actually running — use the companion script:

```bash
python3 scripts/show_names.py              # everything
python3 scripts/show_names.py --no-procs   # skip the per-process tables
```

**This script is not part of the daily run.** Nothing calls it, nothing schedules it, it writes
no files and it changes nothing on the system. It simply prints, to your terminal:

| Section | What it adds over the daily log |
|---|---|
| Identity & hardware | Computer name, local host name, model, chip, **full serial number**, hardware UUID |
| Network | every active interface with its IPv4 / IPv6 addresses, the default gateway, the Wi-Fi SSID |
| Battery & power | raw cycle count, design vs. max capacity in mAh, battery temperature |
| Memory | page-level breakdown, swap, compressor |
| Disk | volume usage, SMART status |
| System | boot time, uptime, load, thermal state |
| Processes | top 12 by CPU and by memory, **with real process names**, plus the running application list |

It needs no arguments and no `sudo`. Because the output **does** contain identifying data, treat
it like a password:

- ❌ do not commit it, and do not paste it into this repo, an issue, a gist or a chat
- ❌ do not redirect it into a file inside this working copy
- ✅ it is fine to read it on screen, or to send it to `pbcopy` / a scratch file outside the repo

> The output starts and ends with a `LOCAL-ONLY OUTPUT` banner so a pasted fragment is still
> recognisable for what it is.

## CSV schema

```
date,time,uptime_days,load_1m,load_5m,load_15m,mem_used_gb,mem_used_pct,swap_used_mb,
battery_pct,battery_cycles,battery_maxcap_pct,battery_cond,battery_temp_c,
disk_used_gb,disk_used_pct,disk_free_gb,ssd_smart,thermal_warning,panics,jetsam_24h,
top_cpu,top_mem,
ac_plugs,charge_sessions,topoff_pct,batt_floor_pct,charge_rate_max,time_ac_h,time_batt_h,
charger_bounces
```

The two `top_*` columns are **always empty**: process names are never recorded in this
repository. They are kept so the schema stays stable and historical rows stay comparable.

### Charging columns

Added 2026-11-17 and **appended to the end on purpose**, so the 23 leading columns kept their
positions and every earlier row still parses — those rows simply have blank cells, which is an
honest record of "not measured" rather than a fabricated zero.

| Column | Meaning |
|---|---|
| `ac_plugs` | Times the charger was connected in the interval |
| `charge_sessions` | Charge sessions that reached `Charging Completed` |
| `topoff_pct` | Highest charge reached — the ceiling in practice |
| `batt_floor_pct` | Lowest charge reached |
| `charge_rate_max` | Fastest ramp in one session, percentage points per hour |
| `time_ac_h` | Hours on AC |
| `time_batt_h` | Hours on battery |
| `charger_bounces` | Transitions within 10 s of each other — a contact fault, not a plug |

`time_ac_h + time_batt_h` should equal the report interval. When run without
`--since`/`--until` the script covers the trailing 24 hours at run time, so it can differ from
the report interval by a few minutes; pass both flags to make the arithmetic exact.

## Privacy

This repo is **public**, so everything in `daily/` is written defensively:

| Data | Policy |
|---|---|
| Computer name / host name | **Never recorded.** Reports say only "MacBook Air (Mac16,12) · Apple M4 · 16 GB · macOS 26.5" |
| IP addresses / network addresses | **Never recorded.** Network is reported as "Wi-Fi active (`en0`)" only |
| Hardware serial number / UUID | **Never recorded.** Not even partially |
| Process / application names | **Never recorded** in the log. `collect.sh` cannot emit them at all; the `top_cpu` / `top_mem` CSV columns stay empty |
| Third-party diagnostics | Described by **category** only ("a cloud-drive sync client", "a browser helper"), never by name |
| Diagnostic file names | Counted, never printed — the file names themselves can embed the host name |
| Charger serial, `gh` tokens, keychain data | Never recorded |
| Charger model / name, USB port path, adapter wattage detail | **Never read.** `collect_charging.py` parses only charge percentages, power-source transitions and timestamps |
| Full `ps` command lines with arguments | Never recorded anywhere in the repo |

The anonymity is **structural, not a switch**: `collect.sh` has no flag that would make it emit
identifying data, so the daily log cannot leak by accident. The unredacted view exists only as
the separate, manually-run `show_names.py` described above.

## Status key

| Emoji | Meaning |
|---|---|
| 🟢 | Normal / healthy — no action needed |
| 🟡 | Watch — worth noting, not urgent |
| 🔴 | Abnormal — investigate |

---

*Collected automatically via WorkBuddy. The daily log is anonymous by design: no computer name,
no network addresses, no serial number, no software names (see [Privacy](#privacy)). For the
unredacted local view, run `python3 scripts/show_names.py`.*
