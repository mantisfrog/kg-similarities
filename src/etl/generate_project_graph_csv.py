import pandas as pd
import os
import re
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src.utils.generate_node_rel import generate_node_csv, generate_rel_csv
from src import config

def generate_project_nodes(df: pd.DataFrame, output_dir: Path):
    """
    Generates node_Project.csv for :Project nodes.
    """
    # Create a copy to avoid modifying the original DataFrame
    df_project = df.copy()

    # Generate projectID:ID from ENO column
    df_project['projectID:ID'] = df_project['projectID']
    
    # Copy ENO to eno:int
    df_project['eno:int'] = df_project['ENO']

    # Create Neo4j point string from longitude and latitude
    df_project['location:point'] = df_project.apply(
        lambda row: f"point({{longitude: {row['LONG_GDA94']}, latitude: {row['LAT_GDA94']}}})"
        if row['LONG_GDA94'] != '' and row['LAT_GDA94'] != '' else '',
        axis=1
    )

    # Rename columns to camelCase as specified
    df_project.rename(columns={
        'GEOLOGIC_AGE': 'geologicAge:string',
        'DEPOSIT_MODEL_ENVIRONMENT': 'depositModelEnvironment:string',
        'DEPOSIT_MODEL_GROUP': 'depositModelGroup:string',
        'DEPOSIT_MODEL_TYPE': 'depositModelType:string',
        'IGNEOUS': 'igneous:string',
        'METALLOGENIC': 'metallogenic:string',
        'SEDIMENTARY': 'sedimentary:string',
        'TECTONIC': 'tectonic:string'
    }, inplace=True)

    # Select and order columns for the output CSV
    output_columns = [
        'projectID:ID', 'eno:int', 'location:point', 'geologicAge:string',
        'depositModelEnvironment:string', 'depositModelGroup:string',
        'depositModelType:string', 'igneous:string', 'metallogenic:string',
        'sedimentary:string', 'tectonic:string'
    ]
    df_project = df_project[output_columns]

    # Save to CSV
    output_file = output_dir / "node_Project.csv"
    df_project.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

def generate_project_name_nodes(df: pd.DataFrame, output_dir: Path):
    """
    Generates node_ProjectName.csv for unique :ProjectName nodes.
    Returns a dictionary mapping name text to its generated ID.
    """
    names = set()
    # Collect names from PROJECT_NAME
    for name in df['PROJECT_NAME'].dropna():
        if name.strip():
            names.add(name.strip())
    
    # Collect names from SYNONYMS, splitting by comma
    for synonyms in df['SYNONYMS'].dropna():
        for synonym in synonyms.split(','):
            if synonym.strip():
                names.add(synonym.strip())

    # Create DataFrame for unique names
    df_names = pd.DataFrame(list(names), columns=['text:string'])
    
    return generate_node_csv(
        df_nodes=df_names,
        id_col_name='projectNameID:ID',
        id_prefix='projectName_',
        value_col_for_mapping='text:string',
        output_dir=output_dir,
        filename="node_ProjectName.csv"
    )

def generate_state_nodes(df: pd.DataFrame, output_dir: Path):
    """
    Generates node_State.csv for unique :State nodes.
    Returns a dictionary mapping state text to its generated ID.
    """
    # Get unique, non-empty state values
    states = df['STATE'].dropna().unique()
    states = [s for s in states if s.strip()]
    
    # Create DataFrame for unique states
    df_states = pd.DataFrame(states, columns=['text:string'])

    return generate_node_csv(
        df_nodes=df_states,
        id_col_name='stateID:ID',
        id_prefix='state_',
        value_col_for_mapping='text:string',
        output_dir=output_dir,
        filename="node_State.csv"
    )

def generate_commodity_nodes(df: pd.DataFrame, output_dir: Path):
    """
    Generates node_Commodity.csv for unique :Commodity nodes.
    Returns a dictionary mapping commodity symbol to its generated ID.
    """
    symbols = set()
    symbol_to_name = {}

    # Collect all unique symbols
    for col in ['COMMODITY_PRIMARY', 'COMMODITY_SECONDARY']:
        for items in df[col].dropna():
            for symbol in items.split(','):
                if symbol.strip():
                    symbols.add(symbol.strip())

    # Build the symbol to name mapping
    for _, row in df.iterrows():
        primary_symbols = [s.strip() for s in row['COMMODITY_PRIMARY'].split(',') if s.strip()]
        secondary_symbols = [s.strip() for s in row['COMMODITY_SECONDARY'].split(',') if s.strip()]
        
        names_str = str(row['COMMODITY_NAMES'])
        secondary_names_match = re.search(r'\((.*)\)', names_str)
        
        primary_names_str = re.sub(r'\(.*\)', '', names_str).strip(' ,')
        primary_names = [n.strip() for n in primary_names_str.split(',') if n.strip()]
        
        secondary_names = []
        if secondary_names_match:
            secondary_names = [n.strip() for n in secondary_names_match.group(1).split(',') if n.strip()]

        for symbol, name in zip(primary_symbols, primary_names):
            symbol_to_name[symbol] = name
        for symbol, name in zip(secondary_symbols, secondary_names):
            symbol_to_name[symbol] = name

    # Create DataFrame for commodities
    df_commodities = pd.DataFrame(list(symbols), columns=['symbol:string'])
    
    # Map symbols to names
    df_commodities['name:string'] = df_commodities['symbol:string'].map(symbol_to_name).fillna('')

    return generate_node_csv(
        df_nodes=df_commodities,
        id_col_name='commodityID:ID',
        id_prefix='commodity_',
        value_col_for_mapping='symbol:string',
        output_dir=output_dir,
        filename="node_Commodity.csv"
    )

