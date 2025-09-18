#!/usr/bin/env python3
"""
This script transforms a processed CSV file of mineral deposits into a set of node and 
relationship CSV files suitable for importing into a graph database like Neo4j.
"""
# Import necessary libraries for data handling, file paths, and regular expressions.
import csv
import re
from pathlib import Path
import pandas as pd

# --- Start of Modification ---

# Get the absolute path of the directory containing this script.
script_dir = Path(__file__).resolve().parent
# Determine the project root directory (two levels up from the script's directory).
project_root = script_dir.parent.parent

# Define absolute paths for the source CSV and the output directory for graph files.
SRC = project_root / "data/processed/Deposits_spatial.csv"
OUTPUT_DIR = project_root / "data/graph"

# Ensure the output directory exists, creating it if necessary.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- End of Modification ---


# Define the columns required from the source CSV file.
COLS = [
    "ENO","DEPOSIT_NAME","SYNONYMS","STATE","LONG_GDA94","LAT_GDA94",
    "OPERATING_STATUS","COMMODITY_PRIMARY","COMMODITY_SECONDARY","COMMODITY_NAMES",
    "COMPANIES","GEOLOGIC_AGE","DEPOSIT_MODEL_ENVIRONMENT","DEPOSIT_MODEL_GROUP",
    "DEPOSIT_MODEL_TYPE","PROVINCES","IGNEOUS","METALLOGENIC","SEDIMENTARY","TECTONIC"
]

# Define specific synonym phrases that should not be split by commas.
SPECIAL_SYNONYMS = [
    "2, 3, 4, 5, 6/7, 9",
    "2, 3",
]

# --- START: Added section for data exclusion ---
# Define data to be excluded from the graph.
EXCLUDED_NAMES = set(SPECIAL_SYNONYMS)
EXCLUDED_COMPANY_NORM = "unnamed owner"
# --- END: Added section for data exclusion ---

def clean(s):
    """Converts various null-like values (None, nan, 'N/A') to an empty string."""
    if s is None:
        return ""
    t = str(s).strip()
    return "" if t.lower() in {"", "nan", "none", "null", "n/a", "na"} else t

def _remove_unmatched_parens(t: str) -> str:
    """Removes any parentheses that do not have a matching pair."""
    s = str(t)
    out = []
    opens = 0
    # First pass: remove unmatched closing parentheses.
    for ch in s:
        if ch == "(":
            opens += 1
            out.append(ch)
        elif ch == ")":
            if opens > 0:
                opens -= 1
                out.append(ch)
            else:
                continue # Discard unmatched ')'
        else:
            out.append(ch)
    
    # Second pass (in reverse): remove unmatched opening parentheses.
    if opens > 0:
        rev = []
        for ch in reversed(out):
            if ch == "(" and opens > 0:
                opens -= 1
                continue # Discard surplus '('
            rev.append(ch)
        out = list(reversed(rev))
    return "".join(out)

def _strip_outer_single_pair(t: str) -> str:
    """Removes a single pair of parentheses that wraps the entire string."""
    s = str(t).strip()
    if len(s) >= 2 and s.startswith("(") and s.endswith(")") and s.count("(") == 1 and s.count(")") == 1:
        return s[1:-1].strip()
    return s

def _normalize_parens_simple(t: str) -> str:
    """Combines parenthesis cleaning helpers."""
    s = _remove_unmatched_parens(t)
    s = _strip_outer_single_pair(s)
    return s.strip()

def split_commas(s):
    """Splits a string by commas after cleaning and normalizing parentheses."""
    s = clean(s)
    if not s:
        return []
    # Clean parentheses on the whole string first (e.g., "(A, B)").
    s = _normalize_parens_simple(s)
    parts = [p.strip() for p in s.split(",")]
    # Clean again on each part to handle edge cases (e.g., "(A", "B)").
    parts = [_normalize_parens_simple(p) for p in parts]
    # Return only non-empty parts.
    return [p for p in parts if clean(p)]

def split_names_cell(s, is_synonyms=False):
    """
    Splits a cell containing deposit names or synonyms based on specific rules.
    - DEPOSIT_NAME is treated as a single entity.
    - SYNONYMS are split by comma, respecting special multi-part phrases.
    """
    s_clean = clean(s)
    if not s_clean:
        return []
    
    if is_synonyms:
        tmp = s_clean
        placeholders = {}
        # Temporarily replace special synonym phrases with placeholders to avoid splitting them.
        for idx, sp in enumerate(sorted(SPECIAL_SYNONYMS, key=len, reverse=True), 1):
            if sp in tmp:
                ph = f"__SPECIAL_{idx}__"
                placeholders[ph] = sp
                tmp = tmp.replace(sp, ph)
        
        # Split by comma and then restore the special phrases.
        parts = [p.strip() for p in tmp.split(",") if clean(p)]
        return [placeholders.get(p, p) for p in parts]
    
    # For DEPOSIT_NAME, return the entire string as one item.
    return [s_clean]

