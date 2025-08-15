#!/usr/bin/env python3
# coding: utf-8

import json, csv

INPUT = "./raw/MineralDeposits.json"
OUTPUT = "./data/MineralDeposits.csv"

HEADERS = [
    "ENO","DEPOSIT_NAME","SYNONYMS","STATE","LONG_GDA94","LAT_GDA94","ACCURACY_M",
    "OPERATING_STATUS","COMMODITY_PRIMARY","COMMODITY_SECONDARY","COMMODITY_NAMES",
    "COMPANIES","COMPANY_WEBSITES","PROVINCES","GEOLOGIC_AGE","DEPOSIT_MODEL"
]

def split_primary_secondary(s: str):
    if not s:
        return "", ""
    items = [t.strip() for t in s.split(",")]
    primaries, secondaries = [], []
    for t in items:
        if not t:
            continue
        has_paren = ("(" in t) or (")" in t) or ("（" in t) or ("）" in t)
        if (t.startswith("(") and t.endswith(")")) or (t.startswith("（") and t.endswith("）")) or has_paren:
            v = t.strip().strip("()").strip("（）").strip()
            if v:
                secondaries.append(v)
        else:
            primaries.append(t)
    return ", ".join(primaries), ", ".join(secondaries)

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

features = data["features"]

with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=HEADERS)
    w.writeheader()

    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [None, None]) 

        row = {}
        for k in HEADERS:
            if k in ("COMMODITY_PRIMARY", "COMMODITY_SECONDARY"):
                row[k] = ""
            else:
                v = props.get(k, "")
                row[k] = "" if v is None else v

        if not row["LONG_GDA94"]:
            row["LONG_GDA94"] = coords[0]
        if not row["LAT_GDA94"]:
            row["LAT_GDA94"] = coords[1]

        primary, secondary = split_primary_secondary(props.get("COMMODITY_CODES", ""))
        row["COMMODITY_PRIMARY"] = primary
        row["COMMODITY_SECONDARY"] = secondary

        w.writerow(row)

print(f"Done -> {OUTPUT}")