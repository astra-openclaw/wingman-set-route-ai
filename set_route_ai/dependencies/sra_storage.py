"""Atomic user data, separated from the immutable distribution."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


class DataError(ValueError):
    pass


def backup_bytes(path, directory):
    path, directory = Path(path), Path(directory)
    data = path.read_bytes()
    target = directory / (path.name + "." + hashlib.sha256(data).hexdigest()[:16] + ".bak")
    directory.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        with target.open("xb") as f:
            f.write(data)
    return target


def load_json(path, default=None, backup_dir=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        backup_bytes(path, backup_dir or path.parent / "recovery")
        raise DataError(f"Invalid JSON in {path.name}; original preserved and backed up. Repair it before continuing.") from exc


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name, suffix=".tmp", delete=False) as f:
            temp = Path(f.name)
            json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def empty_state():
    return {"version": 1, "overrides": {}, "deleted": [], "learning": {},
            "blacklist": {}, "migrations": []}


def validate_state(state):
    if (not isinstance(state, dict) or state.get("version") != 1
            or any(not isinstance(state.get(k), dict) for k in ("overrides", "learning", "blacklist"))
            or any(not isinstance(state.get(k), list) for k in ("deleted", "migrations"))
            or any(not isinstance(x, str) for x in state["deleted"])):
        raise DataError("Invalid user_data.json structure; repair it before continuing.")


def migrate_legacy(skill_dir, user_dir, state, normalize):
    """Read all legacy data first, preserve raw bytes, then commit once.

    Root data is authoritative over the old dependency sample folder. Raw copies
    retain removed entries and orphan learned names even when not routable.
    """
    import copy
    root, user = Path(skill_dir), Path(user_dir)
    if "legacy-v1-v3" in state["migrations"]:
        return state
    updated = copy.deepcopy(state)
    roots = [root / "dependencies" / "data", root / "data"]
    collected = []
    for folder in roots:
        for name in ("destinations.json", "phonetic_learning.json", "blacklist.json", "mouse_calibration.json"):
            source = folder / name
            if source.exists():
                backup_bytes(source, user / "legacy_backup")
                value = load_json(source, backup_dir=user / "recovery")
                if not isinstance(value, dict):
                    raise DataError(f"Invalid legacy {name} structure; preserved in legacy_backup.")
                collected.append((name, value))
    for name, value in collected:
        if name == "destinations.json":
            for key, record in value.items():
                n = normalize(key)
                if not isinstance(record, dict) or not isinstance(record.get("aliases", []), list):
                    raise DataError("Invalid legacy destination record; preserved in legacy_backup.")
                if n:
                    aliases = record.get("aliases", [])
                    if any(not isinstance(a, str) for a in aliases):
                        raise DataError("Invalid legacy aliases; preserved in legacy_backup.")
                    # Existing user edits always win; later legacy root replaces samples.
                    if n not in state["overrides"] and n not in state["deleted"]:
                        updated["overrides"][n] = {**record, "name": record.get("name", key), "aliases": aliases}
        elif name == "phonetic_learning.json":
            for key, target in value.items():
                if not isinstance(target, str):
                    raise DataError("Invalid legacy learned name; preserved in legacy_backup.")
                if normalize(key) not in state["learning"]:
                    updated["learning"][normalize(key)] = normalize(target)
        elif name == "blacklist.json":
            updated["blacklist"].update({normalize(k): v for k, v in value.items()
                                         if normalize(k) not in state["blacklist"]})
    # Legacy v1 lacks display evidence. Keep its coordinates but never trust them.
    calibration = user / "mouse_calibration.json"
    candidates = [v for n, v in collected if n == "mouse_calibration.json"]
    if candidates and not calibration.exists():
        atomic_json(calibration, candidates[-1])
    updated["migrations"].append("legacy-v1-v3")
    atomic_json(user / "user_data.json", updated)
    return updated
