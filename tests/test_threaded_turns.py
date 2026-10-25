"""Mirror Core: initialization, route, cancel and unload use distinct event loops."""
import asyncio
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from support import skill, call, CALIBRATION, atomic_json, fast_pause
from sra_navigation import Navigator


class ThreadedTurnTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sra32-threaded-")
        self.addCleanup(self.temp.cleanup)
        self.user = Path(self.temp.name)
        self.obj = asyncio.run(skill(self.user))
        atomic_json(self.user/"mouse_calibration.json", CALIBRATION)
        self.results = {}
        self.threads = []

    def turn(self, label, factory):
        def run():
            try:
                self.results[label] = asyncio.run(factory())
            except BaseException as exc:
                self.results[label] = exc
        thread = threading.Thread(target=run, daemon=True)
        self.threads.append(thread)
        thread.start()
        return thread

    def join(self, thread):
        thread.join(3)
        self.assertFalse(thread.is_alive(), "Turn failed to finish within three seconds")

    def test_route_cancel_and_unload_three_loops_cleanup(self):
        ready = threading.Event()
        async def hold(nav, seconds):
            if "v" in nav.held:
                ready.set()
                await asyncio.Event().wait()
            await fast_pause(nav, seconds)
        with patch.object(Navigator, "pause", hold):
            route = self.turn("route", lambda: call(self.obj, "plot_route", destination="Daymar"))
            self.assertTrue(ready.wait(3))
            before = len(self.obj.desktop().events)
            started = time.monotonic()
            cancel = self.turn("cancel", lambda: call(self.obj, "cancel_route"))
            unload = self.turn("unload", self.obj.unload)
            for thread in (route, cancel, unload):
                self.join(thread)
            self.assertLess(time.monotonic()-started, .2)
        self.assertIn("cancelled", self.results["route"])
        # Unload may win the stop claim before the explicit cancel turn.
        self.assertTrue(any(part in self.results["cancel"] for part in ("cancelled", "No route", "Navigation is stopping")))
        self.assertIsNone(self.results["unload"])
        self.assertFalse(self.obj.desktop().keys)
        self.assertEqual(self.obj.desktop().clipboard, "previous text")
        self.assertTrue(all(e[0] in ("release","clipboard") for e in self.obj.desktop().events[before:]))

    def test_calibration_cancel_from_other_loop_preserves_file(self):
        ready = threading.Event()
        original = (self.user/"mouse_calibration.json").read_bytes()
        async def speak(*args, **kwargs):
            ready.set()
            await asyncio.Event().wait()
        self.obj.wingman.tts.speak = speak
        calibration = self.turn("calibrate", lambda: call(self.obj, "calibrate_mouse"))
        self.assertTrue(ready.wait(3))
        started = time.monotonic()
        cancel = self.turn("cancel", lambda: call(self.obj, "cancel_route"))
        self.join(calibration)
        self.join(cancel)
        self.assertLess(time.monotonic()-started, .2)
        self.assertIn("cancelled", self.results["calibrate"])
        self.assertIn("cancelled", self.results["cancel"])
        self.assertEqual((self.user/"mouse_calibration.json").read_bytes(), original)
        self.assertIsNone(self.obj._operation_kind)

    def test_unload_alone_from_another_loop_stops_route(self):
        ready = threading.Event()
        async def hold(nav, seconds):
            ready.set()
            await asyncio.Event().wait()
        with patch.object(Navigator, "pause", hold):
            route = self.turn("route", lambda: call(self.obj, "plot_route", destination="Daymar"))
            self.assertTrue(ready.wait(3))
            unload = self.turn("unload", self.obj.unload)
            self.join(route)
            self.join(unload)
        self.assertIn("cancelled", self.results["route"])
        self.assertFalse(self.obj.desktop().keys)

    def test_simultaneous_routes_claim_exactly_one_macro(self):
        ready = threading.Event()
        gate = threading.Barrier(2)
        async def hold(nav, seconds):
            ready.set()
            await asyncio.Event().wait()
        async def plot():
            gate.wait(3)
            return await call(self.obj, "plot_route", destination="Daymar")
        with patch.object(Navigator, "pause", hold):
            a = self.turn("a", plot)
            b = self.turn("b", plot)
            self.assertTrue(ready.wait(3))
            # The losing turn finishes immediately; keep the winner blocked
            # until the claim's rejection has been observed.
            deadline = time.monotonic()+2
            while not self.results and time.monotonic() < deadline:
                time.sleep(.001)
            self.assertEqual(len(self.results), 1)
            self.assertIn("busy", next(iter(self.results.values())))
            self.assertEqual(self.obj.desktop().events.count(("press","f2")), 1)
            cancel = self.turn("cancel", lambda: call(self.obj, "cancel_route"))
            for thread in (a,b,cancel):
                self.join(thread)
        self.assertFalse(self.obj.desktop().keys)
        self.assertTrue(self.obj._done.is_set())
