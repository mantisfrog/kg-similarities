# These logical steps serve as tie breakers within same w_ratio scores.

# Filtering Logic:
# 1. Deduplication: Ensures each company (based on its ticker/ID) is included only once.
# 2. Asset-based Filter: Drops any company whose 'Country of Domicile' is NOT 'Australia' AND its 'Tot Assets:Y' value is missing.

# Sorting Logic:
# The data is sorted in two main tiers:
# 1. Primary Group (companies with a valid Market Cap): Sorted first by a custom country order, then by 'Market Cap' in descending order.
# 2. Secondary Group (remaining companies): Sorted by the same custom country order, then by 'Tot Assets:Y' in descending order.
# The final output lists the primary group first, followed by the secondary group.

import pandas as pd
from pathlib import Path
import pycountry

def convert_shorthand_to_numeric(value):
    """Converts a string with K, M, B suffix to a numeric value."""
    if not isinstance(value, str):
        return pd.to_numeric(value, errors='coerce')
    value = value.strip()
    if not value:
        return None
    suffix = value[-1].upper()
    multiplier = 1
    if suffix == 'K':
        multiplier = 1_000
    elif suffix == 'M':
        multiplier = 1_000_000
    elif suffix == 'B':
        multiplier = 1_000_000_000
    if multiplier > 1:
        numeric_part_str = value[:-1]
        return pd.to_numeric(numeric_part_str, errors='coerce') * multiplier
    return pd.to_numeric(value, errors='coerce')

def iso_to_country_name(code):
    """Converts a 2-letter ISO country code to a country name."""
    if pd.isna(code) or not isinstance(code, str) or len(code.strip()) != 2:
        return None  # Return Not Available for invalid or missing codes
    try:
        country = pycountry.countries.get(alpha_2=code.strip().upper())
        return country.name if country else None
    except (AttributeError, KeyError):
        return None # Handle any lookup errors gracefully



