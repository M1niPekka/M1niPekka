"""System-level controls: volume, screenshots, lock/sleep, battery, processes."""

import subprocess
from datetime import datetime
from pathlib import Path

import psutil


def set_volume(level: int) -> str:
    level = max(0, min(100, level))
    subprocess.run(["osascript", "-e", f"set volume output volume {level}"], check=False)
    return f"Volume set to {level}."


def get_volume() -> str:
    result = subprocess.run(
        ["osascript", "-e", "output volume of (get volume settings)"],
        capture_output=True, text=True,
    )
    return f"Volume is at {result.stdout.strip()}."


def take_screenshot(save_dir: str = "~/Desktop") -> str:
    out_dir = Path(save_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    result = subprocess.run(["screencapture", str(filename)], capture_output=True, text=True)
    if result.returncode != 0:
        return f"Screenshot failed: {result.stderr.strip()}"
    return f"Saved screenshot to {filename}."


def lock_screen() -> str:
    subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to keystroke "q" using {control down, command down}'],
        check=False,
    )
    return "Screen locked."


def sleep_mac() -> str:
    subprocess.run(["pmset", "sleepnow"], check=False)
    return "Going to sleep."


def get_battery() -> str:
    battery = psutil.sensors_battery()
    if battery is None:
        return "No battery information available."
    status = "charging" if battery.power_plugged else "not charging"
    return f"Battery is at {battery.percent}% and {status}."


def list_processes(limit: int = 10) -> str:
    procs = sorted(
        psutil.process_iter(["pid", "name", "cpu_percent"]),
        key=lambda p: p.info.get("cpu_percent") or 0,
        reverse=True,
    )[:limit]
    lines = [f"{p.info['pid']}: {p.info['name']} ({p.info.get('cpu_percent') or 0:.1f}% CPU)" for p in procs]
    return "\n".join(lines) if lines else "No processes found."


def kill_process(name_or_pid: str) -> str:
    killed = []
    for proc in psutil.process_iter(["pid", "name"]):
        if name_or_pid.isdigit():
            if proc.info["pid"] == int(name_or_pid):
                proc.kill()
                killed.append(str(proc.info["pid"]))
        elif name_or_pid.lower() in (proc.info["name"] or "").lower():
            proc.kill()
            killed.append(proc.info["name"])
    if not killed:
        return f"No process matching '{name_or_pid}' found."
    return f"Killed: {', '.join(killed)}."
