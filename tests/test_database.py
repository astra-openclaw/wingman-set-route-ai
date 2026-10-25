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
        baseline=json.loads((ROOT/"set_route_ai/database/legacy_baseline.json").read_text(encoding="utf-8"))
        original={}
        for key, aliases in baseline["aliases"].items():
            for alias in aliases: original.setdefault(alias,set()).add(key)
        self.assertLessEqual(len(collisions),35)
        self.assertTrue(set(collisions) <= {a for a,d in original.items() if len(d)>1})
        self.assertNotIn("shady glen",collisions)
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
        self.assertEqual(len(self.engine.destinations),1330)
        self.assertIn("castra star",self.engine.destinations)
        self.assertIn("ariel",self.engine.destinations)

    def test_added_locations_have_source_identity(self):
        changes=json.loads((ROOT/"docs/UEX-CHANGES.json").read_text(encoding="utf-8"))
        self.assertEqual(len(changes["added"]),69)
        for added in changes["added"]:
            record=self.engine.destinations[added["key"]]
            self.assertIn({"endpoint":added["endpoint"],"id":added["id"]},record["uex"])

    def test_all_twenty_lpoints_and_variants_unique(self):
        for prefix in ("ARC","CRU","HUR","MIC"):
            for i in range(1,6):
                targets=[]
                for spelling in (f"{prefix} L{i}", f"{prefix}-L{i}", f"{prefix} L {i}"):
                    target, choices=self.engine.find_destination(spelling)
                    self.assertIsNotNone(target,spelling);self.assertFalse(choices)
                    targets.append(target)
                self.assertEqual(len(set(targets)),1)
        self.assertEqual(self.engine.find_destination("crew L1")[0],"cru-l1 ambitious dream station")

    def test_spoken_lpoint_numbers_and_letter_variants(self):
        for prefix in ("cru", "crew", "arc", "mic", "hur"):
            for letter in ("l", "el", "ell"):
                for number, word in enumerate(("one", "two", "three", "four", "five"), 1):
                    expected = self.engine.find_destination(f"{prefix} l{number}")
                    self.assertEqual(self.engine.find_destination(f"{prefix} {letter} {word}", fuzzy=False), expected)

    def test_unavailable_system_records_kept_but_never_fuzzy_candidates(self):
        evidence = json.loads((ROOT/"docs/UEX-SYSTEM-AVAILABILITY.json").read_text(encoding="utf-8"))
        unavailable = {k for k, v in self.engine.destinations.items() if v.get("system_available_live") is False}
        self.assertEqual(unavailable, set(evidence["tagged_keys"]))
        self.assertEqual(len(unavailable), 470)
        for key in unavailable:
            record = self.engine.destinations[key]
            self.assertEqual(record["system_availability_evidence"]["is_available_live"], 0)
            self.assertEqual(record["system_availability_evidence"]["endpoint"], "star_systems")
        for phrase in ("corell one", "corel ey", "castra staarz", "sol staarz", "arielx"):
            self.assertEqual(self.engine.find_destination(phrase, fuzzy=False), (None, []))
            target, choices = self.engine.find_destination(phrase)
            self.assertNotIn(target, unavailable)
            self.assertFalse(set(choices) & unavailable)
        self.assertEqual(self.engine.find_destination("Corel I"), ("corel i", []))
        self.assertFalse(self.engine.destinations["corel i"]["system_available_live"])

    def test_missing_system_evidence_is_not_unavailability(self):
        self.engine.add_destination("Example Anchorage")
        self.assertEqual(self.engine.find_destination("Example Anchorag"), ("example anchorage", []))
        self.assertNotIn("system_available_live", self.engine.destinations["example anchorage"])

    def test_in_game_search_labels_and_homonyms(self):
        for key in self.engine.destinations:
            text=self.engine.search_text(key).casefold()
            self.assertNotRegex(text,r"closed|offline|gateway.*(?:stanton|pyro|nyx)")
        target, choices=self.engine.find_destination("Stanton Gateway")
        self.assertIsNone(target);self.assertEqual(len(choices),2)
        for system in ("Pyro","Nyx"):
            key=self.engine.find_destination("Stanton Gateway",system)[0]
            self.assertEqual(self.engine.destinations[key]["system"],system)
            self.assertEqual(self.engine.search_text(key),"Stanton Gateway")

    def test_low_confidence_fuzzy_only_asks(self):
        target, choices=self.engine.find_destination("Gateway")
        self.assertIsNone(target);self.assertTrue(choices)

    def test_explicitly_closed_and_decommissioned_metadata(self):
        for key in ("port olisar","kudre ore mine","mt datacenter l8p-juc-8"):
            self.assertTrue(self.engine.destinations[key]["unavailable_reason"])
