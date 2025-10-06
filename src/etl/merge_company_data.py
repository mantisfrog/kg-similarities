import pandas as pd
from pathlib import Path
from rapidfuzz import fuzz
from tqdm import tqdm
import re
from collections import defaultdict
import numpy as np
import sys
import spacy
import subprocess

# Add the project root to the Python path to allow for absolute imports
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

# Import customised normalization function
from src.utils.normalize_names import normalize_name, filter_dirty_values
from src.utils.calculate_similarities import calculate_text_similarities
from src.utils.build_word_index import build_word_index
from src.utils.select_candidates import select_best_candidate
from src.utils.match_rules import get_match_status



def run_matching_process(left_norm_list, left_norm_to_orig, right_norm_to_orig, right_index, nlp, left_entity_name, right_entity_name, desc):
    """
    A generic function to run the full matching pipeline between two lists of companies.
    """
    results = []
    high_confidence_statuses = {'no_space_exact_match', 'au_removed_match', 'confident_score_match'}

    for normalized_left_name in tqdm(left_norm_list, desc=desc):
        best_match_normalized, w_ratio, levenshtein_ratio = select_best_candidate(
            normalized_left_name, right_index, w_ratio_threshold=80
        )

        left_original = left_norm_to_orig[normalized_left_name]
        
        if best_match_normalized:
            nlp_model_to_use = nlp if w_ratio >= 90 and w_ratio < 100 else None
            secondary_scores = calculate_text_similarities(
                normalized_left_name, best_match_normalized, nlp_model_to_use
            )
            match_status = get_match_status(w_ratio, levenshtein_ratio, secondary_scores)

            # We only consider high-confidence matches as "successful"
            if match_status not in high_confidence_statuses:
                match_status = "low_confidence" # Standardize non-high-confidence matches

            right_original = right_norm_to_orig[best_match_normalized]
            results.append({
                left_entity_name: left_original,
                right_entity_name: right_original,
                "match_status": match_status,
                "w_ratio": w_ratio,
                "levenshtein_ratio": levenshtein_ratio,
                **secondary_scores
            })
        else:
            results.append({
                left_entity_name: left_original,
                right_entity_name: None,
                "match_status": "no_candidate_found",
                "w_ratio": None, "levenshtein_ratio": None, "jaccard_similarity": None,
                "spacy_similarity": None, "no_space_exact_match": None, "au_removed_match": None,
            })
            
    return pd.DataFrame(results).sort_values(by=["w_ratio"], ascending=False)


