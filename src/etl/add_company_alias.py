import pandas as pd
from pathlib import Path
import sys
from tqdm import tqdm

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src import config
# --- NEW IMPORTS for name matching ---
from src.utils.normalize_names import normalize_name
from src.utils.build_word_index import build_word_index
from src.utils.select_candidates import select_best_candidate
from src.utils.calculate_similarities import calculate_text_similarities
from src.utils.match_rules import get_match_status
from src.utils.load_spacy import load_spacy_model


def match_projects_to_companies():
    """
    Performs fuzzy matching between project company names and the newly created
    master company list, saving the results to an intermediate file.
    """
    print("\n--- Starting Step: Matching Projects to Master Companies ---")
    
    # 1. Load necessary files
    print("Loading master company, project, and node data...")
    companies_df = pd.read_csv(config.MASTER_COMPANY_CSV, usecols=["companyID", "Company Name", "SYNONYMS"])
    projects_df = pd.read_csv(config.MASTER_PROJECT_CSV, usecols=["ENO", "COMPANIES"])
    node_project_df = pd.read_csv(config.NODE_PROJECT_CSV, usecols=["projectID:ID", "eno:int"])

    print("Loading spaCy model for semantic matching...")
    nlp = load_spacy_model("en_core_web_md")

    # 2. Create a mapping from ENO to projectID
    node_project_df.rename(columns={"eno:int": "eno"}, inplace=True)
    node_project_df.dropna(subset=["eno"], inplace=True)
    node_project_df["eno"] = node_project_df["eno"].astype(int)
    eno_to_projectID = pd.Series(node_project_df["projectID:ID"].values, index=node_project_df["eno"]).to_dict()

    # 3. Prepare master company data for fuzzy matching
    print("Preparing master company data for fuzzy matching...")
    norm_to_companyID = {}
    all_normalized_names = set()
    for _, row in tqdm(companies_df.iterrows(), total=len(companies_df), desc="Normalizing master companies", file=sys.stdout):
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

    # 4. Iterate through projects and find matches
    print("Matching project companies to master list...")
    matches = []
    high_confidence_statuses = {'no_space_exact_match', 'au_removed_match', 'confident_score_match'}
    projects_df.dropna(subset=["COMPANIES", "ENO"], inplace=True)
    
    for _, row in tqdm(projects_df.iterrows(), total=len(projects_df), desc="Matching projects to companies", file=sys.stdout):
        eno = int(row["ENO"])
        project_id = eno_to_projectID.get(eno)
        if not project_id:
            continue

        project_company_names = [name.strip() for name in str(row["COMPANIES"]).split(',')]
        for original_name in project_company_names:
            if not original_name:
                continue
            
            normalized_name = normalize_name(original_name)
            if not normalized_name:
                continue

            best_match_normalized, w_ratio, lev_ratio = select_best_candidate(
                normalized_name, master_company_index, w_ratio_threshold=80
            )

            if best_match_normalized:
                use_spacy = 95 <= w_ratio < 100
                secondary_scores = calculate_text_similarities(
                    normalized_name, best_match_normalized, nlp_model=nlp if use_spacy else None
                )
                status = get_match_status(w_ratio, lev_ratio, secondary_scores)

                if status in high_confidence_statuses:
                    company_id = norm_to_companyID.get(best_match_normalized)
                    if company_id:
                        matches.append({'companyID': company_id, 'projectID': project_id})

    # 5. Save the matches to the intermediate file
    if matches:
        matches_df = pd.DataFrame(matches).drop_duplicates()
        output_path = config.ensure_parent(config.PROJECT_COMPANY_MATCHES_CSV)
        matches_df.to_csv(output_path, index=False)
        print(f"Successfully saved {len(matches_df)} project-company matches to {output_path}")
    else:
        print("No high-confidence project-company matches were found.")


