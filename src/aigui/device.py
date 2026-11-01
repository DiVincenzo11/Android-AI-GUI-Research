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
    def __init__(self, serial, executable=None, dump_backend="shell"):
        if dump_backend not in {"shell", "uiautomator2"}:
            raise ValueError("Unknown UI hierarchy backend")
        self.dump_backend, self._u2 = dump_backend, None
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
        try:
            if self.foreground() == package:
                return
        except RuntimeError:
            pass
        resolved = self.shell("cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN",
                              "-c", "android.intent.category.LAUNCHER", package)
        component = next((line.strip() for line in reversed(resolved.splitlines())
                          if re.fullmatch(re.escape(package)+r"/[\w.$]+", line.strip())), None)
        if not component:
            raise RuntimeError("Launcher activity unavailable")
        result = self.shell("am", "start", "-W", "-n", component)
        if "Error:" in result or "Exception" in result:
            raise RuntimeError("Launcher activity unavailable: "+result.strip())

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
        if getattr(self,"dump_backend","shell")=="uiautomator2":
            if self._u2 is None:
                import uiautomator2 as u2
                previous=os.environ.get("ADBUTILS_ADB_PATH")
                os.environ["ADBUTILS_ADB_PATH"]=self.executable
                try:self._u2=u2.connect(self.serial)
                finally:
                    if previous is None:os.environ.pop("ADBUTILS_ADB_PATH",None)
                    else:os.environ["ADBUTILS_ADB_PATH"]=previous
                self._u2.jsonrpc.setConfigurator({"waitForIdleTimeout":0,"waitForSelectorTimeout":0})
            self.last_dump_attempts,self.last_dump_errors=1,[]
            return self._u2.dump_hierarchy(compressed=False,max_depth=100)
        remote = "/sdcard/aigui_" + uuid.uuid4().hex + ".xml"
        self.last_dump_errors = []
        try:
            for attempt in range(1, 4):
                self.last_dump_attempts = attempt
                result = self.shell("uiautomator", "dump", remote)
                try:
                    return self.shell("cat", remote)
                except subprocess.CalledProcessError:
                    self.last_dump_errors.append(result.strip()[:400])
                    if attempt == 3:
                        raise RuntimeError("UI hierarchy unavailable after three dump attempts: "+result.strip()[:400]) from None
                    time.sleep(.5)
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

    def record_start(self, seconds=180):
        if not 1 <= seconds <= 180:
            raise ValueError("screenrecord limit must be 1..180 seconds")
        remote = "/sdcard/aigui_" + uuid.uuid4().hex + ".mp4"
        pid = self.shell("sh", "-c", f"screenrecord --time-limit {seconds} {remote} >/dev/null 2>&1 & echo $!").strip()
        if not pid.isdigit():
            raise RuntimeError("screenrecord process ID unavailable")
        return remote, pid

    def record_finish(self, handle, path):
        remote, pid = handle
        # screenrecord may already have reached its time limit. Only signal the
        # process if its command line still belongs to this exact recording.
        self.shell("sh", "-c", f"if [ -r /proc/{pid}/cmdline ] && grep -q '{remote}' /proc/{pid}/cmdline; then kill -2 {pid}; fi")
        time.sleep(1)
        try:
            self.run("pull", remote, str(path))
        finally:
            self.shell("rm", "-f", remote)
