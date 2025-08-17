#!/usr/bin/env python3
# coding: utf-8

import json, csv

INPUT = "./raw/MineralDeposits.json"
OUTPUT = "./data/MineralDeposits.csv"

# CSV column headers
HEADERS = [
    "ENO","DEPOSIT_NAME","SYNONYMS","STATE","LONG_GDA94","LAT_GDA94","ACCURACY_M",
    "OPERATING_STATUS","COMMODITY_PRIMARY","COMMODITY_SECONDARY","COMMODITY_NAMES",
    "COMPANIES","COMPANY_WEBSITES","PROVINCES","GEOLOGIC_AGE","DEPOSIT_MODEL",
    "Environment","Group","Type"
]

def split_primary_secondary(s: str):
    """Split commodity codes into primary and secondary."""
    if not s:
        return "", ""
    items = [t.strip() for t in s.split(",")]
    primaries, secondaries = [], []
    for t in items:
        if not t:
            continue
        has_paren = ("(" in t) or (")" in t) or ("（" in t) or ("）" in t)
        # Secondary if in parentheses
        if (t.startswith("(") and t.endswith(")")) or (t.startswith("（") and t.endswith("）")) or has_paren:
            v = t.strip().strip("()").strip("（）").strip()
            if v:
                secondaries.append(v)
        else:
            primaries.append(t)
    return ", ".join(primaries), ", ".join(secondaries)

def parse_deposit_model(s: str):
    """Parse 'Environment: ..., Group: ..., Type: ...' into fields."""
    env = grp = typ = ""
    if s:
        for part in [p.strip() for p in s.split(",")]:
            if ":" in part:
                k, v = part.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if k == "environment":
                    env = v
                elif k == "group":
                    grp = v
                elif k == "type":
                    typ = v
    return env, grp, typ

# Load JSON data
with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

features = data["features"]

# Write CSV
with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=HEADERS)
    w.writeheader()

    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [None, None]) 

        row = {}
        for k in HEADERS:
            # Fill primary/secondary later
            if k in ("COMMODITY_PRIMARY", "COMMODITY_SECONDARY"):
                row[k] = ""
            else:
                v = props.get(k, "")
                row[k] = "" if v is None else v

        # Use geometry coordinates if missing
        if not row["LONG_GDA94"]:
            row["LONG_GDA94"] = coords[0]
        if not row["LAT_GDA94"]:
            row["LAT_GDA94"] = coords[1]

        # Parse commodity codes
        primary, secondary = split_primary_secondary(props.get("COMMODITY_CODES", ""))
        row["COMMODITY_PRIMARY"] = primary
        row["COMMODITY_SECONDARY"] = secondary

        # Parse deposit model
        env, grp, typ = parse_deposit_model(props.get("DEPOSIT_MODEL", ""))
        row["Environment"] = env
        row["Group"] = grp
        row["Type"] = typ

        w.writerow(row)

print(f"Done -> {OUTPUT}")
