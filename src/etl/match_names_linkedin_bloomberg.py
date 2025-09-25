import pandas as pd
# remove spacy in this version to save time
from pathlib import Path
from fuzzywuzzy import fuzz
from tqdm import tqdm
import re
from collections import defaultdict
import numpy as np

def normalize_name(name):
    """
    Cleans and normalizes a company name by:
    1. Converting to lowercase.
    2. Removing common company suffixes.
    3. Removing punctuation.
    4. Normalizing whitespace (including multiple spaces between words).
    """
    if not isinstance(name, str):
        return ""
        
    name = name.lower()
    
    # Define suffixes to remove using word boundaries (\b) to avoid partial matches (e.g., 'inc' in 'zinc')
    suffixes = [
        'pty ltd', 'p/l', 'proprietary limited', 'ltd', 'limited', 'nl', 
        'no liability', 'inc', 'incorporated', 'corp', 'corporation', 
        'plc', 'group', 'co', 'company', 'llc', 'llp', 'pty'
    ]
    # Create a regex pattern to match any of the suffixes as whole words
    suffix_pattern = r'\b(' + '|'.join(re.escape(s) for s in suffixes) + r')\b'
    name = re.sub(suffix_pattern, '', name)
    
    # Remove common punctuation. Move '-' to the end of the character set to treat it as a literal.
    name = re.sub(r'[.,&/-]', ' ', name)
    
    # Normalize whitespace (remove extra spaces)
    name = ' '.join(name.split())
    
    return name

def build_word_index(company_list):
    """
    Builds an inverted index from words to a set of original company names.
    """
    index = defaultdict(set)
    for original_name in company_list:
        normalized = normalize_name(original_name)
        words = normalized.split()
        for word in words:
            if word: # Avoid empty strings
                index[word].add(original_name)
    return index

