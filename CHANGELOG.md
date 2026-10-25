# Changelog

SetRouteAI by **Thord - galacticgearjammer - ProjectGnome**, expanded by **Dominicus**.

## 3.2.0

- Require valid display/resolution/window-specific calibration; preserve legacy v1 data.
- Guard every input burst by StarCitizen.exe foreground ownership; release held keys on stop.
- Keep shipped locations immutable; atomically persist user edits and migrate older layouts.
- Preserve/back up invalid JSON and refuse to use it instead of resetting it.
- Restrict matches to database destinations; handle collisions and cascade edits consistently.
- Remove 26 empty/single-letter database entries; preserve legacy raw copies during migration.
- Add bounded macro timings, clear-before-paste, clipboard-text restore and cancel_route.
- Read real Star Citizen actionmaps keyboard overrides, modifiers and explicit unbindings.
- Add game-log system disambiguation and resolvable active-mission navigation.
- Scope prompts to navigation and accept validated destinations from cooperating skills.
- Add default-off in-memory screenshot route verification via Wingman's supported facades.
- Cross-check eight UEX datasets; add 73 positively live, active, quantum-marked destinations,
  enrich 333 live matches plus Ariel's system, and add 54 source-backed aliases.
- Publish install/upgrade/privacy/compatibility documentation and deterministic release tooling.
- License software under MIT with original-author and Dominicus attribution.
