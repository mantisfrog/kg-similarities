# Import necessary libraries for JSON, CSV, and path manipulation.
import json, csv
from pathlib import Path

# Get the absolute path of the directory containing this script.
script_dir = Path(__file__).resolve().parent

# Determine the project root directory (two levels up from the script's directory).
project_root = script_dir.parent.parent

# Define absolute paths for the input JSON and output CSV files.
INPUT = project_root / "data/raw/deposit/MineralDeposits.json"
INPUT_CSV = project_root / "data/raw/deposit/MajorResourceProjects.csv"
INPUT_CSV_2 = project_root / "data/raw/deposit/MineView.csv"
COMMODITY_MAPPING_CSV = project_root / "data/raw/deposit/commodity_mapping.csv"
#Rewrite the CommodityNames table using a more robust CommoditySymbol and CommodityName mapping table.
OUTPUT = project_root / "data/processed/MineralDeposits.csv"

# --- End of Modification ---


# Define the column headers for the output CSV file.
HEADERS = [
    "ENO","DEPOSIT_NAME","SYNONYMS","STATE","LONG_GDA94","LAT_GDA94","ACCURACY_M",
    "OPERATING_STATUS","COMMODITY_PRIMARY","COMMODITY_SECONDARY","COMMODITY_NAMES",
    "COMPANIES","COMPANY_WEBSITES","PROVINCES","GEOLOGIC_AGE","DEPOSIT_MODEL",
    "DEPOSIT_MODEL_ENVIRONMENT","DEPOSIT_MODEL_GROUP","DEPOSIT_MODEL_TYPE"
]