def create_master_company_data():
    """
    Reads processed data, merges synonyms and ACNs, consolidates duplicates,
    and creates a master company data file with a changes log.
    """
    try:
        # 1. Define all file paths from config
        # Inputs
        merged_company_data_path = config.MERGED_COMPANY_CSV
        matches_scores_json_path = config.MATCHES_SCORES_JSON_CSV
        former_names_path = config.FORMER_NAMES_CSV
        # Outputs
        output_path = config.MASTER_COMPANY_CSV

        # Read input CSV files
        print(f"Reading merged company data: {merged_company_data_path}")
        df_merged = pd.read_csv(merged_company_data_path)
        
        print(f"Reading match data: {matches_scores_json_path}")
        df_matches = pd.read_csv(matches_scores_json_path)

        # 2. Prepare synonyms from the match file
        print("Processing synonyms...")
        df_synonyms = df_matches[df_matches['Matched_Name'] != df_matches['JSON_Company_Name']].copy()
        synonyms_agg = df_synonyms.groupby(['Matched_Name', 'Matched_Source'])['JSON_Company_Name'].apply(
            lambda x: ', '.join(sorted(list(set(x))))
        ).reset_index()
        synonyms_agg.rename(columns={'JSON_Company_Name': 'SYNONYMS'}, inplace=True)

        # 3. Merge synonyms into the master dataframe
        print("Merging synonyms into company data...")
        df_master = pd.merge(
            df_merged,
            synonyms_agg,
            left_on=['Company Name', 'Source'],
            right_on=['Matched_Name', 'Matched_Source'],
            how='left'
        )
        df_master.drop(columns=['Matched_Name', 'Matched_Source'], inplace=True)
        df_master['SYNONYMS'] = df_master['SYNONYMS'].fillna('')

        # 4. Reorder columns, placing SYNONYMS column after Company Name
        print("Reordering columns...")
        cols = list(df_master.columns)
        synonyms_col = cols.pop(cols.index('SYNONYMS'))
        company_name_index = cols.index('Company Name')
        cols.insert(company_name_index + 1, synonyms_col)
        df_master = df_master[cols]

        # 5. Integrate data from former_names.csv
        print("Integrating data from former_names.csv...")
        try:
            print(f"Reading former names data: {former_names_path}")
            df_former_names = pd.read_csv(former_names_path)

            # 6a. Merge ACN column and place it after SYNONYMS
            df_acn = df_former_names[['ID', 'ACN']].copy()
            df_master = pd.merge(df_master, df_acn, left_on='companyID', right_on='ID', how='left')
            df_master.drop(columns=['ID'], inplace=True)
            
            cols = list(df_master.columns)
            if 'ACN' in cols:
                acn_col = cols.pop(cols.index('ACN'))
                synonyms_index = cols.index('SYNONYMS')
                cols.insert(synonyms_index + 1, acn_col)
                df_master = df_master[cols]

            # 6b. Add former names to SYNONYMS column
            df_master.set_index('companyID', inplace=True)
            for _, row in df_former_names.iterrows():
                company_id = row['ID']
                if company_id in df_master.index:
                    company_name = df_master.loc[company_id, 'Company Name']
                    existing_synonyms_str = df_master.loc[company_id, 'SYNONYMS']
                    existing_names_set = {str(company_name).lower()}
                    if pd.notna(existing_synonyms_str) and existing_synonyms_str:
                        existing_names_set.update([s.strip().lower() for s in existing_synonyms_str.split(',')])
                    
                    former_names_list = [name.strip() for name in str(row['MatchedNames']).split(',')]
                    names_to_add = [name for name in former_names_list if name.lower() not in existing_names_set]
                    
                    if names_to_add:
                        new_synonyms_str = ', '.join(names_to_add)
                        if existing_synonyms_str:
                            df_master.loc[company_id, 'SYNONYMS'] = existing_synonyms_str + ', ' + new_synonyms_str
                        else:
                            df_master.loc[company_id, 'SYNONYMS'] = new_synonyms_str
            df_master.reset_index(inplace=True)

        except FileNotFoundError:
            print(f"Warning: {former_names_path} not found. Skipping ACN and former names integration.", file=sys.stderr)

        # --- Integrate manual aliases before saving master file ---
        manual_aliases_path = config.MANUAL_ALIASES_CSV
        try:
            df_manual = pd.read_csv(manual_aliases_path)
            for _, mrow in df_manual.iterrows():
                cid = mrow['companyID']
                if cid in df_master['companyID'].values:
                    aliases = [a.strip() for a in str(mrow['alias']).split(',') if a.strip()]
                    idxs = df_master.index[df_master['companyID'] == cid].tolist()
                    if not idxs:
                        continue
                    idx = idxs[0]
                    existing_syn = df_master.at[idx, 'SYNONYMS']
                    comp_name = df_master.at[idx, 'Company Name']
                    exist_set = set()
                    if pd.notna(comp_name):
                        exist_set.add(comp_name.strip().lower())
                    if pd.notna(existing_syn) and existing_syn:
                        exist_set.update([s.strip().lower() for s in existing_syn.split(',')])
                    new_aliases = [a for a in aliases if a.lower() not in exist_set]
                    if new_aliases:
                        appended = ', '.join(new_aliases)
                        if existing_syn:
                            df_master.at[idx, 'SYNONYMS'] = existing_syn + ', ' + appended
                        else:
                            df_master.at[idx, 'SYNONYMS'] = appended
        except FileNotFoundError:
            print(f"Warning: {manual_aliases_path} not found. Skipping manual aliases integration.")

        # 6. Consolidate duplicates based on name matching
        print("Consolidating duplicates based on name matching...")

        # Ensure correct processing order by sorting by the numeric part of companyID
        df_master['comp_id_num'] = df_master['companyID'].str.extract(r'(\d+)').astype(int)
        df_master.sort_values('comp_id_num', inplace=True)
        df_master.drop(columns=['comp_id_num'], inplace=True)

        seen_names_map = {}  # Maps a lowercase name to the index of the first row it appeared in
        rows_to_drop = []
        changes_log = []

        for current_index, current_row in df_master.iterrows():
            # Collect all unique, non-empty names from the current row in an ordered list
            all_names_with_dupes = []
            if pd.notna(current_row['Company Name']):
                all_names_with_dupes.append(current_row['Company Name'].strip())
            if pd.notna(current_row['SYNONYMS']) and current_row['SYNONYMS']:
                all_names_with_dupes.extend([s.strip() for s in str(current_row['SYNONYMS']).split(',')])

            current_names = []
            seen_names_lower_for_row = set()
            for name in all_names_with_dupes:
                if name and name.lower() not in seen_names_lower_for_row:
                    current_names.append(name)
                    seen_names_lower_for_row.add(name.lower())

            # Find the first previously seen name, which determines the target row for merging
            target_index = None
            matched_name = None
            for name in current_names:
                if name.lower() in seen_names_map:
                    target_index = seen_names_map[name.lower()]
                    matched_name = name
                    break
            
            # If a match was found in a previous row and the current row's ACN is empty, then merge and drop
            if target_index is not None and pd.isna(current_row['ACN']):
                rows_to_drop.append(current_index)
                
                # --- New Logic: Update specific columns if target is empty and source has data ---
                columns_to_update = ['Revenue:Y', 'Linkedin_empCount', 'Linkedin_Followers']
                updated_cols_log = []
                for col in columns_to_update:
                    if col in df_master.columns: # Ensure column exists
                        if pd.isna(df_master.loc[target_index, col]) and pd.notna(current_row[col]):
                            df_master.loc[target_index, col] = current_row[col]
                            updated_cols_log.append(col)
                # --- End of New Logic ---

                # Get all names from the target row for a case-insensitive check
                target_row = df_master.loc[target_index]
                existing_target_names_lower = set()
                if pd.notna(target_row['Company Name']):
                    existing_target_names_lower.add(target_row['Company Name'].strip().lower())
                if pd.notna(target_row['SYNONYMS']) and target_row['SYNONYMS']:
                    existing_target_names_lower.update([s.strip().lower() for s in str(target_row['SYNONYMS']).split(',')])

                # Find which names from the current row are new to the target row
                names_to_add = sorted([name for name in current_names if name.strip().lower() not in existing_target_names_lower])

                if names_to_add:
                    new_synonyms_part = ', '.join(names_to_add)
                    current_synonyms = df_master.loc[target_index, 'SYNONYMS']
                    if pd.notna(current_synonyms) and current_synonyms:
                        df_master.loc[target_index, 'SYNONYMS'] = current_synonyms + ', ' + new_synonyms_part
                    else:
                        df_master.loc[target_index, 'SYNONYMS'] = new_synonyms_part
                
                # Log the change
                changes_log.append({
                    'Matched_Name': matched_name,
                    'Target_companyID': df_master.loc[target_index, 'companyID'],
                    'Dropped_companyID': current_row['companyID'],
                    'Merged_Names': ', '.join(sorted(list(current_names))),
                    'Updated_Columns': ', '.join(updated_cols_log)
                })
            else:
                # No match found, or ACN is present, so this entity is considered unique for now.
                # Add all its names to the map, pointing to the current index for future checks.
                for name in current_names:
                    if name.lower() not in seen_names_map:
                        seen_names_map[name.lower()] = current_index

        # Perform the drop and save the log
        if rows_to_drop:
            df_master.drop(index=rows_to_drop, inplace=True)
            
            # Enable logging if needed
            # df_changes = pd.DataFrame(changes_log)
            # changes_log_path = config.CHANGES_LOG_CSV
            # print(f"Saving name merge changes log to: {changes_log_path}")
            # changes_log_path.parent.mkdir(parents=True, exist_ok=True)
            # df_changes.to_csv(changes_log_path, index=False, encoding='utf-8-sig')
        else:
            print("No duplicate names found to consolidate.")

        # 7. Save the final master file
        print(f"Saving master data file to: {output_path}")
        config.ensure_parent(output_path)
        df_master.to_csv(output_path, index=False, encoding='utf-8-sig')

        print("Master company data file created successfully.")

        # --- NEW FINAL STEP: Perform project matching after master file is created ---
        match_projects_to_companies()

    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unknown error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    create_master_company_data()