# Import necessary libraries for JSON, CSV, and path manipulation.
import json, csv, re
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
        with open(filepath, "r", encoding="utf-8-sig") as f:
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
    """Splits a comma-separated string of commodities into primary and secondary lists."""
    if not s:
        return "", ""

    # Find all secondary commodities (inside parentheses)
    secondary_groups = re.findall(r'[\(（](.*)[\)）]', s)
    secondaries = []
    for group in secondary_groups:
        secondaries.extend([item.strip() for item in group.split(',') if item.strip()])

    # Remove secondary parts from the string to get primaries
    primaries_str_cleaned = re.sub(r'[\(（].*[\)）]', '', s)
    primaries = [item.strip() for item in primaries_str_cleaned.split(',') if item.strip()]

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
    """Recursively removes newline and carriage return characters from all string values in a nested object."""
    if isinstance(obj, str):
        s = obj.replace("\r", "").replace("\n", "")
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
    with open(INPUT, "r", encoding="utf-8-sig") as f:
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
        with open(INPUT_CSV, "r", encoding="utf-8-sig") as f_in:
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
        with open(INPUT_CSV_2, "r", encoding="utf-8-sig") as f_in:
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

    # --- Final Processing ---
    # Define the mapping for operating status
    status_mapping = {
        "Mine Projects": [
            "mineral deposit", "mining", "new mine", "mine expansion",
            "operating mine", "under development", "care and maintenance",
            "historic mine", "closed"
        ],
        "Processing Projects": ["processing"],
        "Infrastructure Projects": ["infrastructure"],
        "Feasibility Studies": [
            "scoping", "pre-feasibility", "feasibility",
            "definitive feasibility", "bankable feasibility"
        ]
    }
    # Create a reverse mapping for easier lookup (old_status -> new_status)
    reverse_status_mapping = {}
    for new_status, old_statuses in status_mapping.items():
        for old_status in old_statuses:
            reverse_status_mapping[old_status.lower()] = new_status

    # Repopulate COMMODITY_NAMES and OPERATING_STATUS
    for row in all_data:
        # Repopulate COMMODITY_NAMES
        names = []
        primary_symbols_str = row.get("COMMODITY_PRIMARY", "")
        if primary_symbols_str:
            primary_symbols = [s.strip() for s in primary_symbols_str.split(",") if s.strip()]
            for symbol in primary_symbols:
                names.append(symbol_to_name.get(symbol, symbol))

        secondary_symbols_str = row.get("COMMODITY_SECONDARY", "")
        if secondary_symbols_str:
            secondary_symbols = [s.strip() for s in secondary_symbols_str.split(",") if s.strip()]
            secondary_names = [symbol_to_name.get(symbol, symbol) for symbol in secondary_symbols]
            if secondary_names:
                names.append(f"({', '.join(secondary_names)})")
        
        row["COMMODITY_NAMES"] = ", ".join(names)

        # Repopulate OPERATING_STATUS
        current_status = row.get("OPERATING_STATUS", "").lower().strip()
        # Keep original value if no mapping is found
        row["OPERATING_STATUS"] = reverse_status_mapping.get(current_status, row.get("OPERATING_STATUS", ""))


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