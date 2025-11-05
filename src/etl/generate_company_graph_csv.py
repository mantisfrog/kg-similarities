import pandas as pd
import sys
from pathlib import Path
from tqdm import tqdm

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src import config
# --- IMPORTS for advanced matching (NO LONGER NEEDED HERE) ---
# from src.utils.normalize_names import normalize_name
# from src.utils.build_word_index import build_word_index
# from src.utils.select_candidates import select_best_candidate
# from src.utils.calculate_similarities import calculate_text_similarities
# from src.utils.match_rules import get_match_status
# from src.utils.load_spacy import load_spacy_model
# --- Import utility functions ---
from src.utils.generate_node_rel import generate_node_csv, generate_rel_csv


def create_company_nodes(df: pd.DataFrame):
    """
    Generates the node_Company.csv file from the master company data.
    This function is specific and does not use the generic node generator.
    """
    print("Generating Company node CSV...")
    
    # Define columns and their types for the node file
    node_cols = {
        "companyID": "companyID:ID",
        "Company Name": "name:string",
        "Ticker": "Ticker:string",
        "ACN": "ACN:int",
        "Market Cap": "Market Cap:float",
        "Revenue:Y": "Revenue:Y:float",
        "Tot Assets:Y": "Tot Assets:Y:float",
        "Number of Employees:LF": "Number of Employees:LF:int",
        "Company Description": "Company Description:string",
        "Linkedin_empCount": "Linkedin_empCount:int",
        "Linkedin_Followers": "Linkedin_Followers:int",
    }

    int_cols = ["ACN", "Number of Employees:LF", "Linkedin_empCount", "Linkedin_Followers"]
    float_cols = ["Market Cap", "Revenue:Y", "Tot Assets:Y"]

    node_df = df[list(node_cols.keys())].copy()

    # Coerce types, handling errors by turning them into NaNs
    for col in int_cols:
        node_df[col] = pd.to_numeric(node_df[col], errors='coerce').astype('Int64')
    
    for col in float_cols:
        node_df[col] = pd.to_numeric(node_df[col], errors='coerce')

    node_df.rename(columns=node_cols, inplace=True)

    output_path = config.ensure_parent(config.GRAPH_DIR / "node_Company.csv")
    node_df.to_csv(output_path, index=False, na_rep="")
    print(f"Successfully created {output_path}")


def create_owns_project_relationships():
    """
    Generates the rel_Owns.csv file by reading the pre-computed
    matches from the project-company match file.
    """
    print("\nGenerating OWNS relationship CSV from pre-computed matches...")
    
    try:
        # 1. Read the intermediate match file
        matches_df = pd.read_csv(config.PROJECT_COMPANY_MATCHES_CSV)

        if matches_df.empty:
            print("Match file is empty. No relationships to generate.")
            return

        # 2. Rename columns to the required format for generate_rel_csv
        matches_df.rename(columns={
            'companyID': 'START_ID',
            'projectID': 'END_ID'
        }, inplace=True)

        # 3. Generate the final relationship CSV
        generate_rel_csv(matches_df.to_dict('records'), config.GRAPH_DIR, "rel_Owns.csv")

    except FileNotFoundError:
        print(f"Error: Match file not found at {config.PROJECT_COMPANY_MATCHES_CSV}", file=sys.stderr)


def create_company_name_nodes_and_rels(df: pd.DataFrame):
    """
    Creates nodes for each unique company name (official and synonym) and
    the relationships linking them back to the main Company node.
    """
    print("\nGenerating CompanyName nodes and REFERS_TO_COMPANY relationships...")
    companies_df = df[["companyID", "Company Name", "SYNONYMS"]].copy()

    # 1. Collect all unique names
    unique_names = set()
    for _, row in companies_df.iterrows():
        if pd.notna(row["Company Name"]):
            unique_names.add(str(row["Company Name"]).strip())
        if pd.notna(row["SYNONYMS"]):
            synonyms = [s.strip() for s in str(row["SYNONYMS"]).split(',') if s.strip()]
            unique_names.update(synonyms)

    # 2. Generate CompanyName nodes and get the name-to-ID mapping
    df_names = pd.DataFrame(list(unique_names), columns=['text:string'])
    name_to_id = generate_node_csv(
        df_nodes=df_names,
        id_col_name='companyNameID:ID',
        id_prefix='compname_',
        value_col_for_mapping='text:string',
        output_dir=config.GRAPH_DIR,
        filename="node_CompanyName.csv"
    )

    # 3. Generate relationships
    relationships = []
    for _, row in tqdm(companies_df.iterrows(), total=len(companies_df), desc="Generating name relationships", file=sys.stdout):
        company_id = row["companyID"]

        # Process the official "Company Name"
        if pd.notna(row["Company Name"]):
            name = str(row["Company Name"]).strip()
            if name in name_to_id:
                relationships.append({
                    'START_ID': name_to_id[name],
                    'END_ID': company_id,
                    'type:string': 'Current Name'
                })

        # Process the "SYNONYMS"
        if pd.notna(row["SYNONYMS"]):
            synonyms = [s.strip() for s in str(row["SYNONYMS"]).split(',') if s.strip()]
            for syn in synonyms:
                if syn in name_to_id:
                    relationships.append({
                        'START_ID': name_to_id[syn],
                        'END_ID': company_id,
                        'type:string': 'Synonym'
                    })
    
    # 4. Save relationships to CSV
    generate_rel_csv(relationships, config.GRAPH_DIR, "rel_Refers_to_Company.csv")


