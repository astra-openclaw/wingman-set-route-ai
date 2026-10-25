import json
from pathlib import Path
import tempfile
import unittest
from support import ROOT
from destination_engine import DestinationPhoneticEngine

class ShippedDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="sra32-db-")
        self.addCleanup(self.temp.cleanup)
        self.engine=DestinationPhoneticEngine(ROOT/"set_route_ai",Path(self.temp.name))

    def test_every_alias_collision_is_not_first_match(self):
        collisions={a:d for a,d in self.engine.alias_index.items() if len(d)>1}
        self.assertGreaterEqual(len(collisions),37)
        for alias, destinations in collisions.items():
            target,choices=self.engine.find_destination(alias)
            if alias in self.engine.destinations:
                self.assertEqual(target,alias)  # An explicit canonical name wins.
            else:
                self.assertIsNone(target,alias)
                self.assertTrue(set(choices)<=destinations)
                self.assertLessEqual(len(choices),3)

    def test_real_aerial_system_evidence(self):
        self.assertEqual(self.engine.find_destination("aerial","Stanton"),("arial",[]))
        self.assertEqual(self.engine.find_destination("aerial","Sol"),("ariel",[]))
        self.assertEqual(self.engine.find_destination("aerial"),(None,["arial","ariel"]))

    def test_no_noise_keys_and_original_destinations_retained(self):
        self.assertTrue(all(len(k)>1 for k in self.engine.destinations))
        self.assertEqual(len(self.engine.destinations),1364)
        self.assertIn("castra star",self.engine.destinations)
        self.assertIn("ariel",self.engine.destinations)

    def test_added_locations_have_source_identity(self):
        changes=json.loads((ROOT/"docs/UEX-CHANGES.json").read_text(encoding="utf-8"))
        self.assertEqual(len(changes["added"]),73)
        for added in changes["added"]:
            record=self.engine.destinations[added["key"]]
            self.assertIn({"endpoint":added["endpoint"],"id":added["id"]},record["uex"])
