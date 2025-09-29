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
    cleaned_linkedin_output_path = project_root / "data" / "processed" / "Cleaned_Linkedin_Companies.csv"
    
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
    
    # Load spaCy Model
    print("Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        print("Downloading spaCy model 'en_core_web_md'...")
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"])
        nlp = spacy.load("en_core_web_md")

    # Clean dirty values from LinkedIn data before creating the unique list
    linkedin_col_name = 'Company Name'
    linkedin_col = linkedin_df_full[linkedin_col_name]
    cleaned_linkedin_col = filter_dirty_values(linkedin_col)
    
    linkedin_companies = cleaned_linkedin_col.dropna().unique()
    bloomberg_companies = bloomberg_df['LONG_COMP_NAME'].dropna().unique()
    
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
            potential_matches.update(linkedin_index.get(word, set()))
        
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
            
            scores = calculate_text_similarities(normalized_bloomberg, normalized_best_match, nlp if 90 <= highest_score < 100 else None)

            results.append({
                "Bloomberg_Company": bloomberg_name,
                "LinkedIn_Company": best_match_original,
                "w_ratio": highest_score,
                "levenshtein_ratio": scores["levenshtein_ratio"],
                "jaccard_similarity": scores["jaccard_similarity"],
                "spacy_similarity": scores["spacy_similarity"],
                "no_space_exact_match": scores["no_space_exact_match"],
            })
        else:
            # No match found, append with empty values
            results.append({
                "Bloomberg_Company": bloomberg_name,
                "LinkedIn_Company": None,
                "w_ratio": None,
                "levenshtein_ratio": None,
                "jaccard_similarity": None,
                "spacy_similarity": None,
                "no_space_exact_match": None,
            })

    # Create and save match results DataFrame
    match_results_df = pd.DataFrame(results)
    match_results_df = match_results_df.sort_values(by=["w_ratio"], ascending=False)
    
    match_results_df.to_csv(match_output_path, index=False)
    print(f"Match results saved to {match_output_path}")

    # --- Create and save the cleaned (unmatched) LinkedIn file ---
    print("Creating cleaned (unmatched) LinkedIn file...")
    
    # 1. Find LinkedIn company names that were matched with high confidence (w_ratio >= 98)
    high_confidence_matches = match_results_df[match_results_df['w_ratio'] >= 98]
    matched_linkedin_names = high_confidence_matches['LinkedIn_Company'].dropna().unique()
    
    # 2. Filter the original full LinkedIn DataFrame to get the rows that were NOT matched with high confidence
    # This is the "cleaned" data to be saved.
    unmatched_linkedin_df = linkedin_df_full[~linkedin_df_full[linkedin_col_name].isin(matched_linkedin_names)].copy()
    
    # 3. Rename columns of the unmatched data to the desired output format
    unmatched_linkedin_df.rename(columns={
        linkedin_col_name: 'Linkedin_Name',
        'employees_count': 'Linkedin_empCount',
        'followers': 'Linkedin_Followers',
        'description': 'Linkedin_Description'
    }, inplace=True)
    
    # 4. Select only the required columns from the unmatched data
    cleaned_linkedin_df = unmatched_linkedin_df[['Linkedin_Name', 'Linkedin_empCount', 'Linkedin_Followers', 'Linkedin_Description']]
    
    # 5. Save the final cleaned LinkedIn file
    cleaned_linkedin_df.to_csv(cleaned_linkedin_output_path, index=False)
    print(f"Cleaned (unmatched) LinkedIn companies saved to {cleaned_linkedin_output_path}")


if __name__ == "__main__":
    main()