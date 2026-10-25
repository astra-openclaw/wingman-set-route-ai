# SetRouteAI 3.2.0

**Original SetRouteAI: Thord - galacticgearjammer - ProjectGnome.**

**Wingman AI 3 update and 3.2 features: Dominicus.**

Plot Star Citizen routes by voice with **Wingman AI 3.2.11 on Windows**.
SetRouteAI searches a local destination database, then uses your calibrated Starmap.

## Quick start

1. Extract the ZIP's **set_route_ai** folder into Wingman's **custom skills** folder. Use the app's folder shortcut. Avoid a second nested folder.
2. Restart Wingman or reload its configuration. Enable SetRouteAI for your wingman.
3. If you use custom keybinds, set Star Citizen's installation folder in Wingman.
4. Focus Star Citizen and say **“calibrate starmap.”** The game monitor is detected automatically.
5. Follow the three spoken steps: click the search bar, a search result, and an empty map area above your ship.
6. **Close the Starmap**, keep the game focused, and say **“plot a route to Daymar.”**

No extra packages or UEX account are needed. The skill's database works offline.
Your wingman still uses its normal AI provider to understand voice requests.

> **Before each route:** start with the Starmap closed. A sent request is not proof of an active route. Check the map, or opt into vision verification.

## What you can say

| Say | What happens |
| --- | --- |
| “Plot a route to Daymar.” | Searches for Daymar and sends the route inputs. |
| “Set course for cruel one.” / “CRU L1.” | Resolves to CRU-L1 Ambitious Dream Station. |
| “Navigate to Seraphim Station.” | Searches the named station. |
| “Llévame a la estación serafín.” | Your wingman can translate to Seraphim Station; the skill validates the result. |
| “Take me to my mission.” | Uses a known location in your active mission log, or asks for a destination. |
| “Take me to aerial.” | Asks “Arial in Stanton, or Ariel in Sol?” unless the game-log system decides. |
| “Fly to Stanton Gateway.” | Uses the current system, or asks which gateway you mean. |
| “Cancel route.” | Stops the current input sequence, calibration or vision wait. It does not clear a route already set in the game. |
| “Calibrate starmap.” | Records the three click positions again. |
| “Add the alias ‘my yard’ for Brio's Breaker Yard.” | Saves your alias. |
| “List the aliases for Brio's Breaker Yard.” | Reads your aliases. |

You can explicitly add, rename or delete custom destinations and aliases.
Use the exact in-game name when adding one. Renames and deletions also update learned names.

The wingman can correct mishearings and translate destination names using Star Citizen knowledge.
It passes both the intended name and your original words when they differ.
If those point to different places, the skill asks you. It never routes to a name outside its database.
“CRU L99” is refused. Uncertain fuzzy matches ask rather than silently choosing.

Other skills, including UEXCorp, may suggest destinations. They pass the same checks.
Mission routing needs Wingman's game-log integration and a recognizable location; it does not invent one.
Log information is the last observation, not guaranteed live telemetry.

## Settings

These are the names shown in Wingman's settings. Changes apply to the next request.
Out-of-range values are refused.

| Setting | Default | Allowed values / purpose |
| --- | --- | --- |
| Calibration language | English | English, Spanish, German, Chinese or Japanese |
| Starmap key hold seconds | 1.4 | 0.1–3 seconds; original tested Starmap timing |
| Key hold seconds | 0.15 | 0.05–2 seconds; shorter typing and planning chords |
| Starmap opening delay | 3.5 | 1–15 seconds |
| Mouse step delay | 1.3 | 0.2–5 seconds |
| Zoom settle delay | 2.1 | 0.2–10 seconds; original tested zoom timing |
| Search result delay | 1.5 | 0.5–10 seconds |
| Route planning delay | 3.0 | 0.5–15 seconds |
| Zoom-out wheel steps | 60 | 0–100 whole steps |
| Replace a non-text clipboard | Off | Allows replacing a clipboard image or file selection. It cannot be restored. |
| Allow AI candidate choice | Off | Optional AI choice among known candidates; otherwise asks you. Conflicting original/intended names still ask. |
| Verify route with vision | Off | Sends the game-window image to your wingman's configured image-capable AI provider. |
| Show verification image in client log | Off | Also shows the verification image in Wingman's client log. |

There is no monitor-number setting. Calibration detects the game's monitor; vision uses the calibrated game-window rectangle.
Calibration audio supports the five listed languages. Other language understanding depends on your wingman.
Fixed tool-result lines are English.

## Upgrading without losing your data

1. Back up your old **set_route_ai** folder.
2. Copy the new **set_route_ai** folder **over the old folder**, merging its contents.
3. **Keep the old root data/ folder for the first start.** Do not replace it with someone else's data.
4. Reload Wingman and enable the skill. Restore the default skill prompt if you previously saved a custom one.
5. Say **“calibrate starmap.”** Old coordinates are kept as a backup but need fresh display evidence.
6. Check your custom destinations and aliases, then retain your old folder backup.

