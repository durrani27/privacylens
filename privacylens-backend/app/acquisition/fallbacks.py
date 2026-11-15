"""
Tier 3 (manual upload) and Tier 4 (emulator via ADB, last resort).

Iteration 5 (Semester 8) adds the "install the app on the emulator at human pace" step.
Today the emulator tier only EXTRACTS an APK that is already installed on the device.
"""
from __future__ import annotations

import random
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional


class UploadSource:
    """A user-uploaded APK stored at <upload_dir>/<package>.apk."""

    name = "upload"

    def __init__(self, upload_dir: Path):
        self.upload_dir = Path(upload_dir)

    def fetch(self, package: str, dest_dir: Path) -> Optional[Path]:
        path = self.upload_dir / f"{package}.apk"
        return path if path.is_file() else None


def _run_adb(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True).stdout


class AdbEmulatorSource:
    name = "emulator"

    def __init__(self, serial: Optional[str] = None, adb: str = "adb",
                 runner: Callable[[list[str]], str] = _run_adb,
                 pace: tuple[float, float] = (1.0, 3.0), sleep: Callable[[float], None] = time.sleep):
        self.serial, self.adb, self._run, self.pace, self._sleep = serial, adb, runner, pace, sleep

    def _adb(self, *args: str) -> str:
        self._sleep(random.uniform(*self.pace))  # paced like a person, not a tight loop
        cmd = [self.adb] + (["-s", self.serial] if self.serial else []) + list(args)
        return self._run(cmd)

    def fetch(self, package: str, dest_dir: Path) -> Optional[Path]:
        try:
            out = self._adb("shell", "pm", "path", package)
            paths = [l.split(":", 1)[1].strip() for l in out.splitlines() if l.startswith("package:")]
            base = [p for p in paths if p.endswith("base.apk")] or paths[:1]
            if not base:
                return None  # not installed; automated install arrives in Iteration 5
            dest = Path(dest_dir) / f"{package}.apk"
            dest.parent.mkdir(parents=True, exist_ok=True)
            self._adb("pull", base[0], str(dest))
            return dest if dest.exists() else None
        except (OSError, subprocess.SubprocessError):
            return None  # adb missing / no device: treat as unavailable
