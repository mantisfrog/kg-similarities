import pandas as pd
from pathlib import Path
import sys

# --- Start of Modification ---

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src import config

# Define file paths for the source and destination files.
categorization_file = config.CATEGORIZATION_CSV
node_commodity_file = config.NODE_COMMODITY_CSV
# The result will overwrite the original node file.
output_file = config.NODE_COMMODITY_CSV

# Ensure the directory for the output file exists.
config.ensure_parent(output_file)

# --- End of Modification ---


# Read the source data.
# Load the commodity-to-group mappings.
categorization_df = pd.read_csv(categorization_file, usecols=['Commodity', 'Group'])
# Load the commodity node file that will be enriched.
node_commodity_df = pd.read_csv(node_commodity_file, sep=',')

# Merge the group information into the commodity node data.
# A left join ensures all original commodities are kept, even if they have no group.
merged_df = pd.merge(
    node_commodity_df,
    categorization_df,
    left_on='symbol:string',
    right_on='Commodity',
    how='left'
)

# Clean and reorder the data columns.
# Drop the redundant 'Commodity' column that came from the categorization file.
merged_df = merged_df.drop(columns=['Commodity'])
# Rename the 'Group' column to match the desired schema.
merged_df = merged_df.rename(columns={'Group': 'commodityGroup:string'})

# Reorder columns to place the new group column after the symbol column.
cols = list(merged_df.columns)

# Check if the new column exists before trying to move it.
if 'commodityGroup:string' in cols:
    # Remove the new column from its current position (at the end).
    group_col = cols.pop(cols.index('commodityGroup:string'))
    
    try:
        # Find the index of the column to insert after.
        symbol_index = cols.index('symbol:string')
        # Insert the new column immediately after the symbol column.
        cols.insert(symbol_index + 2, group_col)
    except ValueError:
        # As a fallback, if the symbol column doesn't exist, append it to the end.
        cols.append(group_col)
    
    # Apply the new column order to the DataFrame.
    final_df = merged_df[cols]
else:
    final_df = merged_df

# Save the enriched DataFrame back to the CSV file.
# This overwrites the original file without the DataFrame index.
final_df.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"Processing complete. Output saved to: {output_file}")