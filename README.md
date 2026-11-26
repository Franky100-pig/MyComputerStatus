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
| `ac_plugs` | Transitions **to** AC in the interval. A bouncing plug contributes several, so this is an upper bound on physical plug-ins — 2026-11-21 read `4` for two insertions. Compare with `charger_bounces` |
| `charge_sessions` | **Not** a count of charge sessions — it counts `handleChargingStateUpdate` posts matching `Charging Completed`, and `powerd` emits each post twice from two log sources. 2026-11-22 read `67` for **34** distinct events and **one** actual charge (§[below](#charge_sessions-counts-posts-not-sessions)) |
| `topoff_pct` | Highest charge **observed in the interval** — usually the ceiling a session reached, but on a day spent on battery it is simply the charge carried in from the previous day |
| `batt_floor_pct` | Lowest charge reached |
| `charge_rate_max` | Fastest ramp in one session, percentage points per hour. **Blind on a day with no power-source transition** — 2026-11-22 read `0.0` while the pack gained 5 points (§[below](#charge_rate_max-needs-a-plug-event)) |
| `time_ac_h` | Hours on AC |
| `time_batt_h` | Hours on battery |
| `charger_bounces` | Transitions within 10 s of each other — a contact fault, not a plug |

`time_ac_h + time_batt_h` should equal the report interval. When run without
`--since`/`--until` the script covers the trailing 24 hours at run time, so it can differ from
the report interval by a few minutes; pass both flags to make the arithmetic exact.

### `disk_free_gb` is not the complement of `disk_used_gb`

`disk_used_gb` is measured on `/System/Volumes/Data` (`df -k /System/Volumes/Data`), while
`disk_free_gb` is the container-wide available figure. The two therefore do **not** add up to the
capacity, and they can move in very different directions: on 2026-11-20 the Data volume grew
**5.8 GB** while free space fell **16.1 GB**, because a prepared macOS update had written
**15 GB** into `/System/Volumes/Update` — a different volume in the same container. Reading the
gap as a leak, or as "used" minus "free" as the disk size, will be wrong. Check
`df -h /System/Volumes/Update` before concluding anything from a large free-space drop.

> ⚠️ **`diskutil apfs listSnapshots /System/Volumes/Data` can say "No snapshots" when there
> are three.** The update snapshots belong to the *volume group*, not the Data volume alone;
> `tmutil listlocalsnapshots /` lists them (verified 2026-11-23). Do not read "no snapshots" as
> "the staged update was released".

> ⚠️ **Use `df` or `du -sx`, never `du -sh`.** `/System/Volumes/Update` has two other filesystems
> mounted *inside* it — the sealed system volume (16 GiB) at `Update/mnt1` and a support volume
> (2.1 GiB) at `Update/SFR/mnt1` — and plain `du` follows into them. On 2026-11-22 `du -sh` read
> **15 G** for a volume that `df` measured at **967 MiB**. The number looks exactly like the
> 11-20 update payload and is not.

### `charge_rate_max` needs a plug event

`collect_charging.py` scores a ramp only **inside an AC segment created by a power-source
transition**, measured from the level at plug-in to the peak before unplug. A machine that stays
plugged in for the whole interval has no such segment, so nothing is scored and the field falls
back to `0.0`.

`0.0` therefore means "no ramp was measurable", not "the battery did not charge". On 2026-11-22
`ac_plugs` was `0`, `charge_rate_max` was `0.0`, and the pack still went **80 % → 85 % in 43 m
53 s**: an average of **6.8 pts/h**, with **14.1 pts/h** in the steady part and a **27-minute**
first percent. Quote `charge_rate_max` only when `ac_plugs > 0`, and never compress a multi-point
refill into one rate — the first point after a hold costs far more than the rest and drags the
average down by a factor of two.

Six days of measurements on the same pack and, as far as this collector can see, the same adapter
give **12.0, 15.4, 18.9, 20.1, 21.1** pts/h whole-session and **14.6, 22.4, 22.5** pts/h for the
steady middle. The 22.4/22.5 pair looked stable enough on 11-25 to be written down as "the only
stable figure"; 24 hours later the same measurement read **14.6**. No covariate in this log
(time of day, starting charge, reap activity, load) tracks the spread, and adapter wattage is
deliberately not read (see [Privacy](#privacy)), so a lower-rated brick or a hub in the path is
invisible here. Treat the column as a **range, not a value**, and do not derive a charging-time
estimate from a single day.


### `ac_plugs = 0` is ambiguous — read `time_ac_h` with it

`ac_plugs` counts transitions **to** AC. Both a day that never left the adapter (2026-11-22:
`0`, 24.3 h AC) and a day with exactly one unplug and no re-plug (2026-11-23: `0`, 9.4 h AC /
16.5 h battery) read `0`. Use the two time columns to tell them apart; their sum should equal
the report interval.

Until 2026-11-23 those columns could also be flatly wrong. `collect_charging.py` seeded the
pre-transition segment from the **first capacity record**, but a held charge posts no capacity
record until something changes — so on 11-23 that record was the detach itself, marked
`Batt`, and the first 9.4 h on AC were counted as battery (`TIME_AC_H=0.0`, `TIME_BATT_H=25.9`).
The collector now infers the pre-transition source by inverting the first transition when no
capacity record predates it, and clips segments to the requested window (an `--until` before a
transition used to yield a negative duration). Days whose first capacity record predates their
first transition take the unchanged path.

### `topoff_pct` can be a charge limit, not a full charge

On most days `topoff_pct` is simply the highest level a charge session reached. On a machine with
an **85 % charge limit** it is instead the limit itself: on 2026-11-21 the pack was plugged at
89 %, went straight to `Charging Completed Limited`, and sat at exactly **85 % for 86 minutes**
with `ChargingCurrent = 0` and `NotChargingReason = 0x01000000` while `pmset` reported
`AC attached; not charging`. The same machine charged through 85 % to **100 %** on 11-19 and
11-20, because macOS lifts the limit periodically for a full calibration charge. So a flat
`topoff_pct` of 85 is a deliberate hold, not a stuck battery, and the two days cannot be compared
without knowing which state was in force.

### The "85 % hold" is a band, not a level

A charge limit is not a flat line. On 2026-11-22 the machine spent the whole 24.3 h interval on AC
with **zero power-source transitions**, and the pack still moved: it drifted **85 % → 80 % over
22 h 22 m** (0.224 pts/h) and was then **re-filled to 85 % in 43 m 53 s**. 80 % is where the
charger re-engages, so the observable is a **hysteresis band 80–85**, not a fixed 85.

Two consequences for anyone reading the curve:

- The drift is not 5 % of the pack's energy. 5 points on a ~47 Wh battery is 2.4 Wh — about twenty
  minutes of idle use — spread over a day in which the system ran from the adapter. It is gauge
  drift under a hold, and the refill is the gauge being re-anchored.
- `batt_floor_pct` on such a day is the **bottom of the band** (80), not a discharge floor. Compare
  it with 2026-11-21's `36`, which was real use, only after checking `time_batt_h`.

### `charge_sessions` counts posts, not sessions

`powerd` emits each `handleChargingStateUpdate` line **twice** — two log sources carry the same
microsecond timestamp — and it re-asserts the limit state at every maintenance wake. On
2026-11-22 the column read **67** for **34** distinct events: 33 `Charging Completed Limited`
posts (one per dark wake, in step with the 15-minute sleep metronome) plus **one** genuine
`Charging`. So the column is a measure of state-machine activity, not of charging. Read it
alongside `ac_plugs`; when `ac_plugs = 0` there cannot have been more than one session no matter
what this number says.

### Capacity records stop while the machine sleeps

`powerd` posts `Battery capacity change` only when the gauge moves **while awake**. A charge that
happens during sleep therefore appears as a single jump: on 2026-11-21 the curve went **63 % →
72 % in 16 minutes**, which is 34 pts/h — impossible on the 20 W adapter in use, and an artefact
of the maintenance-sleep cycles in between. Never compute a rate across a sleep gap in the
capacity curve. `collect_charging.py` sidesteps this by measuring from the charge level at
plug-in to the peak reached before unplug, both of which are awake endpoints.

### The swap pool shrinks without a reboot

The pool is dynamic in **both** directions, and the daily report once claimed otherwise. On
2026-11-22 macOS grew it from 2 048 MB to 3 072 MB by creating `swapfile2`; the 11-23 report
concluded "the pool never shrinks without a reboot, so 3 072 MB is the new floor until the next
restart". Twenty-four hours later, with the boot epoch unchanged at 17.9 days, `swapfile2` was
**gone** — `/System/Volumes/VM` mtime `22:37:45`, `vm.swapusage` back to `total = 2048.00M`, and
only `swapfile0` / `swapfile1` left. The kernel took the file back because it was entirely unused
(1 237 MB used of 3 072 MB leaves a whole 1 024 MB file empty).

So `swap_used_mb` can fall in two completely different ways, and the sampler's flow counters are
the only way to tell them apart:

- **Paged in.** `swapins` rises by roughly the amount `used` falls. The memory came back.
- **Discarded.** `swapins` and `swapouts` barely move. Pages left swap because the VM objects that
  owned them were destroyed — memory freed, not migrated. On 2026-11-24 `used` fell **1 786 MB**
  while `swapins` moved only **370 MB** and `swapouts` **84 MB**, so ~1.4 GB was discarded.

Read `sysctl vm.swapusage` together with `ls -l /System/Volumes/VM` and the file dates. A pool that
changed size without a boot-epoch change is a shrink or a grow, never a reboot — and a `used` figure
that drops is not automatically a recovery.

The pool then **grew back** on 2026-11-25: `swapfile2` re-created at `13:04:35`, `total` back to
3 072 MB, boot epoch unchanged at 18.9 days. Six days of this column therefore read
2 048 → 3 072 → 2 048 → 3 072 with no restart anywhere, which is the useful conclusion: **the pool
is allocated to fit the working set and returned when a whole file falls idle. It has no floor and
no ceiling worth quoting — track `used`, not `total`.**

It grew once more on **2026-11-26**, to **4 096 MB**, with `swapfile3` created at `12:57`. This
time the ordering is cleaner than "after the plug-in": the sampler rows at 12:51:45 and 13:06:45
bracket the file's birth, and between them swap used rose **502 MB** while **510 MB** was written
out and the compressor fell 0.62 GB. The file was created **inside** an eviction, not after a
power event, which supports the simplest reading of all five changes: the kernel adds a swap file
when it needs the room.

A third direction is worth naming, because it looks like the two above but is not:

- **Evicted.** `swapouts` rises by roughly the amount `used` rises, and the compressor falls.
  On 2026-11-25 the machine wrote **85 660 pages (1.31 GiB)** to disk between 13:00 and 13:15
  while the compressor dropped 7.43 → 6.06 GB and `swapins` moved **85 pages**. That is compressed
  memory moving to disk under real pressure, not a release and not a discard.

### `DIAG_24H` counts analytics payloads, not failures

`.diag` files are not only failed `sysdiagnose` attempts. The per-user diagnostics store also
receives `bug_type 226` health/telemetry summaries, which macOS writes **in a burst of six to
ten files a few seconds after each wake** — expected, benign, and periodic. Because `collect.sh`
can sample mid-burst, the same wake can read as 2 or as 8 depending on which second it was
taken. Treat `DIAG_24H` as "diagnostic payload files touched in the last 24 h", not as an
anomaly counter; real incidents are visible as panics and as `killing_*` records in the log.

The trigger is not always a wake. On 2026-11-24 the two bursts in the interval began **10 s after**
a plug-in at 10:10:04 and **10 s after** a plug-in at 19:43:56, with the machine awake throughout.
Check the power-source transitions before blaming a wake.

There is a third way to read `0`: **the store can be reset out from under you.** On 2026-11-22 the
system-wide directory was re-created at 11:18 and every file in it — including the previous day's
8 — was gone, so `DIAG_24H` and the `.ips` count were both zero with no change in machine health.
Check the directory's own mtime before concluding that nothing was written.

And a fourth, on 2026-11-26: the store can be **deleted outright**, with the parent rebuilt around
an empty `CrashReporter` subdirectory. Both `/Library/Logs/DiagnosticReports` and
`~/Library/Logs/DiagnosticReports` were absent, neither had a `.diag` or `.ips` anywhere under it,
and `/Library/Logs` carried an mtime of 17:00:13 with `~/Library/Logs` at 19:57:03 — each matching
the creation time of the `CrashReporter` directory inside it. `find` on a missing directory returns
nothing, so `PANIC_FILES`, `JETSAM_24H` and `DIAG_24H` all read `0`: a deleted store produces the
same row as a clean day.

`collect.sh` therefore emits a fourth key alongside the counters:

```
DIAG_STORE=present | one-missing | absent
```

It is **not** a CSV column — `append_csv.py` ignores keys it does not map, so historical rows keep
their shape. Read the three zeros as "no events" only when `DIAG_STORE` reads `present`; when it
reads `absent`, the honest value is *unknown*, and the report should say so instead of scoring a
good day. Note that a `per-process-limit` kill still leaves a `killing_specific_process` line in
the kernel stream, so that one check survives the store's disappearance.

### Count kills by `killing_idle_process`, not by `killing`

The kernel writes **two** log lines per reap, about a second apart:

```
memorystatus: killing (idle) <name> [<pid>] due to idle-exit (9)
memorystatus: killing_idle_process pid <pid> [<name>] (idle-exit 0 29294s rf:- type:daemon) 3008KB - memorystatus_available_pages: 424482
```

Grep for `killing` and every kill counts twice — on 2026-11-25 that is 2 233 lines for **1 117**
actual kills, which silently doubles the reported rate to 92/h. Count lines matching
`killing_idle_process` (idle reaps) plus `killing_specific_process` (cap and pressure reaps), and
verify the two halves of an episode pair up. This is the same log-format doubling documented for
`charge_sessions` above, in a different subsystem, and it is the third place in this collector
where counting lines instead of events gives exactly 2×.

A `per-process-limit` kill also produces a `JetsamEvent-*.ips` in
`/Library/Logs/DiagnosticReports` (bug type 298) which macOS later moves to `Retired/`. The
`.ips` and the kernel line describe the same event; count it once.

### Check log retention before quoting a window

Both log stores are circular and both shrink without warning. `pmset -g log` held **65.6 h** on
2026-11-21 and **14.4 h** on 2026-11-22, having rotated overnight; the unified `sleepWake` stream
held 24.0 h. Always read the first line of the file you are about to parse, and say which stream
the sleep numbers came from. When both cover the interval, cross-check them: on 11-22 the two
independent sources produced the same **51 blocks** and totals **0.1 min** apart (9.879 vs
9.880 h).

Rotation is not the only way to lose the store. On **2026-11-26** `pmset -g log` printed one
record from 15:29:51 and four minutes later returned `Error - no messages found in PM ASL data
store at: /var/log/powermanagement` — the **directory did not exist**. A rotated store still holds
tens of hours; an empty one holds nothing, and the difference matters because "0 % asleep" is a
very different claim from "no data". Check that the *store exists*, not just that it is old:

```bash
ls -ld /var/log/powermanagement        # a missing dir = pmset is blind
pmset -g log | head -3                 # banner + first record, or the error line
log show --last 24h --predicate 'subsystem == "com.apple.powerd" AND category == "sleepWake"' | head -3
```

On that day the `sleepWake` stream still held the full 24.0 h and was the only usable source for
the sleep numbers — the report says so rather than presenting the two as equivalent.

### Your own probes land in the numbers

`log show` and `softwareupdate -l` are not free. The `pageins` delta includes the reads performed
by the previous run's log scans (1–4 GiB a day), and on 2026-11-22 a single `softwareupdate -l`
issued by the report itself accounted for the largest hourly block of `softwareupdated` activity
in the whole interval (13 921 of 126 328 entries). Note the probe when its subject is the thing
being measured.

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
