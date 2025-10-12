import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

def generate_node_csv(
    df_nodes: pd.DataFrame, 
    id_col_name: str, 
    id_prefix: str, 
    value_col_for_mapping: str, 
    output_dir: Path, 
    filename: str
) -> Dict[str, str]:
    """
    Generates a node CSV file from a DataFrame of unique values.
    - Sorts the DataFrame by the value column used for mapping.
    - Generates unique IDs based on the sorted order.
    - Saves the DataFrame to a CSV file.
    - Returns a dictionary mapping the value to its generated ID.
    """
    # Sort by the primary value column to ensure deterministic ID generation
    df_nodes.sort_values(value_col_for_mapping, inplace=True)
    df_nodes.reset_index(drop=True, inplace=True)

    # Generate unique IDs
    df_nodes[id_col_name] = id_prefix + (df_nodes.index + 1).astype(str)
    
    # Ensure ID column is first, preserving order of other columns
    cols = [id_col_name] + [col for col in df_nodes.columns if col != id_col_name]
    df_nodes = df_nodes[cols]

    # Save to CSV
    output_file = output_dir / filename
    df_nodes.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

    # Create and return a mapping from the specified value column to ID
    value_to_id = pd.Series(
        df_nodes[id_col_name].values, 
        index=df_nodes[value_col_for_mapping]
    ).to_dict()
    return value_to_id

def generate_rel_csv(rels: List[Dict[str, Any]], output_dir: Path, filename: str):
    """
    Generates a relationship CSV file from a list of relationship dictionaries.
    """
    if not rels:
        print(f"No relationships to generate for {filename}. Skipping.")
        return

    df_rels = pd.DataFrame(rels)
    
    # Rename columns for Neo4j admin import
    rename_map = {'START_ID': ':START_ID', 'END_ID': ':END_ID', 'TYPE': ':TYPE'}
    df_rels.rename(columns=rename_map, inplace=True)
    
    # Save to CSV
    output_file = output_dir / filename
    df_rels.to_csv(output_file, index=False)
    print(f"Generated {output_file}")