def create_country_nodes_and_rels(df: pd.DataFrame):
    """
    Generates Country nodes from the 'Country of Domicile' column and creates
    (Company)-[:DOMICILED_IN]->(Country) relationships.
    """
    print("\nGenerating Country nodes and DOMICILED_IN relationships...")
    df_country = df[["companyID", "Country of Domicile"]].dropna(subset=["Country of Domicile"]).copy()
    df_country["Country of Domicile"] = df_country["Country of Domicile"].str.strip()

    # 1. Generate Country nodes
    unique_countries = pd.DataFrame(df_country["Country of Domicile"].unique(), columns=['text:string'])
    country_to_id = generate_node_csv(
        df_nodes=unique_countries,
        id_col_name='countryID:ID',
        id_prefix='country_',
        value_col_for_mapping='text:string',
        output_dir=config.GRAPH_DIR,
        filename="node_Country.csv"
    )

    # 2. Generate relationships
    rels = []
    for _, row in df_country.iterrows():
        country_name = row["Country of Domicile"]
        if country_name in country_to_id:
            rels.append({
                'START_ID': row['companyID'],
                'END_ID': country_to_id[country_name]
            })
    
    generate_rel_csv(rels, config.GRAPH_DIR, "rel_Domiciled_in.csv")


def create_classification_nodes_and_rels(df: pd.DataFrame):
    """
    Generates nodes and relationships for industry classifications.
    - All classification nodes (e.g., ICBSector, GICSIndustry) are created.
    - Hierarchical relationships between classifications are created (e.g., Subsector-PART_OF->Sector).
    - Companies are linked ONLY to the most specific (finest-grain) classification they belong to in each system.
    """
    print("\nGenerating industry classification nodes and relationships...")
    
    classifications = [
        # System, Column Name,           Label,             ID Prefix,   Parent Column
        ('ICB',  'ICB Sector',          'ICBSector',       'icb_sec_',  None),
        ('ICB',  'ICB Subsector',       'ICBSubsector',    'icb_sub_',  'ICB Sector'),
        ('GICS', 'GICS Industry',       'GICSIndustry',    'gics_ind_', None),
        ('GICS', 'GICS SubIndustry',    'GICSSubIndustry', 'gics_sub_', 'GICS Industry'),
        ('BICS', 'BICS L3 Industry',    'BICSL3',          'bics_l3_',  None),
        ('BICS', 'BICS L4 Sub Industry','BICSL4',          'bics_l4_',  'BICS L3 Industry'),
        ('BICS', 'BICS L5 Segment',     'BICSL5',          'bics_l5_',  'BICS L4 Sub Industry'),
        ('BICS', 'BICS L6 Segment',     'BICSL6',          'bics_l6_',  'BICS L5 Segment'),
    ]
    col_to_label = {c[1]: c[2] for c in classifications}
    
    # --- 1. Generate all classification nodes and build mappings ---
    print("Generating all classification nodes...")
    all_mappings = {}
    for _, col, label, prefix, _ in classifications:
        df_filtered = df.dropna(subset=[col]).copy()
        df_filtered[col] = df_filtered[col].astype(str).str.strip()
        unique_values = pd.DataFrame(df_filtered[col].unique(), columns=['text:string'])
        
        value_to_id = generate_node_csv(
            df_nodes=unique_values,
            id_col_name=f'{label.lower()}ID:ID',
            id_prefix=prefix,
            value_col_for_mapping='text:string',
            output_dir=config.GRAPH_DIR,
            filename=f"node_{label}.csv"
        )
        all_mappings[col] = value_to_id

    # --- 2. Generate hierarchical relationships between classification nodes ---
    print("\nGenerating hierarchical relationships...")
    for _, col, label, _, parent_col in classifications:
        if parent_col:
            rels_hierarchy = []
            df_hierarchy = df.dropna(subset=[col, parent_col]).copy()
            df_hierarchy[col] = df_hierarchy[col].astype(str).str.strip()
            df_hierarchy[parent_col] = df_hierarchy[parent_col].astype(str).str.strip()
            
            unique_pairs = df_hierarchy[[col, parent_col]].drop_duplicates()
            parent_mapping = all_mappings[parent_col]
            child_mapping = all_mappings[col]

            for _, row in unique_pairs.iterrows():
                child_val = row[col]
                parent_val = row[parent_col]
                if child_val in child_mapping and parent_val in parent_mapping:
                    rels_hierarchy.append({
                        'START_ID': child_mapping[child_val],
                        'END_ID': parent_mapping[parent_val]
                    })
            generate_rel_csv(rels_hierarchy, config.GRAPH_DIR, f"rel_Part_of_{label}.csv")

    # --- 3. Generate Company -> Classification relationships (finest granularity only) ---
    print("\nGenerating Company -> Classification relationships (finest granularity)...")
    
    rels_map = {col: [] for col in col_to_label.keys()}

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Connecting companies to classifications", file=sys.stdout):
        company_id = row['companyID']

        # ICB System: Connect to Subsector if available, else Sector
        icb_sub_val = str(row.get('ICB Subsector', '')).strip()
        icb_sec_val = str(row.get('ICB Sector', '')).strip()
        if icb_sub_val and icb_sub_val in all_mappings['ICB Subsector']:
            rels_map['ICB Subsector'].append({'START_ID': company_id, 'END_ID': all_mappings['ICB Subsector'][icb_sub_val]})
        elif icb_sec_val and icb_sec_val in all_mappings['ICB Sector']:
            rels_map['ICB Sector'].append({'START_ID': company_id, 'END_ID': all_mappings['ICB Sector'][icb_sec_val]})

        # GICS System: Connect to SubIndustry if available, else Industry
        gics_sub_val = str(row.get('GICS SubIndustry', '')).strip()
        gics_ind_val = str(row.get('GICS Industry', '')).strip()
        if gics_sub_val and gics_sub_val in all_mappings['GICS SubIndustry']:
            rels_map['GICS SubIndustry'].append({'START_ID': company_id, 'END_ID': all_mappings['GICS SubIndustry'][gics_sub_val]})
        elif gics_ind_val and gics_ind_val in all_mappings['GICS Industry']:
            rels_map['GICS Industry'].append({'START_ID': company_id, 'END_ID': all_mappings['GICS Industry'][gics_ind_val]})

        # BICS System: Connect to the finest level available (L6 down to L3)
        bics_l6_val = str(row.get('BICS L6 Segment', '')).strip()
        bics_l5_val = str(row.get('BICS L5 Segment', '')).strip()
        bics_l4_val = str(row.get('BICS L4 Sub Industry', '')).strip()
        bics_l3_val = str(row.get('BICS L3 Industry', '')).strip()
        if bics_l6_val and bics_l6_val in all_mappings['BICS L6 Segment']:
            rels_map['BICS L6 Segment'].append({'START_ID': company_id, 'END_ID': all_mappings['BICS L6 Segment'][bics_l6_val]})
        elif bics_l5_val and bics_l5_val in all_mappings['BICS L5 Segment']:
            rels_map['BICS L5 Segment'].append({'START_ID': company_id, 'END_ID': all_mappings['BICS L5 Segment'][bics_l5_val]})
        elif bics_l4_val and bics_l4_val in all_mappings['BICS L4 Sub Industry']:
            rels_map['BICS L4 Sub Industry'].append({'START_ID': company_id, 'END_ID': all_mappings['BICS L4 Sub Industry'][bics_l4_val]})
        elif bics_l3_val and bics_l3_val in all_mappings['BICS L3 Industry']:
            rels_map['BICS L3 Industry'].append({'START_ID': company_id, 'END_ID': all_mappings['BICS L3 Industry'][bics_l3_val]})

    # --- 4. Save the generated relationship files ---
    for col, rels in rels_map.items():
        label = col_to_label[col]
        # If the list of relationships is empty, create an empty file with headers
        # to prevent the Cypher import from failing on a missing file.
        if not rels:
            print(f"No relationships for rel_Classified_as_{label}.csv. Creating empty file with headers.")
            output_path = config.ensure_parent(config.GRAPH_DIR / f"rel_Classified_as_{label}.csv")
            # These relationships only have start and end nodes. The headers must match what Cypher expects.
            empty_df = pd.DataFrame(columns=[':START_ID', ':END_ID'])
            empty_df.to_csv(output_path, index=False)
        else:
            generate_rel_csv(rels, config.GRAPH_DIR, f"rel_Classified_as_{label}.csv")


def main():
    """Main function to orchestrate the generation of company-related graph files."""
    config.GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Loading master company data once...")
    master_df = pd.read_csv(config.MASTER_COMPANY_CSV, low_memory=False)
    
    create_company_nodes(master_df)
    # The function now takes no arguments as it reads its own data
    create_owns_project_relationships()
    create_company_name_nodes_and_rels(master_df)
    create_country_nodes_and_rels(master_df)
    create_classification_nodes_and_rels(master_df)


if __name__ == "__main__":
    main()