def norm_key(s):
    """Normalizes a string to be used as a dictionary key (lowercase, single spaces)."""
    return re.sub(r"\s+", " ", clean(s)).strip().lower()

def write_csv(path, rows, header):
    """Utility function to write a list of rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

def main():
    """Main function to orchestrate the data processing and CSV generation."""
    df = pd.read_csv(SRC, dtype=str).fillna("")
    miss = [c for c in COLS if c not in df.columns]
    if miss:
        raise ValueError(f"Missing required columns in source CSV: {miss}")

    # --- Process and generate unique DepositName nodes ---
    deposit_name_vals = set()
    for _, r in df.iterrows():
        # Extract names from DEPOSIT_NAME column (treated as a single name).
        for n in split_names_cell(r["DEPOSIT_NAME"], is_synonyms=False):
            if n not in EXCLUDED_NAMES:
                deposit_name_vals.add((norm_key(n), n))
        # Extract names from SYNONYMS column (split by comma).
        for n in split_names_cell(r["SYNONYMS"], is_synonyms=True):
            if n not in EXCLUDED_NAMES:
                deposit_name_vals.add((norm_key(n), n))
    
    # Create a sorted list of unique deposit names and assign a unique ID to each.
    deposit_name_sorted = [orig for _, orig in sorted(deposit_name_vals, key=lambda x: x[0])]
    deposit_name_id = {v: f"depositName_{i:04d}" for i, v in enumerate(deposit_name_sorted, 1)}

    # --- Process and generate unique Company and CompanyName nodes ---
    company_name_vals = set()
    for _, r in df.iterrows():
        for c in split_commas(r["COMPANIES"]):
            k = norm_key(c)
            if k != EXCLUDED_COMPANY_NORM:
                company_name_vals.add((k, c))

    # Create a sorted list of unique company names and assign a unique ID to each name.
    company_name_sorted = [orig for _, orig in sorted(company_name_vals, key=lambda x: x[0])]
    company_name_id = {v: f"companyName_{i:04d}" for i, v in enumerate(company_name_sorted, 1)}

    # Create canonical Company nodes based on the normalized key.
    company_map = {k: f"company_{i:04d}" for i, k in enumerate(sorted({k for k, v in company_name_vals}), 1)}
    company_id = {v: company_map[norm_key(v)] for v in company_name_sorted}

    # --- Process and generate unique Commodity nodes ---
    sym_keys = {} # Maps normalized symbol to original symbol.
    for _, r in df.iterrows():
        commodities = split_commas(r["COMMODITY_PRIMARY"]) + split_commas(r["COMMODITY_SECONDARY"])
        for s in commodities:
            k = norm_key(s)
            if k not in sym_keys:
                sym_keys[k] = s

    # Attempt to map commodity symbols to their full names.
    sym2name = {k: "" for k in sym_keys}
    for _, r in df.iterrows():
        syms = split_commas(r["COMMODITY_PRIMARY"]) + split_commas(r["COMMODITY_SECONDARY"])
        names = split_commas(r["COMMODITY_NAMES"])
        if not syms or not names:
            continue
        
        # If number of symbols and names match, map them one-to-one.
        if len(names) == len(syms):
            for s, n in zip(syms, names):
                k = norm_key(s)
                if k in sym2name and not sym2name[k] and clean(n):
                    sym2name[k] = n
        # If there is one name for multiple symbols, apply it to all.
        elif len(names) == 1:
            n = names[0]
            for s in syms:
                k = norm_key(s)
                if k in sym2name and not sym2name[k] and clean(n):
                    sym2name[k] = n
    
    # Create a sorted list of unique commodities and assign a unique ID.
    sym_sorted = sorted(sym_keys.keys())
    sym_id = {k: f"commodity_{i:04d}" for i, k in enumerate(sym_sorted, 1)}

    # --- Write Node CSV files ---
    write_csv(
        OUTPUT_DIR / "node_DepositName.csv",
        [[deposit_name_id[v], v, "DepositName"] for v in deposit_name_sorted],
        header=["depositNameID:ID", "depositNameText:string", ":LABEL"]
    )
    
    write_csv(
        OUTPUT_DIR / "node_Company.csv",
        [[cid, "Company"] for cid in sorted(company_map.values())],
        header=["companyID:ID", ":LABEL"]
    )

    write_csv(
        OUTPUT_DIR / "node_CompanyName.csv",
        [[company_name_id[v], v, "CompanyName"] for v in company_name_sorted],
        header=["companyNameID:ID", "companyNameText:string", ":LABEL"]
    )
    
    node_commodity_rows = []
    for k in sym_sorted:
        symbol = sym_keys[k]
        cname = sym2name.get(k, "")
        node_commodity_rows.append([sym_id[k], symbol, cname, "Commodity"])
    write_csv(
        OUTPUT_DIR / "node_Commodity.csv",
        node_commodity_rows,
        header=["commodityID:ID", "commoditySymbol:string", "commodityName:string", ":LABEL"]
    )

    # --- Process and generate Deposit nodes ---
    dep_rows = []
    dep_id = {} # Maps DataFrame index to deposit ID.
    for i, r in df.iterrows():
        did = f"deposit_{i+1:04d}"
        dep_id[i] = did
        eno_raw = clean(r["ENO"])
        try: # Ensure ENO is an integer.
            eno_val = str(int(float(eno_raw))) if eno_raw else ""
        except ValueError:
            eno_val = ""
        
        lon, lat = clean(r["LONG_GDA94"]), clean(r["LAT_GDA94"])
        location = f"{lon},{lat}" if lon and lat else ""
        
        dep_rows.append([
            did, eno_val, clean(r["STATE"]), location, clean(r["OPERATING_STATUS"]),
            clean(r["GEOLOGIC_AGE"]), clean(r["DEPOSIT_MODEL_ENVIRONMENT"]),
            clean(r["DEPOSIT_MODEL_GROUP"]), clean(r["DEPOSIT_MODEL_TYPE"]),
            clean(r["PROVINCES"]), clean(r["IGNEOUS"]), clean(r["METALLOGENIC"]),
            clean(r["SEDIMENTARY"]), clean(r["TECTONIC"]), "Deposit",
        ])
    
    write_csv(
        OUTPUT_DIR / "node_Deposit.csv",
        dep_rows,
        header=[
            "depositID:ID","ENO:int","STATE:string","LOCATION:string",
            "OPERATING_STATUS:string","GEOLOGIC_AGE:string",
            "DEPOSIT_MODEL_ENVIRONMENT:string","DEPOSIT_MODEL_GROUP:string",
            "DEPOSIT_MODEL_TYPE:string","PROVINCES:string","IGNEOUS:string",
            "METALLOGENIC:string","SEDIMENTARY:string","TECTONIC:string",":LABEL"
        ]
    )

    # --- Generate and write Relationship CSV files ---
    
    # Relationship: (DepositName)-[:REFERS_TO_DEPOSIT]->(Deposit)
    rel_refers_deposit = set()
    for i, r in df.iterrows():
        did = dep_id[i]
        names_to_link = split_names_cell(r["DEPOSIT_NAME"], False) + split_names_cell(r["SYNONYMS"], True)
        for n in names_to_link:
            if n in deposit_name_id: # Ensure the name exists as a node before creating a relationship.
                rel_refers_deposit.add((deposit_name_id[n], did))
    write_csv(
        OUTPUT_DIR / "rel_Refers_to_Deposit.csv",
        [[a, b, "REFERS_TO_DEPOSIT"] for (a, b) in sorted(rel_refers_deposit)],
        header=[":START_ID", ":END_ID", ":TYPE"]
    )

    # Relationship: (CompanyName)-[:REFERS_TO_COMPANY]->(Company)
    rel_refers_company = set()
    for name_text, name_id in company_name_id.items():
        comp_id = company_id[name_text]
        rel_refers_company.add((name_id, comp_id))
    write_csv(
        OUTPUT_DIR / "rel_Refers_to_Company.csv",
        [[a, b, "REFERS_TO_COMPANY"] for (a, b) in sorted(rel_refers_company)],
        header=[":START_ID", ":END_ID", ":TYPE"]
    )

    # Relationship: (Deposit)-[:HAS]->(Commodity)
    rel_has = set()
    for i, r in df.iterrows():
        did = dep_id[i]
        for s in split_commas(r["COMMODITY_PRIMARY"]):
            k = norm_key(s)
            if k in sym_id:
                rel_has.add((did, sym_id[k], "HAS", "Primary"))
        for s in split_commas(r["COMMODITY_SECONDARY"]):
            k = norm_key(s)
            if k in sym_id:
                rel_has.add((did, sym_id[k], "HAS", "Secondary"))
    write_csv(
        OUTPUT_DIR / "rel_Has.csv",
        [list(t) for t in sorted(rel_has)],
        header=[":START_ID", ":END_ID", ":TYPE", "ROLE:string"]
    )

    # Relationship: (Company)-[:OWNS]->(Deposit)
    rel_owns = set()
    for i, r in df.iterrows():
        did = dep_id[i]
        for c in split_commas(r["COMPANIES"]):
            if c in company_id: # Ensure the company exists as a node.
                rel_owns.add((company_id[c], did, "OWNS"))
    write_csv(
        OUTPUT_DIR / "rel_Owns.csv",
        [[a, b, t] for (a, b, t) in sorted(rel_owns)],
        header=[":START_ID", ":END_ID", ":TYPE"]
    )

if __name__ == "__main__":
    main()