# Post-Reboot Verification — 2026-10-07

> Second reading of the day, taken **22:06:32 CST** (GMT+8) — ~52 min after the machine was
> **restarted at 21:14:48**. MacBook Air (Mac16,12) · Apple M4 · 16 GB · macOS 26.5 (25F71)

This is a **separate log**, not a replacement for the day's main snapshot
([`2026-10-07.md`](2026-10-07.md), taken at 18:20). It exists to confirm whether the reboot that
the 18:20 report recommended actually cleared the memory pressure.

> **Redaction policy:** no computer name, no IP addresses and no process / application names.
> See [Privacy](../README.md#privacy). For the unredacted local view run
> `python3 scripts/show_names.py`.

## TL;DR

| Area | Status | Notes |
|---|---|---|
| Overall | 🟢 Clean | Reboot fully landed — swap reset to **0 MB**, compressor halved, ~22 GB of disk reclaimed |
| Battery | 🟢 Healthy | 86 %, on AC (optimized-charging hold), 100 cycles, 91 % max capacity, Normal |
| RAM | 🟢 Normal | 9.40 GB / 16 GB (58.7 %, down from 74.0 %), compressor 2.45 GB, **swap 0 MB** |
| CPU | 🟡 Post-boot load | Load 2.93 / 2.74 / 3.03 (~30 % of 10 cores) — expected reindex/startup churn |
| Thermal | 🟢 Normal | No thermal or performance warnings |
| Disk | 🟢 Healthy | 250 / 460 GB used (58 %), 186 GB free, SSD SMART verified |
| Anomalies | 🟢 Clean | 0 kernel panics · 0 Jetsam events in the last 24 h |

---

## 1. Before → after

| Metric | 18:20 (pre-reboot) | 22:06 (post-reboot) | Change |
|---|---|---|---|
| Uptime | 21 days 3 h | **52 min** | reset at 21:14:48 |
| Swap used | 3 850 / 5 120 MB (75.2 %) | **0 / 0 MB** | **−3 850 MB** ✅ |
| Compressor | 5.69 GB | **2.45 GB** | −3.24 GB |
| RAM used | 11.83 GB (74.0 %) | **9.40 GB (58.7 %)** | −2.43 GB / −15.3 pp |
| System-wide free (`memory_pressure`) | 46 % | **71 %** | +25 pp |
| Disk used | 272 GB (64 %) | **250 GB (58 %)** | **−22 GB** |
| Disk free | 159 GB | **186 GB** | +27 GB |
| Jetsam events (24 h) | 1 | **0** | ✅ |
| Battery charge | 85 % | 86 % | — |
| Battery cycles / max cap | 100 / 91 % | 100 / 91 % | unchanged |
| Load average (1/5/15 m) | 2.76 / 2.31 / 2.22 | 2.93 / 2.74 / 3.03 | post-boot churn |
| Kernel panics | 0 | 0 | — |

**The intervention worked.** Not only did the swap pool drain completely (macOS did not even need
to re-create the swap file — `total = 0.00M`), the compressor footprint shrank by more than half.
That was exactly the outcome the 18:20 report was aiming for.

The extra ~22 GB of disk is the standard post-reboot release of local APFS snapshots and
purgeable space — not something the reboot "deleted" from the user's files.

## 2. Memory (RAM)

| Metric | Value |
|---|---|
| Physical | 16.00 GB |
| Active | 5.07 GB |
| Wired | 1.87 GB |
| Compressed (compressor) | **2.45 GB** (160 793 pages) |
| **Used (active + wired + compressed)** | **≈ 9.40 GB → 58.7 %** |
| Free / reclaimable | 0.44 GB free + 5.52 GB inactive = **5.97 GB (37.3 %)** |
| Swap | **0.00 MB / 0.00 MB** — untouched since boot |
| System-wide free % (`memory_pressure`) | **71 %** |

Note the shape of the change: *active* memory is actually higher than before the reboot
(5.07 vs 3.51 GB) because pages that had been squeezed into the compressor are now resident
normally. The real win is the compressor dropping 5.69 → 2.45 GB and swap going to zero.

## 3. Battery

| Metric | Value |
|---|---|
| Charge | **86 %** (internal absolute SoC 81 %) |
| Power source | **AC attached**, not charging — optimized-charging hold |
| Cycle count | **100** (design = 1 000) |
| Max capacity | **91 %** (raw 3 990 / 4 629 mAh ≈ 86.2 %) |
| Condition | **Normal** (`PermanentFailureStatus = 0`) |
| Battery temperature | 30.5 °C |
| Today's SoC band | min 79 % · max 89 % — normal for optimized charging |

Raw max capacity ticked 4 014 → 3 990 mAh since the morning reading. That is ~0.6 % and sits
inside normal gauge noise, not a trend.

## 4. CPU & Thermal

- Load average **2.93 / 2.74 / 3.03** across 10 cores → ~30 %. Elevated relative to the quiet
  18:20 load (2.76 / 2.31 / 2.22) and expected: a reboot restarts indexing, cloud-sync daemons
  and login items all at once. It should settle over the next hour.
- Thermal: no thermal warning level, no performance warning level — no throttling.
- Per-process detail is **not collected** (opt-in; see [Privacy](../README.md#privacy)).

## 5. Disk & Storage

| Metric | Value |
|---|---|
| Volume | 460 GB (APFS, `APPLE SSD AP0512Z`) |
| Used | **250 GB (58 %)** |
| Available | **186 GB** |
| SSD SMART | **Verified** ✅ |

## 6. Anomalies

- **Kernel panics:** none ✅
- **Jetsam (memory-pressure) events in the last 24 h:** **0** ✅ — the previous day's events are
  no longer counted because macOS **purged `/Library/Logs/DiagnosticReports` at 21:48**, which
  removed every earlier `.ips` / `.diag` file (including both Jetsam events and the third-party
  resource diagnostics). The directory now holds a single new report from an **Apple system
  file-copy utility**, timestamped 21:48 — a benign post-boot resource sample.
- **Third-party app crashes:** none ✅

> Because the diagnostic store was cleared, the earlier Jetsam/`.diag` findings can no longer be
> re-read locally. Their substance was already captured in [`2026-10-07.md`](2026-10-07.md).

## 7. System

| Field | Value |
|---|---|
| Model | MacBook Air `Mac16,12` · Apple M4 · 10 cores · 16 GB |
| OS | macOS 26.5 (build 25F71) |
| Uptime | **52 min** (booted 2026-10-07 21:14:48) |
| Network | Wi-Fi active (`en0`) — **addresses not recorded** |

---

## Actions / Observations

1. 🟢 **Nothing to do.** The reboot cleared swap entirely and cut the compressor by more than
   half; memory pressure is back to a healthy baseline.
2. ℹ️ **Give it an hour.** Post-boot load (~3.0 on 10 cores) is startup churn — reindexing and
   login items — and will settle on its own.
3. ℹ️ **Diagnostic history is gone.** macOS pruned the diagnostic reports at 21:48; the old
   Jetsam evidence is no longer on disk.
4. ℹ️ **This entry is not in `data/history.csv`.** The CSV keeps a strict one-row-per-day
   invariant; the post-reboot numbers live in this file only. Say the word if you want
   same-day extra readings appended as separate rows.

---

*Generated automatically. Raw metrics: [`data/history.csv`](../data/history.csv) · Collector: [`scripts/collect.sh`](../scripts/collect.sh)*
