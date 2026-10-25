import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from support import fixture_database
from destination_engine import DestinationPhoneticEngine, normalize
from sra_storage import DataError, atomic_json
from sra_navigation import read_calibration

class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sra32-data-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill, self.user = self.root / "skill", self.root / "user"
        fixture_database(self.skill)
        self.engine = DestinationPhoneticEngine(self.skill, self.user)

    def test_only_database_destinations_and_invalid_pattern(self):
        self.assertEqual(self.engine.find_destination("CRU L99"), (None, []))
        self.assertEqual(self.engine.find_destination("crew l2"), ("cru l2", []))
        for phrase in ("daymar", "aerial", "unknown", "cru l99", "daymer"):
            name, choices = self.engine.find_destination(phrase)
            self.assertTrue(name is None or name in self.engine.destinations)
            self.assertTrue(set(choices) <= self.engine.destinations.keys())

    def test_collision_asks_instead_of_first_match(self):
        self.assertEqual(self.engine.find_destination("aerial"), (None, ["arial", "ariel"]))
        self.assertEqual(self.engine.find_destination("aerial", "Stanton"), (None, ["arial", "ariel"]))

    def test_current_system_uniquely_resolves(self):
        self.assertEqual(self.engine.find_destination("cross", "Pyro"), ("other", []))
        self.assertEqual(self.engine.find_destination("cross", "Stanton"), ("brios breaker yard", []))

    def test_unknown_candidate_system_does_not_decide_a_tie(self):
        self.engine.destinations["other"].pop("system")
        self.assertIsNone(self.engine.find_destination("cross", "Stanton")[0])

    def test_consistent_apostrophe_and_accent_normalization(self):
        self.assertEqual(self.engine.get_aliases("Brio’s Breaker Yard"), ["brios", "cross"])
        self.assertEqual(normalize("  BRÍO'S   Breaker Yard "), "brios breaker yard")

    def test_rename_cascades_and_preserves_aliases(self):
        self.engine.learn("red moon", "daymar")
        self.engine.edit_alias("daymar", "home")
        self.engine.rename_destination("daymar", "New Daymar")
        self.assertEqual(self.engine.find_destination("red moon"), ("new daymar", []))
        self.assertEqual(self.engine.find_destination("home"), ("new daymar", []))
        self.assertNotIn("daymar", self.engine.destinations)
        reloaded = DestinationPhoneticEngine(self.skill, self.user)
        self.assertEqual(reloaded.find_destination("home"), ("new daymar", []))

    def test_delete_cascades_learning_and_aliases(self):
        self.engine.learn("red moon", "daymar")
        self.engine.edit_alias("daymar", "home")
        self.engine.delete_destination("daymar")
        self.assertNotIn("red moon", self.engine.learning)
        self.assertNotIn("home", self.engine.alias_index)
        self.assertEqual(self.engine.find_destination("daymar"), (None, []))

    def test_delete_alias_also_removes_learned_mapping(self):
        self.engine.edit_alias("daymar", "home")
        self.engine.learn("home", "daymar")
        self.engine.edit_alias("daymar", "home", remove=True)
        self.assertNotIn("home", self.engine.learning)

    def test_shipped_database_never_written(self):
        path = self.skill / "database/destinations.json"
        original = path.read_bytes()
        self.engine.add_destination("New Haven")
        self.engine.edit_alias("New Haven", "home")
        self.engine.rename_destination("New Haven", "New Hope")
        self.engine.delete_destination("New Hope")
        self.assertEqual(path.read_bytes(), original)

    def test_corrupt_state_preserved_and_backed_up(self):
        path = self.user / "user_data.json"; path.write_bytes(b'{"broken"')
        for _ in range(2):
            with self.assertRaises(DataError): DestinationPhoneticEngine(self.skill, self.user)
        self.assertEqual(path.read_bytes(), b'{"broken"')
        self.assertEqual(len(list((self.user / "recovery").glob("*.bak"))), 1)

    def test_invalid_state_shape_preserved(self):
        path = self.user / "user_data.json"; path.write_text("[]", encoding="utf-8")
        with self.assertRaises(DataError): DestinationPhoneticEngine(self.skill, self.user)
        self.assertEqual(path.read_text(), "[]")
        self.assertTrue(list((self.user / "recovery").glob("*.bak")))

    def test_failed_atomic_replace_preserves_previous_state(self):
        before = self.engine.state_file.read_bytes()
        with patch("sra_storage.os.replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError): self.engine.add_destination("new haven")
        self.assertEqual(before, self.engine.state_file.read_bytes())
        self.assertNotIn("new haven", self.engine.destinations)
        self.assertFalse(list(self.user.glob("*.tmp")))

    def legacy(self):
        # Remove migration receipt to model first upgrade.
        state = copy.deepcopy(self.engine.state); state["migrations"] = []
        atomic_json(self.engine.state_file, state)
        atomic_json(self.skill / "dependencies/data/destinations.json", {"daymar": {"aliases": ["sample"]}})
        atomic_json(self.skill / "data/destinations.json", {"daymar": {"aliases": ["home"]}, "custom": {"aliases": []}})
        atomic_json(self.skill / "data/phonetic_learning.json", {"go home": "daymar", "orphan": "absent"})
        atomic_json(self.skill / "data/mouse_calibration.json", {"version": 1, "starmap": {}})

    def test_migration_root_precedence_raw_preservation_and_idempotence(self):
        self.legacy()
        engine = DestinationPhoneticEngine(self.skill, self.user)
        self.assertEqual(engine.get_aliases("daymar"), ["home"])
        self.assertEqual(engine.learning["go home"], "daymar")
        self.assertNotIn("orphan", engine.learning)
        self.assertEqual(engine.state["learning"]["orphan"], "absent")
        self.assertIn("custom", engine.destinations)
        before = engine.state_file.read_bytes()
        engine = DestinationPhoneticEngine(self.skill, self.user)
        self.assertEqual(before, engine.state_file.read_bytes())
        self.assertEqual(len(list((self.user/"legacy_backup").glob("*.bak"))), 4)

    def test_migration_corrupt_source_stops_without_receipt(self):
        self.legacy()
        source = self.skill / "data/phonetic_learning.json"; source.write_text("{bad",encoding="utf-8")
        before = self.engine.state_file.read_bytes()
        with self.assertRaises(DataError): DestinationPhoneticEngine(self.skill, self.user)
        self.assertEqual(before, self.engine.state_file.read_bytes())
        self.assertEqual(source.read_text(), "{bad")

    def test_migration_existing_user_edit_wins(self):
        self.legacy()
        state = copy.deepcopy(self.engine.state); state["migrations"] = []
        state["overrides"]["daymar"] = {"aliases": ["mine"]}
        atomic_json(self.engine.state_file, state)
        engine = DestinationPhoneticEngine(self.skill, self.user)
        self.assertEqual(engine.get_aliases("daymar"), ["mine"])

    def test_v1_calibration_migrated_but_not_trusted(self):
        path = self.user/"mouse_calibration.json"
        atomic_json(path, {"version": 1, "starmap": {"search_bar": {"x": 10,"y":20}}})
        migrated = read_calibration(path)
        self.assertEqual(migrated["version"], 2)
        self.assertIsNone(migrated["geometry"])
        self.assertTrue(migrated["needs_recalibration"])
        self.assertEqual(migrated["starmap"]["search_bar"]["x"], 10)

    def test_bad_entries_filtered(self):
        atomic_json(self.skill/"database/destinations.json", {"": {"aliases":[]}, "x":{"aliases":[]}, "daymar":{"aliases":[]}})
        engine = DestinationPhoneticEngine(self.skill,self.user)
        self.assertEqual(list(engine.destinations), ["daymar"])
