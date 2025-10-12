import pandas as pd
from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src.utils.generate_node_rel import generate_node_csv, generate_rel_csv
from src import config

def categorize_reserves(value, q1, q2, q3):
    """Categorizes a value into one of four tiers based on quartiles."""
    if pd.isna(value):
        return None
    if value <= q1:
        return "Tier 4 (Lowest)"
    elif value <= q2:
        return "Tier 3"
    elif value <= q3:
        return "Tier 2"
    else:
        return "Tier 1 (Highest)"

def main():
    """
    Generates ReservesScale nodes and relationships to Project nodes based on ore scale.
    """
    # Define input and output paths
    reserves_summary_csv = config.DEPOSIT_DIR / "ENO_scale_summary.csv"
    node_project_csv = config.NODE_PROJECT_CSV
    output_dir = config.GRAPH_DIR

    # Ensure output directory exists
    config.ensure_parent(output_dir / "dummy.txt")

    print("Loading data...")
    # Load reserves data
    df_reserves = pd.read_csv(reserves_summary_csv)
    # Load project node data to map eno to projectID
    df_project = pd.read_csv(node_project_csv)

    # --- Prepare Data ---
    # Convert eno to a common type for merging
    df_reserves['eno'] = pd.to_numeric(df_reserves['eno'], errors='coerce')
    df_project['eno:int'] = pd.to_numeric(df_project['eno:int'], errors='coerce')

    # Clean and convert ore_scale_t_max to numeric
    df_reserves['ore_scale_t_max'] = pd.to_numeric(df_reserves['ore_scale_t_max'], errors='coerce')
    df_reserves.dropna(subset=['ore_scale_t_max', 'eno'], inplace=True)

    # --- Calculate Quartiles and Categorize ---
    print("Categorizing reserves scale...")
    q1 = df_reserves['ore_scale_t_max'].quantile(0.25)
    q2 = df_reserves['ore_scale_t_max'].quantile(0.50)
    q3 = df_reserves['ore_scale_t_max'].quantile(0.75)

    print(f"Quartiles for ore_scale_t_max: Q1={q1}, Q2={q2}, Q3={q3}")

    df_reserves['tier'] = df_reserves['ore_scale_t_max'].apply(categorize_reserves, args=(q1, q2, q3))

    # --- Generate ReservesScale Nodes ---
    print("Generating ReservesScale nodes...")
    unique_tiers = sorted(df_reserves['tier'].dropna().unique())
    df_tiers = pd.DataFrame(unique_tiers, columns=['text:string'])
    
    tier_to_id = generate_node_csv(
        df_nodes=df_tiers,
        id_col_name='reservesScaleID:ID',
        id_prefix='reservesScale_',
        value_col_for_mapping='text:string',
        output_dir=output_dir,
        filename="node_ReservesScale.csv"
    )

    # --- Generate Relationships ---
    print("Generating Project-[:CATEGORISED_AS]->ReservesScale relationships...")
    # Merge reserves data with project data to get projectID
    df_merged = pd.merge(
        df_reserves,
        df_project[['projectID:ID', 'eno:int']],
        left_on='eno',
        right_on='eno:int',
        how='inner'
    )

    rels = []
    for _, row in df_merged.iterrows():
        tier_label = row['tier']
        if pd.notna(tier_label) and tier_label in tier_to_id:
            start_id = row['projectID:ID']
            end_id = tier_to_id[tier_label]
            rels.append({':START_ID': start_id, ':END_ID': end_id})

    generate_rel_csv(rels, output_dir, "rel_Project_Categorised_as_ReservesScale.csv")

    print("\nReserves scale categorization process completed successfully.")

if __name__ == "__main__":
    main()