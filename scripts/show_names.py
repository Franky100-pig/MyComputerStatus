#!/usr/bin/env python3
"""show_names.py - LOCAL-ONLY, unredacted view of this Mac.

The published daily log (`scripts/collect.sh` -> `daily/*.md` +
`data/history.csv`) is deliberately anonymous: no computer name, no network
addresses, no serial number, no process or application names.

This script is the opposite of that. It surfaces exactly the things the log
leaves out:

  * computer name / local host name / host name
  * hardware model, chip, memory and **full serial number**
  * every active network interface with its IPv4 / IPv6 addresses, the default
    gateway and the current Wi-Fi network name
  * the top processes by CPU and by memory, with their real names
  * the same battery / RAM / disk / thermal numbers the daily log records

It is NOT part of the automated run. Nothing calls it, nothing schedules it, it
writes no files, and it changes no system state. It just prints to stdout.

Usage:
    python3 scripts/show_names.py              # everything
    python3 scripts/show_names.py --no-procs   # skip the per-process tables

    !!! The output contains identifying information. Do NOT commit it, paste it
    !!! into the public repo, an issue, a gist or any public place.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime

BANNER = (
    "=" * 72 + "\n"
    "!! LOCAL-ONLY OUTPUT - contains identifying information\n"
    "!! (computer name, serial number, network addresses, process names).\n"
    "!! Never commit this, never paste it into the public repo.\n"
    + "=" * 72
)


def sh(*cmd: str) -> str:
    """Run a command and return stripped stdout ('' on any failure)."""
    if not shutil.which(cmd[0]):
        return ""
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True, timeout=25)
    except Exception:
        return ""
    return (r.stdout or "").strip()


def section(title: str) -> None:
    print(f"\n## {title}\n")


def kv(label: str, value: str) -> None:
    if value:
        print(f"  {label:<28} {value}")


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


# ---------------------------------------------------------------- identity --
def show_identity() -> None:
    section("Identity & hardware")
    kv("Computer name", sh("scutil", "--get", "ComputerName"))
    kv("Local host name", sh("scutil", "--get", "LocalHostName"))
    kv("Host name", sh("scutil", "--get", "HostName") or "(unset)")

    prof = sh("system_profiler", "SPHardwareDataType")
    wanted = {
        "Model Name": "Model name",
        "Model Identifier": "Model identifier",
        "Chip": "Chip",
        "Total Number of Cores": "CPU cores",
        "Memory": "Memory",
        "Serial Number (system)": "SERIAL NUMBER",
        "Hardware UUID": "Hardware UUID",
    }
    for key, label in wanted.items():
        m = re.search(rf"^\s*{re.escape(key)}:\s*(.+)$", prof, re.MULTILINE)
        if m:
            kv(label, m.group(1).strip())
    kv("macOS", f"{sh('sw_vers', '-productVersion')} ({sh('sw_vers', '-buildVersion')})")


# ----------------------------------------------------------------- network --
def show_network() -> None:
    section("Network")
    default_if = ""
    gw = ""
    route = sh("route", "-n", "get", "default")
    m = re.search(r"^\s*interface:\s*(\S+)", route, re.MULTILINE)
    if m:
        default_if = m.group(1)
    m = re.search(r"^\s*gateway:\s*(\S+)", route, re.MULTILINE)
    if m:
        gw = m.group(1)
    kv("Default interface", default_if)
    kv("Default gateway", gw)

    ifaces = [i for i in sh("ifconfig", "-l").split() if i != "lo0"]
    for iface in ifaces:
        info = sh("ifconfig", iface)
        v4 = re.findall(r"\binet (\d+\.\d+\.\d+\.\d+)(?:\s+netmask\s+(\S+))?", info)
        v6 = re.findall(r"\binet6 ([0-9a-fA-F:]+)%?\S*", info)
        status = "active" if re.search(r"^\s*status: active", info, re.MULTILINE) else "inactive"
        addrs = [a[0] for a in v4] + v6
        if addrs:
            kv(f"{iface} ({status})", ", ".join(addrs))
    ssid = sh("networksetup", "-getairportnetwork", "en0")
    if "Current Wi-Fi Network:" in ssid:
        kv("Wi-Fi network (SSID)", ssid.split("Current Wi-Fi Network:", 1)[1].strip())


# ------------------------------------------------------------------- power --
def show_power() -> None:
    section("Battery & power")
    kv("pmset", sh("pmset", "-g", "batt").replace("\n", " | "))
    batt = sh("ioreg", "-r", "-c", "AppleSmartBattery")
    for key, label, div in (
        ("CycleCount", "Cycle count", 1),
        ("DesignCapacity", "Design capacity", 1),
        ("AppleRawMaxCapacity", "Raw max capacity", 1),
        ("Temperature", "Temperature (C)", 100),
    ):
        m = re.search(rf'"{key}"\s*=\s*(\d+)', batt)
        if m:
            val = int(m.group(1)) / div
            kv(label, f"{val:.1f}" if isinstance(val, float) else str(val))
    kv("Condition", sh("system_profiler", "SPPowerDataType").split("Condition: ")[-1].split("\n")[0] if "Condition: " in sh("system_profiler", "SPPowerDataType") else "")


# ------------------------------------------------------------------ memory --
def show_memory() -> None:
    section("Memory")
    vm = sh("vm_stat")
    page = 16384
    m = re.search(r"page size of (\d+) bytes", vm)
    if m:
        page = int(m.group(1))

    def pages(label: str) -> int:
        mm = re.search(rf"^{re.escape(label)}:\s*([\d.]+)", vm, re.MULTILINE)
        return int(mm.group(1).replace(".", "")) if mm else 0

    free = pages("Pages free")
    active = pages("Pages active")
    inactive = pages("Pages inactive")
    wired = pages("Pages wired down")
    comp = pages("Pages occupied by compressor")
    for label, val in (
        ("Active", active), ("Wired", wired), ("Compressed", comp),
        ("Inactive", inactive), ("Free", free),
    ):
        kv(label, f"{human_bytes(val * page)}  ({val:,} pages)")
    kv("Used (act+wire+comp)", human_bytes((active + wired + comp) * page))
    kv("vm.swapusage", sh("sysctl", "-n", "vm.swapusage"))


# -------------------------------------------------------------------- disk --
def show_disk() -> None:
    section("Disk")
    df = sh("df", "-h", "/System/Volumes/Data").splitlines()
    if len(df) > 1:
        kv("Data volume", df[-1])
    kv("SMART", sh("diskutil", "info", "disk0").split("SMART Status:")[-1].split("\n")[0].strip() if "SMART Status:" in sh("diskutil", "info", "disk0") else "")


# ------------------------------------------------------------------ system --
def show_system() -> None:
    section("System")
    boot = sh("sysctl", "-n", "kern.boottime")
    m = re.search(r"sec = (\d+)", boot)
    if m:
        epoch = int(m.group(1))
        booted = datetime.fromtimestamp(epoch)
        up = datetime.now() - booted
        hours = up.total_seconds() / 3600
        kv("Booted", booted.strftime("%Y-%m-%d %H:%M:%S"))
        kv("Uptime", f"{hours:.2f} h ({hours / 24:.2f} days)")
    kv("Load average", sh("sysctl", "-n", "vm.loadavg"))
    kv("CPU cores", sh("sysctl", "-n", "hw.ncpu"))
    therm = sh("pmset", "-g", "therm")
    kv("Thermal", "no warnings" if "No thermal warning level" in therm else therm.replace("\n", " | "))


# --------------------------------------------------------------- processes --
def show_processes() -> None:
    section("Processes - top 12 by CPU")
    out = sh("ps", "-Ao", "pid,pcpu,pmem,rss,comm", "-r")
    if out:
        for line in out.splitlines()[:13]:
            print(f"  {line.rstrip()}")
    else:
        print("  (ps unavailable in this context)")

    section("Processes - top 12 by memory")
    out = sh("ps", "-Ao", "pid,pcpu,pmem,rss,comm", "-m")
    if out:
        for line in out.splitlines()[:13]:
            print(f"  {line.rstrip()}")
    else:
        print("  (ps unavailable in this context)")

    section("Application bundles currently running")
    apps = sh("osascript", "-e",
              'tell application "System Events" to get name of every process whose background only is false')
    if apps:
        for name in sorted(a.strip() for a in apps.replace("\n", ",").split(",") if a.strip()):
            print(f"  - {name}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Local-only unredacted view of this Mac. Prints identifying info - do not publish.")
    ap.add_argument("--no-procs", action="store_true",
                    help="skip the per-process sections (names, CPU, memory)")
    args = ap.parse_args()

    print(BANNER)
    print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")

    show_identity()
    show_network()
    show_power()
    show_memory()
    show_disk()
    show_system()
    if not args.no_procs:
        show_processes()

    print("\n" + BANNER)
    print("\nReminder: this is a local diagnostic only. The published daily log stays\n"
          "anonymous because it is produced by scripts/collect.sh, which never emits\n"
          "names, addresses or serials.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
