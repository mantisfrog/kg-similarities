#!/usr/bin/env python3
# coding: utf-8

import json, csv

INPUT = "./raw/MineralDeposits.json"
OUTPUT = "./data/MineralDeposits.csv"

HEADERS = [
    "ENO","DEPOSIT_NAME","SYNONYMS","STATE","LONG_GDA94","LAT_GDA94","ACCURACY_M",
    "OPERATING_STATUS","COMMODITY_CODES","COMMODITY_NAMES","COMPANIES","COMPANY_WEBSITES",
    "PROVINCES","GEOLOGIC_AGE","DEPOSIT_MODEL","LINKED_FILES"
]

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

features = data["features"]

with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=HEADERS)
    w.writeheader()

    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [None, None])  # [lon, lat]

        row = {}
        for k in HEADERS:
            v = props.get(k, "")
            row[k] = "" if v is None else v

        if not row["LONG_GDA94"]:
            row["LONG_GDA94"] = coords[0]
        if not row["LAT_GDA94"]:
            row["LAT_GDA94"] = coords[1]

        w.writerow(row)

print(f"Done -> {OUTPUT}")
