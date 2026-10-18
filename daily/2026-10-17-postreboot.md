# Daily Computer Status — 2026-10-17 (post-reboot verification)

> Snapshot captured at **2026-10-18 11:25:02 CST** (GMT+8), **14 h 10 min after a restart**.
> MacBook Air (Mac16,12) · Apple M4 · 16 GB · macOS 26.5 (25F71)

> **Redaction policy:** this report contains **no computer name, no IP addresses and no
> process / application names** by design. See [Privacy](../README.md#privacy); for the
> unredacted local view run `python3 scripts/show_names.py`.

> **Why this file exists:** yesterday's [2026-10-17](2026-10-17.md) report was 🔴 and recommended a
> restart. The machine **was restarted at 21:15:23 that evening — 12 minutes later**. This is the
> verification reading, following the same convention as
> [2026-10-07-postreboot](2026-10-07-postreboot.md). It carries **no new `history.csv` row** — the
> one-row-per-day invariant holds, and 2026-10-17 is already recorded.

## TL;DR

| Area | Status | Notes |
|---|---|---|
| Overall | 🟢 **Recovered** | **The reboot fixed the thing that was actually broken.** Swap pool **7 168 → 1 024 MB**, swap used **6 410 → 122.56 MB**, swap traffic collapsed **~17× / 21×**, and the Jetsam/panic count is zero. But — see the surprise below |
| Surprise | ⚠️ **Reframe** | The compressor is back at **6.46 GB** and RAM at **75.1 %** after only 14 h. The reboot did **not** lower them. That means ~7 GB compressed / ~75 % RAM is this machine's **steady state**, not decay — and my "compressor ≥ 5–7 GB" escalation line was over-weighted. The real discriminator is swap **traffic** |
| Battery | 🟢 Normal | 82 %, AC attached, *not charging* (optimized hold). Cycles **105** (unchanged), 91 % max capacity, Normal, 30.7 °C |
| RAM | 🟡 Watch | 12.03 GB / 16 GB (**75.1 %**), compressor **6.46 GB**, system-wide free **43 %** — but with swap almost unused |
| CPU | 🟢 Normal | Load 2.81 / 2.39 / 2.31 across 10 cores (≈ 28 %) |
| Thermal | 🟢 Normal | No thermal or performance warnings |
| Disk | 🟢 Normal | **266 GB (62 %), 169 GB free** — **−11 GB**, the largest single-day drop in the log (purgeable reclamation at boot) |
| Crashes | 🟢 Clean | **0 panics · 0 Jetsam · 0 `.diag`** retained since the restart |

---

## 1. What the restart changed

| Metric | 2026-10-17 21:03 (pre-reboot) | 2026-10-18 11:25 (post-reboot) | Change |
|---|---|---|---|
| Uptime | 9 d 23 h 49 m | **14 h 10 m** | reboot at 2026-10-17 21:15:23 |
| Swap pool | 7 168 MB | **1 024 MB** | **↓↓ −6 144 MB** |
| Swap used | 6 410.06 MB (89 %) | **122.56 MB (12 %)** | **↓↓ −6 287 MB** |
| Swapins / Swapouts (since boot) | 1 827 492 / 3 167 355 pg | **11 798 / 30 924 pg** | counter reset by reboot |
| Swap traffic, normalised to 24 h | **+5.01 / +9.97 GB** | **+0.30 / +0.80 GB** | **~17× / 21× lower** |
| Jetsam events | **1** (16:53:46, compressor 6.99 GB) | **0** | — |
| RAM used | 12.38 GB (77.4 %) | **12.03 GB (75.1 %)** | barely moved |
| Compressor | 6.81 GB | **6.46 GB** | **barely moved** |
| System-wide free | 32 % | **43 %** | ↑ |
| Disk used | 277 GB (65 %) | **266 GB (62 %)** | **−11 GB** |

**The swap numbers are the story.** The pool reset from a swollen **7 168 MB** back to **1 024 MB** —
which is worth a correction to something this log has repeated for a week: I had been calling
**2 048 MB** "the floor". It is not. The kernel resets to **1 024 MB** when given a clean slate, so
the machine had been running with **7×** its minimum swap allocation. Usage fell with it: 6.41 GB →
**122.56 MB**, 89 % of the pool → 12 %.

**Traffic is the decisive proof, because it is independent of the reboot's counter reset.** Since
boot the machine has paged in **0.18 GB** and out **0.47 GB** over 14.2 h. Scaled to a day that is
**+0.30 / +0.80 GB** — against **+5.01 / +9.97 GB** in the 24 h before the restart, and **+5.25 /
+10.43 GB** on the 10-14 record day. That is a **17× / 21× reduction** on the metric that actually
matters. Zero Jetsam, zero panics, zero `.diag` since boot.

## 2. The surprise — and a correction to my own escalation rule

**The compressor came back within 14 hours.** It is **6.46 GB** now, essentially where it was before
the restart (**6.81 GB**). RAM is **75.1 %** versus 77.4 %. Free memory is again thin at **0.12 GB**.

Read that carefully: a restart clears compressed pages instantly, so this **6.46 GB was rebuilt from
nothing in 14 hours**. The machine is not slowly accumulating garbage over ten days — it genuinely
holds about **12 GB of working set** and compresses ~6.5 GB of it to fit into 16 GB. Active (3.26) +
wired (2.31) + compressed (6.46) ≈ 12.0 GB, with almost nothing free.

**That means the "compressor ≥ 5 GB → ≥ 7 GB" line I have been escalating on is a weak signal on its
own.** It returns within a day regardless of machine health. Yesterday's 🔴 was still correct — all
four triggers fired, and the Jetsam plus the record swap flow plus the pool breaking its ceiling were
real and mutually confirming — but the *compressor* component of that rule deserves less weight than
the report gave it. **The honest discriminator is swap traffic and pool size**, because those are the
ones that separate "compressing to fit" (fine) from "paging to disk" (not fine). Recorded here so the
next report does not repeat the over-weighting, and so this reading is not mistaken for a relapse.

**Going forward:** a high compressor with near-zero swap flow is **🟢 normal for this workload**.
Escalate on **Jetsam, swap traffic ≥ ~2 GB/24 h, or pool growth past ~2 GB** — not on the compressor
number alone.

## 3. Battery

| Metric | Value |
|---|---|
| Charge | **82 %** (AC attached, **not charging**) |
| Power source | AC Power — **fourth consecutive day on the adapter** |
| Cycle count | **105** (design = 1 000) — **unchanged** |
| Max capacity | **91 %** (design 4 629 mAh; nominal 4 000 mAh) |
| Condition | **Normal** |
| Battery temperature | 30.7 °C |
| Gauge-reported daily band | **77 % → 87 %** (gauge-derived) |

Nothing to do here. The pack sits in the optimized-charging hold band (drifts 87 → 77 → back up),
cycle count flat at **105**, health flat at **91 %**. The restart did not touch battery state.

> **⚠️ `pmset -g log` retention has collapsed again — now ~27 minutes** (earliest retained
> **10:58:05**, and **0** usable `Charge:` readings for the date). The 77 → 87 % band is from the
> gauge's `DailyMinSoc` / `DailyMaxSoc` and is approximate. Fifth consecutive short window.

## 4. Disk — the −11 GB is purgeable, and it explains the last three readings

| Metric | Value |
|---|---|
| Used | **266 GB (62 %)** |
| Available | **169 GB** |
| Container free (incl. purgeable) | 181.2 GB |
| Local Time Machine snapshots | none |
| SSD SMART | **Verified** ✅ |

**−11 GB, the largest single-day drop in the log.** With no local snapshots present and container free
space at 181.2 GB against 169 GB reported available, this is **purgeable space being reclaimed at
boot** — not user data being deleted.

That closes a loose end from the last two reports: 10-16 showed **+7 GB** ("unexplained"), 10-17 showed
**−5 GB**, and now **−11 GB**. All three are the same phenomenon — APFS/purgeable accounting moving
around, not real consumption. The underlying trend is flat-to-slowly-rising (271 GB a week ago →
266 GB now). **Disk is not a concern; stop flagging single-day jumps.**

## 5. System

| Field | Value |
|---|---|
| Model | MacBook Air `Mac16,12` · Apple M4 · 10 cores · 16 GB |
| OS | macOS 26.5 (build 25F71) |
| Uptime | **14 h 10 m** — booted **2026-10-17 21:15:23**, a **clean restart** (0 panic reports) |
| Network | Wi-Fi active (`en0`) — **addresses not recorded** |

---

## Actions / Observations

1. 🟢 **The restart worked, on the axis that mattered.** Swap pool 7 168 → 1 024 MB, swap used
   6 410 → 123 MB, traffic down **17–21×**, and no Jetsam since. Nothing further is needed — the
   machine is in its healthy steady state.
2. ⚠️ **Correction carried forward: stop escalating on the compressor number alone.** It rebuilt to
   **6.46 GB in 14 hours**, which proves it is workload, not decay. Escalate on **Jetsam**, **swap
   traffic ≥ 2 GB/24 h**, or **pool growth past ~2 GB**. Also correct the "2 048 MB floor" claim —
   the true floor is **1 024 MB**.
3. 🟢 **Battery: no action.** 82 %, AC, holding in the optimized band, cycles flat at 105.
4. 🟢 **Disk: no action, and the recent jumps are explained.** −11 GB is purgeable reclamation at
   boot; combined with the earlier +7 / −5 GB readings this was never real growth.
5. 🟢 **0 panics · 0 Jetsam · 0 `.diag`** — the diagnostics store was recreated empty at 11:18 today,
   so these zeros are again absence-of-evidence, but they are consistent with the quiet swap flow.
6. ℹ️ **What to watch next.** The real test of the 10-17 🔴 is whether the **pool stays near 1 GB**. If
   it climbs back toward 5–7 GB on a machine that is only days old, that is genuine growth and a
   different finding from uptime accumulation. Otherwise this closes the incident.

---

*Generated automatically. Raw metrics: [`data/history.csv`](../data/history.csv) · Collector: [`scripts/collect.sh`](../scripts/collect.sh)*
