import pandas as pd
import os
import re
from pathlib import Path

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
    df_names.sort_values('text:string', inplace=True)
    df_names.reset_index(drop=True, inplace=True)

    # Generate unique IDs
    df_names['projectNameID:ID'] = 'projectName_' + (df_names.index + 1).astype(str)
    
    # Reorder columns and save
    df_names = df_names[['projectNameID:ID', 'text:string']]
    output_file = output_dir / "node_ProjectName.csv"
    df_names.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

    # Create and return a mapping from name text to ID for relationship generation
    name_to_id = pd.Series(df_names['projectNameID:ID'].values, index=df_names['text:string']).to_dict()
    return name_to_id

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
    df_states.sort_values('text:string', inplace=True)
    df_states.reset_index(drop=True, inplace=True)

    # Generate unique IDs
    df_states['stateID:ID'] = 'state_' + (df_states.index + 1).astype(str)

    # Reorder columns and save
    df_states = df_states[['stateID:ID', 'text:string']]
    output_file = output_dir / "node_State.csv"
    df_states.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

    # Create and return a mapping from state text to ID
    state_to_id = pd.Series(df_states['stateID:ID'].values, index=df_states['text:string']).to_dict()
    return state_to_id

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
    df_commodities.sort_values('symbol:string', inplace=True)
    df_commodities.reset_index(drop=True, inplace=True)
    
    # Map symbols to names and generate IDs
    df_commodities['name:string'] = df_commodities['symbol:string'].map(symbol_to_name).fillna('')
    df_commodities['commodityID:ID'] = 'commodity_' + (df_commodities.index + 1).astype(str)

    # Reorder columns and save
    df_commodities = df_commodities[['commodityID:ID', 'symbol:string', 'name:string']]
    output_file = output_dir / "node_Commodity.csv"
    df_commodities.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

    # Create and return a mapping from symbol to ID
    symbol_to_id = pd.Series(df_commodities['commodityID:ID'].values, index=df_commodities['symbol:string']).to_dict()
    return symbol_to_id

def generate_company_nodes(df: pd.DataFrame, output_dir: Path):
    """
    Generates node_Company.csv for unique :Company nodes.
    Returns a dictionary mapping company name to its generated ID.
    """
    companies = set()
    # Collect companies from COMPANIES column, splitting by comma
    for items in df['COMPANIES'].dropna():
        for company in items.split(','):
            if company.strip():
                companies.add(company.strip())

    # Create DataFrame for unique companies
    df_companies = pd.DataFrame(list(companies), columns=['name:string'])
    df_companies.sort_values('name:string', inplace=True)
    df_companies.reset_index(drop=True, inplace=True)

    # Generate unique IDs
    df_companies['companyID:ID'] = 'company_' + (df_companies.index + 1).astype(str)
    
    # Reorder columns and save
    df_companies = df_companies[['companyID:ID', 'name:string']]
    output_file = output_dir / "node_Company.csv"
    df_companies.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

    # Create and return a mapping from name to ID for relationship generation
    company_to_id = pd.Series(df_companies['companyID:ID'].values, index=df_companies['name:string']).to_dict()
    return company_to_id

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

    df_rels = pd.DataFrame(rels)
    df_rels.rename(columns={'START_ID': ':START_ID', 'END_ID': ':END_ID', 'TYPE': ':TYPE'}, inplace=True)
    output_file = output_dir / "rel_Refers_to.csv"
    df_rels.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

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

    df_rels = pd.DataFrame(rels)
    df_rels.rename(columns={'START_ID': ':START_ID', 'END_ID': ':END_ID', 'TYPE': ':TYPE'}, inplace=True)
    output_file = output_dir / "rel_Located_in.csv"
    df_rels.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

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

    df_rels = pd.DataFrame(rels)
    df_rels.rename(columns={
        'START_ID': ':START_ID', 'END_ID': ':END_ID', 
        'TYPE': ':TYPE'}, inplace=True)
    output_file = output_dir / "rel_Has_Commodity.csv"
    df_rels.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

def generate_owns_rels(df: pd.DataFrame, company_to_id: dict, output_dir: Path):
    """
    Generates rel_Owns.csv for :Company-[:OWNS]->:Project relationships.
    """
    rels = []
    for _, row in df.iterrows():
        end_id = row['projectID']
        
        companies_str = row['COMPANIES'].strip()
        if companies_str:
            for company_name in companies_str.split(','):
                company_name = company_name.strip()
                if company_name and company_name in company_to_id:
                    start_id = company_to_id[company_name]
                    rels.append({'START_ID': start_id, 'END_ID': end_id, 'TYPE': 'OWNS'})

    df_rels = pd.DataFrame(rels)
    df_rels.rename(columns={'START_ID': ':START_ID', 'END_ID': ':END_ID', 'TYPE': ':TYPE'}, inplace=True)
    output_file = output_dir / "rel_Owns.csv"
    df_rels.to_csv(output_file, index=False)
    print(f"Generated {output_file}")

def main():
    """
    Main function to orchestrate the ETL process.
    """
    # Define project paths relative to the script location
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    source_file = project_root / "data/master/ProjectData_Master.csv"
    output_dir = project_root / "data/graph"

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Load the source data
    print(f"Reading source file: {source_file}")
    try:
        df = pd.read_csv(source_file)
    except FileNotFoundError:
        print(f"Error: Source file not found at {source_file}")
        return

    # Global rule: Handle null values by converting to empty strings
    df = df.fillna('')

    # Sort by ENO for deterministic IDs and generate projectID
    df.sort_values('ENO', inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['projectID'] = 'project_' + (df.index + 1).astype(str)

    # --- Generate Node Files ---
    generate_project_nodes(df, output_dir)
    name_to_id = generate_project_name_nodes(df, output_dir)
    state_to_id = generate_state_nodes(df, output_dir)
    symbol_to_id = generate_commodity_nodes(df, output_dir)
    company_to_id = generate_company_nodes(df, output_dir)

    # --- Generate Relationship Files ---
    generate_refers_to_rels(df, name_to_id, output_dir)
    generate_located_in_rels(df, state_to_id, output_dir)
    generate_has_commodity_rels(df, symbol_to_id, output_dir)
    generate_owns_rels(df, company_to_id, output_dir)

    print("\nETL process completed successfully.")

if __name__ == "__main__":
    main()