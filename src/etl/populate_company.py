import pandas as pd
from pathlib import Path
import pycountry

def convert_shorthand_to_numeric(value):
    """Converts a string with K, M, B suffix to a numeric value."""
    if not isinstance(value, str):
        return pd.to_numeric(value, errors='coerce')
    value = value.strip()
    if not value:
        return pd.NA
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
        return pd.NA  # Return Not Available for invalid or missing codes
    try:
        country = pycountry.countries.get(alpha_2=code.strip().upper())
        return country.name if country else pd.NA
    except (AttributeError, KeyError):
        return pd.NA # Handle any lookup errors gracefully

def main():
    project_root = Path(__file__).resolve().parents[2]
    base_path = project_root / 'data' / 'raw' / 'company' / 'bloomberg'
    dirs_to_process = [base_path / 'ICB', base_path / 'BICS']

    df_list = []
    seen_ids = set()
    first_col_name = None

    for directory in dirs_to_process:
        for csv_file in sorted(directory.glob('*.csv')):
            temp_df = pd.read_csv(csv_file, dtype=str)
            if temp_df.empty:
                continue
            if first_col_name is None:
                first_col_name = temp_df.columns[0]
            temp_df = temp_df[~temp_df[first_col_name].isin(seen_ids)]
            if temp_df.empty:
                continue
            seen_ids.update(temp_df[first_col_name])
            df_list.append(temp_df)

    if not df_list:
        return

    combined_df = pd.concat(df_list, ignore_index=True)

    # Convert 2-letter ISO country code in the 3rd column to full country name.
    if len(combined_df.columns) >= 3:
        country_col_name = combined_df.columns[2]
        combined_df[country_col_name] = combined_df[country_col_name].apply(iso_to_country_name)

    if len(combined_df.columns) >= 8:
        for col in combined_df.columns[4:8]:
            combined_df[col] = combined_df[col].apply(convert_shorthand_to_numeric)

    combined_df = combined_df.replace(r'^\s*$', pd.NA, regex=True)
    combined_df.replace(['0', 0, '--'], pd.NA, inplace=True)

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
            # Get the name of the first column from both dataframes to use as join keys
            left_key = combined_df.columns[0]
            right_key = des_df.columns[0]

            # Drop columns from des_df that already exist in combined_df, except for the key
            cols_to_drop = [col for col in des_df.columns if col in combined_df.columns and col != right_key]
            des_df.drop(columns=cols_to_drop, inplace=True)
            
            # Perform the left join
            combined_df = pd.merge(combined_df, des_df, left_on=left_key, right_on=right_key, how='left')

            # If the key from the right table was different and added, drop it
            if left_key != right_key and right_key in combined_df.columns:
                combined_df.drop(columns=[right_key], inplace=True)
        else:
            print(f"Warning: One of the dataframes for joining is empty. Skipping join.")
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


    output_path = project_root / 'data' / 'processed' / 'Bloomberg_Companies.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(output_path, index=False)

if __name__ == "__main__":
    main()