On the first start, root legacy files are backed up byte-for-byte into **legacy_backup/** in Wingman's persistent **generated_files/SetRouteAI** directory.
Only your differences from the original database are imported: added destinations, added/removed aliases and deletions.
An unchanged original or v3 database creates **zero destination overrides**.
Shipped names, systems and future aliases remain available. Old dependency sample folders are **never imported**.

Root learned names and the blacklist are retained. A saved migration receipt prevents repeated imports.
Orphan learned names remain in the backup but cannot route to nonexistent places.
Existing persistent personal edits win over legacy data.

Your personal **user_data.json** and **mouse_calibration.json** live outside the installed skill folder.
Future upgrades replace the shipped database, not those files. Do not manually copy the shipped database into personal data.

Unreadable data is preserved and backed up, never reset to an empty database.
Repair other corrupt personal files from a known-good backup.
For corrupt calibration, a successful new calibration can replace it **after backing up the exact old bytes**.
Timeout or cancellation keeps the previous file.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| Clipboard contains an image or file selection | Copy some text first. Or enable **Replace a non-text clipboard** if you are happy to lose that content. The spoken result tells you when it was replaced. |
| Starmap is left open | Inspect the result and close it manually before another request. This is expected after cancellation, focus loss or an uncertain vision result. |
| Routing stops after switching windows | Return focus to Star Citizen. The skill sends input only while StarCitizen.exe owns the foreground window. |
| Calibration is refused | Recalibrate after changing monitor, resolution, display order, window position/mode, UI scale or layout. No default click coordinates are used. |
| Calibration times out | Each click has 60 seconds. Listen to the full instruction, then click. The last complete calibration is kept. |
| Starmap keybinds disagree | Make the keyboard binding identical for ship HUD, on-foot player and vehicle controls in Star Citizen. Missing overrides still use F2. |
| An action is explicitly unbound | Bind Starmap or plan route to a supported keyboard key in Star Citizen. A blank keyboard override is not a fallback. |
| HOTAS/gamepad binding is present | That's fine. Only keyboard overrides replace F2/R; joystick and gamepad inputs are ignored. |
| Unsupported keyboard key | Use letters, digits, F1–F24, supported navigation keys or left/right Ctrl, Alt and Shift. Numpad Enter is not silently treated as main Enter. |
| The route goes to the wrong result | Check calibration and the exact destination name. Increase **Search result delay** on slower PCs. |
| A location is marked closed, offline or decommissioned | No route input is sent. These are explicit UEX status records, not guesses based on missing data. |
| “Navigation is busy” | Wait, or say **“cancel route.”** Two simultaneous requests never run two macros. |
| “The Wingman log has details” | An unexpected error stopped navigation. Check that log; Python exceptions are not read aloud. |

The read-only keybind file is **LIVE/user/client/0/Profiles/default/actionmaps.xml**, under the game folder configured in Wingman.
Starmap defaults to **F2**; plan route defaults to **R**. Missing files/actions use those defaults.
The skill never edits your game bindings.

The search field is cleared before pasting. Previous Unicode clipboard text is restored after success, failure or cancellation.
Rich clipboard formats are not restored. If Windows rejects key release or clipboard restoration, the skill reports it.
No route is automatically retried.

## Vision: privacy and cost

> **Off by default.** Turning on **Verify route with vision** sends an image of your calibrated game window to your configured AI provider. Image-input charges and that provider's retention policy apply. Overlays, chat or personal information inside the game-window rectangle may be included.

After planning, the skill captures **only the calibrated game-window rectangle**, not the whole monitor.
It encodes the image in memory with a **1.15-megapixel area budget** and JPEG quality 85, then 70, then 55 if needed.
A 5120×1440 image becomes about **2022×569**; 1920×1080 becomes about **1430×804**.
Busy images may be reduced further to fit the 250,000-character budget.

The skill never saves screenshots to disk. The optional client-log image is separate and off by default.
Wingman/client/provider logging may retain what they receive.

No route input is sent while waiting for vision. Cancellation and focus loss stop the wait.

| Spoken result | Meaning |
| --- | --- |
| “Route to Daymar verified.” | The AI reports an active route and matching destination text. |
| “Route to Daymar not confirmed — check the Starmap.” | The AI reports no active route. The map stays open. |
| “Couldn't verify the route to Daymar — check the Starmap.” | Uncertain/wrong text, capture failure or provider failure. The map stays open. |
| “Route request sent for Daymar. The in-game route was not verified.” | Vision is off. Inspect the route yourself. |

Vision is a model's visual judgment, **not a game API acknowledgment**.
Local matching and route inputs make no extra provider call when vision and AI candidate choice are off.
Optional AI candidate choice sends the destination phrase and candidate labels, not mission logs.

## Credits and license

**SetRouteAI by Thord - galacticgearjammer - ProjectGnome**, with the Wingman AI 3 update and 3.2 expansion by **Dominicus**.
The original logo is included unchanged.

Location cross-check data provided by **[UEX](https://uexcorp.space/)**, a community source that may differ from live servers.
See **docs/UEX.md** for sources and terms.

Licensed under the **MIT License**; see **LICENSE**.
This is an unofficial fan project. Star Citizen is a trademark of Cloud Imperium.
Wingman AI is by ShipBit. No endorsement is implied. See **NOTICE.md**.

Other Wingman releases have not been qualified. First use still needs a Windows check of installation, calibration, foreground stopping, clipboard restoration, your actual keybinds and optional vision.
