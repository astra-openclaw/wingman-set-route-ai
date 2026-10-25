# Set Route AI — Wingman AI v3 repair

Original skill by **Thord - galacticgearjammer - ProjectGnome**.
This repair preserves its SetRouteAI identity and existing navigation,
calibration, destination and alias tools. It targets Wingman AI's Skill API 3
and was checked against the official Wingman AI 3.2.11 source.

## Install on Windows

Copy this **one `set_route_ai` folder** to:

```text
%APPDATA%\ShipBit\WingmanAI\custom_skills\set_route_ai
```

The resulting file must be
`%APPDATA%\ShipBit\WingmanAI\custom_skills\set_route_ai\default_config.yaml` —
not `set_route_ai\set_route_ai\default_config.yaml`.
Back up any existing copy, especially its `data` folder, before replacing it.
Restart Wingman AI normally, then select the skill for the desired Wingman.
No Wingman core files, providers or models need changing. The mouse, keyboard
and RapidFuzz dependencies used here are already bundled with Wingman AI 3.2.11.

## Calibrate before routing

Run **calibrate mouse** (or **calibrate starmap**) and follow all three spoken
instructions. Use the same display resolution and UI layout you will use while
routing. Existing version 1 calibration coordinates are preserved, but they are
not proof that the controls align with your current game screen.

After each spoken instruction finishes, left-click and release the indicated
control. Each step has a 60-second timeout after the speech call returns,
including any remaining audio playback. Cancellation or a timeout keeps the
previous calibration; new coordinates are saved only after all three steps.
Instruction languages remain English, Spanish, Chinese, Japanese and German;
the original configured value is English.

With Star Citizen in the foreground and its usual F2 Starmap / R route keys,
try **plot a route to Daymar**. This is a coordinate/key macro: it cannot inspect
the game or prove that a route was accepted. Verify the result in-game. Do not
switch focus while it runs; it replaces the Windows clipboard with the
destination name, just as the original did.

## Destinations and aliases

All four original root `data/*.json` files are preserved byte-for-byte, including
the 1,317-entry destination database, learned names and calibration version.
Runtime reads and writes use this skill's own root `data` directory, not the tiny
sample files under `dependencies/data`. Those samples and the original developer
scripts/backups are retained as supplied, but are not loaded by the skill.

Existing tools: `plot_route`, `calibrate_mouse`, `add_destination`,
`delete_destination`, `rename_destination`, `add_alias`, `delete_alias`,
`list_aliases`. Unknown names are **not** automatically added. Use the explicit
destination/alias tools when needed. An ambiguous AI answer is accepted only if
it exactly identifies one of the candidates (ignoring case/outer whitespace).

## What was checked

Local tests used genuine Wingman 3.2.11 manifest schema, custom-skill loader,
catalog, base class and AI/TTS/audio facades. Providers, desktop input and
clipboard were inert. Checks cover database preservation, destination/alias
CRUD, AI text responses, calibration speech/playback ordering, event-loop
responsiveness, timeout/cancellation cleanup, benchmark cleanup and the original
route macro sequence. No live game input or model request was used by those
tests. In-game calibration and a foreground routing check remain necessary.

Compatibility reference:
[official v3 migration guide](https://github.com/ShipBit/wingman-ai/blob/3.2.11/skills/MIGRATING-TO-V3.md).
