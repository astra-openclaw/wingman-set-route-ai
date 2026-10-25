"""Offline acceptance against the official Wingman AI 3.2.11 source.

Use --module-manager for an exact-tag single-file supplement if the reference
snapshot lacks services/module_manager.py. No files in the reference are changed.
"""
import argparse
import asyncio
import builtins
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

import yaml

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "set_route_ai"
MODULE = FACADE = CONFIG = CUSTOM = CATALOG = GENERATED = None

def stub(name, **attrs):
    mod=types.ModuleType(name);mod.__dict__.update(attrs);sys.modules[name]=mod;return mod

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

class Printr:
    def print(self,*a,**kw):pass
    async def print_async(self,*a,**kw):pass

class Events:
    def subscribe(self,*a):pass
    def unsubscribe(self,*a):pass

class SecretKeeper:
    def __init__(self):self.secret_events=Events()

class Benchmark:
    def __init__(self):self.count=0
    def start_snapshot(self,label):self.count+=1
    def finish_snapshot(self):self.count-=1

class Compatibility(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtime=types.SimpleNamespace(
            context_budget=types.SimpleNamespace(tool_cap=32000),
            play_to_user=AsyncMock(return_value=True),
            audio_player=types.SimpleNamespace(is_playing=False))
        self.facade=types.SimpleNamespace(
            ai=FACADE.SkillAi(self.runtime),tts=FACADE.SkillTts(self.runtime),
            audio=FACADE.SkillAudio(self.runtime),screen=FACADE.SkillScreen(),
            system_one=FACADE.SkillSystemOne(None),
            sc_gamelog=types.SimpleNamespace(available=False),
            star_citizen=types.SimpleNamespace(environment_path=lambda _:None))
        self.obj=MODULE.SetRouteAI(CONFIG.model_copy(deep=True),types.SimpleNamespace(debug_mode=False),self.facade)
        self.assertEqual(await self.obj.validate(),[])

    async def call(self,name,params=None):
        benchmark=Benchmark()
        result=await self.obj.execute_tool(name,params or {},benchmark)
        self.assertEqual(benchmark.count,0)
        self.assertEqual(len(result),2)
        self.assertTrue(all(isinstance(x,str) for x in result))
        return result[0]

    async def test_schema_catalog_tools(self):
        self.assertEqual(CONFIG.api_version,3);self.assertEqual(CONFIG.version,"3.2.0")
        self.assertEqual(CONFIG.author,"Thord - galacticgearjammer - ProjectGnome, Dominicus")
        self.assertEqual(CATALOG.verdict.value,"ok",CATALOG.reason)
        self.assertEqual(len(self.obj.get_tools()),9)
        for name,tool in self.obj.get_tools():self.assertEqual(name,tool["function"]["name"])

    async def test_real_generated_files_boundary_and_missing_calibration(self):
        self.assertEqual(self.obj.user_dir,GENERATED/"SetRouteAI")
        self.assertIn("Calibration",await self.call("plot_route",{"destination":"Daymar"}))

    async def test_real_ai_generate_returns_text_and_allowlist(self):
        completion=types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="arial"))])
        with patch.object(self.facade.ai,"_call",AsyncMock(return_value=completion)) as provider:
            self.assertEqual(await self.obj.choose("aerial",["arial","ariel"]),"arial")
            self.assertEqual(provider.await_count,1)
        completion.choices[0].message.content="imaginary"
        with patch.object(self.facade.ai,"_call",AsyncMock(return_value=completion)):
            self.assertIsNone(await self.obj.choose("aerial",["arial","ariel"]))

    async def test_real_facade_cap_failure_is_honest(self):
        from sra_navigation import verify_route
        with patch.object(self.facade.ai,"_call",AsyncMock(side_effect=FACADE.FacadeError("cap"))):
            self.assertEqual(await verify_route(self.facade,self.obj.printr,"Daymar",1),"UNSURE")
            self.assertIsNone(await self.obj.choose("aerial",["arial","ariel"]))

    async def test_real_screen_and_image_ai_path(self):
        from sra_navigation import verify_route
        completion=types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ROUTE_SET | Daymar"))])
        with patch.object(self.facade.ai,"_call",AsyncMock(return_value=completion)) as provider:
            self.assertEqual(await verify_route(self.facade,self.obj.printr,"Daymar",1),"ROUTE_SET")
            messages=provider.call_args.args[0]
            self.assertTrue(messages[-1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    async def test_real_tts_keyword_contract_and_audio(self):
        self.assertTrue(await self.facade.tts.speak("Calibration",interrupt=False))
        self.assertFalse(self.facade.audio.is_playing)
        self.assertTrue(self.runtime.play_to_user.call_args.kwargs["no_interrupt"])

    async def test_lifecycle_config_update_and_prompt(self):
        await self.obj.prepare()
        new=CONFIG.model_copy(deep=True)
        next(p for p in new.custom_properties if p.id=="plan_delay").value=4
        await self.obj.update_config(new)
        self.assertEqual(self.obj.settings_snapshot()["plan_delay"],4)
        self.assertIn("navigation",await self.obj.get_prompt())
        await self.obj.unload()
        self.assertTrue(self.obj.is_unloaded)

    async def test_actual_system_one_choice_route(self):
        result=types.SimpleNamespace(choice=lambda key,**kw:"arial")
        gate=types.SimpleNamespace(active=True,ask=AsyncMock(return_value=result))
        self.facade.system_one=FACADE.SkillSystemOne(gate)
        stub("providers.typesafe_jev",choice=lambda instructions,criteria,**kw:{"criteria":criteria})
        self.assertEqual(await self.obj.choose("aerial",["arial","ariel"]),"arial")
        self.assertEqual(gate.ask.await_count,1)

    async def test_unknown_and_ambiguous_destinations_do_not_need_desktop(self):
        self.assertIn("No route input",await self.call("plot_route",{"destination":"CRU L99"}))
        self.assertIn("Which destination",await self.call("plot_route",{"destination":"aerial"}))
        self.assertIsNone(self.obj._desktop)

def main():
    global MODULE,FACADE,CONFIG,CUSTOM,CATALOG,GENERATED
    parser=argparse.ArgumentParser()
    parser.add_argument("--reference",required=True,type=Path)
    parser.add_argument("--module-manager",type=Path)
    args=parser.parse_args()
    manager_path=args.module_manager or args.reference/"services/module_manager.py"
    if not manager_path.is_file():
        parser.error("Missing services/module_manager.py; supply the exact 3.2.11 file via --module-manager.")
    sys.path.insert(0,str(args.reference))
    from api.interface import SkillConfig
    from PIL import Image
    CONFIG=SkillConfig(**yaml.safe_load((PAYLOAD/"default_config.yaml").read_text(encoding="utf-8")))
    with tempfile.TemporaryDirectory(prefix="sra32-probe-") as temp:
        CUSTOM=Path(temp)/"custom";GENERATED=Path(temp)/"generated"
        shutil.copytree(PAYLOAD,CUSTOM/"set_route_ai")
        def generated(name):
            p=GENERATED/name;p.mkdir(parents=True,exist_ok=True);return str(p)
        stub("services.benchmark",Benchmark=Benchmark)
        stub("services.printr",Printr=Printr)
        stub("services.secret_keeper",SecretKeeper=SecretKeeper)
        stub("services.file",get_custom_skills_dir=lambda:str(CUSTOM),get_generated_files_dir=generated)
        stub("services.platform_utils",normalize_platform=lambda:"windows")
        stub("services.token_utils",count_tokens=lambda text:len(text),truncate_to_tokens=lambda text,tokens:text[:tokens])
        stub("services.screen_capture",capture=lambda display,region:Image.new("RGB",(1920,1080)))
        FACADE=load("wingmen.facade",args.reference/"wingmen/facade.py")
        load("skills.skill_base",args.reference/"skills/skill_base.py")
        manager=load("services.module_manager",manager_path)
        original_import=builtins.__import__
        def safe_import(name,*a,**kw):
            if name.split(".")[0] in {"keyboard","mouse","ctypes"}:
                raise AssertionError("desktop import during catalog probe")
            return original_import(name,*a,**kw)
        with patch.object(Path,"open",side_effect=AssertionError("file I/O during probe")), \
             patch.object(builtins,"open",side_effect=AssertionError("file I/O during probe")), \
             patch.object(threading.Thread,"start",side_effect=AssertionError("thread during probe")), \
             patch.object(builtins,"__import__",safe_import):
            manager.ModuleManager.probe_import(CONFIG)
            MODULE=manager.ModuleManager.resolve_skill_module(CONFIG)
        catalog=load("services.skill_catalog",args.reference/"services/skill_catalog.py")
        CATALOG=catalog.SkillCatalog()._evaluate("set_route_ai",str(CUSTOM/"set_route_ai/default_config.yaml"),True)
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Compatibility))
        print(json.dumps({"tests":result.testsRun,"successful":result.wasSuccessful(),
                          "catalog_verdict":CATALOG.verdict.value,
                          "import_probe":"no skill I/O, threads or desktop imports",
                          "contracts":"genuine schema, loader, catalog, Skill base, AI, TTS, audio, screen, typed decisions",
                          "external_effects":"inert; no model, screen, input or clipboard calls"}))
        return 0 if result.wasSuccessful() and CATALOG.verdict.value=="ok" else 1

if __name__=="__main__":
    raise SystemExit(main())
