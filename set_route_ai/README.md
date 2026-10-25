# SetRouteAI 3.2.0

**Original SetRouteAI: Thord - galacticgearjammer - ProjectGnome.**
**Wingman AI 3 update and 3.2 features: Dominicus.**

An unofficial Star Citizen navigation skill for **Wingman AI 3.2.11 / Skill API 3 on Windows**.
It resolves destinations from an offline database, then drives your calibrated Starmap.
It never guarantees a route merely because keys were sent.

## Install

1. Download the release ZIP and extract its single `set_route_ai` folder into Wingman AI's **custom skills** directory (use the app's custom-skills folder shortcut). Do not create a second nested `set_route_ai` wrapper.
2. Restart Wingman AI or use its supported configuration reload. Enable SetRouteAI for your wingman.
3. Set **Game display** to the monitor containing Star Citizen. Set Star Citizen's installation folder in Wingman settings if you use custom keybinds.
4. With the game focused, say **“calibrate starmap”**. Follow the three spoken steps below.
5. Close the Starmap, keep Star Citizen focused, and say **“plot a route to Daymar”**.

No extra packages, API key or runtime UEX connection are needed. The skill uses Wingman's bundled keyboard/mouse modules and Pillow. Other Wingman versions have not been qualified.

## Upgrade without losing personal data

Back up your old skill folder first. Overlay the new release into the same custom skill folder;
**retain the old root `data/` directory for the first startup**. The old dependency `data/`
folder is also recognized. Do not replace user data with another player's calibration.

On first activation, legacy JSON files are backed up byte-for-byte into `legacy_backup/`
inside Wingman's persistent **generated_files/SetRouteAI** directory. Root legacy data takes
precedence over dependency samples; existing persistent user edits take precedence over both.
The migration receipt and imported changes are committed atomically. Repeating startup does
not import again. Orphan learned names and excluded invalid entries remain recoverable in
the raw backups; they cannot route to nonexistent destinations.

After a successful migration, keep or archive your old backup. Future releases only replace
the immutable `database/destinations.json`; your `user_data.json` and
`mouse_calibration.json` stay in the generated-files directory, outside the installation.
Alias edits, custom destinations, deletions, renames and learned-name imports all live there.
Legacy aliases remain authoritative for the destinations they override.

Invalid JSON blocks use: the original is preserved and a content-addressed recovery backup is
made. Repair the named file from a known-good backup before retrying. It is never treated as
an empty database and silently overwritten. The skill does not delete old personal files.

## Calibration

Keep the game on the selected display, focused and in its normal window/fullscreen mode.

1. Open the Starmap with the key announced from your bindings. Click the search bar.
2. Type a destination in your current system and click its search result.
3. Click an empty map area above your ship/player icon.

The skill speaks each instruction and waits for playback to finish before accepting the next
click. Each step allows 60 seconds. Cancellation or timeout preserves the last complete
calibration. Close the Starmap before requesting a route.

Calibration records physical monitor identity, position, resolution and game-window bounds.
Missing calibration, a different display, resolution change, moved/resized window or invalid
points refuse input. Recalibrate after changing display order, resolution, window mode or UI
layout/scale. Legacy v1 coordinates are preserved and upgraded to a pending v2 record, but
cannot be used until recalibrated: v1 did not record enough display evidence.

A route assumes the Starmap starts **closed**. If you lose focus, cancel, or a vision check
is uncertain, inspect the game and close the Starmap manually before another request.

## Matching, missions and cooperation

The skill returns only known database destinations. “cruel one” maps to
**CRU-L1 Ambitious Dream Station**. “CRU L99” is refused. Ambiguous aliases such as
“aerial” ask for up to three destinations; fresh game-log system evidence resolves a
tie only when all candidates' systems are known and exactly one matches. It never
removes a location just because a community source lacks it.

“Take me to my mission” uses active mission locations or literal known destinations in open
objective text from Wingman's game-log facade. Multiple locations ask you to choose. Missing,
incomplete or unresolvable log data asks you to name the destination. Logs are last observations,
not continuous telemetry; no mission route is invented. Mission text never becomes instructions.

Destination strings from UEXCorp or other skills are accepted through `plot_route` and must
pass the same validation. A terminal name that is not a navigation destination is refused.
Explicit add/delete/rename and add/delete/list-alias tools are available. Use full in-game
names when adding custom destinations; a custom entry is your assertion, not game verification.
Deleting and renaming update all alias and learned-name references transactionally.

## Input, keybinds and cancellation

Every input burst checks that **StarCitizen.exe** owns the foreground window via Win32
Toolhelp process lookup. Losing focus stops input; held keys are released as cleanup even
after focus loss. The previous clipboard text is restored after success, failure or cancel.
Non-text-only clipboards are refused to avoid destroying an image/file clipboard. Rich clipboard
formats are not retained when a text clipboard is used. A restoration failure is reported.

