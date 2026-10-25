# UEX location cross-check

SetRouteAI by **Thord - galacticgearjammer - ProjectGnome**, expanded by **Dominicus**.
Location data provided by **[UEX](https://uexcorp.space/)**.

Checked 2026-10-25 using public HTTPS GETs at
https://api.uexcorp.space/2.0/ . Current [documentation](https://uexcorp.space/api/documentation/)
advertises https://api.uexcorp.uk/2.0/ ; the .space base answered all eight requests.
[Terms](https://uexcorp.space/about/terms/), section 5, describe a changing API,
community accuracy limits and no availability guarantee. No special attribution formula was
found there; this project prominently credits and links UEX. No authentication or paid access
was used. Requests were spaced at least 2 seconds apart, below the documented 120/minute
and 172800/day limits. There is no UEX network access in the running skill.

| Endpoint | Rows | Explicitly available rows used in comparison |
| --- | ---: | ---: |
| star_systems | 96 | 3 |
| planets | 324 | 11 |
| moons | 73 | 18 |
| space_stations | 60 | 59 |
| cities | 5 | 5 |
| outposts | 119 | 116 |
| poi | 232 | 232 |
| jump_points | 6 | See note |

Jump-point records describe origin/destination systems and orbit names, without a single
canonical name or availability flag. All six connections are recorded separately in the
cross-check report; no synthetic destination names were invented from them.

Before enrichment, 333 primary names matched explicitly available UEX names, 98 names were
missing as primary keys and 958 original names were absent from that live-only subset.
Afterward: 406 exact primary matches, 25 missing primary names, 958 stale **suspects** and
18 possible renames for manual review. Missing-primary results may already be represented
by an alias, such as Area 18 / Area18 or Green Imperial Housing Exchange / Grim HEX.

Applied changes:

- Enriched 333 exact live matches with canonical display spelling, system and source IDs.
- Added 73 names only when UEX explicitly marked them live, not decommissioned and with a
  quantum marker. No unconfirmed names or (NA) labels were added.
- Added 54 station nicknames/spacing variants or compact-equivalent name aliases.
- Retained Ariel from the original database; UEX moons ID 5 identifies it as Sol, unavailable
  live. That metadata prevents “aerial” from arbitrarily choosing between it and Arial.
- Removed only the pre-identified empty key and 25 single-letter noise entries, not entries
  merely missing from UEX. Other unavailable or possibly stale original entries remain.

The repository's UEX-CHANGES.json and UEX-CROSSCHECK.json contain per-entry evidence.
Possible renames are suggestions, never automatic replacements. The developer tool can
repeat the comparison with explicit --fetch or operate entirely on cached snapshots.
