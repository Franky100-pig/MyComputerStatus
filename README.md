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

> ⚠️ **`du` on macOS counts 512-byte blocks by default, not 1 KiB.** `du -sx /System/Volumes/Update`
> prints **1974320**, and that is **964 MiB**, not 1 928 MiB. Six daily reports read the raw count as
> KiB and concluded that `df` and `du` disagreed by 2× on the update volume; corrected 2026-11-27.
> Pass `-m` (megabytes) or set `BLOCKSIZE=1024` if you want a number you can divide by 1024, and
> check the unit before reporting a discrepancy — a 2× gap between two tools measuring the same
> volume is almost always a block-size misreading, not a filesystem fact.

**A rise inside the Data volume has no explanation in this schema.** On 2026-11-28 used went
**287.82 → 289.22 GB** and free **135.93 → 134.53 GB** in the same interval, i.e. **+1.40 GB used
and −1.40 GB free**, with the VM volume unchanged at 2 GB — so the "container moved space between
volumes" reading that explained the previous two days does not apply. `~/Downloads` had **0 files**
modified in 24 h, so downloads were not it; the two largest trees are application containers
(**28.8 GB**) and application support (**21.6 GB**), and neither has a baseline anywhere in this
repo. The CSV's single `disk_used_gb` column cannot attribute a delta, so the honest entry is
"grew, cause unknown" rather than a guess. Re-record `du -sx -m` for the three largest trees
periodically if the number starts moving daily.

### `charge_rate_max` needs a *rise*, not a plug event

`collect_charging.py` scores a ramp **inside an AC segment**, measured from the charge level in
force at the segment's start to the peak reached before it ends. It does not require a
power-source transition to open that segment: if the machine is already on AC when the window
begins, the segment runs the whole window and is scored all the same.

**This section previously claimed the opposite** — that a machine plugged in for the whole
interval has no segment and therefore reads `0.0`. 2026-11-28 refutes it: `ac_plugs = 0` over
24.2 h AC, and the column read **16.3** from a clean 55 → 100 % ramp inside the single
whole-window segment. The condition that actually produces `0.0` is a segment with **no net rise**
above its starting level, which is what a held charge looks like:

`0.0` therefore means "no ramp was measurable", not "the battery did not charge". On 2026-11-22
`ac_plugs` was `0`, `charge_rate_max` was `0.0`, and the pack still went **80 % → 85 % in 43 m
53 s**: an average of **6.8 pts/h**, with **14.1 pts/h** in the steady part and a **27-minute**
first percent. The peak there was 85 against a start of 85 — the pack refilled to the band it
started in, so there was nothing to score. Never compress a multi-point refill into one rate, and
the first point after a hold costs far more than the rest and drags the average down by a factor
of two.