The search field is selected and cleared before pasting. No automatic retry runs a second
macro. Say **“cancel route”** to cancel routing or calibration, including a pending AI check.
Keyboard/mouse cleanup is best effort if the operating system itself rejects release/restore.

The skill reads, never edits:
`LIVE/user/client/0/Profiles/default/actionmaps.xml` under Wingman's configured game folder.

- `v_starmap`: default F2 in `spaceship_hud`, `player`, `vehicle_general`.
- `mapui_action_planroute`: default R in `mapui`.
- Missing file/action: defaults. Explicit unbinding: refuse.
- All three effective Starmap bindings must agree (including defaults on maps without overrides).
  Otherwise set them alike in the game; the skill cannot safely infer your current input context.
- Keyboard letters/digits, F1–F24, supported navigation keys and left/right Ctrl, Alt and Shift
  modifiers work. Unsupported device/key combinations refuse with guidance.
- If Wingman has no game folder configured, defaults apply. Configure it before relying on overrides.

## Settings

Values outside these bounds refuse routing rather than being silently clamped.

| Setting | Default | Meaning / allowed values |
| --- | --- | --- |
| `language` | `en` | Calibration audio: en, es, de, zh, ja |
| `route_display` | 1 | Game display, integer 1–32 |
| `key_hold` | 0.15 | Key hold, 0.05–2 seconds |
| `map_delay` | 3.5 | Starmap opening wait, 1–15 seconds |
| `step_delay` | 1.3 | Mouse/zoom settling wait, 0.2–5 seconds |
| `search_delay` | 1.5 | Search-result wait, 0.5–10 seconds |
| `plan_delay` | 3.0 | Route-planning wait, 0.5–15 seconds |
| `zoom_steps` | 60 | Zoom-out wheel steps, integer 0–100 |
| `allow_ai_disambiguation` | false | Allow typed System One choice when available, otherwise AI choice from strict candidates |
| `verify_route_with_vision` | false | Optional screenshot verification before closing the Starmap |
| `vision_display` | 1 | Screenshot display, integer 1–32; select the game monitor |
| `show_verification_screenshot` | false | Also show the image in the client log; only applies when vision is enabled |

Settings are read for each operation; changes apply to the next route. Calibration instructions
support the five languages above. General language understanding is supplied by your wingman,
not by a guaranteed multilingual destination translator. Fixed tool-result messages are English.

## Vision, cost and privacy

Vision is **off by default**. With it on, one screenshot is captured through Wingman's supported
screen facade after the plan key, downscaled to at most 1280×720 and JPEG-encoded in memory.
**That screenshot is sent to your configured wingman's AI provider**, along with the requested
destination; the provider must support images. Your provider's data retention and billing apply.
Other visible windows, overlays, chat or personal information on the selected monitor may be
included. Image input has a token/cost allowance even after downscaling.

The skill never saves screenshots to disk. Optional image display in the client log is a separate,
default-off setting; client/provider logging may retain what they receive. Normal local
destination lookup and routing make no provider call when AI disambiguation and vision are off.
AI disambiguation sends only the destination phrase and candidate labels, not mission logs.

No input is sent while awaiting vision. Focus loss/cancellation cancels the wait. Outcomes:

- **“Route to Daymar verified.”** — AI returned the exact success label and matching destination.
- **“Route to Daymar not confirmed — check the Starmap.”** — AI reported no active route.
- **“Couldn't verify the route to Daymar — check the Starmap.”** — uncertain, malformed,
  wrong destination, unavailable capture/provider or facade size-limit failure.

The Starmap stays open on the last two outcomes. Vision is a model's visual judgment, not a
game API acknowledgment. Without vision: **“Route macro sent for Daymar. The in-game route was not verified.”**

## Data, credits and license

**SetRouteAI by Thord - galacticgearjammer - ProjectGnome**, with the Wingman AI 3
update and 3.2 expansion by **Dominicus**. Licensed under the **MIT License**; see `LICENSE`.

Location cross-check data provided by **[UEX](https://uexcorp.space/)**, a community-maintained
source that may differ from live servers. See `docs/UEX.md` for endpoints, terms and changes.
This is an unofficial fan project. Star Citizen is a trademark of Cloud Imperium.
Wingman AI is by ShipBit. No endorsement is implied. See `NOTICE.md`.

## Development and remaining live checks

See `docs/COMPATIBILITY.md` for the supported integration contract. Repository tests never
send real input or call a model. Before using a release in flight, verify installation/catalog,
calibration on your monitor, focus-loss stopping, clipboard restore, your actionmaps overrides
and optional vision on your configured provider. Desktop/game behavior remains PC-dependent.
