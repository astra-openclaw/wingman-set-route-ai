# SetRouteAI 3.2.0

**Original authors: Thord - galacticgearjammer - ProjectGnome.**
**Wingman AI 3 update and 3.2 expansion: Dominicus.**

Offline database-backed, calibrated Star Citizen navigation for Wingman AI 3.2.11
(Skill API 3, Windows), with optional screenshot verification.

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
It excludes personal data, caches, tests and backups, includes LICENSE, and uses
fixed metadata plus stored entries for byte-identical rebuilds across zlib versions.

Developer-only UEX refresh (never runs in the skill):

```text
python -B tools/uex_crosscheck.py --cache <scratch-cache> --fetch --report <report.json>
```

Without `--fetch`, cached snapshots are compared offline. Reports are advisory;
review every database change. No UEX absence is grounds for deleting an entry.
