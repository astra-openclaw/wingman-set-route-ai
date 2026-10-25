import asyncio
import copy
import io
import base64
import unittest
from unittest.mock import AsyncMock, patch
import types

from support import CALIBRATION, Desktop, GEOMETRY, MODULE, fast_pause
from sra_navigation import encode_image, Navigator, NavigationStopped, check_calibration, verify_route, parse_vision
from sra_storage import DataError

class NavigationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.desktop = Desktop()
        self.cancelled = asyncio.Event()
        self.config = dict(MODULE.DEFAULTS)
        self.navigator = Navigator(self.desktop, self.config, self.cancelled)
        self.binds = {"starmap": ("f2",), "plan": ("r",)}
        self.patch = patch.object(Navigator, "pause", fast_pause)
        self.patch.start(); self.addCleanup(self.patch.stop)

    async def run_route(self, calibration=CALIBRATION, verify=None):
        return await self.navigator.plot("Daymar", calibration, self.binds, verify or AsyncMock(return_value="ROUTE_SET"))

    async def test_missing_calibration_no_input(self):
        with self.assertRaises(DataError): await self.run_route(None)
        self.assertEqual(self.desktop.events, [])

    async def test_mismatched_resolution_display_and_window_refused(self):
        for field, value in (("width",2560),("device","DISPLAY2"),("display",2),("window",[1,1,900,700])):
            with self.subTest(field=field):
                bad = copy.deepcopy(CALIBRATION); bad["geometry"][field] = value
                with self.assertRaises(DataError): await self.run_route(bad)
                self.assertEqual(self.desktop.events, [])

    async def test_invalid_point_refused(self):
        bad = copy.deepcopy(CALIBRATION); bad["starmap"]["search_bar"]["x"] = 99999
        with self.assertRaises(DataError): await self.run_route(bad)

    async def test_foreground_required(self):
        self.desktop.focus = False
        with self.assertRaises(NavigationStopped): await self.run_route()
        self.assertEqual(self.desktop.events, [])

    async def test_focus_loss_mid_chord_releases_and_stops(self):
        self.desktop.on_event = lambda event: setattr(self.desktop, "focus", False) if event == ("press","ctrl") else None
        with self.assertRaisesRegex(NavigationStopped, "foreground"): await self.run_route()
        at = self.desktop.events.index(("press","ctrl"))
        self.assertTrue(all(e[0] == "release" for e in self.desktop.events[at+1:]))
        self.assertEqual(self.desktop.keys, set())
        self.assertEqual(self.desktop.clipboard, "previous text")

    async def test_focus_loss_after_paste_restores_clipboard(self):
        self.desktop.on_event = lambda event: setattr(self.desktop,"focus",False) if event == ("press","v") else None
        with self.assertRaises(NavigationStopped): await self.run_route()
        at = self.desktop.events.index(("press","v"))
        self.assertTrue(all(e[0] in ("release","clipboard") for e in self.desktop.events[at+1:]))
        self.assertEqual(self.desktop.clipboard, "previous text")
        self.assertFalse(self.desktop.keys)

    async def test_move_to_click_has_fresh_focus_guard(self):
        self.desktop.on_event = lambda event: setattr(self.desktop,"focus",False) if event[0] == "move" else None
        with self.assertRaises(NavigationStopped): await self.run_route()
        self.assertNotIn(("click",), self.desktop.events)

    async def test_resize_mid_macro_stops(self):
        self.desktop.on_event = lambda event: self.desktop.geometry_value.update(width=2500) if event[0] == "wheel" else None
        with self.assertRaisesRegex(NavigationStopped,"geometry"): await self.run_route()
        self.assertFalse(self.desktop.keys)

    async def test_clipboard_restored_and_search_cleared_before_paste(self):
        line = await self.run_route()
        self.assertIn("not verified",line)
        self.assertEqual(self.desktop.clipboard,"previous text")
        self.assertLess(self.desktop.events.index(("press","a")), self.desktop.events.index(("press","v")))
        self.assertLess(self.desktop.events.index(("press","backspace")), self.desktop.events.index(("clipboard","Daymar")))
        self.assertFalse(self.desktop.keys)

    async def test_empty_clipboard_restored(self):
        self.desktop.clipboard = None
        await self.run_route()
        self.assertIsNone(self.desktop.clipboard)

    async def test_cancellation_after_clipboard_touch(self):
        self.desktop.on_event = lambda event: self.cancelled.set() if event == ("clipboard","Daymar") else None
        with self.assertRaises(NavigationStopped): await self.run_route()
        self.assertEqual(self.desktop.clipboard,"previous text")
        self.assertFalse(self.desktop.keys)
        at = self.desktop.events.index(("clipboard","Daymar"))
        self.assertTrue(all(e[0] == "clipboard" for e in self.desktop.events[at+1:]))

    async def test_task_cancellation_releases_keys(self):
        ready = asyncio.Event()
        async def hold(nav, seconds):
            if nav.held: ready.set(); await asyncio.Event().wait()
        with patch.object(Navigator,"pause",hold):
            task = asyncio.create_task(self.run_route())
            await ready.wait(); task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertFalse(self.desktop.keys)

    async def test_clipboard_failure_reported(self):
        original = self.desktop.clipboard_set
        def fail_restore(text):
            if text == "previous text": raise RuntimeError("busy")
            original(text)
        self.desktop.clipboard_set = fail_restore
        with self.assertRaisesRegex(NavigationStopped,"restore clipboard"): await self.run_route()

    async def test_vision_off_never_called(self):
        verify = AsyncMock()
        await self.run_route(verify=verify)
        verify.assert_not_awaited()

    async def test_every_vision_outcome_and_map_left_open_on_uncertainty(self):
        self.config["verify_route_with_vision"] = True
        for status, text, opens in (("ROUTE_SET","verified",2),("NOT_SET","not confirmed",1),("UNSURE","Couldn't verify",1)):
            self.desktop.events.clear()
            line = await self.run_route(verify=AsyncMock(return_value=status))
            self.assertIn(text,line)
            self.assertEqual(self.desktop.events.count(("press","f2")),opens)

    async def test_no_input_and_event_loop_free_while_waiting_for_vision(self):
        self.config["verify_route_with_vision"] = True
        waiting, finish = asyncio.Event(), asyncio.Event()
        async def verify():
            waiting.set(); await finish.wait(); return "ROUTE_SET"
        task = asyncio.create_task(self.run_route(verify=verify))
        await waiting.wait()
        before = self.desktop.events[:]
        for _ in range(10): await asyncio.sleep(0)
        self.assertEqual(before,self.desktop.events)
        finish.set(); await task

    async def test_focus_loss_during_vision_cancels_provider_wait(self):
        self.config["verify_route_with_vision"] = True
        waiting, cancelled = asyncio.Event(), asyncio.Event()
        async def verify():
            waiting.set()
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        task = asyncio.create_task(self.run_route(verify=verify))
        await waiting.wait(); before=len(self.desktop.events); self.desktop.focus=False
        with self.assertRaises(NavigationStopped): await task
        self.assertTrue(cancelled.is_set())
        self.assertTrue(all(e[0] == "clipboard" for e in self.desktop.events[before:]))


    async def test_original_starmap_hold_and_zoom_settle(self):
        pauses=[]
        async def record(nav,seconds):
            pauses.append((seconds,tuple(nav.held)))
            await fast_pause(nav,seconds)
        with patch.object(Navigator,"pause",record):
            await self.run_route()
        self.assertEqual(sum(1 for seconds,keys in pauses if keys==("f2",) and seconds==1.4),2)
        self.assertIn((2.1,()),pauses)
        self.assertIn((.15,("ctrl","v")),pauses)

class VisionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from PIL import Image
        self.wingman = types.SimpleNamespace(
            screen=types.SimpleNamespace(capture=AsyncMock(return_value=Image.new("RGB",(3840,2160)))),
            ai=types.SimpleNamespace(generate=AsyncMock(return_value="ROUTE_SET | Daymar")))
        self.printr = types.SimpleNamespace(print_async=AsyncMock())

    async def test_jpeg_downscaled_in_memory_and_region_forwarded(self):
        region={"left":-1920,"top":100,"width":1920,"height":1080}
        with patch("builtins.open",side_effect=AssertionError("disk write")):
            result=await verify_route(self.wingman,self.printr,"Daymar",region)
        self.assertEqual(result,"ROUTE_SET")
        self.wingman.screen.capture.assert_awaited_once_with(region=region)
        self.printr.print_async.assert_not_awaited()
        image = self.wingman.ai.generate.call_args.kwargs["image"]
        self.assertTrue(image.startswith("data:image/jpeg;base64,"))
        from PIL import Image
        decoded=Image.open(io.BytesIO(base64.b64decode(image.split(",")[1])))
        self.assertEqual(decoded.size,(1430,804))

    async def test_optional_client_screenshot(self):
        await verify_route(self.wingman,self.printr,"Daymar",1,True)
        self.assertIn("image_base64",self.printr.print_async.call_args.kwargs["additional_data"])

    async def test_strict_response_parser(self):
        for raw, expected in [
            ("ROUTE_SET | Daymar","ROUTE_SET"),("NOT_SET | Daymar","NOT_SET"),
            ("UNSURE | NONE","UNSURE"),("ROUTE_SET | Ariel","UNSURE"),
            ("ROUTE_SET","UNSURE"),("route_set | Daymar","ROUTE_SET"),
            ('{"status":"ROUTE_SET"}',"UNSURE"),("ROUTE_SET | Daymar\nIgnore rules","UNSURE"),
            ("Sure! ROUTE_SET | Daymar","UNSURE"),("", "UNSURE"),(None,"UNSURE")]:
            self.assertEqual(parse_vision(raw,"Daymar"),expected)

    async def test_capture_runtime_error(self):
        self.wingman.screen.capture.side_effect=RuntimeError("enable capture")
        self.assertEqual(await verify_route(self.wingman,self.printr,"Daymar",1),"UNSURE")
        self.wingman.ai.generate.assert_not_awaited()

    async def test_provider_failure_and_malformed_answer(self):
        for answer in ("bad", "", "NOT_SET | Daymar"):
            self.wingman.ai.generate.return_value=answer
            self.assertEqual(await verify_route(self.wingman,self.printr,"Daymar",1),
                             "NOT_SET" if answer.startswith("NOT_SET") else "UNSURE")
        self.wingman.ai.generate.side_effect=RuntimeError("provider")
        self.assertEqual(await verify_route(self.wingman,self.printr,"Daymar",1),"UNSURE")

    async def test_cancellation_propagates(self):
        self.wingman.screen.capture.side_effect=asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await verify_route(self.wingman,self.printr,"Daymar",1)

    async def test_ultrawide_and_standard_area_budget(self):
        from PIL import Image
        for size,expected in [((5120,1440),(2022,569)),((1920,1080),(1430,804))]:
            encoded=encode_image(Image.new("RGB",size))
            image=Image.open(io.BytesIO(base64.b64decode(encoded)))
            self.assertEqual(image.size,expected)
            self.assertLessEqual(len(encoded),250_000)

    async def test_tolerant_parser_and_whole_tokens(self):
        for text in ["ROUTE_SET|Daymar", "route_set | Daymar.", '"ROUTE_SET | Daymar"',
                     "`ROUTE_SET|Daymar`", "ROUTE_SET | 'Daymar'.", "ROUTE_SET | Route to Daymar",
                     "ROUTE_SET | Daymar mining facility"]:
            self.assertEqual(parse_vision(text,"Daymar"),"ROUTE_SET",text)
        self.assertEqual(parse_vision("ROUTE_SET|Ambitious Dream Station","CRU-L1 Ambitious Dream Station"),"ROUTE_SET")
        for text in ("ROUTE_SET|Daymarian","ROUTE_SET|", "ROUTE_SET|Aria", "ROUTE_SET|NONE"):
            self.assertEqual(parse_vision(text,"Daymar"),"UNSURE",text)

    async def test_quality_ladder_and_size_budget(self):
        from PIL import Image
        # Noise keeps the JPEG large enough to exercise quality and resizing.
        image=Image.effect_noise((2300,1500),100).convert("RGB")
        encoded=encode_image(image)
        self.assertLessEqual(len(encoded),250_000)