def main():
    """
    Compares company names using a left-join logic from Bloomberg to LinkedIn
    with an efficient blocking strategy. Scores are calculated on normalized names.
    """
    # Setup paths
    project_root = Path(__file__).resolve().parents[2]
    linkedin_path = project_root / "data" / "raw" / "company" / "linkedin_unpickled" / "linkedin_mining_companies.csv"
    bloomberg_path = project_root / "data" / "processed" / "Bloomberg_Companies.csv"
    match_output_path = project_root / "data" / "processed" / "Matches_Scores_Linkedin_Bloomberg.csv"
    combined_output_path = project_root / "data" / "processed" / "Bloomberg_Companies_with_Linkedin.csv"
    
    match_output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load data
    print("Loading data files...")
    try:
        # Load full linkedin data for final merge
        linkedin_df_full = pd.read_csv(linkedin_path)
        bloomberg_df = pd.read_csv(bloomberg_path)
    except Exception as e:
        print(f"Error loading data files: {e}")
        return
    
    # Clean dirty values from LinkedIn data before creating the unique list
    dirty_values = ["Minerals", "Mining Corp"]
    linkedin_col_name = linkedin_df_full.columns[0]
    linkedin_col = linkedin_df_full[linkedin_col_name]
    cleaned_linkedin_col = linkedin_col[~linkedin_col.isin(dirty_values)]
    
    linkedin_companies = cleaned_linkedin_col.dropna().unique()
    bloomberg_companies = bloomberg_df.iloc[:, 1].dropna().unique()
    
    print(f"Loaded {len(linkedin_companies)} LinkedIn companies (after cleaning) and {len(bloomberg_companies)} Bloomberg companies.")
    
    # --- Indexing/Blocking Strategy (Left Join Logic) ---
    # Build index on the "right" table (LinkedIn) to look up matches for the "left" table (Bloomberg)
    print("Building word index from LinkedIn companies for efficient lookup...")
    linkedin_index = build_word_index(linkedin_companies)
    
    results = []
    print("Finding best match for each Bloomberg company...")
    
    # Iterate through the "left" table (Bloomberg)
    for bloomberg_name in tqdm(bloomberg_companies, desc="Matching Bloomberg Companies"):
        normalized_bloomberg = normalize_name(bloomberg_name)
        words = normalized_bloomberg.split()
        
        # Find all potential matches from the LinkedIn index
        potential_matches = set()
        for word in words:
            potential_matches.update(linkedin_index[word])
        
        best_match_original = None
        highest_score = -1

        if potential_matches:
            # Find the best match among the candidates based on WRatio of NORMALIZED names
            for linkedin_name in potential_matches:
                normalized_linkedin = normalize_name(linkedin_name)
                score = fuzz.WRatio(normalized_bloomberg, normalized_linkedin)
                if score > highest_score:
                    highest_score = score
                    best_match_original = linkedin_name
        
        # Append result for the current Bloomberg company
        if best_match_original:
            # A best match was found, calculate all scores for this specific pair using NORMALIZED names
            normalized_best_match = normalize_name(best_match_original)
            results.append({
                "Bloomberg_Company": bloomberg_name,
                "LinkedIn_Company": best_match_original,
                "Levenshtein_Ratio": fuzz.ratio(normalized_bloomberg, normalized_best_match),
                "Partial_Ratio": fuzz.partial_ratio(normalized_bloomberg, normalized_best_match),
                "Token_Sort_Ratio": fuzz.token_sort_ratio(normalized_bloomberg, normalized_best_match),
                "Token_Set_Ratio": fuzz.token_set_ratio(normalized_bloomberg, normalized_best_match),
                "WRatio": highest_score,  # This is the score used for matching
            })
        else:
            # No match found, append with empty values
            results.append({
                "Bloomberg_Company": bloomberg_name,
                "LinkedIn_Company": None,
                "Levenshtein_Ratio": np.nan,
                "Partial_Ratio": np.nan,
                "Token_Sort_Ratio": np.nan,
                "Token_Set_Ratio": np.nan,
                "WRatio": np.nan,
            })

    # Create and save match results DataFrame
    match_results_df = pd.DataFrame(results)
    match_results_df = match_results_df.sort_values(by=["WRatio"], ascending=False)
    
    match_results_df.to_csv(match_output_path, index=False)
    print(f"Match results saved to {match_output_path}")

    # --- Create and save the combined Bloomberg + LinkedIn file ---
    print("Creating combined Bloomberg and LinkedIn file...")
    
    # 1. Find LinkedIn company names that were matched with high confidence (WRatio >= 98)
    high_confidence_matches = match_results_df[match_results_df['WRatio'] >= 98]
    matched_linkedin_names = high_confidence_matches['LinkedIn_Company'].dropna().unique()
    
    # 2. Filter the original full LinkedIn DataFrame to get the rows that were NOT matched with high confidence
    # This is the "remaining" data to be appended.
    remaining_linkedin_df = linkedin_df_full[~linkedin_df_full[linkedin_col_name].isin(matched_linkedin_names)].copy()
    
    # 3. Rename columns of the remaining data to match the desired output format
    remaining_linkedin_df.rename(columns={
        linkedin_col_name: 'Linkedin_Name',
        'employees_count': 'Linkedin_empCount',
        'followers': 'Linkedin_Followers',
        'description': 'Linkedin_Description'
    }, inplace=True)
    
    # 4. Select only the required columns from the remaining data
    linkedin_to_append = remaining_linkedin_df[['Linkedin_Name', 'Linkedin_empCount', 'Linkedin_Followers', 'Linkedin_Description']]
    
    # 5. Combine the original bloomberg_df with the new linkedin data
    # The concat function will automatically fill non-matching columns with NaN
    combined_df = pd.concat([bloomberg_df, linkedin_to_append], ignore_index=True)
    
    # 6. Save the final combined file
    combined_df.to_csv(combined_output_path, index=False)
    print(f"Combined file saved to {combined_output_path}")


if __name__ == "__main__":
    main()