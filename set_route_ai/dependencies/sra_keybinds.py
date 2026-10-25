"""Read-only Star Citizen keyboard overrides."""
import re
from pathlib import Path
import xml.etree.ElementTree as ET


class BindError(ValueError):
    pass


def keyboard_binding(value, action="navigation"):
    if not value or (value.startswith("kb1_") and not value[4:].strip()):
        raise BindError(f"The {action} keyboard action is explicitly unbound. Bind it in Star Citizen.")
    if not value.startswith("kb1_"):
        raise BindError("A required action is not a keyboard binding. Set a keyboard override.")
    aliases = {"lctrl": "left ctrl", "rctrl": "right ctrl", "lalt": "left alt",
               "ralt": "right alt", "lshift": "left shift", "rshift": "right shift",
               "escape": "esc", "space": "space", "return": "enter",
               "pgup": "page up", "pgdn": "page down",
               "backspace": "backspace", "delete": "delete", "insert": "insert"}
    keys = []
    for part in value[4:].lower().split("+"):
        if part in aliases:
            keys.append(aliases[part])
        elif re.fullmatch(r"[a-z0-9]|f(?:[1-9]|1[0-9]|2[0-4])|tab|home|end|up|down|left|right", part):
            keys.append(part)
        else:
            raise BindError("Unsupported keyboard binding; use supported keyboard keys for navigation.")
    return tuple(keys)


def read_bindings(path):
    overrides = {}
    if path is not None and Path(path).exists():
        try:
            root = ET.fromstring(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, ET.ParseError) as exc:
            raise BindError("Could not read your Star Citizen keybindings. Repair them before routing.") from exc
        if root.tag != "ActionMaps" or root.find("ActionProfiles") is None:
            raise BindError("Your Star Citizen keybindings have an unsupported layout.")
        for amap in root.findall("./ActionProfiles/actionmap"):
            for action in amap.findall("action"):
                bindings = [b.get("input", "") for b in action.findall("rebind")
                            if b.get("input", "").startswith("kb1_")]
                if bindings:
                    key = (amap.get("name"), action.get("name"))
                    if key in overrides and overrides[key] != bindings:
                        raise BindError("Duplicate conflicting action overrides.")
                    overrides[key] = bindings

    def effective(map_name, action, default):
        values = overrides.get((map_name, action), [default])
        label = "Starmap" if action == "v_starmap" else "plan route"
        parsed = {keyboard_binding(v, label) for v in values}
        if len(parsed) != 1:
            raise BindError("Multiple conflicting keyboard overrides; choose one binding per action.")
        return parsed.pop()

    maps = ("spaceship_hud", "player", "vehicle_general")
    starmap = {effective(m, "v_starmap", "kb1_f2") for m in maps}
    if len(starmap) != 1:
        raise BindError("Starmap keyboard bindings disagree for ship, on foot and vehicle controls. Make them agree in Star Citizen before routing.")
    return {"starmap": starmap.pop(), "plan": effective("mapui", "mapui_action_planroute", "kb1_r")}
