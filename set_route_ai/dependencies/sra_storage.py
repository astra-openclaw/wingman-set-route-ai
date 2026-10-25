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
        raise DataError("Saved data is unreadable; the original was preserved and backed up. Check the Wingman log for details.") from exc


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
        raise DataError("Saved data has an invalid structure. Repair it before continuing.")


def migrate_legacy(skill_dir, user_dir, state, normalize):
    """Import only changes against the original database; ignore dependency samples."""
    import copy
    root, user = Path(skill_dir), Path(user_dir)
    if "legacy-v1-v3" in state["migrations"]:
        return state
    updated = copy.deepcopy(state)
    baseline = load_json(root / "database/legacy_baseline.json")
    if not isinstance(baseline, dict):
        raise DataError("The upgrade baseline is missing. Reinstall the complete skill.")
    aliases = baseline["aliases"]
    redirects = baseline.get("redirects", {})
    collected = []
    for name in ("destinations.json", "phonetic_learning.json", "blacklist.json", "mouse_calibration.json"):
        source = root / "data" / name
        if source.exists():
            backup_bytes(source, user / "legacy_backup")
            value = load_json(source, backup_dir=user / "recovery")
            if not isinstance(value, dict):
                raise DataError("Invalid legacy data; original preserved and backed up.")
            if name == "destinations.json" and hashlib.sha256(source.read_bytes()).hexdigest() == baseline["sha256"]:
                continue
            collected.append((name, value))
    for name, value in collected:
        if name == "destinations.json":
            records = {}
            for key, record in value.items():
                n = normalize(key)
                if (not isinstance(record, dict) or not isinstance(record.get("aliases", []), list)
                        or any(not isinstance(a, str) for a in record.get("aliases", []))):
                    raise DataError("Invalid legacy destination; original preserved and backed up.")
                if len(n) > 1:
                    records[n] = record
            for key, record in records.items():
                target = redirects.get(key, key)
                if target in state["overrides"] or target in state["deleted"]:
                    continue
                current = {normalize(a) for a in record.get("aliases", []) if len(normalize(a)) > 1}
                if key not in aliases:
                    updated["overrides"][target] = {**record, "name": record.get("name", key),
                                                    "aliases": sorted(current)}
                else:
                    added, removed = current - set(aliases[key]), set(aliases[key]) - current
                    if added or removed:
                        edit = updated["overrides"].setdefault(target, {
                            "alias_delta": True, "aliases": [], "removed_aliases": []})
                        edit["aliases"] = sorted(set(edit["aliases"]) | added)
                        edit["removed_aliases"] = sorted(set(edit["removed_aliases"]) | removed)
            for missing in set(aliases) - set(records):
                target = redirects.get(missing, missing)
                if target not in state["overrides"]:
                    updated["deleted"] = sorted(set(updated["deleted"]) | {target})
        elif name == "phonetic_learning.json":
            for key, target in value.items():
                if not isinstance(target, str):
                    raise DataError("Invalid legacy learned name; original preserved and backed up.")
                if normalize(key) not in state["learning"]:
                    target = normalize(target)
                    updated["learning"][normalize(key)] = redirects.get(target, target)
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
