import pandas as pd
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src import config
from src.utils.generate_node_rel import generate_node_csv, generate_rel_csv

def create_category_nodes_and_rels(df: pd.DataFrame, column_name: str, node_label: str, id_prefix: str):
    """
    Generates node and relationship CSV files for a single category column in company grouping data.
    This function creates (Company)-[:CATEGORISED_AS]->(CategoryNode) relationships.

    Args:
        df (pd.DataFrame): DataFrame containing company grouping data.
        column_name (str): The column name to process (e.g., 'Tier_MarketCap').
        node_label (str): The label for the new node in the graph (e.g., 'TierMarketCap').
        id_prefix (str): Short prefix for generating unique IDs for new nodes (e.g., 'tmc_').
    """
    print(f"\nGenerating nodes and relationships for '{column_name}'...")

    # 1. Prepare DataFrame: Select relevant columns and drop rows missing this category value.
    df_category = df[["companyID", column_name]].dropna(subset=[column_name]).copy()
    df_category[column_name] = df_category[column_name].astype(str).str.strip()

    if df_category.empty:
        print(f"No data found for '{column_name}'. Skipping.")
        return

    # 2. Create nodes for each unique category value.
    unique_values_df = pd.DataFrame(df_category[column_name].unique(), columns=['text:string'])
    value_to_id_map = generate_node_csv(
        df_nodes=unique_values_df,
        id_col_name=f'{node_label.lower()}ID:ID',
        id_prefix=id_prefix,
        value_col_for_mapping='text:string',
        output_dir=config.GRAPH_DIR,
        filename=f"node_{node_label}.csv"
    )

    # 3. Create relationships between Company nodes and new category nodes.
    relationships = []
    for _, row in df_category.iterrows():
        company_id = row['companyID']
        category_value = row[column_name]
        
        # Ensure the category value exists in our mapping before creating relationships
        if category_value in value_to_id_map:
            relationships.append({
                ':START_ID': company_id,
                ':END_ID': value_to_id_map[category_value]
            })

    # 4. Save relationships to CSV file.
    # The relationship type in the graph will be :CATEGORISED_AS, handled by the Cypher script.
    generate_rel_csv(
        relationships, 
        config.GRAPH_DIR, 
        f"rel_CategorisedAs_{node_label}.csv"
    )

def create_country_to_country_group_rels():
    """
    Specifically handles relationships between Country and CountryGroup.
    It loads master company data to get country information and connects it with grouping data,
    thereby creating (Country)-[:PART_OF]->(CountryGroup) relationships.
    """
    print("\nGenerating nodes and relationships for 'Country' and 'CountryGroup'...")

    try:
        # 1. Load required data
        source_file = config.DATA_DIR / "raw" / "company" / "company_group.csv"
        company_groups_df = pd.read_csv(source_file, usecols=["companyID", "CountryGroup"])
        
        master_company_df = pd.read_csv(config.MASTER_COMPANY_CSV, usecols=["companyID", "Country of Domicile"])
        
        # Load generated country nodes to get mapping from country name to ID
        country_nodes_df = pd.read_csv(config.GRAPH_DIR / "node_Country.csv")
        country_name_to_id = pd.Series(country_nodes_df['countryID:ID'].values, index=country_nodes_df['text:string']).to_dict()

    except FileNotFoundError as e:
        print(f"Error: Required file not found: {e.filename}. Please ensure 'generate_company_graph_csv.py' has been run.", file=sys.stderr)
        return

    # 2. Merge data to establish Country -> CountryGroup mapping
    df_merged = pd.merge(company_groups_df, master_company_df, on="companyID")
    df_country_to_group = df_merged[["Country of Domicile", "CountryGroup"]].dropna().drop_duplicates()

    if df_country_to_group.empty:
        print("No data found for 'CountryGroup' or unable to map to countries. Skipping.")
        return

    # 3. Generate CountryGroup nodes
    unique_groups_df = pd.DataFrame(df_country_to_group["CountryGroup"].unique(), columns=['text:string'])
    group_to_id_map = generate_node_csv(
        df_nodes=unique_groups_df,
        id_col_name='countrygroupID:ID',
        id_prefix='cg_',
        value_col_for_mapping='text:string',
        output_dir=config.GRAPH_DIR,
        filename="node_CountryGroup.csv"
    )

    # 4. Create (Country)-[:PART_OF]->(CountryGroup) relationships
    relationships = []
    for _, row in df_country_to_group.iterrows():
        country_name = row["Country of Domicile"]
        group_name = row["CountryGroup"]

        if country_name in country_name_to_id and group_name in group_to_id_map:
            relationships.append({
                ':START_ID': country_name_to_id[country_name],
                ':END_ID': group_to_id_map[group_name]
            })

    # 5. Save relationship file
    generate_rel_csv(
        relationships,
        config.GRAPH_DIR,
        "rel_Country_PartOf_CountryGroup.csv"
    )

def main():
    """
    Main function to read company grouping data and generate all required node and relationship files for graph import.
    """
    print("Starting company categorization process...")
    
    # Ensure output directory exists
    config.GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    # Load source CSV file
    try:
        source_file = config.DATA_DIR / "raw" / "company" / "company_group.csv"
        company_groups_df = pd.read_csv(source_file)
        print(f"Data loaded from {source_file}")
    except FileNotFoundError:
        print(f"Error: Source file not found at {source_file}", file=sys.stderr)
        sys.exit(1)

    # Define categories to process from CSV.
    # Format: { 'column_name_in_csv': ('node_label_in_graph', 'id_prefix_for_nodes') }
    # CountryGroup has been removed and will be handled separately
    categories = {
        'Tier_MarketCap': ('TierMarketCap', 'tmc_'),
        'Tier_Revenue': ('TierRevenue', 'trv_'),
        'Tier_Assets': ('TierAssets', 'tas_'),
        'Group_AssetTurnover': ('GroupAssetTurnover', 'gat_'),
        'Group_MarketToAsset': ('GroupMarketToAsset', 'gma_'),
    }

    # Process each defined category
    for column, (label, prefix) in categories.items():
        if column in company_groups_df.columns:
            create_category_nodes_and_rels(company_groups_df, column, label, prefix)
        else:
            print(f"Warning: Column '{column}' not found in CSV. Skipping.")

    # Handle CountryGroup separately to create Country -> CountryGroup relationships
    create_country_to_country_group_rels()

    print("\nSuccessfully generated all node and relationship files for company categories.")

if __name__ == "__main__":
    main()