def main():
    project_root = Path(__file__).resolve().parents[2]
    base_path = project_root / 'data' / 'raw' / 'company' / 'bloomberg'
    dirs_to_process = [base_path / 'ICB', base_path / 'BICS']

    df_list = []
    seen_ids = set()
    # Use a fixed, known ID column name for deduplication instead of the first column by index.
    id_col_name = "Ticker"

    for directory in dirs_to_process:
        for csv_file in sorted(directory.glob('*.csv')):
            temp_df = pd.read_csv(csv_file, dtype=str)
            if temp_df.empty:
                continue
            
            # Ensure the expected ID column exists in the dataframe for deduplication.
            if id_col_name not in temp_df.columns:
                print(f"Warning: Expected ID column '{id_col_name}' not found in {csv_file}. Skipping file.")
                continue

            temp_df = temp_df[~temp_df[id_col_name].isin(seen_ids)]
            if temp_df.empty:
                continue
            seen_ids.update(temp_df[id_col_name])
            df_list.append(temp_df)

    if not df_list:
        return

    combined_df = pd.concat(df_list, ignore_index=True)

    # Define original column names from the source files for explicit selection.
    country_col_name = "Cntry Terrtry Of Dom"
    numeric_cols = ["Market Cap", "Revenue:Y", "Tot Assets:Y", "Number of Employees LF"]

    # Convert 2-letter ISO country code to full country name using the specific column name.
    if country_col_name in combined_df.columns:
        combined_df[country_col_name] = combined_df[country_col_name].apply(iso_to_country_name)

    # Convert shorthand numeric strings to numbers for specific columns by name.
    for col in numeric_cols:
        if col in combined_df.columns:
            combined_df[col] = combined_df[col].apply(convert_shorthand_to_numeric)

    combined_df = combined_df.replace(r'^\s*$', None, regex=True)
    combined_df.replace(['0', 0, '--'], None, inplace=True)

    # Define the standardized headers
    new_headers = [
        "Ticker", "Short Name", "Country of Domicile", "Company Type", 
        "Market Cap", "Revenue:Y", "Tot Assets:Y", "Number of Employees:LF", 
        "ICB Sector", "ICB Subsector", "GICS Industry", "GICS SubIndustry", 
        "BICS L3 Industry", "BICS L4 Sub Industry", "BICS L5 Segment", "BICS L6 Segment"
    ]

    # Rename columns if the count matches
    if len(combined_df.columns) == len(new_headers):
        combined_df.columns = new_headers
    else:
        print(f"Warning: Column count mismatch. Expected {len(new_headers)}, but found {len(combined_df.columns)}. Headers not renamed.")

    # Perform a left join with the description file
    des_file_path = project_root / 'data' / 'raw' / 'company' / 'bloomberg' / 'TICKER_NAME_DES.csv'
    if des_file_path.exists():
        des_df = pd.read_csv(des_file_path, dtype=str)
        
        if not des_df.empty and not combined_df.empty:
            # Use explicit key name for joining.
            left_key = 'Ticker'
            right_key = 'Ticker'

            # Ensure keys exist before attempting a join.
            if left_key not in combined_df.columns:
                print(f"Warning: Join key '{left_key}' not in main dataframe. Skipping join.")
            elif right_key not in des_df.columns:
                print(f"Warning: Join key '{right_key}' not in description dataframe. Skipping join.")
            else:
                # Drop columns from des_df that already exist in combined_df, except for the key
                cols_to_drop = [col for col in des_df.columns if col in combined_df.columns and col != right_key]
                des_df.drop(columns=cols_to_drop, inplace=True)
                
                # Perform the left join
                combined_df = pd.merge(combined_df, des_df, left_on=left_key, right_on=right_key, how='left')

    else:
        print(f"Warning: Description file not found at {des_file_path}")

    # Reorder and drop columns as requested
    if 'Short Name' in combined_df.columns and 'LONG_COMP_NAME' in combined_df.columns:
        # Get current column list
        cols = combined_df.columns.tolist()
        
        # Find the index of 'Short Name'
        short_name_index = cols.index('Short Name')
        
        # Remove 'LONG_COMP_NAME' from its current position
        cols.remove('LONG_COMP_NAME')
        
        # Insert 'LONG_COMP_NAME' at the 'Short Name' position
        cols.insert(short_name_index, 'LONG_COMP_NAME')
        
        # Reorder the DataFrame with the new column order
        combined_df = combined_df[cols]
        
        # Drop the 'Short Name' column
        combined_df.drop(columns=['Short Name'], inplace=True)

    # Filter rows: Drop if Country is not Australia AND Market Cap, Revenue:Y, Tot Assets:Y are all null
    if all(col in combined_df.columns for col in ['Country of Domicile', 'Market Cap', 'Revenue:Y', 'Tot Assets:Y']):
        rows_to_drop = combined_df[
            (combined_df['Country of Domicile'] != 'Australia') &
            combined_df[['Market Cap', 'Revenue:Y', 'Tot Assets:Y']].isna().all(axis=1)
        ].index

        if not rows_to_drop.empty:
            combined_df.drop(rows_to_drop, inplace=True)
            print(f"{len(rows_to_drop)} rows dropped due to filter criteria.")
            print(f"{len(combined_df)} rows remaining.")

    # Custom sort before output
    if all(col in combined_df.columns for col in ['Market Cap', 'Country of Domicile', 'Tot Assets:Y']):
        # Define the custom sort order for countries
        country_order = [
            "Australia", "United States", "China", "United Kingdom", "France", 
            "Japan", "Canada", "Mexico", "Saudi Arabia", "India", "South Africa", 
            "Korea, Republic of", "Brazil"
        ]
        
        # --- New Sorting Logic ---
        
        # 1. Split DataFrame into two groups
        # Group 1: Market Cap is not null and not zero
        market_cap_valid = combined_df['Market Cap'].notna() & (combined_df['Market Cap'] != 0)
        df_market_cap = combined_df[market_cap_valid].copy()
        
        # Group 2: Remaining records (Market Cap is null or zero)
        df_remaining = combined_df[~market_cap_valid].copy()

        # Helper function to apply country-based sorting
        def sort_by_country_and_value(df, value_col, ascending_val):
            if df.empty:
                return df
            df['country_cat'] = pd.Categorical(
                df['Country of Domicile'], 
                categories=country_order, 
                ordered=True
            )
            df.sort_values(
                by=['country_cat', value_col], 
                ascending=[True, ascending_val], 
                inplace=True,
                na_position='last'
            )
            df.drop(columns=['country_cat'], inplace=True)
            return df

        # 2. Sort the first group by Market Cap (desc) and then by country
        df_market_cap = sort_by_country_and_value(df_market_cap, 'Market Cap', False)

        # 3. Sort the second group by Total Assets (desc) and then by country
        df_remaining = sort_by_country_and_value(df_remaining, 'Tot Assets:Y', False)
        
        # 4. Concatenate the sorted groups
        combined_df = pd.concat([df_market_cap, df_remaining], ignore_index=True)

    output_path = project_root / 'data' / 'processed' / 'Bloomberg_Companies.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(output_path, index=False)

if __name__ == "__main__":
    main()
