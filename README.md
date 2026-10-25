# SetRouteAI 3.2.0

**Original authors: Thord - galacticgearjammer - ProjectGnome.**
**Wingman AI 3 update and 3.2 expansion: Dominicus.**

Say **“plot a route to Daymar,” “set course for CRU L1,”** or **“take me to my mission.”**
SetRouteAI drives your calibrated Star Citizen Starmap in **Wingman AI 3.2.11 on Windows**.
It detects the game monitor, respects keyboard overrides alongside HOTAS binds, and stops
when you say **“cancel route”** or leave the game window. Your clipboard, including images,
is restored afterward. Routing and calibration allow only the skill's expected speech
through the final reply, preventing premature filler announcements. Cancellation speaks one
route- or calibration-specific confirmation. When a corrected destination has no match,
similar heard-word matches are offered as questions before any route input.

**First use:** install the ZIP's single skill folder, enable it, focus Star Citizen and say
**“calibrate starmap.”** Close the map before requesting a route.

**Upgrading:** copy over your old skill folder and **keep its root data/ folder for the first
start**. Only personal differences are migrated; dependency samples are ignored.

> Optional vision sends only the calibrated game-window rectangle to your configured AI
> provider. It is off by default; provider privacy rules and image-input costs apply.

Read the [installation, upgrade, settings and privacy guide](set_route_ai/README.md).
See [CHANGELOG](CHANGELOG.md), [NOTICE](NOTICE.md), the [MIT License](LICENSE),
and the [compatibility contract](docs/COMPATIBILITY.md).

## Developer checks

Use Python 3.11 with current, unpinned packages from `requirements-dev.txt`.
Set `PYTHONDONTWRITEBYTECODE=1` or use `-B` for all commands.

```text
python -B -m unittest discover -s tests -v
python -B tests/static_check.py
python -B tests/compatibility.py --reference <official-3.2.11-source>
python -B tools/build_release.py
```

The static check requires `SRA_PRIVATE_WORDS` supplied externally as a JSON array
or newline-separated list; it fails if missing. Do not commit private terms.
If the reference snapshot lacks the official loader, supply its exact-tag file
with `--module-manager <file>`. The probe makes all external effects inert.

The ZIP builder allowlists release files and produces one `set_route_ai/` root.
It excludes personal data, caches, tests and backups, includes the original logo and LICENSE, and uses
fixed metadata plus stored entries for byte-identical rebuilds across zlib versions.

Developer-only UEX refresh (never runs in the skill):

```text
python -B tools/uex_crosscheck.py --cache <scratch-cache> --fetch --report <report.json>
```

Without `--fetch`, cached snapshots are compared offline. Reports are advisory;
review every database change. No UEX absence is grounds for deleting an entry.
