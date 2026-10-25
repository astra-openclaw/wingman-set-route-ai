# Changelog

SetRouteAI by **Thord - galacticgearjammer - ProjectGnome**, expanded by **Dominicus**.

## 3.2.0 (unreleased)

- Detect the game's monitor automatically; require valid monitor/resolution/window calibration.
- Guard every input burst by StarCitizen.exe foreground ownership and clean up held keys on stop.
- Make cancellation work across Wingman's separate voice-turn threads; accept only one macro at a time.
- Keep the original Starmap hold (1.4 seconds), zoom settle (2.1 seconds), result settle (0.5 seconds), and four immediate bound-plan-key taps, with bounded settings.
- Clear search before paste and restore ordered clipboard formats, including images, file selections and rich text, after routing or interruption. Snapshot up to 256 MB off-thread; unreadable/unsupported content produces one short notice without blocking routing.
- Respect keyboard overrides while ignoring joystick/gamepad binds; report explicit unbindings and conflicting maps.
- Import only personal differences from the original database. Ignore dependency samples and preserve future shipped aliases.
- Back up corrupt data without resetting it. Successful recalibration can replace a corrupt calibration after byte backup.
- Merge 32 duplicate records with aliases preserved; keep 1,330 destinations and no new cross-destination alias collisions.
- Resolve all 20 L-point short forms uniquely; require 0.90 fuzzy confidence and a 0.05 lead for automatic matching.
- Keep in-game search text separate from system-qualified keys; ask about same-named gateways using their systems.
- Support corrected/translated names with exact heard-word disagreement checks; agreement never produces a one-option “which” question. Recognize spoken L-point numbers and letter variants.
- If the corrected destination has no match or candidates, suggest matches from the player's heard words as a question, even at high fuzzy confidence. If neither resolves, quote the heard words in the refusal.
- Add game-log mission/system awareness and validated destinations from cooperating skills.
- Verify routes optionally with an in-memory, game-window-only image using a 1.15 MP budget suited to ultrawide screens.
- Tolerate harmless vision formatting differences. On NOT_SET/UNSURE, retry only the plan taps once and verify once more; otherwise leave the map open. Log each parsed verdict and read text server-side only, never the image.
- Speak natural guidance and hide unexpected exception text. Guard routing and calibration through the final reply: only the expected skill lines play, even after a fast return; clear after final playback, a 25-second reply timeout or a new user message.
- Refuse explicitly closed, offline or decommissioned UEX locations. Preserve and evidence-tag 470 records in systems UEX explicitly marks unavailable live; exclude those records from fuzzy and AI choices and explain exact requests. Missing data is never proof of unavailability.
- Include the unchanged original logo, MIT license and author credits in the deterministic install ZIP.
- Publish a player-first guide to setup, upgrades, settings, troubleshooting and vision privacy/cost.
