import asyncio
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from support import skill, call, MODULE


class SpeechGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sra32-speech-")
        self.addCleanup(self.temp.cleanup)
        self.obj = await skill(Path(self.temp.name))
        self.name = self.obj.wingman.name

    async def play(self, text):
        result = await self.obj.on_play_to_user(text, None)
        if result != "{SKIP-TTS}":
            await self.obj._playback_started(self.name)
            await self.obj._playback_finished(self.name)
        return result

    async def test_fast_return_blocks_fillers_before_and_after(self):
        for destination in ("aerial", "CRU L99", "Daymar"):
            await self.obj.on_add_user_message("navigation request")
            original = self.obj.engine.find_destination
            def resolve(*args, **kwargs):
                self.assertEqual(asyncio.run(self.obj.on_play_to_user("Routing now.", None)), "{SKIP-TTS}")
                return original(*args, **kwargs)
            with patch.object(self.obj.engine, "find_destination", resolve):
                line = await call(self.obj, "plot_route", destination=destination)
            self.assertFalse(self.obj._busy)
            self.assertEqual(await self.obj.on_play_to_user("Course set!", None), "{SKIP-TTS}")
            self.assertEqual(await self.play(line), line)
            self.assertEqual(await self.play("Ordinary conversation."), "Ordinary conversation.")

    async def test_exact_expected_line_only_once_and_other_playback_ignored(self):
        line = await call(self.obj, "plot_route", destination="aerial")
        await self.obj._playback_started(self.name)
        await self.obj._playback_finished(self.name)
        self.assertIsNotNone(self.obj._speech_guard)  # An earlier filler finishing is not our reply.
        self.assertEqual(await self.obj.on_play_to_user(line, None), line)
        self.assertEqual(await self.obj.on_play_to_user(line, None), "{SKIP-TTS}")
        await self.obj._playback_started("Other Pilot")
        await self.obj._playback_finished("Other Pilot")
        self.assertIsNotNone(self.obj._speech_guard)
        await self.obj._playback_started(self.name)
        self.assertEqual(await self.obj.on_play_to_user("Another filler", None), "{SKIP-TTS}")
        await self.obj._playback_finished(self.name)
        self.assertIsNone(self.obj._speech_guard)

    async def test_timeout_next_message_and_stale_completion(self):
        line = await call(self.obj, "plot_route", destination="Daymar")
        start = self.obj._speech_guard["time"]
        with patch.object(MODULE.time, "monotonic", return_value=start + 24.9):
            self.assertEqual(await self.obj.on_play_to_user("Filler", None), "{SKIP-TTS}")
        with patch.object(MODULE.time, "monotonic", return_value=start + 25):
            self.assertEqual(await self.obj.on_play_to_user("Normal", None), "Normal")
        old_guard = self.obj._arm()
        await self.obj.on_add_user_message("new turn")
        self.obj._expect_speech(old_guard, line, final=True)
        self.assertEqual(await self.obj.on_play_to_user("Normal", None), "Normal")
        newer = self.obj._arm()
        self.obj._expect_speech(old_guard, line, final=True)
        self.assertIs(self.obj._speech_guard, newer)

    async def test_calibration_languages_steps_final_and_fillers_in_order(self):
        for language, instructions in MODULE.CALIBRATION.items():
            self.obj.config.custom_properties = [types.SimpleNamespace(id="language", value=language)]
            clicks = iter([False, False, True, False] * 3)
            self.obj.desktop().left_pressed = lambda: next(clicks)
            spoken = []
            async def speak(text, **kwargs):
                self.assertEqual(await self.play("Calibrating now."), "{SKIP-TTS}")
                self.assertEqual(await self.obj.on_play_to_user(text, None), text)
                spoken.append(text)
                await self.obj._playback_started(self.name)
                self.assertEqual(await self.play("Still calibrating."), "{SKIP-TTS}")
                await self.obj._playback_finished(self.name)
                self.assertEqual(await self.play("Background filler."), "{SKIP-TTS}")
                return True
            self.obj.wingman.tts.speak = speak
            line = await call(self.obj, "calibrate_mouse")
            self.assertEqual(spoken, [step.format(key="f2") for step in instructions])
            self.assertIn("calibration complete", line)
            self.assertEqual(await self.play("Finished already!"), "{SKIP-TTS}")
            self.assertEqual(await self.play(line), line)
            self.assertIsNone(self.obj._speech_guard)

    async def test_normalization_preserves_unicode_and_accepts_punctuation_changes(self):
        guard = self.obj._arm()
        self.obj._expect_speech(guard, "Öffne die Sternenkarte. 星図。", final=True)
        expected = "ÖFFNE die Sternenkarte — 星図"
        self.assertEqual(await self.play(expected), expected)

    async def test_guard_hooks_are_safe_on_independent_turn_threads(self):
        line = await call(self.obj, "plot_route", destination="aerial")
        def hook(text):
            return asyncio.run(self.obj.on_play_to_user(text, None))
        outputs = await asyncio.gather(*(asyncio.to_thread(hook, "Filler") for _ in range(20)))
        self.assertEqual(set(outputs), {"{SKIP-TTS}"})
        outputs = await asyncio.gather(*(asyncio.to_thread(hook, line) for _ in range(8)))
        self.assertEqual(outputs.count(line), 1)
        await asyncio.to_thread(lambda: asyncio.run(self.obj._playback_started(self.name)))
        await asyncio.to_thread(lambda: asyncio.run(self.obj._playback_finished(self.name)))
        self.assertIsNone(self.obj._speech_guard)

    async def test_long_operation_stays_guarded_until_final_timeout_window(self):
        guard = self.obj._arm()
        with patch.object(MODULE.time, "monotonic", return_value=guard["time"] + 90):
            self.assertEqual(await self.obj.on_play_to_user("Filler", None), "{SKIP-TTS}")
        self.obj._expect_speech(guard, "Final reply.", final=True)
        self.assertEqual(await self.play("Final reply."), "Final reply.")

    async def test_prepare_subscribes_once_and_unload_detaches(self):
        subscriptions = []
        def subscribe(callback):
            sub = types.SimpleNamespace(unsubscribe=Mock())
            subscriptions.append((callback, sub))
            return sub
        self.obj.wingman.audio.on_playback_started = subscribe
        self.obj.wingman.audio.on_playback_finished = subscribe
        await self.obj.prepare()
        await self.obj.prepare()
        self.assertEqual(len(subscriptions), 2)
        await call(self.obj, "plot_route", destination="Daymar")
        await self.obj.unload()
        await self.obj.unload()
        for _, sub in subscriptions:
            sub.unsubscribe.assert_called_once()
        self.assertIsNone(self.obj._speech_guard)
