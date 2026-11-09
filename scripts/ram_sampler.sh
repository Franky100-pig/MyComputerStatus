#!/bin/bash
# RAM sampler for the MyComputerStatus daily log.
# Appends one CSV line per run. Local only - never pushed.
set -u
OUT="$HOME/.local/share/mcs/ram.csv"
PG=$(sysctl -n hw.pagesize 2>/dev/null || echo 16384)
TOT=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
VM=$(vm_stat 2>/dev/null)
g() { echo "$VM" | awk -F: -v k="$1" '$1 ~ k {gsub(/[ .]/,"",$2); print $2; exit}'; }
A=$(g 'Pages active'); W=$(g 'Pages wired'); C=$(g 'Pages occupied by compressor')
[ -z "$A" ] && exit 0
USED_PCT=$(echo "scale=1; ($A+$W+$C)*$PG*100/$TOT" | bc)
USED_GB=$(echo "scale=2; ($A+$W+$C)*$PG/1073741824" | bc)
COMP_GB=$(echo "scale=2; $C*$PG/1073741824" | bc)
SWAP=$(sysctl -n vm.swapusage | awk -F'used = ' '{print $2}' | awk '{print $1}' | tr -d 'M')
[ -f "$OUT" ] || echo "epoch,iso,used_gb,used_pct,compressor_gb,swap_mb" > "$OUT"
printf '%s,%s,%s,%s,%s,%s\n' "$(date +%s)" "$(date '+%Y-%m-%dT%H:%M:%S')" "$USED_GB" "$USED_PCT" "$COMP_GB" "$SWAP" >> "$OUT"
