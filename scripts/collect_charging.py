#!/usr/bin/env python3
"""collect_charging.py - Summarise the last N hours of charging behaviour from the power log.

Emits KEY=VALUE lines, same contract as `collect.sh`, so both can be piped into
`append_csv.py`. Read-only, no sudo, and none of the keys can carry identifying data:
this script only ever looks at charge percentages, power-source transitions and
timestamps. It never reads a charger name, serial or port path.

Usage:
    python3 scripts/collect_charging.py                  # last 24 h
    python3 scripts/collect_charging.py --hours 48
    python3 scripts/collect_charging.py --from-file dump.txt   # offline / repeatable

The interesting number is CHARGE_RATE_MAX: the fastest sustained percentage-per-hour
seen in any single AC session. Snapshot percentages in `history.csv` cannot show that,
and it is the figure that tells you whether an adapter is the bottleneck.

NOTE: `log` is called by ABSOLUTE PATH. In zsh, `log` is a shell builtin (it lists
logged-in users), so a bare `log show ...` fails with "too many arguments" and writes
a zero-byte file that looks exactly like a successful empty query.
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime, timedelta

TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\.\d+[+-]\d{4}")
CAP = re.compile(r"Battery capacity change posted\(0x[0-9a-f]+\)\. Capacity:(\d+) Source:(\w+)")
SRC = re.compile(r"Settings change for power source change to (\w+) Power")
STATE = re.compile(r"handleChargingStateUpdate State:([A-Za-z ]+?)  ?VBUS")
COMPLETED = re.compile(r"^Charging Completed")

# A pair of transitions closer together than this is a contact/handshake fault, not
# a deliberate plug. 10 s is deliberately tight: a user unplugging and replugging to
# test takes seconds, but the 11-16 fault toggled four times in eight.
BOUNCE_WINDOW_S = 10


def read_log(hours: int, since: str | None, until: str | None) -> str:
    start = since or (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    cmd = ["/usr/bin/log", "show", "--predicate", 'process == "powerd"',
           "--start", start, "--style", "syslog"]
    if until:
        cmd += ["--end", until]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"collect_charging: log show failed: {out.stderr.strip()[:200]}")
    return out.stdout


def parse(text: str):
    curve, transitions, completed = [], [], []
    for line in text.splitlines():
        m = TS.match(line)
        if not m:
            continue
        try:
            t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        c = CAP.search(line)
        if c:
            curve.append((t, int(c.group(1)), c.group(2)))
            continue
        s = SRC.search(line)
        if s:
            transitions.append((t, s.group(1)))
            continue
        st = STATE.search(line)
        if st and COMPLETED.match(st.group(1)):
            completed.append((t, st.group(1).strip()))
    curve.sort()
    transitions.sort()
    completed.sort()
    return curve, transitions, completed


def summarise(curve, transitions, completed, start=None, end=None):
    if not curve:
        return {}

    # Default to the span the samples actually cover, with a small lead-in so a source
    # change just before the first sample is still counted.
    start = start or curve[0][0] - timedelta(minutes=5)
    end = end or datetime.now()

    # Time on AC vs battery. Assume the source in force at the first sample held
    # before it, so the segment from `start` is not silently dropped.
    # Sources arrive in two spellings - "Batt" on the capacity line, "Battery" on the
    # transition line - so normalise to AC / Battery and never call str.capitalize()
    # on "AC" (it yields "Ac", which silently makes every segment count as battery).
    def norm(s):
        return "AC" if s.upper().startswith("AC") else "Battery"

    # ...but the first sample is NOT a reliable statement about the start of the
    # window. A held charge posts no capacity record at all, so the first record in
    # the dump is often the power-source transition itself - and it reports the
    # source AFTER the switch. On 2026-11-23 that made 9.4 h of AC read as battery
    # (TIME_AC_H 0.0 / TIME_BATT_H 25.9 for an interval that began on AC). A
    # transition to X implies the machine was not on X before it, so when no
    # capacity record predates the first transition, invert that transition.
    first_t = transitions[0] if transitions else None
    if first_t is not None and curve[0][0] >= first_t[0]:
        cur_src = "Battery" if norm(first_t[1]) == "AC" else "AC"
    else:
        cur_src = norm(curve[0][2])

    segments, cur_t = [], start
    for t, src in transitions:
        if t <= start:
            cur_src = norm(src)
            continue
        segments.append((cur_t, t, cur_src))
        cur_t, cur_src = t, norm(src)
    segments.append((cur_t, end, cur_src))

    # Clip to the window before summing. A transition AFTER `until` still opens a
    # segment, and the next (end, ...) one then runs backwards - a sub-window query
    # ending before a plug-in used to report a negative TIME_BATT_H. The daily run
    # always ends at "now", so this only ever bit exact-window queries.
    clipped = [(max(a, start), min(b, end), s) for a, b, s in segments]
    ac_h = sum((b - a).total_seconds() for a, b, s in clipped if s == "AC" and b > a) / 3600
    batt_h = sum((b - a).total_seconds() for a, b, s in clipped if s != "AC" and b > a) / 3600

    # Fastest ramp inside a single AC segment, measured the way the report states it:
    # from the charge level in force at the moment of plugging to the level reached at
    # the end of that session. Using the first in-segment capacity record instead would
    # start the clock a few minutes late (the gauge only updates on percentage change)
    # and overstate the rate.
    rate_max = 0.0
    for a, b, s in segments:
        if s != "AC":
            continue
        pts = [(t, c) for t, c, _ in curve if a <= t <= b]
        if not pts:
            continue
        before = [c for t, c, _ in curve if t <= a]
        start_cap = before[-1] if before else pts[0][1]
        peak_t, peak_c = max(pts, key=lambda p: p[1])
        span_h = (peak_t - a).total_seconds() / 3600
        if span_h > 0 and peak_c > start_cap:
            rate_max = max(rate_max, (peak_c - start_cap) / span_h)

    bounces = sum(
        1 for (t1, _), (t2, _) in zip(transitions, transitions[1:])
        if (t2 - t1).total_seconds() <= BOUNCE_WINDOW_S
    )

    caps = [c for _, c, _ in curve]
    return {
        "AC_PLUGS": sum(1 for _, s in transitions if s == "AC"),
        "CHARGE_SESSIONS": len(completed),
        "TOPOFF_PCT": max(caps),
        "BATT_FLOOR_PCT": min(caps),
        "CHARGE_RATE_MAX": f"{rate_max:.1f}",
        "TIME_AC_H": f"{ac_h:.1f}",
        "TIME_BATT_H": f"{batt_h:.1f}",
        "CHARGER_BOUNCES": bounces,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--since", help="window start, 'YYYY-MM-DD HH:MM:SS' (default: now - hours)")
    ap.add_argument("--until", help="window end, 'YYYY-MM-DD HH:MM:SS' (default: now)")
    ap.add_argument("--from-file", help="parse a saved `log show` dump instead of querying")
    args = ap.parse_args()

    fmt = "%Y-%m-%d %H:%M:%S"
    since = datetime.strptime(args.since, fmt) if args.since else None
    until = datetime.strptime(args.until, fmt) if args.until else None

    text = (open(args.from_file, errors="replace").read() if args.from_file
            else read_log(args.hours, args.since, args.until))
    curve, transitions, completed = parse(text)
    values = summarise(curve, transitions, completed, since, until)
    if not values:
        print("collect_charging: no battery samples in window", file=sys.stderr)
        return 1
    for k, v in values.items():
        print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
