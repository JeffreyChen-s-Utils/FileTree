"""Own a fresh noninteractive clipboard station; never open or empty an existing station."""

from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
import re
import sys
import threading
import time
import uuid

_PREFIX = "filetree-clipboard-"
_MAX_BYTES = 128 * 1024 * 1024
_UTF16_UNIT = 2


def require(condition: bool, message: str) -> None:
    """Refuse an uncertain station, scope or native result."""
    if not condition:
        raise RuntimeError(message)


def disposable_runner() -> None:
    """Require the disposable hosted Windows runner; never request elevation."""
    require(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted", "Disposable hosted Windows runner required")


def before_qt() -> None:
    """Refuse every Qt import before changing a process or thread GUI namespace."""
    require(not any(name == "PySide6" or name.startswith("PySide6.") for name in sys.modules),
            "Private station must precede Qt imports")


class _Flags(c.Structure):
    _fields_ = [("inherit", w.BOOL), ("reserved", w.BOOL), ("flags", w.DWORD)]


class _Security(c.Structure):
    _fields_ = [("size", w.DWORD), ("descriptor", c.c_void_p), ("inherit", w.BOOL)]


_HWND_MESSAGE = -3
_IME_CLASS = "IME"  # the system's default IME window retires with the thread's last other window


def _api(library: object, name: str, args: list, result: object) -> object:
    function = getattr(library, name)
    function.argtypes, function.restype = args, result
    return function


class _Native:
    def __init__(self) -> None:
        user = c.WinDLL("user32", use_last_error=True)
        kernel = c.WinDLL("kernel32", use_last_error=True)
        security = c.WinDLL("advapi32", use_last_error=True)
        self.station = _api(user, "GetProcessWindowStation", [], w.HANDLE)
        self.set_station = _api(user, "SetProcessWindowStation", [w.HANDLE], w.BOOL)
        self.create_station = _api(user, "CreateWindowStationW", [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p], w.HANDLE)
        self.create_desktop = _api(user, "CreateDesktopW", [w.LPCWSTR, w.LPCWSTR, c.c_void_p,
                                                           w.DWORD, w.DWORD, c.c_void_p], w.HANDLE)
        self.thread = _api(kernel, "GetCurrentThreadId", [], w.DWORD)
        self.desktop = _api(user, "GetThreadDesktop", [w.DWORD], w.HANDLE)
        self.set_desktop = _api(user, "SetThreadDesktop", [w.HANDLE], w.BOOL)
        self.close_desktop = _api(user, "CloseDesktop", [w.HANDLE], w.BOOL)
        self.close_station = _api(user, "CloseWindowStation", [w.HANDLE], w.BOOL)
        self.info = _api(user, "GetUserObjectInformationW", [w.HANDLE, c.c_int, c.c_void_p,
                                                            w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
        self.descriptor = _api(security, "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                               [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.c_void_p], w.BOOL)
        self.free = _api(kernel, "LocalFree", [c.c_void_p], c.c_void_p)
        self.open_clipboard = _api(user, "OpenClipboard", [w.HWND], w.BOOL)
        self.close_clipboard = _api(user, "CloseClipboard", [], w.BOOL)
        self.clipboard_data = _api(user, "GetClipboardData", [w.UINT], w.HANDLE)
        self.size = _api(kernel, "GlobalSize", [w.HANDLE], c.c_size_t)
        self.lock = _api(kernel, "GlobalLock", [w.HANDLE], c.c_void_p)
        self.unlock = _api(kernel, "GlobalUnlock", [w.HANDLE], w.BOOL)
        # WINFUNCTYPE exists only on Windows; the module itself must still import elsewhere for tests.
        self.enum_callback = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        self.enum_thread_windows = _api(user, "EnumThreadWindows", [w.DWORD, self.enum_callback, w.LPARAM], w.BOOL)
        self.find_window = _api(user, "FindWindowExW", [w.HWND, w.HWND, w.LPCWSTR, w.LPCWSTR], w.HWND)
        self.window_thread = _api(user, "GetWindowThreadProcessId", [w.HWND, c.POINTER(w.DWORD)], w.DWORD)
        self.window_class = _api(user, "GetClassNameW", [w.HWND, w.LPWSTR, c.c_int], c.c_int)
        self.destroy_window = _api(user, "DestroyWindow", [w.HWND], w.BOOL)
        self.is_window = _api(user, "IsWindow", [w.HWND], w.BOOL)

    def checked(self, value):
        if not value:
            raise c.WinError(c.get_last_error())
        return value

    def name(self, handle: int) -> str:
        value, needed = c.create_unicode_buffer(512), w.DWORD()
        self.checked(self.info(handle, 2, value, c.sizeof(value), c.byref(needed)))
        return value.value

    def visible(self, handle: int) -> bool:
        flags, needed = _Flags(), w.DWORD()
        self.checked(self.info(handle, 1, c.byref(flags), c.sizeof(flags), c.byref(needed)))
        return bool(flags.flags & 1)

    def thread_windows(self) -> list[int]:
        """Top-level and message-only windows of the calling thread (EnumThreadWindows omits the latter)."""
        thread, found = self.thread(), []
        callback = self.enum_callback(lambda handle, _param: found.append(handle) is None)
        self.enum_thread_windows(thread, callback, 0)
        handle = None
        while handle := self.find_window(w.HWND(_HWND_MESSAGE), handle, None, None):
            if self.window_thread(handle, None) == thread:
                found.append(handle)
        return found

    def class_name(self, handle: int) -> str:
        value = c.create_unicode_buffer(256)
        return value.value if self.window_class(handle, value, len(value)) else ""

    def security(self) -> c.c_void_p:
        descriptor = c.c_void_p()
        # Grant only the object's owner and the OS; desktops inherit this protected DACL.
        self.checked(self.descriptor("D:P(A;;GA;;;OW)(A;;GA;;;SY)", 1, c.byref(descriptor), None))
        require(bool(descriptor.value), "Private station security descriptor is missing")
        return descriptor


def guard(native: _Native, station: str, desktop: str) -> dict:
    """Verify the exact private station/desktop and noninteractive flag before clipboard access."""
    require(re.fullmatch(_PREFIX + "[0-9a-f]{32}", station) is not None
            and re.fullmatch("probe-[0-9a-f]{32}", desktop) is not None, "Unknown private clipboard scope")
    actual_station = native.station()
    actual_desktop = native.desktop(native.thread())
    require(native.name(actual_station) == station and native.name(actual_desktop) == desktop
            and not native.visible(actual_station), "Private noninteractive clipboard scope changed")
    return {"station": station, "desktop": desktop, "noninteractive": True, "pid": os.getpid()}


class PrivateStation:
    """Create-only private objects in a fresh helper; restore and close only owned handles."""

    def __init__(self) -> None:
        disposable_runner()
        before_qt()
        self.native = _Native()
        self.station_name = _PREFIX + uuid.uuid4().hex
        self.desktop_name = "probe-" + uuid.uuid4().hex
        self.station = self.desktop = None
        self.previous_station = self.native.checked(self.native.station())
        self.previous_desktop = self.native.checked(self.native.desktop(self.native.thread()))
        self.station_changed = self.desktop_changed = False
        self.cleanup: list[dict] = []

    def __enter__(self) -> PrivateStation:
        descriptor = self.native.security()
        try:
            attributes = _Security(c.sizeof(_Security), descriptor, True)
            self.station = self.native.checked(self.native.create_station(
                self.station_name, 1, 0xF037F, c.byref(attributes)))  # CWF_CREATE_ONLY; no existing-station fallback
            require(self.native.name(self.station) == self.station_name and not self.native.visible(self.station),
                    "Created station identity/visibility differs")
            self.station_changed = True
            self.native.checked(self.native.set_station(self.station))
            self.desktop = self.native.checked(self.native.create_desktop(
                self.desktop_name, None, None, 0, 0xF01FF, c.byref(attributes)))
            self.desktop_changed = True
            self.native.checked(self.native.set_desktop(self.desktop))
            self.check()
            return self
        except BaseException:
            self.close()
            raise
        finally:
            self.native.free(descriptor)

    def check(self) -> dict:
        """Recheck the active scope; this must precede every clipboard API."""
        return guard(self.native, self.station_name, self.desktop_name)

    def close(self) -> None:
        """Attempt ordered owned cleanup, retaining every failed restoration/close."""
        if self.station is None and self.desktop is None and not (self.station_changed or self.desktop_changed):
            require(all(item["ok"] for item in self.cleanup), "Private clipboard cleanup incomplete")
            return
        if self.desktop_changed:
            self._retire_windows()
        actions = [("restore-desktop", self.desktop_changed, self.native.set_desktop, self.previous_desktop),
                   ("restore-station", self.station_changed, self.native.set_station, self.previous_station)]
        for name, active, function, handle in actions:
            if active:
                ok = bool(function(handle))
                self.cleanup.append({"action": name, "ok": ok, "error": 0 if ok else c.get_last_error()})
        restored = all(item["ok"] for item in self.cleanup)
        if restored:
            actual = [self.native.name(self.native.station()),
                      self.native.name(self.native.desktop(self.native.thread()))]
            expected = [self.native.name(self.previous_station), self.native.name(self.previous_desktop)]
            restored = actual == expected
            self.cleanup.append({"action": "verify-restored", "ok": restored, "actual": actual, "expected": expected})
        if restored:
            for name, handle, function in [("close-desktop", self.desktop, self.native.close_desktop),
                                           ("close-station", self.station, self.native.close_station)]:
                if handle is not None:
                    ok = bool(function(handle))
                    self.cleanup.append({"action": name, "ok": ok, "error": 0 if ok else c.get_last_error()})
        self.station = self.desktop = None
        self.station_changed = self.desktop_changed = False
        require(all(item["ok"] for item in self.cleanup), "Private clipboard cleanup incomplete")

    def _retire_windows(self) -> None:
        """Destroy the windows this thread left on the owned desktop, which SetThreadDesktop refuses to leave.

        The thread had no windows when it entered (SetThreadDesktop would have refused), so each one lives
        on the private desktop. Qt 6.11/6.12 keep a theme-change observer window after QApplication is
        deleted: hosted run 39034413839 and a local probe both restored with error 170 (ERROR_BUSY).
        """
        try:
            current = self.native.name(self.native.desktop(self.native.thread()))
        except OSError as error:  # still attempt the restoration that follows
            self.cleanup.append({"action": "retire-windows", "ok": False, "error": str(error)[:512]})
            return
        if current != self.desktop_name:
            return
        windows = [(handle, self.native.class_name(handle)) for handle in self.native.thread_windows()]
        for handle, name in windows:
            # Destroying one window can retire others (owned windows, the default IME window).
            if name != _IME_CLASS and self.native.is_window(handle):
                ok = bool(self.native.destroy_window(handle))
                self.cleanup.append({"action": "retire-window", "class": name, "ok": ok,
                                     "error": 0 if ok else c.get_last_error()})
        residual = [self.native.class_name(handle) for handle in self.native.thread_windows()]
        if residual:
            self.cleanup.append({"action": "residual-windows", "ok": False, "classes": residual})

    def __exit__(self, *_args) -> None:
        self.close()


def _read_text(native: _Native, station: str, desktop: str) -> tuple[str, int]:
    guard(native, station, desktop)
    native.checked(native.open_clipboard(None))
    try:
        guard(native, station, desktop)
        handle = native.checked(native.clipboard_data(13))
        size = native.size(handle)
        require(_UTF16_UNIT <= size <= _MAX_BYTES and size % _UTF16_UNIT == 0,
                "Native clipboard payload size refused")
        pointer = native.checked(native.lock(handle))
        try:
            raw = c.string_at(pointer, size).decode("utf-16-le", errors="surrogatepass")
        finally:
            native.unlock(handle)
        text, separator, _padding = raw.partition("\0")
        require(bool(separator), "Native clipboard text lacks a terminator")
    finally:
        native.checked(native.close_clipboard())
    return text, size


def _join(native: _Native, station: str, desktop: str, handles: tuple[int, int]) -> None:
    require(re.fullmatch(_PREFIX + "[0-9a-f]{32}", station) is not None
            and re.fullmatch("probe-[0-9a-f]{32}", desktop) is not None, "Unknown inherited private clipboard scope")
    require(native.name(handles[0]) == station and native.name(handles[1]) == desktop
            and not native.visible(handles[0]), "Inherited private clipboard handle identity differs")
    native.checked(native.set_station(handles[0]))
    native.checked(native.set_desktop(handles[1]))
    guard(native, station, desktop)


def read_private(station: str, desktop: str, parent: int, station_handle: int, desktop_handle: int) -> dict:
    """Read only private CF_UNICODETEXT; a stalled native reader exits its own process after 30 s."""
    disposable_runner()
    require(parent == os.getppid() and parent > 0, "Private clipboard reader parent differs")
    before_qt()
    native = _Native()
    _join(native, station, desktop, (station_handle, desktop_handle))
    scope = guard(native, station, desktop)
    print("FILETREE_NATIVE_READ_START " + json.dumps(scope), file=sys.stderr, flush=True)
    watchdog = threading.Timer(30, os._exit, args=(124,))
    watchdog.daemon = True
    started = time.perf_counter()
    watchdog.start()
    try:
        text, size = _read_text(native, station, desktop)
    finally:
        watchdog.cancel()
        watchdog.join()
    elapsed = (time.perf_counter()-started)*1000
    normalized = text.replace("\r\n", "\n")
    return {"scope": scope, "parent_pid": parent, "bytes": size, "characters": len(text),
            "read_ms": elapsed, "normalized_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(read_private(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))),
          flush=True)