def load_commodity_mapping(filepath):
    """Loads commodity mappings from symbol to name and name to symbol."""
    symbol_to_name, name_to_symbol = {}, {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if not row or len(row) < 2 or not row[0] or not row[1]:
                    continue
                val1, val2 = row[0].strip(), row[1].strip()
                # Heuristic: shorter string is symbol, longer is name
                symbol, name = (val1, val2) if len(val1) <= len(val2) else (val2, val1)
                if symbol and name:
                    symbol_to_name[symbol] = name
                    name_to_symbol[name] = symbol
    except FileNotFoundError:
        print(f"Warning: Commodity mapping file not found at {filepath}")
    return symbol_to_name, name_to_symbol

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

def main():
    """Main function to orchestrate the data loading, processing, and writing."""
    # Ensure the output directory exists.
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # --- Data Loading and Initial Processing ---
    all_data = []
    existing_enos = set()
    symbol_to_name, name_to_symbol = load_commodity_mapping(COMMODITY_MAPPING_CSV)

    # 1. Process MineralDeposits.json
    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)
    data = clean_strings(data)
    features = data.get("features", [])

    for feat in features:
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", {}) or {}
        coords = geom.get("coordinates", [None, None])
        eno = props.get("ENO")

        if eno and str(eno) not in existing_enos:
            row = {h: "" for h in HEADERS}
            for k in HEADERS:
                v = props.get(k)
                row[k] = "" if v is None else v

            row["ENO"] = eno
            existing_enos.add(str(eno))

            if not row["LONG_GDA94"]:
                row["LONG_GDA94"] = coords[0]
            if not row["LAT_GDA94"]:
                row["LAT_GDA94"] = coords[1]

            primary, secondary = split_primary_secondary(props.get("COMMODITY_CODES", ""))
            row["COMMODITY_PRIMARY"] = primary
            row["COMMODITY_SECONDARY"] = secondary

            env, grp, typ = parse_deposit_model(props.get("DEPOSIT_MODEL", ""))
            row["DEPOSIT_MODEL_ENVIRONMENT"] = env
            row["DEPOSIT_MODEL_GROUP"] = grp
            row["DEPOSIT_MODEL_TYPE"] = typ
            all_data.append(row)

    # 2. Process MajorResourceProjects.csv
    try:
        with open(INPUT_CSV, "r", encoding="utf-8") as f_in:
            reader = csv.DictReader(f_in)
            for row_in in reader:
                cleaned_row_in = clean_strings(row_in)
                eno = cleaned_row_in.get("ENO")

                if eno and eno not in existing_enos:
                    new_row = {h: "" for h in HEADERS}
                    new_row["ENO"] = eno
                    new_row["DEPOSIT_NAME"] = cleaned_row_in.get("PROJECT_NAME", "")
                    new_row["STATE"] = cleaned_row_in.get("STATE", "")
                    new_row["LONG_GDA94"] = cleaned_row_in.get("LONG_GDA94", "")
                    new_row["LAT_GDA94"] = cleaned_row_in.get("LAT_GDA94", "")
                    new_row["ACCURACY_M"] = cleaned_row_in.get("ACCURACY_M", "")
                    new_row["OPERATING_STATUS"] = cleaned_row_in.get("PROJECT_TYPE", "")
                    
                    primary, secondary = split_primary_secondary(cleaned_row_in.get("COMMODITY_PRIMARY", ""))
                    new_row["COMMODITY_PRIMARY"] = primary
                    new_row["COMMODITY_SECONDARY"] = secondary
                    
                    new_row["COMPANIES"] = cleaned_row_in.get("PRINCIPAL_COMPANY", "")
                    
                    all_data.append(new_row)
                    existing_enos.add(eno)
    except FileNotFoundError:
        print(f"Warning: {INPUT_CSV} not found. Skipping.")

    # 3. Process MineView.csv
    try:
        with open(INPUT_CSV_2, "r", encoding="latin-1") as f_in:
            reader = csv.DictReader(f_in)
            for row_in in reader:
                cleaned_row_in = clean_strings(row_in)
                eno = cleaned_row_in.get("ENO")

                if eno and eno not in existing_enos:
                    new_row = {h: "" for h in HEADERS}
                    new_row["ENO"] = eno
                    new_row["DEPOSIT_NAME"] = cleaned_row_in.get("name", "")
                    new_row["LONG_GDA94"] = cleaned_row_in.get("LONG_GDA94", "")
                    new_row["LAT_GDA94"] = cleaned_row_in.get("LAT_GDA94", "")
                    new_row["OPERATING_STATUS"] = cleaned_row_in.get("status", "")
                    
                    commodity_names_str = cleaned_row_in.get("commodity", "")
                    primary_names_str, secondary_names_str = split_primary_secondary(commodity_names_str)
                    
                    primary_names = [n.strip() for n in primary_names_str.split(",") if n.strip()]
                    secondary_names = [n.strip() for n in secondary_names_str.split(",") if n.strip()]

                    primary_symbols = [name_to_symbol.get(n, n) for n in primary_names]
                    secondary_symbols = [name_to_symbol.get(n, n) for n in secondary_names]

                    new_row["COMMODITY_PRIMARY"] = ", ".join(primary_symbols)
                    new_row["COMMODITY_SECONDARY"] = ", ".join(secondary_symbols)
                    
                    new_row["COMPANIES"] = cleaned_row_in.get("owner", "")
                    
                    all_data.append(new_row)
                    existing_enos.add(eno)
    except FileNotFoundError:
        print(f"Warning: {INPUT_CSV_2} not found. Skipping.")

    # --- Final Processing: Repopulate COMMODITY_NAMES ---
    for row in all_data:
        names = []
        primary_symbols_str = row.get("COMMODITY_PRIMARY", "")
        if primary_symbols_str:
            primary_symbols = [s.strip() for s in primary_symbols_str.split(",") if s.strip()]
            for symbol in primary_symbols:
                names.append(symbol_to_name.get(symbol, symbol))

        secondary_symbols_str = row.get("COMMODITY_SECONDARY", "")
        if secondary_symbols_str:
            secondary_symbols = [s.strip() for s in secondary_symbols_str.split(",") if s.strip()]
            for symbol in secondary_symbols:
                name = symbol_to_name.get(symbol, symbol)
                names.append(f"({name})")
        
        row["COMMODITY_NAMES"] = ", ".join(names)

    # --- Write Final CSV ---
    if all_data:
        with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(all_data)
        print(f"Successfully processed and wrote {len(all_data)} rows to {OUTPUT}")
    else:
        print("No data processed.")

if __name__ == "__main__":
    main()