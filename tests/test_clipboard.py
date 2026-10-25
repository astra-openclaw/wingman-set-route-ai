"""Ordered Win32 clipboard ownership/bytes, with no actual Windows calls."""
import asyncio
import ctypes
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from support import skill, call, CALIBRATION, fast_pause, atomic_json
from sra_desktop import WindowsDesktop, ClipboardBusy, CLIPBOARD_LIMIT
from sra_navigation import Navigator
from test_windows_adapter import Library

TEXT = (13, "original text\0".encode("utf-16-le"))
DIB = (8, b"dib\0pixels")
DIBV5 = (17, b"dibv5\0pixels")
PNG = (0xC001, b"\x89PNG\r\n\x1a\n\0image")
FILES = (15, b"DROPFILES\0C:\\Example\\map.txt\0\0")
CUSTOM = (0xC002, b"registered\0format\xff")
NOTE = " Some clipboard content couldn't be kept."


class FakeClipboard:
    def __init__(self, formats=()):
        self.user, self.kernel = Library(), Library()
        with patch("sra_desktop.sys.platform", "win32"), patch.object(
                ctypes, "WinDLL", lambda name, **kw: self.user if name == "user32" else self.kernel, create=True):
            self.desktop = WindowsDesktop()
        self.desktop.c = types.SimpleNamespace(
            string_at=ctypes.string_at, memmove=ctypes.memmove,
            set_last_error=lambda value: None, get_last_error=lambda: 0)
        self.formats = list(formats)
        self.allocations = {}
        self.data_handles = {}
        self.sizes = {}
        self.next_handle = 100
        self.thread = None
        self.owner = None
        self.open_attempts = 0
        self.busy_attempts = 0
        self.transactions = []
        self.freed = []
        self.transferred = []
        self.unreadable = set()
        self.failed_sets = set()
        self.on_get = lambda fmt: None
        self.on_set = lambda fmt: None
        self.created = self.destroyed = 0
        self.user.CreateWindowExW.action = self.create_window
        self.user.DestroyWindow.action = self.destroy_window
        self.user.OpenClipboard.action = self.open
        self.user.CloseClipboard.action = self.close
        self.user.EnumClipboardFormats.action = self.enumerate
        self.user.GetClipboardData.action = self.get
        self.user.EmptyClipboard.action = self.empty
        self.user.SetClipboardData.action = self.set
        self.kernel.GlobalSize.action = lambda handle: self.sizes.get(handle, len(self.allocations[handle]))
        self.kernel.GlobalLock.action = lambda handle: ctypes.addressof(self.allocations[handle])
        self.kernel.GlobalUnlock.action = lambda handle: 1
        self.kernel.GlobalAlloc.action = self.allocate
        self.kernel.GlobalFree.action = self.free

    def check(self):
        assert self.thread == threading.get_ident(), "transaction crossed threads"

    def create_window(self, *args):
        assert args[8] == -3
        self.created += 1
        return 42

    def destroy_window(self, hwnd):
        assert self.thread is None
        self.destroyed += 1
        return 1

    def open(self, owner):
        self.open_attempts += 1
        if self.busy_attempts:
            self.busy_attempts -= 1
            return 0
        assert self.thread is None
        self.thread, self.owner = threading.get_ident(), owner
        self.transactions.append(self.thread)
        return 1

    def close(self):
        self.check()
        self.thread = None
        return 1

    def enumerate(self, previous):
        self.check()
        ids = [fmt for fmt, _ in self.formats]
        index = ids.index(previous) + 1 if previous else 0
        return ids[index] if index < len(ids) else 0

    def allocate(self, flags, size):
        self.next_handle += 1
        self.allocations[self.next_handle] = ctypes.create_string_buffer(size)
        return self.next_handle

    def get(self, fmt):
        self.check()
        self.on_get(fmt)
        if fmt in self.unreadable:
            return 0
        data = dict(self.formats)[fmt]
        handle = self.allocate(2, len(data))
        ctypes.memmove(ctypes.addressof(self.allocations[handle]), data, len(data))
        self.data_handles[fmt] = handle
        if fmt == 0xC099:
            self.sizes[handle] = CLIPBOARD_LIMIT + 1
        return handle

    def empty(self):
        self.check()
        assert self.owner, "EmptyClipboard needs a window owner for SetClipboardData"
        self.formats = []
        return 1

    def set(self, fmt, handle):
        self.check()
        if fmt in self.failed_sets:
            return 0
        self.formats.append((fmt, bytes(self.allocations[handle])))
        self.transferred.append(handle)
        self.on_set(fmt)
        return handle

    def free(self, handle):
        assert handle not in self.transferred, "Windows owns transferred memory"
        self.freed.append(handle)
        del self.allocations[handle]
        return None


