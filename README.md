# MyComputerStatus

A daily health log for this MacBook Air — battery wear, RAM pressure, thermal state, disk
headroom, and anything abnormal (kernel panics, memory-pressure kills, crash reports).

One markdown snapshot per day in [`daily/`](daily/), plus a machine-readable row per day in
[`data/history.csv`](data/history.csv) so trends can be charted over time.

> **Machine:** MacBook Air `Mac16,12` · Apple M4 (10 cores) · 16 GB RAM · macOS 26.5 (25F71)
>
> Only generic hardware facts are published. **No computer name, no network addresses, no serial
> number and no software / process names** appear anywhere in this repository — see
> [Privacy](#privacy).

---

## What gets recorded

| Metric | Source |
|---|---|
| Battery charge, source, cycle count, max capacity, condition, temperature | `pmset -g batt`, `ioreg AppleSmartBattery`, `system_profiler SPPowerDataType` |
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
scripts/append_csv.py    Pipes collect.sh output into data/history.csv
scripts/show_names.py    LOCAL-ONLY unredacted view — never used by the daily run
```

## Reproducing a run

```bash
# Print today's metrics (anonymous by design: no names, no IPs, no serials)
bash scripts/collect.sh

# Append today's row to data/history.csv
bash scripts/collect.sh | python3 scripts/append_csv.py

# Preview without writing
bash scripts/collect.sh | python3 scripts/append_csv.py --dry-run
```

`collect.sh` is read-only — it never changes system state. It requires no `sudo`; the one thing
it cannot read without elevation is `powermetrics` sensor data, so thermal state is reported via
`pmset -g therm` instead.

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
top_cpu,top_mem
```

The final two columns (`top_cpu`, `top_mem`) are **always empty**: process names are never
recorded in this repository. The columns are kept so the schema stays stable and historical rows
stay comparable.

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
