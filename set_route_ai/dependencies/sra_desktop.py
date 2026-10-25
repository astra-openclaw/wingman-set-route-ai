"""Lazy Windows desktop adapter. Never instantiated by the catalog or tests."""
import sys
import time
from typing import NamedTuple
from contextlib import contextmanager


CLIPBOARD_LIMIT = 256 * 1024 * 1024
HANDLE_FORMATS = {2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E}


class ClipboardBusy(RuntimeError):
    pass


class ClipboardSnapshot(NamedTuple):
    formats: tuple
    partial: bool = False


class WindowsDesktop:
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("SetRouteAI desktop routing requires Windows.")
        import ctypes
        from ctypes import wintypes as w
        self.c, self.w = ctypes, w
        self.u, self.k = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)
        self.u.GetForegroundWindow.restype = w.HWND
        self.u.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        self.k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
        self.k.CreateToolhelp32Snapshot.restype = w.HANDLE
        self.k.CloseHandle.argtypes = [w.HANDLE]
        self.u.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
        self.u.MonitorFromWindow.argtypes = [w.HWND, w.DWORD]
        self.u.MonitorFromWindow.restype = w.HANDLE
        self.u.GetMonitorInfoW.argtypes = [w.HANDLE, ctypes.c_void_p]
        self.u.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        self.u.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        self.u.GetPhysicalCursorPos.argtypes = [ctypes.POINTER(w.POINT)]
        self.u.SetPhysicalCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.k.GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]
        self.k.GlobalAlloc.restype = w.HGLOBAL
        self.k.GlobalLock.argtypes = [w.HGLOBAL]
        self.k.GlobalLock.restype = ctypes.c_void_p
        self.k.GlobalSize.argtypes = [w.HGLOBAL]
        self.k.GlobalSize.restype = ctypes.c_size_t
        self.k.GlobalFree.restype = w.HGLOBAL
        self.u.EnumClipboardFormats.argtypes = [w.UINT]
        self.u.EnumClipboardFormats.restype = w.UINT
        self.u.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                         ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                         w.HWND, w.HMENU, w.HINSTANCE, ctypes.c_void_p]
        self.u.CreateWindowExW.restype = w.HWND
        self.u.DestroyWindow.argtypes = [w.HWND]
        self.k.GlobalUnlock.argtypes = [w.HGLOBAL]
        self.k.GlobalFree.argtypes = [w.HGLOBAL]
        self.u.OpenClipboard.argtypes = [w.HWND]
        self.u.GetClipboardData.argtypes = [w.UINT]
        self.u.GetClipboardData.restype = w.HANDLE
        self.u.SetClipboardData.argtypes = [w.UINT, w.HANDLE]
        self.u.SetClipboardData.restype = w.HANDLE
        self._keyboard = self._mouse = None

    def foreground(self):
        c, w = self.c, self.w
        class Entry(c.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                        ("th32DefaultHeapID", c.c_size_t), ("th32ModuleID", w.DWORD),
                        ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                        ("pcPriClassBase", w.LONG), ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR * 260)]
        first, following = self.k.Process32FirstW, self.k.Process32NextW
        for fn in (first, following):
            fn.argtypes = [w.HANDLE, c.POINTER(Entry)]
            fn.restype = w.BOOL
        hwnd = self.u.GetForegroundWindow()
        if not hwnd:
            return False
        pid = w.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        snapshot = self.k.CreateToolhelp32Snapshot(2, 0)
        if snapshot in (None, c.c_void_p(-1).value):
            return False
        try:
            entry = Entry()
            entry.dwSize = c.sizeof(Entry)
            found = None
            ok = first(snapshot, c.byref(entry))
            while ok:
                if entry.th32ProcessID == pid.value:
                    found = entry.szExeFile.casefold()
                    break
                ok = following(snapshot, c.byref(entry))
            # Verify foreground did not change while walking the snapshot.
            return found == "starcitizen.exe" and hwnd == self.u.GetForegroundWindow()
        finally:
            self.k.CloseHandle(snapshot)

    @contextmanager
    def _physical(self):
        old = self.u.SetThreadDpiAwarenessContext(self.c.c_void_p(-4))
        if not old:
            raise RuntimeError("Could not establish physical display coordinates.")
        try:
            yield
        finally:
            self.u.SetThreadDpiAwarenessContext(old)

    def geometry(self):
        c, w = self.c, self.w
        class Info(c.Structure):
            _fields_ = [("cbSize", w.DWORD), ("rcMonitor", w.RECT), ("rcWork", w.RECT),
                        ("dwFlags", w.DWORD), ("szDevice", w.WCHAR * 32)]
        monitors = []
        callback_type = c.WINFUNCTYPE(w.BOOL, w.HANDLE, w.HDC, c.POINTER(w.RECT), w.LPARAM)
        def visit(handle, hdc, rect, data):
            info = Info()
            info.cbSize = c.sizeof(Info)
            if not self.u.GetMonitorInfoW(handle, c.byref(info)):
                return False
            r = info.rcMonitor
            monitors.append((handle, {"device": info.szDevice, "left": r.left, "top": r.top,
                                      "width": r.right-r.left, "height": r.bottom-r.top}))
            return True
        callback = callback_type(visit)
        with self._physical():
            self.u.EnumDisplayMonitors.argtypes = [w.HDC, c.c_void_p, callback_type, w.LPARAM]
            if not self.u.EnumDisplayMonitors(None, None, callback, 0):
                raise RuntimeError("Could not inspect displays.")
            hwnd = self.u.GetForegroundWindow()
            game_monitor = self.u.MonitorFromWindow(hwnd, 2)
            selected = next(((i, info) for i, (handle, info) in enumerate(monitors, 1)
                             if handle == game_monitor), None)
            if selected is None:
                raise RuntimeError("Could not identify the game monitor.")
            display, info = selected
            rect = w.RECT()
            if not self.u.GetWindowRect(hwnd, c.byref(rect)):
                raise RuntimeError("Could not inspect the game window.")
            return {**info, "display": display, "window": [rect.left, rect.top, rect.right, rect.bottom]}

    def position(self):
        point = self.w.POINT()
        if not self.u.GetPhysicalCursorPos(self.c.byref(point)):
            raise RuntimeError("Could not read the pointer.")
        return point.x, point.y

    def left_pressed(self):
        return bool(self.u.GetAsyncKeyState(1) & 0x8000)

    def press(self, key):
        if self._keyboard is None:
            import keyboard.keyboard as keyboard
            self._keyboard = keyboard
        self._keyboard.press(key)

    def release(self, key):
        if self._keyboard is not None:
            self._keyboard.release(key)

    def move(self, x, y):
        if not self.u.SetPhysicalCursorPos(x, y):
            raise RuntimeError("Could not move the pointer.")

    def click(self):
        if self._mouse is None:
            import mouse.mouse as mouse
            self._mouse = mouse
        self._mouse.click()

    def wheel(self, steps):
        if self._mouse is None:
            import mouse.mouse as mouse
            self._mouse = mouse
        self._mouse.wheel(steps)

    @contextmanager
    def _clipboard_open(self, writing=False):
        # A real owner window is required when EmptyClipboard precedes SetClipboardData.
        # HWND_MESSAGE creates an invisible window on this worker's thread.
        owner = self.u.CreateWindowExW(0, "STATIC", "", 0, 0, 0, 0, 0, -3, None, None, None) if writing else None
        if writing and not owner:
            raise RuntimeError("Could not create clipboard owner.")
        opened = False
        try:
            for attempt in range(3):
                if self.u.OpenClipboard(owner):
                    opened = True
                    break
                if attempt < 2:
                    time.sleep(.05)
            if not opened:
                raise ClipboardBusy("The clipboard is busy; try again.")
            yield
        finally:
            if opened:
                self.u.CloseClipboard()
            if owner:
                self.u.DestroyWindow(owner)

    def clipboard_get(self):
        """Copy all movable-memory formats in enumeration order, bounded in memory."""
        saved, skipped, total, partial = [], set(), 0, False
        with self._clipboard_open():
            current, seen = 0, set()
            while True:
                self.c.set_last_error(0)
                current = self.u.EnumClipboardFormats(current)
                if not current:
                    partial |= bool(self.c.get_last_error())
                    break
                if current in seen:
                    partial = True
                    break
                seen.add(current)
                if current in HANDLE_FORMATS:
                    skipped.add(current)
                    continue
                try:
                    handle = self.u.GetClipboardData(current)
                    size = self.k.GlobalSize(handle) if handle else 0
                    if not size or size > CLIPBOARD_LIMIT - total:
                        partial = True
                        continue
                    pointer = self.k.GlobalLock(handle)
                    if not pointer:
                        partial = True
                        continue
                    try:
                        data = self.c.string_at(pointer, size)
                    finally:
                        self.k.GlobalUnlock(handle)
                    saved.append((current, data))
                    total += size
                except Exception:
                    partial = True
        # Windows recreates CF_BITMAP from DIB/DIBV5. Other skipped handles
        # cannot be reconstructed by transferring their handle bytes.
        if {fmt for fmt, _ in saved} & {8, 17}:
            skipped.discard(2)
        return ClipboardSnapshot(tuple(saved), partial or bool(skipped))

    def _clipboard_write(self, formats):
        failed = False
        with self._clipboard_open(writing=True):
            if not self.u.EmptyClipboard():
                raise RuntimeError("Could not clear clipboard.")
            for fmt, data in formats:
                handle = None
                try:
                    handle = self.k.GlobalAlloc(2, len(data))
                    if not handle:
                        raise RuntimeError("Clipboard allocation failed.")
                    pointer = self.k.GlobalLock(handle)
                    if not pointer:
                        raise RuntimeError("Clipboard lock failed.")
                    try:
                        self.c.memmove(pointer, data, len(data))
                    finally:
                        self.k.GlobalUnlock(handle)
                    if not self.u.SetClipboardData(fmt, handle):
                        raise RuntimeError("Could not transfer clipboard data.")
                    handle = None  # Windows owns the allocation after success.
                except Exception:
                    failed = True
                finally:
                    if handle:
                        self.k.GlobalFree(handle)
        if failed:
            raise RuntimeError("Could not restore all clipboard content.")

    def clipboard_set(self, text):
        self._clipboard_write(((13, (text + "\0").encode("utf-16-le")),))

    def clipboard_restore(self, snapshot):
        self._clipboard_write(snapshot.formats)
