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
| poi | 232 | 230 |
| jump_points | 6 | See note |

Jump-point records describe origin/destination systems and orbit names, without a single
canonical name or availability flag. All six connections are recorded separately in the
cross-check report; no synthetic destination names were invented from them.

Before enrichment, 333 primary names matched explicitly available UEX names, 98 names were
missing as primary keys and 958 original names were absent from that live-only subset.
After review: **402 exact primary matches, 27 missing primary names, 928 stale suspects**
and 13 possible renames for manual review. Missing-primary results can already be aliases,
status-filtered records or deliberately separate system-qualified keys.

Reviewed changes:

- Keep the original 333 enrichments with spelling, system and source IDs, plus Ariel's Sol metadata.
- Fold 32 proven duplicate records into their canonical destinations, preserving every old alias.
  This includes 18 named L-point stations; CRU L2 and CRU L3 have no named station in this UEX
  snapshot and retain their original short labels. All 20 short forms resolve uniquely.
- Of the initial 73 added keys, 69 remain after folding two closed/offline additions and deferring
  two uncertain additions (Julep Aid Shelter and Cluster RSC-340). Some retained keys replace
  original duplicates rather than adding a distinct place. No unproven spelling change is applied.
- Preserve closed/offline original locations, with explicit status refusal. Port Olisar is retained
  but marked decommissioned from space_stations ID 22. Mere absence never causes refusal/deletion.
- Remove the incorrect Shady Glen alias from Samson. All 35 remaining cross-destination alias
  collisions already existed under the original normalization; no new collision is introduced.
- Store gateway systems separately from the display/search label. Nyx, Pyro and Stanton Gateway
  homonyms remain separate records; matching expands shared labels before deciding by system.
- Keep and tag **470 destinations** in systems explicitly marked `is_available_live=0` by
  the same star_systems snapshot (only Stanton, Pyro and Nyx are live there). Association
  uses existing system metadata, an exact UEX location-name/system match, or an explicit
  system-qualified original name such as Corel I / Corel - Geddon / Corel Star. Each tagged
  record stores the system ID, explicit zero flag and association evidence. These records
  are excluded from fuzzy and AI candidates; exact requests explain the unavailable system.
  Exact alias collisions remain visible as real ambiguities (for example Arial / Ariel),
  but choosing an unavailable place never sends input. Unknown/missing systems are not tagged.
  UEX-SYSTEM-AVAILABILITY.json records the snapshot hash and complete tagged-key list.
- Final database: **1,330 destinations**. The 26 empty/single-letter noise keys stay removed.

The repository's UEX-CHANGES.json and UEX-CROSSCHECK.json contain per-entry evidence.
Possible renames are suggestions, never automatic replacements. The developer tool can
repeat the comparison with explicit --fetch or operate entirely on cached snapshots.
