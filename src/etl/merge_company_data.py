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



def main():
    """
    Compares company names using a left-join logic from Bloomberg to LinkedIn and 
    Modern Slavery with an efficient blocking strategy. Scores are calculated on 
    normalized names.
    """
    # Setup paths
    project_root = Path(__file__).resolve().parents[2]
    linkedin_path = project_root / "data" / "raw" / "company" / "linkedin_unpickled" / "linkedin_mining_companies.csv"
    bloomberg_path = project_root / "data" / "processed" / "Bloomberg_Companies.csv"
    ms_path = project_root / "data" / "raw" / "company" / "modern_slavery" / "cleaned_ms_statements.csv"
    match_output_path = project_root / "data" / "processed" / "Matches_Scores_Bloomberg_to_Linkedin.csv"
    ms_match_output_path = project_root / "data" / "processed" / "Matches_Scores_Merged_to_MS.csv"
    master_data_output_path = project_root / "data" / "processed" / "CompanyData_Master.csv"
    
    master_data_output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load data
    print("Loading data files...")
    try:
        # Load and perform initial deduplication
        linkedin_df_raw = pd.read_csv(linkedin_path).drop_duplicates(subset=['Company Name'], keep='first')
        bloomberg_df_raw = pd.read_csv(bloomberg_path).drop_duplicates(subset=['Ticker'], keep='first')
        ms_df_raw = pd.read_csv(ms_path).drop_duplicates(subset=['CompanyName'], keep='first')
    except Exception as e:
        print(f"Error loading data files: {e}")
        return

    # Load spaCy Model
    print("Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        print("Downloading spaCy model 'en_core_web_md'...")
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"])
        nlp = spacy.load("en_core_web_md")

    # --- Pre-processing and Normalization ---
    print("Normalizing and cleaning all datasets...")

    def preprocess_dataframe(df, name_col, filter_dirty=False):
        """Applies cleaning, normalization, and deduplication to a dataframe."""
        name_series = df[name_col]
        if filter_dirty:
            name_series = filter_dirty_values(name_series)

        df['normalized_name'] = name_series.apply(
            lambda x: normalize_name(str(x)) if pd.notna(x) else None
        )
        df.dropna(subset=['normalized_name'], inplace=True)
        df = df[df['normalized_name'] != '']
        df.drop_duplicates(subset=['normalized_name'], keep='first', inplace=True)
        return df

    # Bloomberg and modern slavery datasets are assumed clean; only filter LinkedIn
    linkedin_df = preprocess_dataframe(linkedin_df_raw.copy(), 'Company Name', filter_dirty=True)
    bloomberg_df = preprocess_dataframe(bloomberg_df_raw.copy(), 'LONG_COMP_NAME')
    ms_df = preprocess_dataframe(ms_df_raw.copy(), 'CompanyName')

    # Create lists of unique, normalized names for matching
    linkedin_companies_norm = linkedin_df['normalized_name'].tolist()
    bloomberg_companies_norm = bloomberg_df['normalized_name'].tolist()
    ms_companies_norm = ms_df['normalized_name'].tolist()

    # Create maps from normalized name back to original name for result reporting
    bloomberg_norm_to_orig = pd.Series(bloomberg_df['LONG_COMP_NAME'].values, index=bloomberg_df.normalized_name).to_dict()
    linkedin_norm_to_orig = pd.Series(linkedin_df['Company Name'].values, index=linkedin_df.normalized_name).to_dict()
    ms_norm_to_orig = pd.Series(ms_df['CompanyName'].values, index=ms_df.normalized_name).to_dict()

    print(f"Loaded {len(linkedin_companies_norm)} LinkedIn, {len(bloomberg_companies_norm)} Bloomberg, and {len(ms_companies_norm)} MS companies after cleaning.")
    
    # --- Indexing/Blocking Strategy (Left Join Logic) ---
    print("Building word index from LinkedIn companies for efficient lookup...")
    linkedin_index = build_word_index(linkedin_companies_norm)
    
    results = []
    print("Finding best match for each Bloomberg company...")
    
    # Iterate through the "left" table (Bloomberg)
    for normalized_bloomberg in tqdm(bloomberg_companies_norm, desc="Matching Bloomberg Companies"):
        # Step 1: Select the best candidate with w_ratio >= 80
        best_match_normalized, w_ratio, levenshtein_ratio = select_best_candidate(
            normalized_bloomberg, linkedin_index, w_ratio_threshold=80
        )

        bloomberg_original = bloomberg_norm_to_orig[normalized_bloomberg]
        
        if best_match_normalized:
            # Step 2: Calculate secondary similarities
            # Conditionally pass the nlp model to optimize performance
            nlp_model_to_use = nlp if w_ratio >= 90 and w_ratio < 100 else None
            # Spacy score is used only for exclusion, 'East' and 'West' have a similarity of 1.00
            # This is not the desired outcome, so we set other thresholds lower and only use spacy
            # for exclusion criteria.
            secondary_scores = calculate_text_similarities(
                normalized_bloomberg, best_match_normalized, nlp_model_to_use
            )
            
            # Step 3: Apply matching rules
            match_status = get_match_status(w_ratio, levenshtein_ratio, secondary_scores)

            linkedin_original = linkedin_norm_to_orig[best_match_normalized]
            results.append({
                "Bloomberg_Company": bloomberg_original,
                "LinkedIn_Company": linkedin_original,
                "match_status": match_status,
                "w_ratio": w_ratio,
                "levenshtein_ratio": levenshtein_ratio,
                **secondary_scores
            })
        else:
            results.append({
                "Bloomberg_Company": bloomberg_original,
                "LinkedIn_Company": None,
                "match_status": None,
                "w_ratio": None,
                "levenshtein_ratio": None,
                "jaccard_similarity": None,
                "spacy_similarity": None,
                "no_space_exact_match": None,
                "au_removed_match": None,
            })

    # Create and save match results DataFrame
    linkedin_match_results_df = pd.DataFrame(results)
    linkedin_match_results_df = linkedin_match_results_df.sort_values(by=["w_ratio"], ascending=False)
    
    # Uncomment the following line to save Bloomberg -> LinkedIn match results
    # linkedin_match_results_df.to_csv(match_output_path, index=False)
    # print(f"Match results saved to {match_output_path}")

    # --- Create intermediate merged data (Bloomberg + LinkedIn) ---
    print("Merging high-confidence LinkedIn matches with Bloomberg data...")
    high_confidence_li_matches = linkedin_match_results_df[
        linkedin_match_results_df['match_status'].isin(['no_space_exact_match', 'au_removed_match','confident_score_match'])
    ].copy()
    
    merged_df = pd.merge(
        bloomberg_df,
        high_confidence_li_matches[['Bloomberg_Company', 'LinkedIn_Company']],
        left_on='LONG_COMP_NAME',
        right_on='Bloomberg_Company',
        how='left'
    ).drop(columns=['Bloomberg_Company'])

    # Use the LinkedIn name for matching if available, otherwise use the Bloomberg name
    merged_df['name_for_matching'] = merged_df['LinkedIn_Company'].fillna(merged_df['LONG_COMP_NAME'])
    merged_df['normalized_name_for_matching'] = merged_df['name_for_matching'].apply(
        lambda x: normalize_name(str(x)) if pd.notna(x) else None
    )
    # Create a map from the new normalized name back to the original Bloomberg name to track entities
    merged_norm_to_orig_bloomberg = pd.Series(merged_df['LONG_COMP_NAME'].values, index=merged_df.normalized_name_for_matching).to_dict()


    # --- Second Match: (Bloomberg + LinkedIn) -> Modern Slavery ---
    print("Starting match process for (Bloomberg+LinkedIn) -> Modern Slavery...")
    ms_index = build_word_index(ms_companies_norm)

    ms_results = []
    print("Finding best match for each merged company in Modern Slavery data...")

    for normalized_merged_name in tqdm(merged_df['normalized_name_for_matching'].dropna().unique(), desc="Matching Merged to MS"):
        # Step 1: Select the best candidate with w_ratio >= 80
        best_match_normalized, w_ratio, levenshtein_ratio = select_best_candidate(
            normalized_merged_name, ms_index, w_ratio_threshold=80
        )

        # Map back to the original Bloomberg company to maintain a consistent key
        bloomberg_original = merged_norm_to_orig_bloomberg.get(normalized_merged_name)
        if not bloomberg_original:
            continue

        if best_match_normalized:
            # Step 2: Calculate secondary similarities
            nlp_model_to_use = nlp if w_ratio >= 90 else None
            secondary_scores = calculate_text_similarities(
                normalized_merged_name, best_match_normalized, nlp_model_to_use
            )

            # Step 3: Apply matching rules
            match_status = get_match_status(w_ratio, levenshtein_ratio, secondary_scores)
            
            ms_original = ms_norm_to_orig[best_match_normalized]
            ms_results.append({
                "Bloomberg_Company": bloomberg_original,
                "MS_Company": ms_original,
                "match_status": match_status,
                "w_ratio": w_ratio,
                "levenshtein_ratio": levenshtein_ratio,
                **secondary_scores
            })
        else:
            ms_results.append({
                "Bloomberg_Company": bloomberg_original,
                "MS_Company": None,
                "match_status": None,
                "w_ratio": None,
                "levenshtein_ratio": None,
                "jaccard_similarity": None,
                "spacy_similarity": None,
                "no_space_exact_match": None,
                "au_removed_match": None,
            })

    ms_match_results_df = pd.DataFrame(ms_results)
    ms_match_results_df = ms_match_results_df.sort_values(by=["w_ratio"], ascending=False)
    
    # Uncomment the following line to save (Bloomberg + LinkedIn) -> Modern Slavery match results
    # ms_match_results_df.to_csv(ms_match_output_path, index=False)
    # print(f"Modern Slavery match results saved to {ms_match_output_path}")

    # --- Create and save the master company data file ---
    print("Creating the master company data file...")

    # 1. Identify high-confidence matches from the second match
    high_confidence_ms_matches = ms_match_results_df[
        ms_match_results_df['match_status'].isin(['no_space_exact_match', 'au_removed_match','confident_score_match'])
    ].copy()

    # 2. Create the final master_df by merging MS matches into the already merged (BB+LI) dataframe
    master_df = pd.merge(
        merged_df,
        high_confidence_ms_matches[['Bloomberg_Company', 'MS_Company']],
        left_on='LONG_COMP_NAME',
        right_on='Bloomberg_Company',
        how='left'
    ).drop(columns=['Bloomberg_Company'])

    # Merge additional details from source dataframes into the master_df
    master_df = pd.merge(
        master_df,
        linkedin_df[['Company Name', 'description', 'employees_count', 'followers']],
        left_on='LinkedIn_Company',
        right_on='Company Name',
        how='left'
    )
    master_df = pd.merge(
        master_df,
        ms_df[['CompanyName', 'FirstAnnualRevenue']],
        left_on='MS_Company',
        right_on='CompanyName',
        how='left'
    )

    # 3. Prepare the three data sources with a unified schema before concatenation
    
    # Prepare Bloomberg-sourced data
    df1 = master_df.copy()
    df1['Source'] = 'Bloomberg'
    df1['Company Name'] = df1['LONG_COMP_NAME']
    df1['Company Description'] = df1['CIE_DES_BULK'].fillna(df1['description'])
    df1['Revenue:Y'] = df1['Revenue:Y'].fillna(df1['FirstAnnualRevenue'])
    df1.rename(columns={
        'employees_count': 'Linkedin_empCount',
        'followers': 'Linkedin_Followers'
    }, inplace=True)


    # Prepare unmatched LinkedIn data
    matched_linkedin_names = set(high_confidence_li_matches['LinkedIn_Company'].dropna())
    unmatched_linkedin_df = linkedin_df[~linkedin_df['Company Name'].isin(matched_linkedin_names)].copy()
    df2 = unmatched_linkedin_df
    df2['Source'] = 'LinkedIn'
    df2['Company Description'] = df2['description']
    df2.rename(columns={
        'employees_count': 'Linkedin_empCount',
        'followers': 'Linkedin_Followers'
    }, inplace=True)


    # Prepare unmatched Modern Slavery data
    matched_ms_names = set(high_confidence_ms_matches['MS_Company'].dropna())
    unmatched_ms_df = ms_df[~ms_df['CompanyName'].isin(matched_ms_names)].copy()
    df3 = unmatched_ms_df
    df3['Source'] = 'Modern Slavery'
    df3['Company Name'] = df3['CompanyName']
    df3['Revenue:Y'] = df3['FirstAnnualRevenue']


    # 4. Combine the standardized dataframes
    master_df = pd.concat([df1, df2, df3], ignore_index=True, sort=False)

    # 5. Define final columns and reorder the master DataFrame
    
    # Add a unique company ID
    master_df['companyID:ID'] = [f'company_{i+1}' for i in range(len(master_df))]
    
    final_columns = [
        'companyID:ID', 'Ticker', 'Company Name', 'Country of Domicile', 'Company Type',
        'Market Cap', 'Revenue:Y', 'Tot Assets:Y', 'Number of Employees:LF',
        'ICB Sector', 'ICB Subsector', 'GICS Industry', 'GICS SubIndustry',
        'BICS L3 Industry', 'BICS L4 Sub Industry', 'BICS L5 Segment',
        'BICS L6 Segment', 'Company Description', 'Linkedin_empCount',
        'Linkedin_Followers', 'Source'
    ]
    
    # Ensure all required columns exist, adding any that are missing
    for col in final_columns:
        if col not in master_df.columns:
            master_df[col] = np.nan

    # Select and reorder columns to match the final schema
    master_df = master_df[final_columns]

    # 6. Save the final master file
    master_df.to_csv(master_data_output_path, index=False)
    print(f"Master company data saved to {master_data_output_path}")

    # 7. Print final counts based on the master file composition
    print("\n--- Final Master File Composition ---")
    source_counts = master_df['Source'].value_counts()
    bloomberg_count = source_counts.get('Bloomberg', 0)
    linkedin_count = source_counts.get('LinkedIn', 0)
    ms_count = source_counts.get('Modern Slavery', 0)

    print(f"Companies from Bloomberg (base): {bloomberg_count}")
    print(f"Additional companies from LinkedIn (unmatched): {linkedin_count}")
    print(f"Additional companies from Modern Slavery (unmatched): {ms_count}")
    print(f"Total companies in final master file: {len(master_df)}")


if __name__ == "__main__":
    main()