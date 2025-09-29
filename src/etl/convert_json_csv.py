#!/usr/bin/env python3
# coding: utf-8

# Import necessary libraries for JSON, CSV, and path manipulation.
import json, csv
from pathlib import Path

# --- Start of Modification ---

# Get the absolute path of the directory containing this script.
script_dir = Path(__file__).resolve().parent

# Determine the project root directory (two levels up from the script's directory).
project_root = script_dir.parent.parent

# Define absolute paths for the input JSON and output CSV files.
INPUT = project_root / "data/raw/deposit/MineralDeposits.json"
OUTPUT = project_root / "data/processed/MineralDeposits.csv"

# --- End of Modification ---


# Define the column headers for the output CSV file.
HEADERS = [
    "ENO","DEPOSIT_NAME","SYNONYMS","STATE","LONG_GDA94","LAT_GDA94","ACCURACY_M",
    "OPERATING_STATUS","COMMODITY_PRIMARY","COMMODITY_SECONDARY","COMMODITY_NAMES",
    "COMPANIES","COMPANY_WEBSITES","PROVINCES","GEOLOGIC_AGE","DEPOSIT_MODEL",
    "DEPOSIT_MODEL_ENVIRONMENT","DEPOSIT_MODEL_GROUP","DEPOSIT_MODEL_TYPE"
]

def split_primary_secondary(s: str):
    """Splits a comma-separated string of commodities into primary and secondary lists.
       Commodities in parentheses are considered secondary."""
    if not s:
        return "", ""
    items = [t.strip() for t in s.split(",")]
    primaries, secondaries = [], []
    for t in items:
        if not t:
            continue
        # Check for both English and Chinese parentheses.
        has_paren = ("(" in t) or (")" in t) or ("（" in t) or ("）" in t)
        if (t.startswith("(") and t.endswith(")")) or (t.startswith("（") and t.endswith("）")) or has_paren:
            # Strip parentheses and whitespace to get the value.
            v = t.strip().strip("()").strip("（）").strip()
            if v:
                secondaries.append(v)
        else:
            primaries.append(t)
    return ", ".join(primaries), ", ".join(secondaries)

def parse_deposit_model(s: str):
    """Parses a string like 'Environment: X, Group: Y, Type: Z' into separate values."""
    env = grp = typ = ""
    if s:
        # Split the string by comma to process each key-value pair.
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

def clean_strings(obj):
    """Recursively removes newline and carriage return characters from all string values in a nested object.
       Also fixes known dirty data issues."""
    if isinstance(obj, str):
        s = obj.replace("\r", "").replace("\n", "")
        # Replace historical name and name errors with correct names.
        # https://www.delisted.com.au/ and Bloomberg Company Actions <GO>.
        s = s.replace("AuRico Gold Corporporation", "AuRico Gold Corporation")
        s = s.replace("Resource and Investment NL", "Auris Minerals Ltd")
        s = s.replace("Vendetta Mining Crop", "Vendetta Mining Corp")
        s = s.replace("Henna shenhuo Group Co. Ltd", "Henan Shenhuo Group Co Ltd")
        s = s.replace("Minemakers Ltd (MAK)", "Avenira Limited")
        s = s.replace("BHP Billiton Limited", "BHP Group Limited")
        s = s.replace("Gujarat NRE", "Gujarat NRE Coke Ltd")
        s = s.replace("Black Oak Minerals Limited", "Marda Operations Pty Ltd")
        s = s.replace("Southern Cross Gold Ltd", "Marda Operations Pty Ltd")
        s = s.replace("Centrex Metals Limited", "Centrex Ltd")
        s = s.replace("Fortescue Metals Group Limited", "Fortescue Ltd")
        s = s.replace("Cougar Energy Ltd", "Moreton Resources")
        s = s.replace("Minerals and Metals Group (MMG)", "MMG Ltd")
        s = s.replace("Minerals and Metals Group", "MMG Ltd")
        s = s.replace("MMG Limited (MMG)", "MMG Ltd")
        s = s.replace("Minerals Corporation", "MSM Corporation International Ltd")

        return s
    elif isinstance(obj, dict):
        return {k: clean_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_strings(v) for v in obj]
    else:
        return obj

# Open and load the source JSON file.
with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

# Clean the loaded data to remove unwanted characters.
data = clean_strings(data)

# Extract the list of 'features' from the GeoJSON-like data structure.
features = data.get("features", [])

# Ensure the directory for the output file exists, creating it if necessary.
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Open the output CSV file for writing.
# 'utf-8-sig' ensures compatibility with Excel; newline='' is required by the csv module.
with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=HEADERS)
    # Write the header row to the CSV.
    w.writeheader()

    # Iterate over each feature (deposit) from the JSON data.
    for feat in features:
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", {}) or {}
        coords = geom.get("coordinates", [None, None])

        row = {}
        # Populate the row with data from the 'properties' dictionary.
        for k in HEADERS:
            # These fields will be populated by specialized functions later.
            if k in ("COMMODITY_PRIMARY", "COMMODITY_SECONDARY"):
                row[k] = ""
            else:
                v = props.get(k, "")
                # Ensure None values are converted to empty strings.
                row[k] = "" if v is None else v

        # Use coordinates from the 'geometry' section as a fallback.
        if not row["LONG_GDA94"]:
            row["LONG_GDA94"] = coords[0]
        if not row["LAT_GDA94"]:
            row["LAT_GDA94"] = coords[1]

        # Parse the single commodity codes field into primary and secondary.
        primary, secondary = split_primary_secondary(props.get("COMMODITY_CODES", ""))
        row["COMMODITY_PRIMARY"] = primary
        row["COMMODITY_SECONDARY"] = secondary

        # Parse the single deposit model field into environment, group, and type.
        env, grp, typ = parse_deposit_model(props.get("DEPOSIT_MODEL", ""))
        row["DEPOSIT_MODEL_ENVIRONMENT"] = env
        row["DEPOSIT_MODEL_GROUP"] = grp
        row["DEPOSIT_MODEL_TYPE"] = typ

        # Write the processed row to the CSV file.
        w.writerow(row)