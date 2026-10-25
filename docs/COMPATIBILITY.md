# Compatibility contract

SetRouteAI by **Thord - galacticgearjammer - ProjectGnome**, expanded by **Dominicus**.
Target: **Wingman AI 3.2.11, Skill API 3, Windows, Python 3.11**.

References below are paths and line numbers in the official `ShipBit/wingman-ai` tag `3.2.11`. That source is read-only. No core modifications or internal runtime access are required.

| Boundary | Supported reference | Implementation policy |
| --- | --- | --- |
| Ownership and import safety | `skills/MIGRATING-TO-V3.md:14–60` | Skill config/storage on `self`; runtime only on `self.wingman`. No I/O, hooks or threads during import. |
| Legacy tool API | `skills/skill_base.py:442–445`, `:698`, `:826` | Keep supported `get_tools` / `execute_tool`; benchmark object is duck-typed, no service import. |
| Lifecycle | `skills/skill_base.py:514`, `:585`, `:664`, `:689`, `:777` | Fresh settings per operation; validation loads data; unload cancels owned work; base hooks preserved. |
| Persistent user data | `skills/skill_base.py:929–945` | `get_generated_files_dir()` only; shipped database is immutable. Atomic JSON overlay stores edits, learning and migration receipt. |
| Screen capture | `wingmen/facade.py:1627–1652` | Await `screen.capture(display=...)`; handle `RuntimeError`; no direct screen-capture services. |
| Vision | `wingmen/facade.py:359–444`, `:280`, `:23`; `skills/vision_ai/main.py:60–92` | Await `ai.generate(prompt, system=..., image=...)`, a string result. Capped calls may raise `FacadeError`. JPEG encoding/downscaling on a worker thread; no disk screenshots. Pillow ships in `requirements.txt:93`. |
| Client image logging | `skills/MIGRATING-TO-V3.md:150–177` | Optional `printr.print_async(additional_data={"image_base64": ...})`; off by default. |
| Game folder | `wingmen/facade.py:1653–1711` | `star_citizen.environment_path("LIVE")`; read `user/client/0/Profiles/default/actionmaps.xml`, never write it. |
| Game log | `wingmen/facade.py:1712–1772`; public snapshot shape corroborated by `services/sc_gamelog/state.py:55–90`, `:361–422` | Check `sc_gamelog.available`, take fresh `state()` snapshots; read active_missions dictionary, objective and objectives strings. No imports of the state implementation, no subscription needed, no history database access. Treat all values as untrusted data. |
| Typed choices | `wingmen/facade.py:1773–1995` | Optional disambiguation: check `system_one.available`, use `choice` + `decide`; fallback to strictly allowlisted `ai.generate`. Never accept model-supplied destinations outside candidates. |
| Cooperation | `skills/MIGRATING-TO-V3.md:255–290` | Accept other tools' destination strings through `plot_route` validation; no direct imports of other skills. |
| Speech | `skills/MIGRATING-TO-V3.md:88–106` | Await `tts.speak(..., interrupt=False)`; drain `audio.is_playing` with finite, cancellable waits. |
| Manifest | `api/interface.py:950` | Free-form version `3.2.0`; original authors and Dominicus credited. |
| Desktop | Python stdlib ctypes / Win32 API; bundled keyboard and mouse packages | Lazy import; Toolhelp process lookup of foreground window, monitor metadata, clipboard text preservation; no desktop actions in tests. |

## Keybind contract

Read the real `ActionMaps/ActionProfiles/actionmap/action/rebind` hierarchy.
`v_starmap` defaults to F2 across `spaceship_hud`, `player`, `vehicle_general`;
`mapui_action_planroute` defaults to R in `mapui`. Missing files/actions use defaults.
An explicit empty binding is unbound, not a default. Conflicting effective Starmap
bindings across maps refuse routing, since the active gameplay context is unknown.
Unsupported device bindings or key names refuse routing with guidance. Modifiers
are translated into keyboard-package names; no actionmaps file is edited.

## Verification boundary

Tests use inert desktop, game-log and provider doubles. The compatibility probe
loads the genuine schema, Skill base, facades, module manager and catalog with only
external effects stubbed. A passing result does not prove a live in-game route.