def main():
    """
    Merges company data using an "Enrich-Append" strategy.
    1. Enriches Bloomberg with Modern Slavery data, then appends unmatched MS records.
    2. Enriches the result with LinkedIn data, then appends unmatched LinkedIn records.
    """
    # --- 1. SETUP AND PRE-PROCESSING ---
    # Setup paths
    project_root = Path(__file__).resolve().parents[2]
    linkedin_path = project_root / "data" / "raw" / "company" / "linkedin_unpickled" / "linkedin_mining_companies.csv"
    bloomberg_path = project_root / "data" / "processed" / "Bloomberg_Companies.csv"
    ms_path = project_root / "data" / "raw" / "company" / "modern_slavery" / "cleaned_ms_statements.csv"
    ms_match_output_path = project_root / "data" / "processed" / "Matches_Scores_Bloomberg_to_MS.csv"
    li_match_output_path = project_root / "data" / "processed" / "Matches_Scores_Merged_to_Linkedin.csv"
    merged_company_data_output_path = project_root / "data" / "processed" / "CompanyData_Merged.csv"
    
    merged_company_data_output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load data
    print("Loading data files...")
    linkedin_df_raw = pd.read_csv(linkedin_path).drop_duplicates(subset=['Company Name'], keep='first')
    bloomberg_df_raw = pd.read_csv(bloomberg_path).drop_duplicates(subset=['Ticker'], keep='first')
    ms_df_raw = pd.read_csv(ms_path).drop_duplicates(subset=['CompanyName'], keep='first')

    # Load spaCy Model
    print("Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        print("Downloading spaCy model 'en_core_web_md'...")
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"])
        nlp = spacy.load("en_core_web_md")

    # Pre-process and Normalize all dataframes
    print("Normalizing and cleaning all datasets...")
    def preprocess_dataframe(df, name_col, filter_dirty=False):
        name_series = df[name_col]
        if filter_dirty:
            name_series = filter_dirty_values(name_series)
        df['normalized_name'] = name_series.apply(lambda x: normalize_name(str(x)) if pd.notna(x) else None)
        df.dropna(subset=['normalized_name'], inplace=True)
        df = df[df['normalized_name'] != '']
        df.drop_duplicates(subset=['normalized_name'], keep='first', inplace=True)
        return df

    linkedin_df = preprocess_dataframe(linkedin_df_raw.copy(), 'Company Name', filter_dirty=True)
    bloomberg_df = preprocess_dataframe(bloomberg_df_raw.copy(), 'LONG_COMP_NAME')
    ms_df = preprocess_dataframe(ms_df_raw.copy(), 'CompanyName')

    # Create normalized lists and maps for matching
    bloomberg_companies_norm = bloomberg_df['normalized_name'].tolist()
    ms_companies_norm = ms_df['normalized_name'].tolist()
    bloomberg_norm_to_orig = pd.Series(bloomberg_df['LONG_COMP_NAME'].values, index=bloomberg_df.normalized_name).to_dict()
    ms_norm_to_orig = pd.Series(ms_df['CompanyName'].values, index=ms_df.normalized_name).to_dict()
    
    print(f"Loaded {len(linkedin_df)} LinkedIn, {len(bloomberg_df)} Bloomberg, and {len(ms_df)} MS companies after cleaning.")

    # --- 2. STAGE 1: BLOOMBERG + MODERN SLAVERY ---
    print("\n--- STAGE 1: Matching Bloomberg -> Modern Slavery ---")
    ms_index = build_word_index(ms_companies_norm)
    ms_match_results_df = run_matching_process(
        left_norm_list=bloomberg_companies_norm,
        left_norm_to_orig=bloomberg_norm_to_orig,
        right_norm_to_orig=ms_norm_to_orig,
        right_index=ms_index,
        nlp=nlp,
        left_entity_name="Bloomberg_Company",
        right_entity_name="MS_Company",
        desc="Matching Bloomberg to MS"
    )
    ms_match_results_df.to_csv(ms_match_output_path, index=False)
    print(f"Modern Slavery match results saved to {ms_match_output_path}")

    # Enrich Bloomberg with MS Revenue
    high_confidence_statuses = ['no_space_exact_match', 'au_removed_match', 'confident_score_match']
    high_confidence_ms_matches = ms_match_results_df[ms_match_results_df['match_status'].isin(high_confidence_statuses)].copy()
    
    ms_revenue_data = ms_df[['CompanyName', 'FirstAnnualRevenue']]
    matches_with_revenue = pd.merge(high_confidence_ms_matches, ms_revenue_data, left_on='MS_Company', right_on='CompanyName')
    
    master_df = pd.merge(bloomberg_df, matches_with_revenue[['Bloomberg_Company', 'FirstAnnualRevenue']], left_on='LONG_COMP_NAME', right_on='Bloomberg_Company', how='left')
    master_df['Revenue:Y'] = master_df['Revenue:Y'].fillna(master_df['FirstAnnualRevenue'])
    master_df.drop(columns=['Bloomberg_Company', 'FirstAnnualRevenue'], inplace=True)
    master_df['Source'] = 'Bloomberg'

    # Append unmatched MS companies
    matched_ms_names = set(high_confidence_ms_matches['MS_Company'].dropna())
    unmatched_ms_df = ms_df[~ms_df['CompanyName'].isin(matched_ms_names)].copy()
    unmatched_ms_df.rename(columns={'CompanyName': 'LONG_COMP_NAME', 'FirstAnnualRevenue': 'Revenue:Y'}, inplace=True)
    unmatched_ms_df['Source'] = 'Modern Slavery'
    
    master_df = pd.concat([master_df, unmatched_ms_df], ignore_index=True, sort=False)

    # --- 3. STAGE 2: (BLOOMBERG+MS) + LINKEDIN ---
    print("\n--- STAGE 2: Matching (Bloomberg+MS) -> LinkedIn ---")
    # Re-normalize the combined dataframe for the next matching round
    master_df['normalized_name'] = master_df['LONG_COMP_NAME'].apply(lambda x: normalize_name(str(x)) if pd.notna(x) else None)
    master_df.dropna(subset=['normalized_name'], inplace=True)
    master_df = master_df[master_df['normalized_name'] != ''].drop_duplicates(subset=['normalized_name'], keep='first')

    merged_companies_norm = master_df['normalized_name'].tolist()
    merged_norm_to_orig = pd.Series(master_df['LONG_COMP_NAME'].values, index=master_df.normalized_name).to_dict()
    linkedin_norm_to_orig = pd.Series(linkedin_df['Company Name'].values, index=linkedin_df.normalized_name).to_dict()
    
    linkedin_index = build_word_index(linkedin_df['normalized_name'].tolist())
    li_match_results_df = run_matching_process(
        left_norm_list=merged_companies_norm,
        left_norm_to_orig=merged_norm_to_orig,
        right_norm_to_orig=linkedin_norm_to_orig,
        right_index=linkedin_index,
        nlp=nlp,
        left_entity_name="Master_Company",
        right_entity_name="LinkedIn_Company",
        desc="Matching Merged to LinkedIn"
    )
    li_match_results_df.to_csv(li_match_output_path, index=False)
    print(f"LinkedIn match results saved to {li_match_output_path}")

    # Enrich master_df with LinkedIn data
    high_confidence_li_matches = li_match_results_df[li_match_results_df['match_status'].isin(high_confidence_statuses)].copy()
    
    li_data_to_merge = linkedin_df[['Company Name', 'description', 'employees_count', 'followers']]
    matches_with_li_data = pd.merge(high_confidence_li_matches, li_data_to_merge, left_on='LinkedIn_Company', right_on='Company Name')

    master_df = pd.merge(master_df, matches_with_li_data[['Master_Company', 'description', 'employees_count', 'followers']], left_on='LONG_COMP_NAME', right_on='Master_Company', how='left')
    master_df['CIE_DES_BULK'] = master_df['CIE_DES_BULK'].fillna(master_df['description'])
    master_df.drop(columns=['Master_Company', 'description'], inplace=True)

    # Append unmatched LinkedIn companies
    matched_li_names = set(high_confidence_li_matches['LinkedIn_Company'].dropna())
    unmatched_li_df = linkedin_df[~linkedin_df['Company Name'].isin(matched_li_names)].copy()
    unmatched_li_df.rename(columns={'Company Name': 'LONG_COMP_NAME', 'description': 'CIE_DES_BULK'}, inplace=True)
    unmatched_li_df['Source'] = 'LinkedIn'

    master_df = pd.concat([master_df, unmatched_li_df], ignore_index=True, sort=False)

    # --- 4. FINALIZATION ---
    print("\n--- Finalizing Merged Company File ---")
    # Standardize final column names according to your rules
    master_df.rename(columns={
        'LONG_COMP_NAME': 'Company Name',
        'CIE_DES_BULK': 'Company Description',
        'employees_count': 'Linkedin_empCount',
        'followers': 'Linkedin_Followers'
    }, inplace=True)

    # Add companyID as a unique identifier
    master_df.insert(0, 'companyID', [f'comp_{i+1}' for i in range(len(master_df))])

    # Dynamically define the final columns to keep all Bloomberg columns + new ones
    # 1. Start with the full list of original Bloomberg columns
    final_columns = bloomberg_df_raw.columns.tolist()

    # 2. Replace the original names with the new names from the rename step
    if 'LONG_COMP_NAME' in final_columns:
        final_columns[final_columns.index('LONG_COMP_NAME')] = 'Company Name'
    if 'CIE_DES_BULK' in final_columns:
        final_columns[final_columns.index('CIE_DES_BULK')] = 'Company Description'

    # 3. Add the new columns that were created during the merge process
    newly_added_columns = ['Linkedin_empCount', 'Linkedin_Followers', 'Source']
    for col in newly_added_columns:
        if col not in final_columns:
            final_columns.append(col)

    # Ensure companyID is the first column in the final output
    final_columns.insert(0, 'companyID')

    # Ensure all required columns exist in the master_df, filling missing ones with NaN
    for col in final_columns:
        if col not in master_df.columns:
            master_df[col] = np.nan
            
    # Select and order the final columns according to the dynamically generated list
    master_df = master_df[final_columns]

    # Save the final merged company data file
    master_df.to_csv(merged_company_data_output_path, index=False)
    print(f"Merged company data saved to {merged_company_data_output_path}")

    # Print final counts
    print("\n--- Final Merged File Composition ---")
    source_counts = master_df['Source'].value_counts()
    bloomberg_count = source_counts.get('Bloomberg', 0)
    linkedin_count = source_counts.get('LinkedIn', 0)
    ms_count = source_counts.get('Modern Slavery', 0)

    print(f"Companies from Bloomberg (base and enriched): {bloomberg_count}")
    print(f"Additional companies from Modern Slavery (unmatched): {ms_count}")
    print(f"Additional companies from LinkedIn (unmatched): {linkedin_count}")
    print(f"Total companies in final merged file: {len(master_df)}")


if __name__ == "__main__":
    main()
