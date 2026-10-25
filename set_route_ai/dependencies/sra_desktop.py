"""Lazy Windows desktop adapter. Never instantiated by the catalog or tests."""
import sys
from contextlib import contextmanager


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

    def geometry(self, display):
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
            if not 1 <= display <= len(monitors):
                raise RuntimeError("Configured display is unavailable.")
            hwnd = self.u.GetForegroundWindow()
            handle, info = monitors[display-1]
            if self.u.MonitorFromWindow(hwnd, 2) != handle:
                raise RuntimeError("Star Citizen is on a different display; select its display and recalibrate.")
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

    def clipboard_get(self):
        if not self.u.OpenClipboard(None):
            raise RuntimeError("Clipboard is busy; try again.")
        try:
            if not self.u.IsClipboardFormatAvailable(13):
                if self.u.CountClipboardFormats():
                    raise RuntimeError("Clipboard contains non-text data. Copy text or clear it before routing.")
                return None
            handle = self.u.GetClipboardData(13)
            pointer = self.k.GlobalLock(handle) if handle else None
            if not pointer:
                raise RuntimeError("Could not read clipboard text.")
            try:
                return self.c.wstring_at(pointer)
            finally:
                self.k.GlobalUnlock(handle)
        finally:
            self.u.CloseClipboard()

    def clipboard_set(self, text):
        handle = None
        if text is not None:
            data = (text + "\0").encode("utf-16-le")
            handle = self.k.GlobalAlloc(2, len(data))
            if not handle:
                raise RuntimeError("Clipboard allocation failed.")
            pointer = self.k.GlobalLock(handle)
            if not pointer:
                self.k.GlobalFree(handle)
                raise RuntimeError("Clipboard lock failed.")
            self.c.memmove(pointer, data, len(data))
            self.k.GlobalUnlock(handle)
        if not self.u.OpenClipboard(None):
            if handle:
                self.k.GlobalFree(handle)
            raise RuntimeError("Clipboard is busy; try again.")
        try:
            if not self.u.EmptyClipboard():
                raise RuntimeError("Could not clear clipboard.")
            if handle:
                if not self.u.SetClipboardData(13, handle):
                    raise RuntimeError("Could not set clipboard text.")
                handle = None
        finally:
            self.u.CloseClipboard()
            if handle:
                self.k.GlobalFree(handle)
