"""Cancellation output is played on each originating turn's own thread/loop."""
import asyncio
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from support import skill, CALIBRATION, atomic_json, fast_pause, Benchmark, MODULE
from sra_navigation import Navigator


class CancelSpeechTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sra32-cancel-speech-")
        self.addCleanup(self.temp.cleanup)
        self.user = Path(self.temp.name)
        self.obj = asyncio.run(skill(self.user))
        atomic_json(self.user / "mouse_calibration.json", CALIBRATION)
        self.returned = {}
        self.spoken = []
        self.events = []
        self.failures = []
        self.identities = {}

    def turn(self, label, factory):
        def run():
            try:
                asyncio.run(factory())
            except BaseException as exc:
                self.failures.append(exc)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def join(self, *threads):
        for thread in threads:
            thread.join(4)
            self.assertFalse(thread.is_alive(), "Turn did not finish")
        self.assertEqual(self.failures, [])

    async def execute(self, label, tool, **parameters):
        benchmark = Benchmark()
        self.identities[label] = (threading.get_ident(), id(asyncio.get_running_loop()))
        self.returned[label] = await self.obj.execute_tool(tool, parameters, benchmark)
        self.assertEqual(benchmark.open, 0)
        return self.returned[label][1]

    async def play(self, label, text):
        result = await self.obj.on_play_to_user(text, None)
        if result != "{SKIP-TTS}":
            self.spoken.append((label, result))
            await self.obj._playback_started(self.obj.wingman.name)
            self.events.append((label, "started"))
            await self.obj._playback_finished(self.obj.wingman.name)
            self.events.append((label, "finished"))
        return result

    def ordered_cancellation(self, tool, first, clear_guard):
        ready = threading.Event()
        gates = {name: threading.Event() for name in ("operation", "cancel")}
        gates[first].set()
        order = []
        original = (self.user / "mouse_calibration.json").read_bytes()

        async def hold(*args, **kwargs):
            ready.set()
            await asyncio.Event().wait()

        async def operation():
            line = await self.execute("operation", tool, **({"destination": "Daymar"} if tool == "plot_route" else {}))
            self.assertTrue(await asyncio.to_thread(gates["operation"].wait, 3))
            await self.play("operation", line)
            order.append("operation")
            gates["cancel"].set()

        async def cancel():
            if clear_guard:
                await self.obj.on_add_user_message("Cancel route.")
            line = await self.execute("cancel", "cancel_route")
            self.assertTrue(await asyncio.to_thread(gates["cancel"].wait, 3))
            await self.play("cancel", line)
            order.append("cancel")
            # Playback finished before the other turn may submit its line.
            gates["operation"].set()

        with patch.object(Navigator, "pause", hold), patch.object(self.obj.wingman.tts, "speak", hold):
            route = self.turn("operation", operation)
            self.assertTrue(ready.wait(3))
            stop = self.turn("cancel", cancel)
            self.join(route, stop)
        expected = MODULE.CALIBRATION_CANCELLED if tool == "calibrate_mouse" else MODULE.ROUTE_CANCELLED
        self.assertEqual(self.spoken, [("cancel", expected)])
        self.assertEqual(order, [first, "operation" if first == "cancel" else "cancel"])
        self.assertEqual(self.events, [("cancel", "started"), ("cancel", "finished")])
        self.assertNotEqual(*self.identities.values())
        self.assertNotEqual(self.returned["operation"][0], self.returned["cancel"][0])
        self.assertEqual((self.user / "mouse_calibration.json").read_bytes(), original)
        self.assertFalse(self.obj.desktop().keys)

    def test_route_cancel_plays_first_and_finishes_before_stopped_turn(self):
        self.ordered_cancellation("plot_route", "cancel", clear_guard=False)

    def test_route_stopped_turn_arrives_before_cancel_confirmation(self):
        self.ordered_cancellation("plot_route", "operation", clear_guard=True)

    def test_calibration_cancel_plays_first(self):
        self.ordered_cancellation("calibrate_mouse", "cancel", clear_guard=True)

    def test_calibration_stopped_turn_arrives_first(self):
        self.ordered_cancellation("calibrate_mouse", "operation", clear_guard=False)

    def stop_without_playback(self):
        ready = threading.Event()
        async def hold(nav, seconds):
            ready.set()
            await asyncio.Event().wait()
        with patch.object(Navigator, "pause", hold):
            route = self.turn("operation", lambda: self.execute("operation", "plot_route", destination="Daymar"))
            self.assertTrue(ready.wait(3))
            stop = self.turn("cancel", lambda: self.execute("cancel", "cancel_route"))
            self.join(route, stop)

    def test_receipts_survive_playback_and_new_route_without_affecting_its_line(self):
        self.stop_without_playback()
        asyncio.run(self.play("cancel", self.returned["cancel"][1]))
        asyncio.run(self.obj.on_add_user_message("Plot a route to Daymar."))
        with patch.object(Navigator, "pause", fast_pause):
            normal = self.turn("normal", lambda: self.execute("normal", "plot_route", destination="Daymar"))
            self.join(normal)
        guard = self.obj._speech_guard
        self.assertEqual(asyncio.run(self.play("operation", self.returned["operation"][1])), "{SKIP-TTS}")
        self.assertIs(self.obj._speech_guard, guard)
        self.assertEqual(asyncio.run(self.play("normal", self.returned["normal"][1])), self.returned["normal"][1])
        self.assertEqual([label for label, _ in self.spoken], ["cancel", "normal"])
        self.assertEqual(self.obj._speech_suppressed, [])

    def test_suppression_expires_independently_of_guard(self):
        self.stop_without_playback()
        expiry = max(self.obj._speech_suppressed[0][1], self.obj._speech_allowed[0][1])
        asyncio.run(self.obj.on_add_user_message("Another question."))
        with patch.object(MODULE.time, "monotonic", return_value=expiry):
            line = self.returned["operation"][1]
            self.assertEqual(asyncio.run(self.play("expired", line)), line)
            self.assertEqual(self.obj._speech_suppressed, [])
            self.assertEqual(self.obj._speech_allowed, [])

    def test_suppression_is_one_shot_and_outlives_guard_timeout(self):
        self.stop_without_playback()
        start = self.obj._speech_guard["time"]
        line = self.returned["operation"][1]
        with patch.object(MODULE.time, "monotonic", return_value=start + 26):
            self.assertEqual(asyncio.run(self.play("operation", line)), "{SKIP-TTS}")
            self.assertEqual(asyncio.run(self.play("one shot consumed", line)), line)

    def test_second_cancel_while_stopping_does_not_duplicate_confirmation(self):
        ready, cleaning, release = (threading.Event() for _ in range(3))
        async def hold(nav, seconds):
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                self.assertTrue(await asyncio.to_thread(release.wait, 3))
        async def request(label, tool, **parameters):
            line = await self.execute(label, tool, **parameters)
            await self.play(label, line)
        with patch.object(Navigator, "pause", hold):
            route = self.turn("operation", lambda: request("operation", "plot_route", destination="Daymar"))
            self.assertTrue(ready.wait(3))
            stop = self.turn("cancel", lambda: request("cancel", "cancel_route"))
            self.assertTrue(cleaning.wait(3))
            try:
                again = self.turn("again", lambda: request("again", "cancel_route"))
                self.join(again)
                self.assertEqual(self.returned["again"][1], MODULE.STOPPING)
            finally:
                release.set()
            self.join(route, stop)
        self.assertEqual([text for _, text in self.spoken], [MODULE.STOPPING, MODULE.ROUTE_CANCELLED])
        self.assertFalse(self.obj.desktop().keys)

    def test_cleanup_warning_and_partial_clipboard_notice_move_to_cancel_turn(self):
        from sra_desktop import ClipboardSnapshot
        ready = threading.Event()
        snapshot = self.obj.desktop().clipboard_get()
        self.obj.desktop().clipboard_get = lambda: ClipboardSnapshot(snapshot.formats, partial=True)
        def cannot_restore(snapshot):
            raise OSError("inert clipboard failure")
        self.obj.desktop().clipboard_restore = cannot_restore
        async def hold(nav, seconds):
            if "v" in nav.held:
                ready.set()
                await asyncio.Event().wait()
            await fast_pause(nav, seconds)
        async def request(label, tool, **parameters):
            line = await self.execute(label, tool, **parameters)
            await self.play(label, line)
        with patch.object(Navigator, "pause", hold):
            operation = self.turn("operation", lambda: request("operation", "plot_route", destination="Daymar"))
            self.assertTrue(ready.wait(3))
            stop = self.turn("cancel", lambda: request("cancel", "cancel_route"))
            self.join(operation, stop)
        expected = (MODULE.ROUTE_CANCELLED + " Stopped. Could not restore all clipboard content."
                    + " Some clipboard content couldn't be kept.")
        self.assertEqual(self.spoken, [("cancel", expected)])
        self.assertEqual(self.returned["operation"], ("Route operation cancelled.", "Route operation cancelled."))
        self.assertFalse(self.obj.desktop().keys)

    def test_cancel_before_navigation_task_exists_still_has_single_owner(self):
        ready, release = threading.Event(), threading.Event()
        self.obj.engine = None
        validate = self.obj.validate
        async def delayed_validate():
            ready.set()
            self.assertTrue(await asyncio.to_thread(release.wait, 3))
            return await validate()
        async def request(label, tool, **parameters):
            line = await self.execute(label, tool, **parameters)
            await self.play(label, line)
        self.obj.validate = delayed_validate
        operation = self.turn("operation", lambda: request("operation", "plot_route", destination="Daymar"))
        self.assertTrue(ready.wait(3))
        stop = self.turn("cancel", lambda: request("cancel", "cancel_route"))
        self.assertTrue(self.obj._cancelled.wait(3))
        release.set()
        self.join(operation, stop)
        self.assertEqual(self.spoken, [("cancel", MODULE.ROUTE_CANCELLED)])
        self.assertFalse(self.obj.desktop().events)

    def test_idle_cancel_line_unchanged(self):
        async def idle():
            line = await self.execute("idle", "cancel_route")
            await self.play("idle", line)
        idle = self.turn("idle", idle)
        self.join(idle)
        self.assertEqual(self.spoken, [("idle", "No route or calibration is running.")])

    def test_internal_stop_and_focus_loss_still_speak_their_own_lines(self):
        for stop in ("internal", "focus"):
            with self.subTest(stop=stop):
                self.obj.desktop().focus = True
                def event(value):
                    if value == ("press", "v"):
                        if stop == "internal":
                            self.obj._cancelled.set()
                        else:
                            self.obj.desktop().focus = False
                self.obj.desktop().on_event = event
                async def route():
                    line = await self.execute(stop, "plot_route", destination="Daymar")
                    await self.play(stop, line)
                with patch.object(Navigator, "pause", fast_pause):
                    thread = self.turn(stop, route)
                    self.join(thread)
                self.assertEqual(self.spoken[-1], (stop, self.returned[stop][1]))
                self.assertFalse(self.obj._speech_suppressed)
                self.assertFalse(self.obj._speech_allowed)

    def test_unload_alone_keeps_operation_stop_speech(self):
        ready = threading.Event()
        async def hold(nav, seconds):
            ready.set()
            await asyncio.Event().wait()
        async def route():
            line = await self.execute("operation", "plot_route", destination="Daymar")
            await self.play("operation", line)
        with patch.object(Navigator, "pause", hold):
            operation = self.turn("operation", route)
            self.assertTrue(ready.wait(3))
            unload = self.turn("unload", self.obj.unload)
            self.join(operation, unload)
        self.assertEqual(self.spoken, [("operation", MODULE.CANCELLED)])
        self.assertFalse(self.obj._speech_suppressed)
