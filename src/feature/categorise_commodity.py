import pandas as pd
from pathlib import Path
import sys

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src import config
from src.utils.generate_node_rel import generate_rel_csv

# Define file paths for the source and destination files.
categorization_file = config.CATEGORIZATION_CSV
commodity_node_file = config.NODE_COMMODITY_CSV  # Input commodity nodes
output_node_file = config.NODE_COMMODITY_GROUP_CSV
output_rel_file = config.REL_COMMODITY_GROUP_CSV

# Ensure the directory for the output files exists.
config.ensure_parent(output_node_file)
config.ensure_parent(output_rel_file)

# Load the commodity-to-group mappings.
try:
    categorization_df = pd.read_csv(categorization_file, usecols=['Commodity', 'Group'])
    # Drop any rows where either Commodity or Group is missing, as they are essential.
    categorization_df.dropna(subset=['Commodity', 'Group'], inplace=True)
except FileNotFoundError:
    print(f"Error: Categorization file not found at {categorization_file}", file=sys.stderr)
    sys.exit(1)
except KeyError:
    print(f"Error: 'Commodity' or 'Group' column not found in {categorization_file}", file=sys.stderr)
    sys.exit(1)

# Load the existing commodity nodes to get their IDs.
try:
    commodity_nodes_df = pd.read_csv(commodity_node_file, usecols=['commodityID:ID', 'symbol:string'])
except FileNotFoundError:
    print(f"Error: Commodity node file not found at {commodity_node_file}", file=sys.stderr)
    sys.exit(1)
except KeyError:
    print(f"Error: Required columns not found in {commodity_node_file}", file=sys.stderr)
    sys.exit(1)


# --- 1. Create CommodityGroup node file ---
print("Generating CommodityGroup node file...")
# Get unique group names from the 'Group' column to create distinct nodes.
unique_groups = categorization_df['Group'].unique()

# Create a DataFrame for the new nodes.
# The ID for the node is the group name itself, ensuring uniqueness.
commodity_group_nodes = pd.DataFrame({
    'commodityGroupID:ID': unique_groups,
    'name:string': unique_groups,
    ':LABEL': 'CommodityGroup'
})

# Save the new node file.
commodity_group_nodes.to_csv(output_node_file, index=False, encoding='utf-8-sig')
print(f"-> Successfully created CommodityGroup node file: {output_node_file}")


# --- 2. Create relationship file ---
print("\nGenerating Commodity-to-Group relationship file...")
# Merge categorization data with commodity node data to get the correct START_ID.
# The 'Commodity' column in categorization.csv should match the 'symbol:string' in node_Commodity.csv.
merged_df = pd.merge(
    categorization_df,
    commodity_nodes_df,
    left_on='Commodity',
    right_on='symbol:string',
    how='inner'
)

# Check for commodities in categorization file that are not in the node file.
if len(merged_df) < len(categorization_df):
    unmapped_commodities = set(categorization_df['Commodity']) - set(merged_df['Commodity'])
    print(f"Warning: The following commodities from {categorization_file.name} were not found in {commodity_node_file.name} and will be skipped:")
    for commodity in sorted(list(unmapped_commodities)):
        print(f"  - {commodity}")

# Create the relationship list using the correct IDs and standard column names.
relationships = merged_df.rename(columns={
    'commodityID:ID': 'START_ID',
    'Group': 'END_ID'
})[['START_ID', 'END_ID']].to_dict('records')

# Save the relationship file using the standard utility.
generate_rel_csv(relationships, Path(output_rel_file).parent, Path(output_rel_file).name)

print("\nProcessing complete.")