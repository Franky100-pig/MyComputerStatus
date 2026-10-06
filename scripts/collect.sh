#!/bin/bash
# collect.sh - Collect daily macOS health metrics as KEY=VALUE lines.
# Usage: bash scripts/collect.sh
# Designed for macOS Apple Silicon. No sudo required. Read-only.
#
# ANONYMITY GUARANTEE
# -------------------
# This collector NEVER emits identifying data:
#   * no computer name / host name
#   * no IP addresses or other network addresses
#   * no hardware serial numbers or UUIDs
#   * no process names, application names or window titles
# That is structural, not a switch: there is deliberately NO flag that makes it
# leak, because its output is what gets published in `daily/` and
# `data/history.csv`. If you want the unredacted view for yourself, run
# `python3 scripts/show_names.py` (local-only, never part of the daily run).

set -u

PAGE=$(sysctl -n hw.pagesize 2>/dev/null || echo 16384)
TOTAL_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)

kv() { printf '%s=%s\n' "$1" "$2"; }

# bc prints ".4" instead of "0.4" for values below 1 - normalise it.
dec1() { bc 2>/dev/null | sed 's/^\./0./'; }

# ---- Identity / OS (generic hardware only - no host name, no serial) ----
kv DATE "$(date '+%Y-%m-%d')"
kv TIME "$(date '+%H:%M:%S %Z')"
kv MODEL "$(sysctl -n hw.model 2>/dev/null)"
kv CHIP "$(system_profiler SPHardwareDataType 2>/dev/null | awk -F': ' '/Chip|Chipset/{print $2; exit}')"
kv RAM_GB "$(echo "scale=1; $TOTAL_BYTES/1073741824" | bc 2>/dev/null)"
kv OS "$(sw_vers -productVersion) ($(sw_vers -buildVersion))"

# ---- Uptime ----
BOOT=$(sysctl -n kern.boottime | awk -F'[=,]' '{print $2}' | tr -d ' ')
kv BOOT_EPOCH "$BOOT"
kv UPTIME_DAYS "$(echo "scale=1; ($(date +%s)-$BOOT)/86400" | dec1)"

# ---- Load ----
kv LOAD_1M "$(sysctl -n vm.loadavg | awk '{print $2}')"
kv LOAD_5M "$(sysctl -n vm.loadavg | awk '{print $3}')"
kv LOAD_15M "$(sysctl -n vm.loadavg | awk '{print $4}')"
kv CPU_CORES "$(sysctl -n hw.ncpu)"

# ---- Memory ----
VM=$(vm_stat)
pg() { echo "$VM" | awk -F: -v k="$1" '$1 ~ k {gsub(/[ .]/,"",$2); print $2; exit}'; }
FREE=$(pg 'Pages free'); ACTIVE=$(pg 'Pages active'); INACTIVE=$(pg 'Pages inactive')
WIRED=$(pg 'Pages wired'); COMP=$(pg 'Pages occupied by compressor')
for pair in "MEM_FREE_PAGES:$FREE" "MEM_ACTIVE_PAGES:$ACTIVE" "MEM_INACTIVE_PAGES:$INACTIVE" \
            "MEM_WIRED_PAGES:$WIRED" "MEM_COMPRESSOR_PAGES:$COMP"; do
  k=${pair%%:*}; v=${pair#*:}; [ -n "$v" ] && kv "$k" "$v"
done
# Derived GB (2 decimals)
if [ -n "$ACTIVE" ]; then
  kv MEM_USED_GB "$(echo "scale=2; ($ACTIVE+$WIRED+$COMP)*$PAGE/1073741824" | bc 2>/dev/null)"
  kv MEM_USED_PCT "$(echo "scale=1; ($ACTIVE+$WIRED+$COMP)*$PAGE*100/$TOTAL_BYTES" | bc 2>/dev/null)"
fi
kv SWAP_TOTAL_MB "$(sysctl -n vm.swapusage | awk -F'total = ' '{print $2}' | awk '{print $1}' | tr -d 'M')"
kv SWAP_USED_MB "$(sysctl -n vm.swapusage | awk -F'used = ' '{print $2}' | awk '{print $1}' | tr -d 'M')"

# ---- Battery ----
PS=$(pmset -g batt 2>/dev/null)
kv BATTERY_PCT "$(echo "$PS" | grep -o '[0-9]*%' | head -1 | tr -d '%')"
kv BATTERY_SOURCE "$(echo "$PS" | grep -o "'.*'" | head -1 | tr -d "'")"
if echo "$PS" | grep -q "AC attached"; then kv BATTERY_AC attached; fi
BATT=$(ioreg -r -c AppleSmartBattery 2>/dev/null)
kv BATTERY_CYCLES "$(echo "$BATT" | awk -F'= ' '/"CycleCount" =/{gsub(/[^0-9]/,"",$2); print $2; exit}')"
kv BATTERY_TEMP_C "$(echo "$BATT" | awk -F'= ' '/"Temperature" =/{printf "%.1f", $2/100; exit}')"
kv BATTERY_CONDITION "$(system_profiler SPPowerDataType 2>/dev/null | awk -F': ' '/Condition/{print $2; exit}')"
kv BATTERY_MAXCAP_PCT "$(system_profiler SPPowerDataType 2>/dev/null | awk -F': ' '/Maximum Capacity/{print $2; exit}' | tr -d '%')"

# ---- Disk ----
DISK=$(df -k /System/Volumes/Data 2>/dev/null | tail -1)
kv DISK_TOTAL_GB "$(echo "$DISK" | awk '{printf "%.0f", $2/1048576}')"
kv DISK_USED_GB "$(echo "$DISK" | awk '{printf "%.0f", $3/1048576}')"
kv DISK_FREE_GB "$(echo "$DISK" | awk '{printf "%.0f", $4/1048576}')"
kv DISK_USED_PCT "$(echo "$DISK" | awk '{print $5}' | tr -d '%')"
kv SSD_SMART "$(diskutil info disk0 2>/dev/null | awk -F': ' '/SMART Status/{print $2; exit}' | xargs)"

# ---- Thermal ----
if pmset -g therm 2>/dev/null | grep -q "No thermal warning level"; then
  kv THERMAL_WARNING none
else
  kv THERMAL_WARNING "$(pmset -g therm 2>/dev/null | head -1)"
fi

# ---- Anomalies (last 24h) ----
PANICS=$(ls /Library/Logs/DiagnosticReports/*.panic 2>/dev/null | wc -l | tr -d ' ')
kv PANIC_FILES "$PANICS"
# Note: diagnostic file NAMES can embed the host name, so we only count them -
# never print them. Classification (which app / which category) is done by hand
# in the daily report, with the name genericised.
kv JETSAM_24H "$(find /Library/Logs/DiagnosticReports -name 'JetsamEvent-*.ips' -mtime -1 2>/dev/null | wc -l | tr -d ' ')"
kv DIAG_24H "$(find /Library/Logs/DiagnosticReports -maxdepth 1 -name '*.diag' -mtime -1 2>/dev/null | wc -l | tr -d ' ')"

# ---- Process names: NEVER collected ----
# The keys are emitted empty so the CSV schema stays stable. Per-process detail
# is intentionally absent from the published log; use scripts/show_names.py
# locally if you want it.
kv TOP_CPU ""
kv TOP_MEM ""
