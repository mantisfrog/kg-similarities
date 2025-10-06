import csv
import sys
import re
from collections import defaultdict
from pathlib import Path

# Increase CSV field size limit in case the TSV has very long fields
csv.field_size_limit(sys.maxsize)

def process_files(master_csv_path, company_tsv_path, output_csv_path):
    """
    Matches company names from a master CSV to a large TSV file,
    handles name variations, and finds all associated company names by ACN.
    """
    print(f"Starting to load {company_tsv_path} into memory...")
    # Use two dictionaries to optimize lookups
    # name_to_acn: for quickly finding the first matching ACN from a company name
    # acn_to_names: for quickly finding all associated company names from an ACN
    name_to_acn = {}
    acn_to_names = defaultdict(list)

    try:
        with open(company_tsv_path, mode='r', encoding='utf-8', newline='') as tsvfile:
            tsv_reader = csv.reader(tsvfile, delimiter='\t')
            for i, row in enumerate(tsv_reader):
                # Ensure the row has at least 2 columns to extract name and ACN
                if len(row) >= 2:
                    name, acn = row[0].strip(), row[1].strip()
                    if name and acn:
                        # 1. Add all names to the acn_to_names dictionary without additional conditions
                        #    This ensures we collect all names associated with an ACN
                        acn_to_names[acn].append(name)

                        # 2. Check if this row can be used as a valid "initial match"
                        #    Condition 1: Column 14 exists and is empty
                        #    Condition 2: Column 14 is not empty, but its content (company name) is not in existing initial matches
                        is_valid_for_initial_match = False
                        if len(row) >= 14:
                            # Get the previous company name from column 14 and convert to uppercase
                            prev_company_name = row[13].strip().upper()
                            # If column 14 is empty, or the company name in it is not in our initial match dictionary, then it qualifies
                            if not prev_company_name or prev_company_name not in name_to_acn:
                                is_valid_for_initial_match = True
                        
                        if is_valid_for_initial_match:
                            # Store only the first valid name-ACN pair encountered
                            if name not in name_to_acn:
                                name_to_acn[name] = acn
                if (i + 1) % 1000000 == 0:
                    print(f"  Processed {i + 1} rows...")
    except FileNotFoundError:
        print(f"Error: TSV file not found at '{company_tsv_path}'")
        return
    except Exception as e:
        print(f"Error reading TSV file: {e}")
        return

    print(f"TSV file loading completed. Loaded {len(name_to_acn)} unique company names.")
    print(f"Starting to process {master_csv_path} and write to {output_csv_path}...")

    try:
        with open(master_csv_path, mode='r', encoding='utf-8') as master_csv, \
             open(output_csv_path, mode='w', encoding='utf-8', newline='') as output_csv:
            
            csv_reader = csv.reader(master_csv)
            csv_writer = csv.writer(output_csv)
            
            # Write the output file header
            csv_writer.writerow(['ID', 'ACN', 'MatchedNames'])
            
            # Skip the header row in master_csv if it exists
            next(csv_reader, None)

            found_count = 0
            for i, row in enumerate(csv_reader):
                if len(row) >= 3:
                    company_id = row[0].strip()
                    company_name = row[2].strip()
                    
                    if not company_name:
                        continue

                    upper_name = company_name.upper()
                    
                    # Use a set to automatically handle and store all unique name variants
                    names_to_check = {upper_name}
                    
                    # Define pairs of variations to replace mutually
                    variation_pairs = [
                        ('LTD', 'LIMITED'),
                        ('CORP', 'CORPORATION'),
                    ]

                    for v1, v2 in variation_pairs:
                        # Use regex with word boundaries (\b) to ensure only whole words are replaced
                        # Check if v1 exists, and if so, generate a variant by replacing it with v2
                        if re.search(r'\b' + v1 + r'\b', upper_name):
                            names_to_check.add(re.sub(r'\b' + v1 + r'\b', v2, upper_name))
                        # Check if v2 exists, and if so, generate a variant by replacing it with v1
                        if re.search(r'\b' + v2 + r'\b', upper_name):
                            names_to_check.add(re.sub(r'\b' + v2 + r'\b', v1, upper_name))

                    found_acn = None
                    # Try to match all possible name variants
                    for name_variant in names_to_check:
                        if name_variant in name_to_acn:
                            found_acn = name_to_acn[name_variant]
                            break # Stop after finding the first match
                    
                    if found_acn:
                        # If an ACN was found, get all associated company names
                        all_associated_names = acn_to_names.get(found_acn, [])
                        if all_associated_names:
                            # Convert company names to title case before writing
                            formatted_names = [name.title() for name in all_associated_names]
                            csv_writer.writerow([company_id, found_acn, ",".join(formatted_names)])
                            found_count += 1
                
                if (i + 1) % 5000 == 0:
                    print(f"  Processed {i + 1} CSV records, found {found_count} matches...")

    except FileNotFoundError:
        print(f"Error: Master CSV file not found at '{master_csv_path}'")
        return
    except Exception as e:
        print(f"Error processing CSV file: {e}")
        return

    print(f"Processing completed. Total matches found: {found_count}.")
    print(f"Results saved to {output_csv_path}")


if __name__ == '__main__':
    # --- File path configuration ---
    project_root = Path(__file__).resolve().parents[2]
    MASTER_CSV = project_root / "data" / "master" / "CompanyData_Master.csv"
    COMPANY_TSV = project_root / "data" / "raw" / "company" / "COMPANY_202509.tsv"
    OUTPUT_CSV = project_root / "data" / "raw" / "company" / "former_names.csv"
    # --------------------

    # Ensure output directory exists
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    process_files(MASTER_CSV, COMPANY_TSV, OUTPUT_CSV)