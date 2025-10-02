import pandas as pd
import spacy
from pathlib import Path
from rapidfuzz import fuzz
from tqdm import tqdm
import re
from collections import defaultdict
import numpy as np
import subprocess
import sys

# Add the project root to the Python path to allow for absolute imports
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

# Import customised normalization function
from src.utils.normalize_names import normalize_name
from src.utils.calculate_similarities import calculate_text_similarities
from src.utils.build_word_index import build_word_index
from src.utils.select_candidates import select_best_candidate
from src.utils.match_rules import get_match_status



def main():
    """
    For each company in node_CompanyName.csv, find the best match in the master data file,
    which contains data from Bloomberg, LinkedIn, and Modern Slavery statements.
    The matching logic is hierarchical: it stops as soon as a perfect match is found.
    """
    # 1. Setup Paths
    project_root = Path(__file__).resolve().parents[2]
    graph_path = project_root / "data" / "graph" / "node_CompanyName.csv"
    master_data_path = project_root / "data" / "master" / "CompanyData_Master.csv"
    output_path = project_root / "data" / "processed" / "Matches_Scores_Graph.csv"
    consolidated_output_path = output_path.parent / "Perfect_Matches_All_Sources.csv"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. Load Data
    print("Loading data files...")
    try:
        graph_df = pd.read_csv(graph_path)
        master_cols = ['companyID:ID', 'Company Name', 'Source']
        master_df = pd.read_csv(master_data_path, usecols=master_cols)
    except Exception as e:
        print(f"Error loading data files: {e}")
        return

    master_df['Source'] = master_df['Source'].fillna('')
    company_name_col = 'Company Name'

    bloomberg_df = master_df[master_df['Source'] == 'Bloomberg'].copy()
    linkedin_df = master_df[master_df['Source'] == 'LinkedIn'].copy()
    modern_slavery_df = master_df[master_df['Source'] == 'Modern Slavery'].copy()

    # Normalize names and create maps to original names for each source
    bloomberg_df['normalized_name'] = bloomberg_df[company_name_col].apply(lambda x: normalize_name(str(x)) if pd.notna(x) else '')
    linkedin_df['normalized_name'] = linkedin_df[company_name_col].apply(lambda x: normalize_name(str(x)) if pd.notna(x) else '')
    modern_slavery_df['normalized_name'] = modern_slavery_df[company_name_col].apply(lambda x: normalize_name(str(x)) if pd.notna(x) else '')

    bloomberg_norm_to_orig = pd.Series(bloomberg_df[company_name_col].values, index=bloomberg_df.normalized_name).to_dict()
    linkedin_norm_to_orig = pd.Series(linkedin_df[company_name_col].values, index=linkedin_df.normalized_name).to_dict()
    modern_slavery_norm_to_orig = pd.Series(modern_slavery_df[company_name_col].values, index=modern_slavery_df.normalized_name).to_dict()

    # Create lists of unique, normalized names for matching
    bloomberg_companies_norm = bloomberg_df['normalized_name'].dropna().unique()
    linkedin_companies_norm = linkedin_df['normalized_name'].dropna().unique()
    modern_slavery_companies_norm = modern_slavery_df['normalized_name'].dropna().unique()
    graph_companies = graph_df['companyNameText:string'].dropna().unique()
    
    print(f"Loaded {len(graph_companies)} graph nodes.")
    print(f"Loaded {len(bloomberg_companies_norm)} Bloomberg, {len(linkedin_companies_norm)} LinkedIn, and {len(modern_slavery_companies_norm)} Modern Slavery companies from master file.")

    # 3. Load spaCy Model
    print("Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        print("Downloading spaCy model 'en_core_web_md'...")
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"])
        nlp = spacy.load("en_core_web_md")

    # 4. Build Indexes for fast lookup
    print("Building indexes for all data sources...")
    bloomberg_index = build_word_index(bloomberg_companies_norm)
    linkedin_index = build_word_index(linkedin_companies_norm)
    modern_slavery_index = build_word_index(modern_slavery_companies_norm)

    # 5. Main Hierarchical Matching Loop
    all_results = []
    print("Finding the first perfect match for each graph node using hierarchical logic...")
    perfect_match_statuses = {'no_space_exact_match', 'au_removed_match', 'confident_score_match'}
    score_keys = ["w_ratio", "levenshtein_ratio", "jaccard_similarity", "spacy_similarity", "no_space_exact_match", "au_removed_match"]

    for graph_name in tqdm(graph_companies, desc="Matching Graph Nodes"):
        normalized_graph_name = normalize_name(graph_name)
        
        # --- 1. Try to match with Bloomberg ---
        # Spacy score is used only for exclusion, 'East' and 'West' have a similarity of 1.00
        # This is not the desired outcome, so we set other thresholds lower and only use spacy
        # for exclusion criteria.
        best_match_bloomberg, w_ratio_bb, lev_ratio_bb = select_best_candidate(normalized_graph_name, bloomberg_index)
        if best_match_bloomberg:
            nlp_model_to_use = nlp if w_ratio_bb >= 90 and w_ratio_bb < 100 else None
            secondary_scores_bb = calculate_text_similarities(normalized_graph_name, best_match_bloomberg, nlp_model_to_use)
            match_status_bb = get_match_status(w_ratio_bb, lev_ratio_bb, secondary_scores_bb)

            if match_status_bb in perfect_match_statuses:
                original_matched_name = bloomberg_norm_to_orig.get(best_match_bloomberg)
                result = {
                    "Graph_Company_Name": graph_name,
                    "Graph_Company_Name_Normalized": normalized_graph_name,
                    "Matched_Name": original_matched_name,
                    "Matched_Name_Normalized": best_match_bloomberg,
                    "Matched_Source": "Bloomberg",
                    "Matching_Rule": match_status_bb,
                    "w_ratio": w_ratio_bb,
                    "levenshtein_ratio": lev_ratio_bb,
                    **secondary_scores_bb
                }
                all_results.append(result)
                continue

        # --- 2. If no Bloomberg match, try LinkedIn ---
        best_match_li, w_ratio_li, lev_ratio_li = select_best_candidate(normalized_graph_name, linkedin_index)
        if best_match_li:
            nlp_model_to_use = nlp if w_ratio_li >= 90 else None
            secondary_scores_li = calculate_text_similarities(normalized_graph_name, best_match_li, nlp_model_to_use)
            match_status_li = get_match_status(w_ratio_li, lev_ratio_li, secondary_scores_li)

            if match_status_li in perfect_match_statuses:
                original_matched_name = linkedin_norm_to_orig.get(best_match_li)
                result = {
                    "Graph_Company_Name": graph_name,
                    "Graph_Company_Name_Normalized": normalized_graph_name,
                    "Matched_Name": original_matched_name,
                    "Matched_Name_Normalized": best_match_li,
                    "Matched_Source": "LinkedIn",
                    "Matching_Rule": match_status_li,
                    "w_ratio": w_ratio_li,
                    "levenshtein_ratio": lev_ratio_li,
                    **secondary_scores_li
                }
                all_results.append(result)
                continue

        # --- 3. If no Bloomberg or LinkedIn match, try Modern Slavery ---
        best_match_ms, w_ratio_ms, lev_ratio_ms = select_best_candidate(normalized_graph_name, modern_slavery_index)
        if best_match_ms:
            nlp_model_to_use = nlp if w_ratio_ms >= 90 else None
            secondary_scores_ms = calculate_text_similarities(normalized_graph_name, best_match_ms, nlp_model_to_use)
            match_status_ms = get_match_status(w_ratio_ms, lev_ratio_ms, secondary_scores_ms)

            if match_status_ms in perfect_match_statuses:
                original_matched_name = modern_slavery_norm_to_orig.get(best_match_ms)
                result = {
                    "Graph_Company_Name": graph_name,
                    "Graph_Company_Name_Normalized": normalized_graph_name,
                    "Matched_Name": original_matched_name,
                    "Matched_Name_Normalized": best_match_ms,
                    "Matched_Source": "Modern Slavery",
                    "Matching_Rule": match_status_ms,
                    "w_ratio": w_ratio_ms,
                    "levenshtein_ratio": lev_ratio_ms,
                    **secondary_scores_ms
                }
                all_results.append(result)
                continue
            
        # --- 4. No perfect match found in any source ---
        all_results.append({
            "Graph_Company_Name": graph_name,
            "Graph_Company_Name_Normalized": normalized_graph_name,
            "Matched_Name": None,
            "Matched_Name_Normalized": None,
            "Matched_Source": None,
            "Matching_Rule": None,
            **{key: None for key in score_keys}
        })

    # 6. Create and Save Results
    print("Processing and saving match results...")
    results_df = pd.DataFrame(all_results)

    # Uncomment the following line to save all matching scores
    results_df.to_csv(output_path, index=False)
    print(f"Hierarchical matching process complete. All final matches saved to {output_path}")

    # 7. Create a consolidated 'Perfect Match' file by merging with original data
    all_merged_dfs = []

    # --- Process Bloomberg matches ---
    final_bloomberg_matches = results_df[results_df['Matched_Source'] == 'Bloomberg'].copy()
    if not final_bloomberg_matches.empty:
        merged_bloomberg = pd.merge(
            final_bloomberg_matches,
            bloomberg_df,
            left_on='Matched_Name',
            right_on=company_name_col,
            how='inner'
        )
        all_merged_dfs.append(merged_bloomberg)
        print(f"Found {len(merged_bloomberg)} perfect Bloomberg matches.")

    # --- Process LinkedIn matches ---
    final_linkedin_matches = results_df[results_df['Matched_Source'] == 'LinkedIn'].copy()
    if not final_linkedin_matches.empty:
        merged_linkedin = pd.merge(
            final_linkedin_matches,
            linkedin_df,
            left_on='Matched_Name',
            right_on=company_name_col,
            how='inner'
        )
        all_merged_dfs.append(merged_linkedin)
        print(f"Found {len(merged_linkedin)} perfect LinkedIn matches.")

    # --- Process Modern Slavery matches ---
    final_ms_matches = results_df[results_df['Matched_Source'] == 'Modern Slavery'].copy()
    if not final_ms_matches.empty:
        merged_ms = pd.merge(
            final_ms_matches,
            modern_slavery_df,
            left_on='Matched_Name',
            right_on=company_name_col,
            how='inner'
        )
        all_merged_dfs.append(merged_ms)
        print(f"Found {len(merged_ms)} perfect Modern Slavery matches.")

    # --- Consolidate, clean, and save ---
    if all_merged_dfs:
        consolidated_df = pd.concat(all_merged_dfs, ignore_index=True)
        
        # Columns to remove from the final output
        cols_to_drop = [
            'Matched_Source', 'Matching_Rule', 'w_ratio', 'levenshtein_ratio',
            'jaccard_similarity', 'spacy_similarity', 'no_space_exact_match',
            'au_removed_match', 'normalized_name', 'Company Name', 'Source'
        ]
        
        # Drop only the columns that actually exist
        existing_cols_to_drop = [col for col in cols_to_drop if col in consolidated_df.columns]
        consolidated_df.drop(columns=existing_cols_to_drop, inplace=True)
        
        # Save the consolidated file
        consolidated_df.to_csv(consolidated_output_path, index=False)
        print(f"Saved {len(consolidated_df)} total perfect matches to {consolidated_output_path}")
    else:
        print("No perfect matches found across all sources.")


if __name__ == "__main__":
    main()