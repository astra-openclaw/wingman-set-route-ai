"""Database-only destination matching and transactional personal edits."""
import copy
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher

from sra_storage import (DataError, atomic_json, backup_bytes, empty_state,
                         load_json, migrate_legacy, validate_state)


def normalize(text):
    text = unicodedata.normalize("NFKD", str(text)).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class DestinationPhoneticEngine:
    normalize = staticmethod(normalize)

    def __init__(self, skill_dir, user_dir):
        self.skill_dir, self.user_dir = Path(skill_dir), Path(user_dir)
        self.state_file = self.user_dir / "user_data.json"
        shipped = load_json(self.skill_dir / "database" / "destinations.json",
                            backup_dir=self.user_dir / "recovery")
        self.shipped = self._records(shipped)
        self.state = load_json(self.state_file, empty_state(), self.user_dir / "recovery")
        try:
            validate_state(self.state)
            self._records(self.state["overrides"])
            if any(not isinstance(v, str) for v in self.state["learning"].values()):
                raise DataError("Invalid learned mappings.")
        except DataError:
            if self.state_file.exists():
                backup_bytes(self.state_file, self.user_dir / "recovery")
            raise
        self.state = migrate_legacy(self.skill_dir, self.user_dir, self.state, normalize)
        self._refresh()

    @staticmethod
    def _records(raw):
        if not isinstance(raw, dict):
            raise DataError("Destination database must be an object.")
        result = {}
        for name, value in raw.items():
            if (not isinstance(value, dict) or not isinstance(value.get("aliases", []), list)
                    or any(not isinstance(a, str) for a in value.get("aliases", []))
                    or not isinstance(value.get("removed_aliases", []), list)
                    or any(not isinstance(a, str) for a in value.get("removed_aliases", []))):
                raise DataError("Invalid destination record.")
            key = normalize(name)
            if not key or len(key) == 1:
                continue
            record = {**value, "name": value.get("name", name),
                      "aliases": sorted(set(normalize(a) for a in value.get("aliases", []) if len(normalize(a)) > 1))}
            if key in result:
                record["aliases"] = sorted(set(record["aliases"] + result[key]["aliases"]))
            result[key] = record
        return result

    def _refresh(self):
        self.destinations = copy.deepcopy(self.shipped)
        for key, value in self._records(self.state["overrides"]).items():
            if value.get("alias_delta"):
                if key in self.destinations:
                    record = self.destinations[key]
                    record["aliases"] = sorted((set(record["aliases"]) | set(value["aliases"]))
                                               - set(value.get("removed_aliases", [])))
            else:
                self.destinations[key] = {**self.destinations.get(key, {}), **value}
        for key in self.state["deleted"]:
            self.destinations.pop(normalize(key), None)
        self.learning = {normalize(k): normalize(v) for k, v in self.state["learning"].items()
                         if normalize(v) in self.destinations}
        self.name_index = {}
        for dest, data in self.destinations.items():
            self.name_index.setdefault(normalize(data.get("search", data["name"])), set()).add(dest)
        self.alias_index = {}
        for dest, data in self.destinations.items():
            for alias in data["aliases"]:
                self.alias_index.setdefault(alias, set()).add(dest)

    def _commit(self, state):
        atomic_json(self.state_file, state)
        self.state = state
        self._refresh()

    def display(self, key):
        return self.destinations[key]["name"]

    def label(self, key):
        data = self.destinations[key]
        return data["name"] + (f" in {data['system']}" if data.get("system") else "")

    def search_text(self, key):
        return self.destinations[key].get("search", self.display(key))

    def find_destination(self, phrase, system=None, fuzzy=True):
        key = normalize(phrase)
        key = re.sub(r"^(?:plot (?:a )?route to|set course for|take me to|route to|navigate to)\s+", "", key)
        if len(key) < 2 or self.state["blacklist"].get(key):
            return None, []
        if key in self.destinations:
            return key, []
        candidates = set(self.alias_index.get(key, set())) | self.name_index.get(key, set())
        scored = {}
        if key in self.learning:
            candidates.add(self.learning[key])
        if not candidates:
            special = re.fullmatch(r"(cru|crew|mic|hur|arc)[ -]?l[ -]?(\d+)", key)
            if special:
                prefix, number = special.groups()
                target = ("cru" if prefix == "crew" else prefix) + " l" + number
                if target in self.destinations:
                    return target, []
                candidates = set(self.alias_index.get(target, set()))
                if not candidates:
                    return None, []
            if not candidates and fuzzy:
                for token, destinations in self.alias_index.items():
                    score = SequenceMatcher(None, key, token).ratio()
                    if score >= .82:
                        for dest in destinations:
                            scored[dest] = max(scored.get(dest, 0), score)
                for dest in self.destinations:
                    score = SequenceMatcher(None, key, dest).ratio()
                    if score >= .82:
                        scored[dest] = max(scored.get(dest, 0), score)
                ranked = sorted(scored, key=lambda d: (-scored[d], d))
                if ranked and scored[ranked[0]] >= .90 and (len(ranked) == 1 or scored[ranked[0]] - scored[ranked[1]] >= .05):
                    candidates = {ranked[0]}
                else:
                    return None, ranked[:3]
        # A nickname for a homonymous gateway must not silently choose a system.
        for candidate in list(candidates):
            candidates.update(self.name_index.get(normalize(self.search_text(candidate)), set()))
        if system and len(candidates) > 1:
            local = {d for d in candidates if normalize(self.destinations[d].get("system", "")) == normalize(system)}
            if len(local) == 1 and all(self.destinations[d].get("system") for d in candidates):
                return next(iter(local)), []
        if len(candidates) == 1:
            return next(iter(candidates)), []
        return None, sorted(candidates)[:3]

    def get_aliases(self, destination):
        record = self.destinations.get(normalize(destination))
        return list(record["aliases"]) if record else None

    def add_destination(self, name):
        key = normalize(name)
        if len(key) < 2:
            raise DataError("Use a destination name of at least two characters.")
        if key in self.destinations:
            raise DataError("That destination already exists.")
        state = copy.deepcopy(self.state)
        state["deleted"] = [d for d in state["deleted"] if d != key]
        state["overrides"][key] = {"name": name.strip(), "aliases": []}
        self._commit(state)

    def delete_destination(self, name):
        key = normalize(name)
        if key not in self.destinations:
            raise DataError("Destination not found.")
        state = copy.deepcopy(self.state)
        state["overrides"].pop(key, None)
        state["deleted"] = sorted(set(state["deleted"] + [key]))
        state["learning"] = {k: v for k, v in state["learning"].items() if normalize(v) != key}
        self._commit(state)

    def rename_destination(self, old, new):
        old, key = normalize(old), normalize(new)
        if old not in self.destinations:
            raise DataError("Destination not found.")
        if len(key) < 2 or key in self.destinations:
            raise DataError("New name must be unique and have at least two characters.")
        state = copy.deepcopy(self.state)
        state["overrides"].pop(old, None)
        state["overrides"][key] = {**self.destinations[old], "name": new.strip()}
        state["deleted"] = sorted((set(state["deleted"]) | {old}) - {key})
        state["learning"] = {k: key if normalize(v) == old else v for k, v in state["learning"].items()}
        self._commit(state)

    def edit_alias(self, destination, alias, remove=False):
        key, alias = normalize(destination), normalize(alias)
        if key not in self.destinations:
            raise DataError("Destination not found.")
        if len(alias) < 2:
            raise DataError("Use an alias of at least two characters.")
        state = copy.deepcopy(self.state)
        record = copy.deepcopy(self.destinations[key])
        aliases = set(record["aliases"])
        if remove:
            aliases.discard(alias)
            if normalize(state["learning"].get(alias, "")) == key:
                state["learning"].pop(alias, None)
        else:
            aliases.add(alias)
        record["aliases"] = sorted(aliases)
        if key in self.shipped:
            base = set(self.shipped[key]["aliases"])
            state["overrides"][key] = {"alias_delta": True, "aliases": sorted(aliases-base),
                                       "removed_aliases": sorted(base-aliases)}
        else:
            state["overrides"][key] = record
        self._commit(state)

    def learn(self, phrase, destination):
        key, dest = normalize(phrase), normalize(destination)
        if dest not in self.destinations or key == dest or len(key) < 2:
            return
        # Never make a collision disappear through a learned first-match shortcut.
        if self.alias_index.get(key, set()) - {dest}:
            return
        state = copy.deepcopy(self.state)
        state["learning"][key] = dest
        self._commit(state)
