import pandas as pd
import sys
from pathlib import Path
from tqdm import tqdm

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src import config
# --- IMPORTS for advanced matching ---
from src.utils.normalize_names import normalize_name
from src.utils.build_word_index import build_word_index
from src.utils.select_candidates import select_best_candidate
from src.utils.calculate_similarities import calculate_text_similarities
from src.utils.match_rules import get_match_status
from src.utils.load_spacy import load_spacy_model
# --- NEW: Import utility functions ---
from src.utils.generate_node_rel import generate_node_csv, generate_rel_csv


def create_company_nodes():
    """
    Generates the node_Company.csv file from the master company data.
    This function is specific and does not use the generic node generator.
    """
    print("Generating Company node CSV...")
    df = pd.read_csv(config.MASTER_COMPANY_CSV, low_memory=False)

    # Define columns and their types for the node file
    node_cols = {
        "companyID": "companyID:ID",
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
    Generates the rel_Owns_project.csv file by matching companies to projects
    using an advanced fuzzy matching logic.
    """
    print("\nGenerating OWNS_PROJECT relationship CSV...")
    companies_df = pd.read_csv(config.MASTER_COMPANY_CSV, usecols=["companyID", "Company Name", "SYNONYMS"])
    projects_df = pd.read_csv(config.MASTER_PROJECT_CSV, usecols=["ENO", "COMPANIES"])
    node_project_df = pd.read_csv(config.NODE_PROJECT_CSV, usecols=["projectID:ID", "eno:int"])

    print("Loading spaCy model for semantic matching...")
    nlp = load_spacy_model("en_core_web_md")

    # 1. Create a mapping from ENO to projectID
    node_project_df.rename(columns={"eno:int": "eno"}, inplace=True)
    node_project_df.dropna(subset=["eno"], inplace=True)
    node_project_df["eno"] = node_project_df["eno"].astype(int)
    eno_to_projectID = pd.Series(node_project_df["projectID:ID"].values, index=node_project_df["eno"]).to_dict()

    # 2. Prepare master company data for fuzzy matching
    print("Preparing master company data for fuzzy matching...")
    norm_to_companyID = {}
    all_normalized_names = set()

    for _, row in tqdm(companies_df.iterrows(), total=len(companies_df), desc="Normalizing master companies"):
        company_id = row["companyID"]
        names = []
        if pd.notna(row["Company Name"]):
            names.append(str(row["Company Name"]).strip())
        if pd.notna(row["SYNONYMS"]):
            names.extend([name.strip() for name in str(row["SYNONYMS"]).split(',')])
        
        for name in names:
            if name:
                normalized_name = normalize_name(name)
                if normalized_name:
                    all_normalized_names.add(normalized_name)
                    norm_to_companyID[normalized_name] = company_id
    
    master_company_norm_list = list(all_normalized_names)
    print("Building word index for master company list...")
    master_company_index = build_word_index(master_company_norm_list)

    # 3. Iterate through projects and find matches using fuzzy logic
    print("Matching project companies to master list...")
    relationships = []
    unmatched_log = []
    high_confidence_statuses = {'no_space_exact_match', 'au_removed_match', 'confident_score_match'}
    projects_df.dropna(subset=["COMPANIES", "ENO"], inplace=True)
    
    for _, row in tqdm(projects_df.iterrows(), total=len(projects_df), desc="Matching projects to companies"):
        eno = int(row["ENO"])
        project_id = eno_to_projectID.get(eno)
        
        if not project_id:
            continue

        company_names_str = str(row["COMPANIES"])
        project_company_names = [name.strip() for name in company_names_str.split(',')]
        
        for original_name in project_company_names:
            if not original_name:
                continue
            
            normalized_name = normalize_name(original_name)
            if not normalized_name:
                continue

            best_match_normalized, w_ratio, lev_ratio = select_best_candidate(
                normalized_name, master_company_index, w_ratio_threshold=80
            )

            match_found = False
            if best_match_normalized:
                use_spacy = 95 <= w_ratio < 100
                secondary_scores = calculate_text_similarities(
                    normalized_name, best_match_normalized, nlp_model=nlp if use_spacy else None
                )
                status = get_match_status(w_ratio, lev_ratio, secondary_scores)

                if status in high_confidence_statuses:
                    company_id = norm_to_companyID.get(best_match_normalized)
                    if company_id:
                        relationships.append({
                            'START_ID': company_id,
                            'END_ID': project_id
                        })
                        match_found = True

            if not match_found:
                unmatched_log.append({
                    "ENO": eno,
                    "ProjectID": project_id,
                    "UnmatchedCompanyName": original_name
                })

    # 4. Create and save the relationship and log CSVs
    unique_rels = [dict(t) for t in {tuple(d.items()) for d in relationships}]
    generate_rel_csv(unique_rels, config.GRAPH_DIR, "rel_Owns_project.csv")

    if unmatched_log:
        unmatched_df = pd.DataFrame(unmatched_log).drop_duplicates()
        log_output_path = config.ensure_parent(config.UNMATCHED_JSON_COMPANIES_LOG_CSV)
        unmatched_df.to_csv(log_output_path, index=False)
        print(f"Successfully created unmatched companies log at {log_output_path} with {len(unmatched_df)} entries.")


def create_company_name_nodes_and_rels():
    """
    Creates nodes for each unique company name (official and synonym) and
    the relationships linking them back to the main Company node.
    """
    print("\nGenerating CompanyName nodes and REFERS_TO_COMPANY relationships...")
    companies_df = pd.read_csv(config.MASTER_COMPANY_CSV, usecols=["companyID", "Company Name", "SYNONYMS"])

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
    for _, row in tqdm(companies_df.iterrows(), total=len(companies_df), desc="Generating name relationships"):
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


def main():
    """Main function to orchestrate the generation of company-related graph files."""
    config.GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    create_company_nodes()
    create_owns_project_relationships()
    create_company_name_nodes_and_rels()


if __name__ == "__main__":
    main()