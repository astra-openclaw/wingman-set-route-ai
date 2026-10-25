"""Developer-only UEX comparison. Never imported by the skill."""
import argparse
from difflib import get_close_matches
import json
import re
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "set_route_ai" / "dependencies"))
from destination_engine import normalize

BASE = "https://api.uexcorp.space/2.0/"
DOCS = "https://uexcorp.space/api/documentation/"
TERMS = "https://uexcorp.space/about/terms/"
ENDPOINTS = ("star_systems", "planets", "moons", "space_stations", "cities",
             "outposts", "poi", "jump_points")


def fetch(cache):
    cache.mkdir(parents=True, exist_ok=True)
    for endpoint in ENDPOINTS:
        request = Request(BASE + endpoint, headers={"User-Agent": "SetRouteAI-crosscheck/3.2"})
        try:
            with urlopen(request, timeout=30) as response:
                raw = json.load(response)
            if raw.get("status") != "ok" or not isinstance(raw.get("data"), list):
                raise ValueError("Unexpected API response")
            (cache / (endpoint + ".json")).write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            # A missing optional endpoint is evidence, not an empty successful set.
            (cache / (endpoint + ".json")).write_text(
                json.dumps({"status": "unavailable", "error": type(exc).__name__, "data": []}), encoding="utf-8")
        time.sleep(2)  # <= 30 requests/minute; documented limit 120/minute.


def compare(database, datasets):
    system_names = {r["id"]: r["name"] for r in datasets.get("star_systems", {}).get("data", [])}
    available, endpoint_counts, unavailable, jump_connections = {}, {}, [], []
    excluded = []
    for endpoint in ENDPOINTS:
        payload = datasets.get(endpoint, {})
        if payload.get("status") != "ok":
            unavailable.append(endpoint)
            continue
        rows = payload.get("data", [])
        endpoint_counts[endpoint] = {"all": len(rows), "available": 0}
        for row in rows:
            if endpoint == "jump_points":
                jump_connections.append({k: row.get(k) for k in ("id", "star_system_origin_name", "star_system_destination_name", "orbit_origin_name", "orbit_destination_name")})
            if not isinstance(row.get("name"), str):
                continue
            if row.get("is_decommissioned") or re.search(r"\b(closed|offline)\b", row["name"], re.I):
                excluded.append({"name": row["name"], "endpoint": endpoint, "id": row.get("id"),
                                 "reason": "Explicitly decommissioned, closed or offline"})
                continue
            # Explicit live availability takes precedence; unknown is not proof.
            if not row.get("is_available_live", row.get("is_available", False)):
                continue
            endpoint_counts[endpoint]["available"] += 1
            key = normalize(row["name"])
            record = {"name": row["name"], "endpoint": endpoint, "id": row.get("id"),
                      "system": row.get("star_system_name") or system_names.get(row.get("id_star_system"), "")}
            if endpoint == "star_systems":
                record["system"] = row["name"]
            available.setdefault(key, []).append(record)
    existing = {normalize(k): k for k in database}
    missing = [{"key": k, "records": available[k]} for k in sorted(set(available)-set(existing))]
    suspects = sorted(set(existing)-set(available))
    renames = []
    for suspect in suspects:
        options = get_close_matches(suspect, list(available), n=2, cutoff=.88)
        if options:
            renames.append({"existing": suspect, "possible_names": options, "action": "review only"})
    exact = [{"key": k, "records": available[k]} for k in sorted(set(available)&set(existing))]
    return {"source": BASE, "documentation": DOCS, "terms": TERMS,
            "credit": "Location cross-check data provided by UEX (https://uexcorp.space/).",
            "policy": "No automatic deletions or renames. Missing UEX records are only stale suspects. Unavailable endpoints make coverage partial.",
            "excluded_status_records": excluded,
            "name_policy": "System suffixes are record identifiers, not Starmap search text. Review homonyms and existing aliases before adding a location.",
            "endpoint_counts": endpoint_counts, "unavailable_endpoints": unavailable,
            "jump_connections": jump_connections,
            "jump_note": "Connection endpoint has no availability or canonical name field; recorded separately, not invented as destinations.",
            "exact_matches": exact, "missing": missing, "stale_suspects": suspects, "possible_renames": renames}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true", help="Explicit developer-only HTTPS refresh")
    parser.add_argument("--database", type=Path, default=ROOT / "set_route_ai/database/destinations.json")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.fetch:
        fetch(args.cache)
    datasets = {name: json.loads((args.cache / (name + ".json")).read_text(encoding="utf-8"))
                for name in ENDPOINTS if (args.cache / (name + ".json")).exists()}
    report = compare(json.loads(args.database.read_text(encoding="utf-8")), datasets)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"exact": len(report["exact_matches"]), "missing": len(report["missing"]),
                      "suspects": len(report["stale_suspects"]), "possible_renames": len(report["possible_renames"]),
                      "unavailable": report["unavailable_endpoints"], "counts": report["endpoint_counts"]}))
    return 1 if report["unavailable_endpoints"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
