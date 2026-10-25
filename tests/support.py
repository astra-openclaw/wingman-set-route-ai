import asyncio
import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "set_route_ai/dependencies"))
from sra_storage import atomic_json

class BaseSkill:
    def __init__(self, config, settings, wingman):
        self.config, self.settings, self.wingman = config, settings, wingman
        self.printr = types.SimpleNamespace(print_async=AsyncMock())
        self.log = types.SimpleNamespace(error=lambda *a: None)
    async def validate(self): return []
    async def unload(self): pass
    def get_generated_files_dir(self): return self._test_user

def load_skill():
    base = types.ModuleType("skills.skill_base")
    base.Skill = BaseSkill
    sys.modules["skills.skill_base"] = base
    spec = importlib.util.spec_from_file_location("test_skill_payload", ROOT / "set_route_ai/main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

MODULE = load_skill()
GEOMETRY = {"display": 1, "device": "DISPLAY1", "left": 0, "top": 0,
            "width": 1920, "height": 1080, "window": [0, 0, 1920, 1080]}
CALIBRATION = {"version": 2, "geometry": GEOMETRY, "starmap": {
    "search_bar": {"x": 200, "y": 120}, "destination": {"x": 250, "y": 350},
    "map_center": {"x": 960, "y": 540}}}

class Desktop:
    def __init__(self):
        self.events = []
        self.focus = True
        self.geometry_value = GEOMETRY.copy()
        self.clipboard = "previous text"
        self.keys = set()
        self.on_event = lambda event: None
    def foreground(self): return self.focus
    def geometry(self, display):
        if display != self.geometry_value["display"]: raise RuntimeError("Wrong display.")
        return self.geometry_value
    def event(self, *event):
        self.events.append(event)
        self.on_event(event)
    def press(self, key):
        self.keys.add(key); self.event("press", key)
    def release(self, key):
        self.keys.discard(key); self.event("release", key)
    def move(self, x, y): self.event("move", x, y)
    def click(self): self.event("click")
    def wheel(self, steps): self.event("wheel", steps)
    def clipboard_get(self): return self.clipboard
    def clipboard_set(self, text):
        self.clipboard = text; self.event("clipboard", text)
    def left_pressed(self): return False
    def position(self): return 200, 120

async def fast_pause(self, seconds):
    self.guard()
    await asyncio.sleep(0)
    self.guard()

class Benchmark:
    def __init__(self): self.open = 0
    def start_snapshot(self, label): self.open += 1
    def finish_snapshot(self): self.open -= 1

async def skill(user, props=None, state=None):
    from PIL import Image
    wingman = types.SimpleNamespace(
        ai=types.SimpleNamespace(generate=AsyncMock(return_value="UNSURE | NONE")),
        screen=types.SimpleNamespace(capture=AsyncMock(return_value=Image.new("RGB", (1920,1080)))),
        audio=types.SimpleNamespace(is_playing=False),
        tts=types.SimpleNamespace(speak=AsyncMock(return_value=True)),
        sc_gamelog=types.SimpleNamespace(available=state is not None, state=lambda: state),
        star_citizen=types.SimpleNamespace(environment_path=lambda _: None),
        system_one=types.SimpleNamespace(available=False))
    config = types.SimpleNamespace(custom_properties=[
        types.SimpleNamespace(id=k, value=v) for k,v in (props or {}).items()])
    obj = MODULE.SetRouteAI(config, types.SimpleNamespace(debug_mode=False), wingman)
    obj._test_user = str(user)
    await obj.validate()
    obj._desktop = Desktop()
    return obj

async def call(obj, name, **args):
    benchmark = Benchmark()
    result = await obj.execute_tool(name, args, benchmark)
    assert benchmark.open == 0
    return result[0]

def fixture_database(root):
    atomic_json(root / "database/destinations.json", {
        "daymar": {"name": "Daymar", "system": "Stanton", "aliases": []},
        "arial": {"name": "Arial", "system": "Stanton", "aliases": ["aerial"]},
        "ariel": {"name": "Ariel", "system": "Stanton", "aliases": ["aerial"]},
        "other": {"name": "Other", "system": "Pyro", "aliases": ["cross"]},
        "brios breaker yard": {"name": "Brio's Breaker Yard", "system": "Stanton", "aliases": ["cross", "brios"]},
        "cru l2": {"name": "CRU L2", "aliases": []}})
