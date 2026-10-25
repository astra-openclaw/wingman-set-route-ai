# Changelog

SetRouteAI by **Thord - galacticgearjammer - ProjectGnome**, expanded by **Dominicus**.

## 3.2.0

- Detect the game's monitor automatically; require valid monitor/resolution/window calibration.
- Guard every input burst by StarCitizen.exe foreground ownership and clean up held keys on stop.
- Make cancellation work across Wingman's separate voice-turn threads; accept only one macro at a time.
- Keep the original Starmap hold (1.4 seconds) and zoom settle (2.1 seconds), with bounded settings.
- Clear search before paste and restore clipboard text. Replacing non-text content is opt-in and announced.
- Respect keyboard overrides while ignoring joystick/gamepad binds; report explicit unbindings and conflicting maps.
- Import only personal differences from the original database. Ignore dependency samples and preserve future shipped aliases.
- Back up corrupt data without resetting it. Successful recalibration can replace a corrupt calibration after byte backup.
- Merge 32 duplicate records with aliases preserved; keep 1,330 destinations and no new cross-destination alias collisions.
- Resolve all 20 L-point short forms uniquely; require 0.90 fuzzy confidence and a 0.05 lead for automatic matching.
- Keep in-game search text separate from system-qualified keys; ask about same-named gateways using their systems.
- Support corrected/translated names alongside the player's original words, with disagreement checks.
- Add game-log mission/system awareness and validated destinations from cooperating skills.
- Verify routes optionally with an in-memory, game-window-only image using a 1.15 MP budget suited to ultrawide screens.
- Tolerate harmless vision formatting differences; leave the map open when uncertain.
- Speak natural guidance, hide unexpected exception text, and suppress premature filler claims during navigation.
- Refuse explicitly closed, offline or decommissioned UEX locations; never delete a place merely because UEX lacks it.
- Include the unchanged original logo, MIT license and author credits in the deterministic install ZIP.
- Publish a player-first guide to setup, upgrades, settings, troubleshooting and vision privacy/cost.
