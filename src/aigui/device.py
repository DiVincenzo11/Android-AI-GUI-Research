"""ADB transport. No hard-coded SDK paths, credentials, or third-party planners."""
from __future__ import annotations
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time
import uuid


class Adb:
    def __init__(self, serial, executable=None):
        self.executable = executable or os.environ.get("ADB") or shutil.which("adb")
        if not self.executable:
            sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
            if sdk:
                p = Path(sdk)/"platform-tools"/("adb.exe" if os.name == "nt" else "adb")
                if p.is_file():
                    self.executable = str(p)
        if not self.executable:
            raise RuntimeError("ADB not found: set ADB or ANDROID_HOME, or add adb to PATH")
        self.serial = serial
        self.run("get-state")

    def run(self, *args, binary=False, timeout=40):
        p = subprocess.run([self.executable, "-s", self.serial, *map(str, args)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=True)
        return p.stdout if binary else p.stdout.decode("utf-8", errors="replace")

    def shell(self, *args):
        # ADB joins remote shell arguments: quote at the device-shell boundary as well.
        return self.run("shell", " ".join(shlex.quote(str(a)) for a in args))

    @staticmethod
    def package_name(package):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+", package):
            raise ValueError("Invalid Android package")
        return package

    def launch(self, package):
        self.package_name(package)
        result = self.shell("monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        if "No activities found" in result or "aborted" in result.lower():
            raise RuntimeError("Launcher activity unavailable")

    def foreground(self):
        # Recent Android versions omit mCurrentFocus from the 'windows' subsection.
        text = self.shell("dumpsys", "window")
        lines = [l for l in text.splitlines() if "mCurrentFocus=" in l or "mFocusedApp=" in l]
        for line in lines:
            hit = re.search(r"\s([\w.]+)/[\w.$]+", line)
            if hit:
                return hit[1]
        raise RuntimeError("Foreground package cannot be established")

    def guard(self, package):
        actual = self.foreground()
        if actual != package:
            raise RuntimeError(f"Foreign foreground: {actual}; expected {package}")

    def dump(self):
        remote = "/sdcard/aigui_" + uuid.uuid4().hex + ".xml"
        try:
            self.shell("uiautomator", "dump", remote)
            return self.shell("cat", remote)
        finally:
            self.shell("rm", "-f", remote)

    def screenshot(self, path):
        data = self.run("exec-out", "screencap", "-p", binary=True)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Invalid device screenshot")
        Path(path).write_bytes(data)

    def tap(self, bounds, package):
        self.guard(package)
        self.shell("input", "tap", (bounds[0]+bounds[2])//2, (bounds[1]+bounds[3])//2)

    def text(self, text, package):
        self.guard(package)
        if not re.fullmatch(r"[A-Za-z0-9 .,?!:_+\-/]+", text):
            raise ValueError("ADB text input supports the documented ASCII subset only; use a separate IME adapter for Unicode")
        self.shell("input", "text", text.replace(" ", "%s"))

    def record_start(self, seconds=120):
        if not 1 <= seconds <= 180:
            raise ValueError("screenrecord limit must be 1..180 seconds")
        remote = "/sdcard/aigui_" + uuid.uuid4().hex + ".mp4"
        pid = self.shell("sh", "-c", f"screenrecord --time-limit {seconds} {remote} >/dev/null 2>&1 & echo $!").strip()
        if not pid.isdigit():
            raise RuntimeError("screenrecord process ID unavailable")
        return remote, pid

    def record_finish(self, handle, path):
        remote, pid = handle
        self.shell("kill", "-2", pid)
        time.sleep(1)
        try:
            self.run("pull", remote, str(path))
        finally:
            self.shell("rm", "-f", remote)