def generate_refers_to_rels(df: pd.DataFrame, name_to_id: dict, output_dir: Path):
    """
    Generates rel_Refers_to.csv for :ProjectName-[:REFERS_TO_PROJECT]->:Project relationships.
    """
    rels = []
    for _, row in df.iterrows():
        end_id = row['projectID']
        
        # Relationship from PROJECT_NAME
        name = row['PROJECT_NAME'].strip()
        if name and name in name_to_id:
            start_id = name_to_id[name]
            rels.append({'START_ID': start_id, 'END_ID': end_id, 'TYPE': 'REFERS_TO_PROJECT'})
            
        # Relationships from SYNONYMS
        synonyms = row['SYNONYMS'].strip()
        if synonyms:
            for synonym in synonyms.split(','):
                synonym = synonym.strip()
                if synonym and synonym in name_to_id:
                    start_id = name_to_id[synonym]
                    rels.append({'START_ID': start_id, 'END_ID': end_id, 'TYPE': 'REFERS_TO_PROJECT'})

    generate_rel_csv(rels, output_dir, "rel_Refers_to.csv")

def generate_located_in_rels(df: pd.DataFrame, state_to_id: dict, output_dir: Path):
    """
    Generates rel_Located_in.csv for :Project-[:LOCATED_IN]->:State relationships.
    """
    rels = []
    for _, row in df.iterrows():
        state = row['STATE'].strip()
        if state and state in state_to_id:
            start_id = row['projectID']
            end_id = state_to_id[state]
            rels.append({'START_ID': start_id, 'END_ID': end_id, 'TYPE': 'LOCATED_IN'})

    generate_rel_csv(rels, output_dir, "rel_Located_in.csv")

def generate_has_commodity_rels(df: pd.DataFrame, symbol_to_id: dict, output_dir: Path):
    """
    Generates rel_Has_Commodity.csv for :Project-[:HAS_COMMODITY]->:Commodity relationships.
    """
    rels = []
    for _, row in df.iterrows():
        start_id = row['projectID']
        
        # Primary commodities
        primary_commodities = row['COMMODITY_PRIMARY'].strip()
        if primary_commodities:
            for symbol in primary_commodities.split(','):
                symbol = symbol.strip()
                if symbol and symbol in symbol_to_id:
                    end_id = symbol_to_id[symbol]
                    rels.append({
                        'START_ID': start_id, 'END_ID': end_id, 
                        'TYPE': 'HAS_COMMODITY', 'role:string': 'Primary'
                    })

        # Secondary commodities
        secondary_commodities = row['COMMODITY_SECONDARY'].strip()
        if secondary_commodities:
            for symbol in secondary_commodities.split(','):
                symbol = symbol.strip()
                if symbol and symbol in symbol_to_id:
                    end_id = symbol_to_id[symbol]
                    rels.append({
                        'START_ID': start_id, 'END_ID': end_id, 
                        'TYPE': 'HAS_COMMODITY', 'role:string': 'Secondary'
                    })

    generate_rel_csv(rels, output_dir, "rel_Has_Commodity.csv")

def main():
    """
    Main function to orchestrate the generation of all project-related nodes and relationships.
    """
    # Load the master project data
    df = pd.read_csv(config.MASTER_PROJECT_CSV, dtype=str).fillna('')
    
    # Define the output directory for all graph CSVs
    output_dir = config.GRAPH_DIR
    # Ensure the directory exists using the helper function.
    # We can use any file path that will be inside the graph directory.
    config.ensure_parent(config.NODE_COMMODITY_CSV)
    
    print(f"Generating graph CSVs in: {output_dir}")
    
    # Generate a unique projectID for each unique ENO
    df.sort_values('ENO', inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['projectID'] = 'project_' + (df.index + 1).astype(str)

    # --- Generate Node Files ---
    generate_project_nodes(df, output_dir)
    name_to_id = generate_project_name_nodes(df, output_dir)
    state_to_id = generate_state_nodes(df, output_dir)
    symbol_to_id = generate_commodity_nodes(df, output_dir)

    # --- Generate Relationship Files ---
    generate_refers_to_rels(df, name_to_id, output_dir)
    generate_located_in_rels(df, state_to_id, output_dir)
    generate_has_commodity_rels(df, symbol_to_id, output_dir)

    print("\nETL process completed successfully.")

if __name__ == "__main__":
    main()