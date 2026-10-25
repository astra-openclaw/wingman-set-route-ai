import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from support import ROOT

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

BUILD=load("release_builder",ROOT/"tools/build_release.py")
CROSS=load("uex_comparison",ROOT/"tools/uex_crosscheck.py")
STATIC=load("privacy_check",ROOT/"tests/static_check.py")

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="sra32-release-")
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_release_identical_single_root_and_license(self):
        a,b=self.root/"a.zip",self.root/"b.zip"
        self.assertEqual(BUILD.build(a),BUILD.build(b))
        self.assertEqual(a.read_bytes(),b.read_bytes())
        with zipfile.ZipFile(a) as z:
            names=z.namelist()
            self.assertTrue(all(n.startswith("set_route_ai/") for n in names))
            self.assertIn("set_route_ai/LICENSE",names)
            self.assertEqual(z.read("set_route_ai/LICENSE"),(ROOT/"LICENSE").read_bytes())
            self.assertFalse(any("/data/" in n or "calibration.json" in n or "backup" in n or "/tests/" in n for n in names))
            self.assertTrue(all(z.getinfo(n).date_time==(2020,1,1,0,0,0) for n in names))

    def test_release_ignores_user_data_and_developer_files(self):
        import shutil
        copy=self.root/"copy";shutil.copytree(ROOT/"set_route_ai",copy/"set_route_ai")
        for extra in BUILD.EXTRA_FILES:
            target=copy/extra;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/extra,target)
        data=copy/"set_route_ai/data";data.mkdir();(data/"mouse_calibration.json").write_text("USER-DATA-SENTINEL",encoding="utf-8")
        (copy/"set_route_ai/dependencies/backup.py").write_text("USER-DATA-SENTINEL",encoding="utf-8")
        archive=self.root/"copy.zip";BUILD.build(archive,copy)
        with zipfile.ZipFile(archive) as z:self.assertFalse(any("USER-DATA-SENTINEL" in z.read(n).decode("utf-8") for n in z.namelist()))

    def test_static_check_requires_external_terms(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):STATIC.private_words()

    def test_static_check_catches_supplied_sentinel(self):
        (self.root/"example.txt").write_text("SENTINEL-WORD",encoding="utf-8")
        self.assertTrue(STATIC.scan(self.root,["sentinel-word"]))
        self.assertEqual(STATIC.scan(self.root,["absent-sentinel"]),[])

    def test_uex_absence_is_suspect_not_deletion(self):
        database={"old station":{"aliases":[]},"daymar":{"aliases":[]}}
        datasets={name:{"status":"ok","data":[]} for name in CROSS.ENDPOINTS}
        datasets["moons"]["data"]=[{"id":1,"name":"Daymar","is_available_live":1,"star_system_name":"Stanton"},
                                   {"id":2,"name":"Future Moon","is_available_live":0}]
        datasets["poi"]["data"]=[{"id":3,"name":"New Location","is_available_live":1}]
        report=CROSS.compare(database,datasets)
        self.assertEqual(report["stale_suspects"],["old station"])
        self.assertEqual([x["key"] for x in report["missing"]],["new location"])
        self.assertEqual(set(database),{"old station","daymar"})

    def test_uex_unavailable_endpoint_marks_partial(self):
        report=CROSS.compare({},{"moons":{"status":"unavailable","data":[]}})
        self.assertIn("moons",report["unavailable_endpoints"])

    def test_jump_connections_retained_without_invented_names(self):
        datasets={name:{"status":"ok","data":[]} for name in CROSS.ENDPOINTS}
        datasets["jump_points"]["data"]=[{"id":1,"star_system_origin_name":"Stanton","star_system_destination_name":"Pyro"}]
        report=CROSS.compare({},datasets)
        self.assertEqual(len(report["jump_connections"]),1);self.assertFalse(report["missing"])
