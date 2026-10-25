"""Offline acceptance against official Wingman source; all peripherals are inert.

Run: python tests/compatibility.py --reference <Wingman AI 3.2.11 source checkout>
Only test copies of the skill's data are ever written.
"""
import argparse
import ast
import asyncio
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import AsyncMock, patch

import rapidfuzz
import yaml

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "set_route_ai"
MODULE = FACADE = CONFIG = CUSTOM = CATALOG = None


def stub(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    return module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Printr:
    def print(self, *args, **kwargs):
        pass

    async def print_async(self, *args, **kwargs):
        pass


class Events:
    def subscribe(self, *args):
        pass

    def unsubscribe(self, *args):
        pass


class SecretKeeper:
    def __init__(self):
        self.secret_events = Events()


class Benchmark:
    def __init__(self):
        self.starts = []
        self.finishes = 0

    def start_snapshot(self, label):
        self.starts.append(label)

    def finish_snapshot(self):
        self.finishes += 1


class Compatibility(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for source in (PAYLOAD / "data").glob("*.json"):
            shutil.copyfile(source, CUSTOM / "set_route_ai/data" / source.name)
        self.speech = []

        async def runtime_speak(text, **kwargs):
            self.speech.append((text, kwargs))
            await asyncio.sleep(0)
            return True

        self.runtime = types.SimpleNamespace(
            context_budget=types.SimpleNamespace(tool_cap=32000),
            play_to_user=runtime_speak,
            audio_player=types.SimpleNamespace(is_playing=False),
        )
        # Real facade objects, no old methods injected onto the skill boundary.
        self.facade = types.SimpleNamespace(
            ai=FACADE.SkillAi(self.runtime),
            tts=FACADE.SkillTts(self.runtime),
            audio=FACADE.SkillAudio(self.runtime),
        )
        self.obj = MODULE.SetRouteAI(CONFIG.model_copy(deep=True),
                                    types.SimpleNamespace(debug_mode=False), self.facade)
        self.assertEqual(await self.obj.validate(), [])

    async def call(self, name, parameters=None):
        benchmark = Benchmark()
        result = await self.obj.execute_tool(name, parameters or {}, benchmark)
        self.assertEqual(len(benchmark.starts), 1)
        self.assertEqual(benchmark.finishes, 1)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(isinstance(value, str) for value in result))
        return result[0]

    async def test_genuine_schema_catalog_and_tool_inventory(self):
        self.assertEqual(CONFIG.api_version, 3)
        self.assertEqual(CONFIG.author, "Thord - galacticgearjammer - ProjectGnome")
        self.assertEqual(next(p.value for p in CONFIG.custom_properties if p.id == "language"), "en")
        self.assertEqual(CATALOG.verdict.value, "ok", CATALOG.reason)
        self.assertEqual({name for name, _ in self.obj.get_tools()}, {
            "plot_route", "calibrate_mouse", "add_destination", "delete_destination",
            "rename_destination", "add_alias", "delete_alias", "list_aliases",
        })
        self.assertNotIn("list_destinations", CONFIG.prompt)
        self.assertNotIn("register it as a new destination", CONFIG.prompt)

    async def test_unchanged_fixtures_and_real_database_smoke(self):
        for source in (ROOT / "original/set_route_ai/data").glob("*.json"):
            self.assertEqual(source.read_bytes(), (PAYLOAD / "data" / source.name).read_bytes())
        self.assertEqual(len(self.obj.engine.destinations), 1317)
        self.assertEqual(len(self.obj.engine.learning), 19)
        for name in ("Daymar", "Port Tressler", "Baijini Point", "Everus Harbor", "Orison"):
            matched, alternatives = self.obj.engine.find_destination(name)
            self.assertEqual(matched, name.lower())
            self.assertEqual(alternatives, [])
        self.assertEqual(self.obj.engine.find_destination("port tresler")[0], "port tressler")
        self.assertEqual((self.obj.search_x, self.obj.search_y), (469, 269))
        self.assertEqual((self.obj.destination_x, self.obj.destination_y), (539, 500))
        self.assertEqual((self.obj.map_x, self.obj.map_y), (1923, 1091))
        self.assertEqual(self.obj.supported_calibration_version, 1)

    async def test_real_fuzzy_facade_string_and_invalid_answers(self):
        candidates = ["Port Tressler", "Baijini Point"]
        for answer, expected in [("  PORT TRESSLER  ", "Port Tressler"),
                                 ("Unknown", None), ("", None),
                                 ("Unlisted Station", None),
                                 ("Port Tressler is best", None)]:
            completion = types.SimpleNamespace(choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content=answer))])
            with patch.object(self.facade.ai, "_call", AsyncMock(return_value=completion)) as provider:
                self.assertEqual(await self.obj._fuzzy_llm_match("port tresler", candidates), expected)
                self.assertEqual(provider.await_count, 1)
        with patch.object(self.facade.ai, "_call", AsyncMock()) as provider:
            self.assertIsNone(await self.obj._fuzzy_llm_match("nothing", []))
            provider.assert_not_awaited()
        with patch.object(self.facade.ai, "_call", AsyncMock(side_effect=FACADE.FacadeError("cap"))):
            with self.assertRaises(FACADE.FacadeError):
                await self.obj._fuzzy_llm_match("phrase", candidates)

    async def test_calibration_waits_for_tts_and_captures_three_steps(self):
        events = []
        position = 0
        button_states = iter([False, True, False] * 3)

        async def speak(text, **kwargs):
            events.append("speech-start")
            await asyncio.sleep(0)
            events.append("speech-finished")
            self.assertTrue(kwargs["no_interrupt"])
            return True

        def button():
            self.assertEqual(events[-1], "speech-finished")
            return next(button_states)

        def point():
            nonlocal position
            position += 1
            return (position * 10, position * 20)

        self.runtime.play_to_user = speak
        with patch.object(self.obj, "_left_button_pressed", button), \
                patch.object(self.obj, "_mouse_position", point):
            self.assertEqual(await self.call("calibrate_mouse"), "Mouse calibration complete.")
        self.assertEqual(events, ["speech-start", "speech-finished"] * 3)
        saved = json.loads(self.obj.calibration_file.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"version": 1, "starmap": {
            "search_bar": {"x": 10, "y": 20}, "destination": {"x": 20, "y": 40},
            "map_center": {"x": 30, "y": 60}}})

    async def test_calibration_responsive_and_cancellation_has_no_threads(self):
        before_data = self.obj.calibration_file.read_bytes()
        before_threads = {t.ident for t in threading.enumerate()}
        benchmark = Benchmark()
        with patch.object(self.obj, "_left_button_pressed", return_value=False):
            task = asyncio.create_task(self.obj.execute_tool("calibrate_mouse", {}, benchmark))
            # If calibration blocks the event loop this timeout cannot complete.
            await asyncio.wait_for(asyncio.sleep(0.025), timeout=0.2)
            self.assertFalse(task.done())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(benchmark.finishes, 1)
        self.assertEqual(before_data, self.obj.calibration_file.read_bytes())
        self.assertEqual(before_threads, {t.ident for t in threading.enumerate()})
        self.assertEqual([t for t in asyncio.all_tasks() if t is not asyncio.current_task()], [])

    async def test_calibration_drains_early_returning_tts_before_click(self):
        async def early_speak(text, **kwargs):
            self.runtime.audio_player.is_playing = True
            return True

        self.runtime.play_to_user = early_speak
        states = iter([False, True, False])
        with patch.object(self.obj, "_left_button_pressed", side_effect=lambda: next(states)) as button, \
                patch.object(self.obj, "_mouse_position", return_value=(12, 34)):
            task = asyncio.create_task(self.obj._capture_mouse_position("Instructions"))
            await asyncio.sleep(0.025)
            button.assert_not_called()
            self.assertFalse(task.done())
            self.runtime.audio_player.is_playing = False
            self.assertEqual(await asyncio.wait_for(task, timeout=0.2), (12, 34))

    async def test_calibration_timeout_and_unspeakable_prompt_keep_old_data(self):
        before = self.obj.calibration_file.read_bytes()
        real_wait_for = asyncio.wait_for

        async def quick_timeout(coro, timeout):
            return await real_wait_for(coro, timeout=0.01)

        with patch.object(self.obj, "_left_button_pressed", return_value=False), \
                patch.object(asyncio, "wait_for", quick_timeout):
            self.assertIn("timed out", await self.call("calibrate_mouse"))
        self.assertEqual(before, self.obj.calibration_file.read_bytes())
        with patch.object(self.runtime, "play_to_user", AsyncMock(return_value=False)), \
                patch.object(self.obj, "_left_button_pressed") as button:
            with self.assertRaisesRegex(RuntimeError, "could not be spoken"):
                await self.call("calibrate_mouse")
            button.assert_not_called()
        self.assertEqual(before, self.obj.calibration_file.read_bytes())

    async def test_destination_and_alias_crud_persists(self):
        self.assertIn("added", await self.call("add_destination", {"name": "Testing Port"}))
        self.assertIn("already exists", await self.call("add_destination", {"name": "Testing Port"}))
        self.assertIn("added", await self.call("add_alias", {"destination": "Testing Port", "alias": "My Home"}))
        self.assertEqual(self.obj.engine.find_destination("my home")[0], "testing port")
        self.assertIn("already exists", await self.call("add_alias", {"destination": "Testing Port", "alias": "My Home"}))
        self.assertIn("my home", await self.call("list_aliases", {"destination": "Testing Port"}))
        self.assertIn("renamed", await self.call("rename_destination", {"old_name": "Testing Port", "new_name": "New Testing Port"}))
        self.assertEqual(self.obj.engine.find_alias("My Home"), "new testing port")
        self.assertIn("deleted", await self.call("delete_alias", {"destination": "New Testing Port", "alias": "My Home"}))
        self.assertIsNone(self.obj.engine.find_alias("My Home"))
        self.assertIn("deleted", await self.call("delete_destination", {"name": "New Testing Port"}))
        self.assertIsNone(self.obj.engine.find_exact("New Testing Port"))
        disk = json.loads(Path(self.obj.engine.destinations_file).read_text(encoding="utf-8"))
        self.assertNotIn("new testing port", disk)
        self.assertIn("daymar", disk)

    async def test_benchmark_cleanup_on_early_returns_and_exceptions(self):
        for tool in ("plot_route", "add_destination", "delete_destination", "rename_destination",
                     "add_alias", "delete_alias", "list_aliases", "unknown_tool"):
            await self.call(tool)
        for tool in ("delete_destination", "list_aliases"):
            await self.call(tool, {"name": "unlisted", "destination": "unlisted"})
        benchmark = Benchmark()
        with patch.object(self.obj.engine, "find_destination", side_effect=RuntimeError("failed")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                await self.obj.execute_tool("plot_route", {"destination": "x"}, benchmark)
        self.assertEqual(benchmark.finishes, 1)

    async def test_route_ai_timeout_is_not_reported_as_calibration(self):
        benchmark = Benchmark()
        with patch.object(self.obj.engine, "find_destination", return_value=(None, ["daymar", "port tressler"])), \
                patch.object(self.facade.ai, "_call", AsyncMock(side_effect=asyncio.TimeoutError)):
            with self.assertRaises(asyncio.TimeoutError):
                await self.obj.execute_tool("plot_route", {"destination": "fuzzy"}, benchmark)
        self.assertEqual(benchmark.finishes, 1)

    async def test_route_sequence_is_inert_and_yields(self):
        actions = []
        real_sleep = asyncio.sleep

        async def fast_sleep(delay):
            actions.append(("sleep", delay))
            await real_sleep(0)

        def operation(name):
            return lambda *args: actions.append((name, *args))

        mouse = types.ModuleType("mouse.mouse")
        keyboard = types.ModuleType("keyboard.keyboard")
        for name in ("move", "click", "wheel"):
            setattr(mouse, name, operation(name))
        for name in ("press", "release"):
            setattr(keyboard, name, operation(name))
        modules = {"mouse": types.SimpleNamespace(mouse=mouse), "mouse.mouse": mouse,
                   "keyboard": types.SimpleNamespace(keyboard=keyboard), "keyboard.keyboard": keyboard}
        with patch.dict(sys.modules, modules), patch.object(asyncio, "sleep", fast_sleep), \
                patch.object(self.obj, "_set_clipboard", operation("clipboard")):
            response = await self.call("plot_route", {"destination": "Daymar"})
        self.assertIn("not verified", response)
        self.assertEqual(actions, [
            ("press", "f2"), ("sleep", 1.4), ("release", "f2"), ("sleep", 3.5),
            ("move", 1923, 1091), ("click",), ("sleep", 1.3),
            ("wheel", -60), ("sleep", 2.1),
            ("move", 469, 269), ("click",), ("sleep", 1.5),
            ("clipboard", "daymar"), ("sleep", 0.3),
            ("press", "ctrl"), ("press", "v"), ("release", "v"), ("release", "ctrl"),
            ("sleep", 1.0), ("move", 539, 500), ("click",), ("sleep", 0.5),
            ("move", 1923, 1091), ("click",), ("sleep", 1.3),
            *[(op, "r") for _ in range(4) for op in ("press", "release")],
            ("sleep", 3.0), ("press", "f2"), ("sleep", 1.4), ("release", "f2"),
        ])


def main():
    global MODULE, FACADE, CONFIG, CUSTOM, CATALOG
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.reference))
    from api.interface import SkillConfig
    CONFIG = SkillConfig(**yaml.safe_load((PAYLOAD / "default_config.yaml").read_text(encoding="utf-8")))
    with tempfile.TemporaryDirectory(prefix="set-route-ai-v3-") as directory:
        CUSTOM = Path(directory) / "custom"
        shutil.copytree(PAYLOAD, CUSTOM / "set_route_ai")
        stub("services.benchmark", Benchmark=Benchmark)
        stub("services.printr", Printr=Printr)
        stub("services.secret_keeper", SecretKeeper=SecretKeeper)
        stub("services.file", get_custom_skills_dir=lambda: str(CUSTOM))
        stub("services.platform_utils", normalize_platform=lambda: "windows")
        # Tokenization is an inert peripheral, not the facade under test.
        stub("services.token_utils", count_tokens=lambda text: len(text),
             truncate_to_tokens=lambda text, tokens: text[:tokens])
        FACADE = load("wingmen.facade", args.reference / "wingmen/facade.py")
        load("skills.skill_base", args.reference / "skills/skill_base.py")
        manager = load("services.module_manager", ROOT / "evidence/upstream/module_manager.py")
        original_import = builtins.__import__

        def safe_import(name, *args, **kwargs):
            if name.split(".")[0] in {"mouse", "keyboard"}:
                raise AssertionError("desktop import during catalog probe")
            return original_import(name, *args, **kwargs)

        with patch.object(Path, "open", side_effect=AssertionError("file work during probe")), \
                patch.object(builtins, "open", side_effect=AssertionError("file work during probe")), \
                patch.object(threading.Thread, "start", side_effect=AssertionError("thread during probe")), \
                patch.object(builtins, "__import__", safe_import):
            manager.ModuleManager.probe_import(CONFIG)
            MODULE = manager.ModuleManager.resolve_skill_module(CONFIG)
        catalog = load("services.skill_catalog", args.reference / "services/skill_catalog.py")
        CATALOG = catalog.SkillCatalog()._evaluate("set_route_ai", str(CUSTOM / "set_route_ai/default_config.yaml"), True)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Compatibility)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary = {
            "python": sys.version.split()[0], "rapidfuzz": rapidfuzz.__version__,
            "tests_run": result.testsRun, "successful": result.wasSuccessful(),
            "catalog_verdict": CATALOG.verdict.value, "catalog_reason": CATALOG.reason,
            "import_probe": "PASS (official ModuleManager, no skill file I/O, threads or desktop imports)",
            "real_contract": "SkillConfig, Skill base, SkillAi.generate and SkillTts.speak from official 3.2.11 source",
            "peripherals": "inert provider boundary, tokenizer, logger, file root, mouse, keyboard, clipboard",
            "data_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (PAYLOAD / "data").glob("*.json")},
        }
        for source in (PAYLOAD / "main.py", PAYLOAD / "dependencies/destination_engine.py"):
            ast.parse(source.read_text(encoding="utf-8"), feature_version=(3, 11))
        (ROOT / "tests/results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
