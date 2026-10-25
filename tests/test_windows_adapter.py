"""Mock Win32 ABI calls only: never call a real desktop API."""
import ctypes
from unittest.mock import patch
import unittest
import types
from support import ROOT
from sra_desktop import WindowsDesktop

class Fn:
    def __init__(self, action=lambda *a:1):self.action=action
    def __call__(self,*a):return self.action(*a)

class Library:
    def __init__(self):self.functions={}
    def __getattr__(self,name):return self.functions.setdefault(name,Fn())

class Win32Tests(unittest.TestCase):
    def setUp(self):
        self.user,self.kernel=Library(),Library()
        with patch("sra_desktop.sys.platform","win32"),patch.object(ctypes,"WinDLL",lambda name,**kw:self.user if name=="user32" else self.kernel,create=True):
            self.desktop=WindowsDesktop()
        self.user.GetForegroundWindow.action=lambda:42
        def pid(hwnd,pointer):pointer._obj.value=100;return 1
        self.user.GetWindowThreadProcessId.action=pid
        self.kernel.CreateToolhelp32Snapshot.action=lambda *a:999
        self.executable="StarCitizen.exe"
        def first(handle,pointer):
            pointer._obj.th32ProcessID=100;pointer._obj.szExeFile=self.executable;return True
        self.kernel.Process32FirstW.action=first
        self.kernel.Process32NextW.action=lambda *a:False
        self.closed=[]
        self.kernel.CloseHandle.action=lambda h:self.closed.append(h)

    def test_process_name_guard_and_handle_cleanup(self):
        self.assertTrue(self.desktop.foreground());self.assertEqual(self.closed,[999])
        self.executable="Other.exe";self.assertFalse(self.desktop.foreground())

    def test_snapshot_failure_fails_closed(self):
        self.kernel.CreateToolhelp32Snapshot.action=lambda *a:ctypes.c_void_p(-1).value
        self.assertFalse(self.desktop.foreground())

    def test_foreground_change_during_enumeration_fails_closed(self):
        hwnd=iter([42,43]);self.user.GetForegroundWindow.action=lambda:next(hwnd)
        self.assertFalse(self.desktop.foreground())

    def test_absent_foreground_fails_closed(self):
        self.user.GetForegroundWindow.action=lambda:None
        self.assertFalse(self.desktop.foreground())

    def test_non_text_clipboard_refused_without_emptying(self):
        self.user.IsClipboardFormatAvailable.action=lambda *a:False
        self.user.CountClipboardFormats.action=lambda:1
        emptied=[];self.user.EmptyClipboard.action=lambda:emptied.append(True)
        with self.assertRaisesRegex(RuntimeError,"non-text"):self.desktop.clipboard_get()
        self.assertEqual(emptied,[])

    def test_geometry_selects_game_monitor_with_absolute_pixels(self):
        # Two monitors; the foreground game lives on the negative-X monitor.
        self.user.MonitorFromWindow.action=lambda *a:202
        def info(handle,pointer):
            record=pointer._obj
            record.szDevice="DISPLAY2" if handle==202 else "DISPLAY1"
            r=record.rcMonitor
            r.left=-1920 if handle==202 else 0;r.top=0
            r.right=0 if handle==202 else 1920;r.bottom=1080
            return 1
        self.user.GetMonitorInfoW.action=info
        def rect(hwnd,pointer):
            r=pointer._obj;r.left=-1800;r.top=100;r.right=-200;r.bottom=1000
            return 1
        self.user.GetWindowRect.action=rect
        def enumerate_monitors(hdc,clip,callback,data):
            return callback(101,None,None,0) and callback(202,None,None,0)
        self.user.EnumDisplayMonitors.action=enumerate_monitors
        with patch.object(ctypes,"WINFUNCTYPE",ctypes.CFUNCTYPE,create=True):
            geometry=self.desktop.geometry()
        self.assertEqual(geometry,{"display":2,"device":"DISPLAY2","left":-1920,"top":0,
                                   "width":1920,"height":1080,"window":[-1800,100,-200,1000]})