Seven days of measurements on the same pack and, as far as this collector can see, the same adapter
give **12.0, 15.4, 16.3, 18.9, 20.1, 21.1** pts/h whole-session and **14.6, 22.4, 22.5** pts/h for
the steady middle. The 22.4/22.5 pair looked stable enough on 11-25 to be written down as "the only
stable figure"; 24 hours later the same measurement read **14.6**. A seventh day (11-27) then
produced **20.9, 19.0 and 15.6** in three sessions on the same adapter, at the highest 1-minute load
of the week; an eighth produced **16.3** at a mid-range load. No covariate in this log (time of day,
starting charge, reap activity, load) tracks the spread — 11-24 charged at 21.1 pts/h with a
1-minute load of 1.74 and 11-27 charged at 20.9 with 3.82 — and adapter wattage is deliberately not
read (see [Privacy](#privacy)), so a lower-rated brick or a hub in the path is invisible here.
Treat the column as a **range, not a value**, and do not derive a charging-time estimate from a
single day.


### `ac_plugs = 0` is ambiguous — read `time_ac_h` with it

`ac_plugs` counts transitions **to** AC. Both a day that never left the adapter (2026-11-22:
`0`, 24.3 h AC) and a day with exactly one unplug and no re-plug (2026-11-23: `0`, 9.4 h AC /
16.5 h battery) read `0`. Use the two time columns to tell them apart; their sum should equal
the report interval. 2026-11-28 is a third case of the same `0` — 24.2 h AC, 0.0 h battery — and it
differs from 11-22 in every other column: `topoff_pct` 100 instead of 85, `charge_rate_max` 16.3
instead of 0.0, because one day ran a full charge and the other held a limit. With
`time_batt_h = 0.0` there is no discharge window at all, so no asleep/awake discharge rate is
computable that day — say so rather than dividing by zero.

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

On **2026-11-27** the log finally caught the transition itself. The sequence was: `Charging Completed
Limited` at 09:24:26 with the pack at 85 %, unplug at 10:01:04, **plug in at 10:13:55**, then nine
seconds later

```
2026-11-27 10:14:04.492087  [com.apple.powerd:charging] SOC limit disabled
```

followed by fourteen capacity records climbing 86 → **99 %**, where the pack was unplugged at
11:07:19. `DailyMaxSoc` in `IORegistry` independently reads **99**. So the observable for a lifted
limit is that single line in the `powerd` **`charging`** category — not `batterychargingstate`.

Two cautions, both learned the same day:

- **`SOC limit disabled` also prints on battery**, where the limit is simply not in force and the
  line means nothing. It appeared three times in 24 h — 01:10:37 and 10:10:02 (both on battery),
  10:14:04 (charging). Only the third one is evidence.
- **The value is redacted.** The policy arrives as `received SOC limit from <pid>: <private>` and
  `SOC limit policy:<private>`, so "the OS decided to recalibrate" and "the limit was switched off by
  hand" are indistinguishable from the log. Full charges on 11-19, 11-20, 11-21, then five days at
  85, then 11-27 fits a six-day recalibration cadence — but a cadence inferred from four points is a
  hypothesis, not a mechanism.

The cost of a lift is measurable for the first time: on 11-27 the pack sat **above 90 % for 3 h 4 m**
(2 h 1 m awake, 1 h 3 m asleep). `LifetimeData.TimeAtHighSoc` in `IORegistry` now has data to compare
against the next one.

**2026-11-28 settled both open questions, and the cadence was the wrong one.** The limit stayed
off: the pack went **55 → 100 %** in 2 h 45 m and the only state post in 24 h read plain
`Charging Completed` — with **no `Limited` suffix at all**. That absence is better evidence than
the `SOC limit disabled` line, which prints on battery too and whose value is redacted. So read
`topoff_pct = 100` with a missing `Limited` post as "limit off", and `topoff_pct = 85` with a
`Limited` post as "limit on".

The proposed six-day recalibration cadence (`11-19/20/21 → five days at 85 → 11-27`) predicted
the next full charge around 12-02; it arrived the next day. **Two consecutive full charges is not
a cadence**, and the four-point hypothesis is withdrawn. `SOC limit disabled` is a state change,
not a schedule — which also means `topoff_pct` cannot be forecast from its own history.

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

**The band is a property of the limited state, not of the pack.** On 2026-11-28 the limit was off
and the machine sat on AC at a reported **100 % for 21 h 25 m** with **no capacity record at all**
— 36 records in 24 h, the last one at 22:55:53 — while `ChargingCurrent` read `0 mA`,
`IsCharging` read `No` and `NotChargingReason` `0x400001`. So:

- **A flat 85 with a `Limited` post** is hysteresis: the charger re-engages at 80.
- **A flat 100 with `Charging Completed`** is charging disabled: the pack is not being topped up
  and there is no band to observe.

The missing 3 points went into the *other* register: `StateOfCharge` reads **97** under a
published `CurrentCapacity` of 100. A flat level therefore never means "nothing happened" — check
which of the two states is in force, and compare `StateOfCharge` before concluding the pack did
not move.

### `charge_sessions` counts posts, not sessions

`powerd` emits each `handleChargingStateUpdate` line **twice** — two log sources carry the same
microsecond timestamp — and it re-asserts the limit state at every maintenance wake. On
2026-11-22 the column read **67** for **34** distinct events: 33 `Charging Completed Limited`
posts (one per dark wake, in step with the 15-minute sleep metronome) plus **one** genuine
`Charging`. So the column is a measure of state-machine activity, not of charging. Read it
alongside `ac_plugs`; when `ac_plugs = 0` there cannot have been more than one session no matter
what this number says.

The inflation is specific to the **limited** state: on 2026-11-28, with the limit off, the column
read **1** for one session across 24.2 h on AC and eleven hours of sleep. So a large
`charge_sessions` under a small number of real sessions is itself evidence that a charge limit is
in force — the re-assertion, not the charging, is what generates the posts.

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

**A release can take two files at once.** At **21:55:12 on 11-26** `/System/Volumes/VM`'s mtime
moved and *both* `swapfile2` and `swapfile3` disappeared, taking the pool from 4 096 MB back to
**2 048 MB** — ten minutes after the 21:44:30 reap burst began (100 idle kills, 21:44:30 →
21:46:10) and inside a 15-minute sampler gap in which swap used fell **2 629 → 1 026 MB**. So the
pool follows the **working set**, in both directions, on a scale of minutes:

| Day | Change | Trigger | Ordering |
|---|---|---|---|
| 11-22 | 2 048 → 3 072 | `swapfile2` born | not established |
| 11-23 | 3 072 → 2 048 | `swapfile2` deleted | file entirely unused |
| 11-25 | 2 048 → 3 072 | `swapfile2` re-born | 14 min after a plug-in, inside a burst |
| 11-26 | 3 072 → 4 096 | `swapfile3` born | inside an eviction |
| **11-27** | **4 096 → 2 048** | **both extra files deleted** | **10 min after a reap burst** |
| **11-28** | **2 048 → 2 048** | **no change** | pool held a second day; no ~13:00 growth |

**But a reap does not imply a release.** On 2026-11-28 the machine ran the same 100-kill episode
(18:22:27 → 18:24:06) and the pool **did not move** — `/System/Volumes/VM` kept its 11-27 21:46
mtime and `swap_used_mb` fell only 209 MB, of which 47 MB was paged in and 0 MB written out. So the
reaper is *sometimes* the visible half of a refit (11-27) and sometimes an event with no visible
consequence at all (11-28). The 100-kills-in-100-seconds shape is now two for two and looks like a
**cap plus a 1-second pacer**; what fires it is still unknown.

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

**The plug explanation survived four days and then failed its null test.** On 2026-11-28 there was
**no power transition of any kind** in 24.2 h — `AC_PLUGS = 0`, an empty `Settings change for power
source` grep over 15 968 `powerd` lines — and the same **eight `SFA-*` payloads** still arrived, at
19:35:13–17. Four coincidences (10 s, 10 s, 10 s, 8 s after a plug) are not a mechanism; the plug
was a covariate of days on which the machine was being plugged in at all. The burst's real trigger
is unknown, and the honest description is "a burst of 6–10 files a few seconds wide, at a time this
log has not predicted".

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

**`present` is not the same as "all day".** The stores came back on 2026-11-27 with *birth* times of
15:46:23 (system) and 19:39:23 (user), and every file in them dated from 19:39 — no backfill, no
recovery of the 11-26 window. A store that is 31 minutes old can only report on 31 minutes, so
`present` converts *unknown* into *known-partial*, not into *known-clean*:

```
stat -f "birth=%SB mtime=%Sm %N" ~/Library/Logs/DiagnosticReports
```

Check the birth time alongside `DIAG_STORE`, and state the covered window in the report rather than
the interval. The re-creation was itself done by the post-plug-in `.diag` burst — the same eight
`SFA-*` payloads that appear in `DIAG_24H` are what re-materialised the directory.

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

**But the two do not always both exist.** On 2026-11-28 the kernel stream recorded **two**
`per-process-limit` reaps (22:26:45 and 17:53:02) while `JETSAM_24H` read **0**, because the system
store was rebuilt at **19:51:33** — after both events — and took their reports with it:

| Event | Kernel record | `.ips` |
|---|---|---|
| `per-process-limit` #1 | 11-27 22:26:45, 15 360 KB, 597 782 pages avail. | **destroyed with the old store** |
| `per-process-limit` #2 | 11-28 17:53:02, 15 792 KB, 585 594 pages avail. | **destroyed with the old store** |

So `JETSAM_24H` is a count of **survivors**, not of events, and on a day with two store rebuilds it
is close to meaningless. The kernel line is the durable record: it lives in the unified log, needs
no directory to exist, and carries the available-pages figure the `.ips` was wanted for. Read the
zero as "no report survived" and quote the kernel count alongside it.

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

A store that reappears is **not** a store that came back. On 2026-11-27 `/var/log/powermanagement`
existed again (directory mtime 14:34) but its oldest record was **15:55:30** — 3 h 3 m of a 24.1 h
interval, 12.6 %. The eleven hours of 11-26 that the deletion destroyed were destroyed; the recovery
is always forward-only. Read `pmset -g log | head -3` for the first record, never `ls` alone, and
when the coverage is that thin say so in the header rather than in a footnote.

Retention across seven consecutive runs: **14.4 h → 7.7 h → 35.6 h → 59.7 h → empty → 3 h →
8.5 h**. There is no trend to design around, which is the practical argument for taking sleep
accounting from `sleepWake` every day instead of choosing per run. On 2026-11-28 the 8.5 hours were
enough for the best cross-check in the archive — **5 of 5** blocks matching to within 0.3 s — while
still leaving the night, 65 % of the interval, outside the store's reach.

### A boot epoch cannot drift

`kern.boottime` was quoted as `1793971474` on 11-18 and `1793971475` on 11-19 and 11-26, then read
`1793971472` on 11-28 — with uptime rising by exactly 1.0 d across every one of those runs and no
reboot in any stream. A boot time cannot move three seconds without a restart, so the earlier
figures were **derived** (`now - uptime`) rather than read from the register: an arithmetic result
with the same number of digits looks exactly like a register read, and a 3-second error hides in a
figure nobody checks. `sysctl -n kern.boottime` is the only correct source; convert it to a date
with `date -r <sec>` rather than subtracting uptime.

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