class ClipboardAdapterTests(unittest.TestCase):
    def test_ordered_exact_round_trips(self):
        for formats in [(TEXT,), (DIB, DIBV5, PNG, TEXT), (FILES, CUSTOM), ()]:
            with self.subTest(formats=[fmt for fmt, _ in formats]):
                fake = FakeClipboard(formats)
                snapshot = fake.desktop.clipboard_get()
                self.assertEqual(snapshot.formats, formats)
                self.assertFalse(snapshot.partial)
                fake.desktop.clipboard_set("Daymar")
                fake.desktop.clipboard_restore(snapshot)
                self.assertEqual(fake.formats, list(formats))
                self.assertEqual(fake.created, fake.destroyed)

    def test_bitmap_synthesizable_from_dib_is_not_loss(self):
        fake = FakeClipboard(((2, b"handle"), DIB, TEXT))
        snapshot = fake.desktop.clipboard_get()
        self.assertEqual(snapshot.formats, (DIB, TEXT))
        self.assertFalse(snapshot.partial)

    def test_all_gdi_owner_display_formats_are_skipped(self):
        from sra_desktop import HANDLE_FORMATS
        fake = FakeClipboard(tuple((fmt, b"not-hglobal") for fmt in sorted(HANDLE_FORMATS)))
        fake.on_get = lambda fmt: self.fail("GDI handle read as bytes")
        snapshot = fake.desktop.clipboard_get()
        self.assertEqual(snapshot.formats, ())
        self.assertTrue(snapshot.partial)
        fake.desktop.clipboard_restore(snapshot)
        self.assertEqual(fake.formats, [])

    def test_total_cap_is_cumulative_and_later_small_formats_survive(self):
        fake = FakeClipboard((DIB, (PNG[0], PNG[1] * 4), TEXT))
        with patch("sra_desktop.CLIPBOARD_LIMIT", len(DIB[1]) + len(TEXT[1])):
            snapshot = fake.desktop.clipboard_get()
        self.assertEqual(snapshot.formats, (DIB, TEXT))
        self.assertTrue(snapshot.partial)
        fake.desktop.clipboard_restore(snapshot)
        self.assertEqual(fake.formats, list(snapshot.formats))

    def test_unreadable_format_does_not_abort_other_formats(self):
        fake = FakeClipboard((DIB, PNG, TEXT))
        fake.unreadable.add(8)
        snapshot = fake.desktop.clipboard_get()
        self.assertEqual(snapshot.formats, (PNG, TEXT))
        self.assertTrue(snapshot.partial)
        fake.desktop.clipboard_restore(snapshot)
        self.assertEqual(fake.formats, list(snapshot.formats))

    def test_busy_retry_and_owner_cleanup(self):
        fake = FakeClipboard((TEXT,))
        fake.busy_attempts = 3
        with patch("sra_desktop.time.sleep"):
            with self.assertRaisesRegex(ClipboardBusy, "^The clipboard is busy; try again.$"):
                fake.desktop.clipboard_set("Daymar")
        self.assertEqual(fake.formats, [TEXT])
        self.assertEqual(fake.open_attempts, 3)
        self.assertEqual(fake.created, fake.destroyed)

    def test_set_failure_frees_handle_and_restores_other_formats(self):
        fake = FakeClipboard((DIB, TEXT))
        snapshot = fake.desktop.clipboard_get()
        fake.failed_sets.add(8)
        with self.assertRaisesRegex(RuntimeError, "restore all clipboard"):
            fake.desktop.clipboard_restore(snapshot)
        self.assertEqual(fake.formats, [TEXT])
        self.assertEqual(len(fake.freed), 1)
        self.assertEqual(fake.created, fake.destroyed)


class ClipboardRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sra32-clipboard-")
        self.addCleanup(self.temp.cleanup)
        self.obj = await skill(Path(self.temp.name))
        atomic_json(Path(self.temp.name) / "mouse_calibration.json", CALIBRATION)
        self.loop_thread = threading.get_ident()
        self.patch = patch.object(Navigator, "pause", fast_pause)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def attach(self, formats):
        fake = FakeClipboard(formats)
        desktop = self.obj.desktop()
        desktop.clipboard_get = fake.desktop.clipboard_get
        desktop.clipboard_set = fake.desktop.clipboard_set
        desktop.clipboard_restore = fake.desktop.clipboard_restore
        return fake

    async def test_content_variants_route_with_exact_result_and_saved_bytes(self):
        cases = [
            ((TEXT,), (TEXT,), False),
            ((DIB, DIBV5, PNG, TEXT), (DIB, DIBV5, PNG, TEXT), False),
            ((FILES, CUSTOM), (FILES, CUSTOM), False),
            (((2, b"GDI"),), (), True),
            (((0xC099, b"over-cap"), TEXT), (TEXT,), True),
            ((), (), False),
        ]
        for formats, saved, partial in cases:
            with self.subTest(formats=[f for f, _ in formats]):
                fake = self.attach(formats)
                line = await call(self.obj, "plot_route", destination="Daymar")
                self.assertEqual(line, "Route request sent for Daymar. The in-game route was not verified." + (NOTE if partial else ""))
                self.assertEqual(fake.formats, list(saved))
                self.assertTrue(fake.transactions)
                self.assertNotIn(self.loop_thread, fake.transactions)
                self.assertEqual(fake.created, fake.destroyed)

    async def test_unreadable_note_is_once(self):
        fake = self.attach((DIB, PNG, TEXT))
        fake.unreadable.update({8, PNG[0]})
        line = await call(self.obj, "plot_route", destination="Daymar")
        self.assertEqual(line.count(NOTE), 1)
        self.assertIn("request sent", line)
        self.assertEqual(fake.formats, [TEXT])

    async def test_busy_snapshot_speaks_guidance_and_sends_no_input(self):
        fake = self.attach((PNG, TEXT))
        fake.busy_attempts = 3
        with patch("sra_desktop.time.sleep"):
            line = await call(self.obj, "plot_route", destination="Daymar")
        self.assertEqual(line, "The clipboard is busy; try again.")
        self.assertEqual(fake.formats, [PNG, TEXT])
        self.assertFalse(self.obj.desktop().events)

    async def test_cancel_focus_loss_and_failure_restore_every_format(self):
        for stop in ("cancel", "focus", "failure"):
            for partial in (False, True):
                with self.subTest(stop=stop, partial=partial):
                    self.obj.desktop().focus = True
                    fake = self.attach((DIB, DIBV5, PNG, FILES, CUSTOM, TEXT))
                    if partial:
                        fake.unreadable.add(PNG[0])
                    expected = [DIB, DIBV5, FILES, CUSTOM, TEXT] if partial else [DIB, DIBV5, PNG, FILES, CUSTOM, TEXT]
                    def on_event(event):
                        if event != ("press", "v"):
                            return
                        if stop == "cancel":
                            self.obj._cancelled.set()
                        elif stop == "focus":
                            self.obj.desktop().focus = False
                        else:
                            raise OSError("inert input failure")
                    self.obj.desktop().on_event = on_event
                    line = await call(self.obj, "plot_route", destination="Daymar")
                    expected_line = {"cancel": "Route cancelled.",
                        "focus": "Stopped: Star Citizen lost foreground focus. No further route input was sent.",
                        "failure": "Navigation stopped; nothing more was sent. The Wingman log has details."}[stop]
                    self.assertEqual(line, expected_line + (NOTE if partial else ""))
                    self.assertEqual(fake.formats, expected)
                    self.assertFalse(self.obj.desktop().keys)

    async def test_delayed_snapshot_keeps_loop_free_and_cancellation_waits_for_close(self):
        fake = self.attach((PNG, TEXT))
        entered, release = threading.Event(), threading.Event()
        def delayed(fmt):
            entered.set()
            release.wait(2)
        fake.on_get = delayed
        route = asyncio.create_task(call(self.obj, "plot_route", destination="Daymar"))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            route.cancel()
            for _ in range(10):
                await asyncio.sleep(0)
            self.assertFalse(route.done())
            self.assertFalse(self.obj.desktop().events)
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await route
            self.assertIsNone(fake.thread)
            self.assertFalse(self.obj._busy)
            self.assertEqual(fake.formats, [PNG, TEXT])
        finally:
            release.set()

    async def test_task_cancel_during_write_waits_then_restores_snapshot(self):
        fake = self.attach((PNG, FILES, TEXT))
        entered, release = threading.Event(), threading.Event()
        def delayed(fmt):
            if fake.formats == [(13, "Daymar\0".encode("utf-16-le"))]:
                entered.set()
                release.wait(2)
        fake.on_set = delayed
        route = asyncio.create_task(call(self.obj, "plot_route", destination="Daymar"))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            route.cancel()
            for _ in range(10):
                await asyncio.sleep(0)
            self.assertFalse(route.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await route
            self.assertEqual(fake.formats, [PNG, FILES, TEXT])
            self.assertIsNone(fake.thread)
            self.assertFalse(self.obj.desktop().keys)
        finally:
            release.set()
