import pandas as pd
import spacy
from pathlib import Path
from fuzzywuzzy import fuzz
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
from src.utils.normalize_names import normalize_name, filter_dirty_values
from src.utils.calculate_similarities import calculate_text_similarities
from src.utils.build_word_index import build_word_index



def find_best_match(source_name, candidate_index, nlp_model):
    """
    Finds the best match for a source name from an indexed list of candidates.
    Returns the best match name and a dictionary of scores.
    """
    normalized_source = normalize_name(source_name)
    words = normalized_source.split()
    
    potential_matches = set()
    for word in words:
        potential_matches.update(candidate_index.get(word, set()))
        
    if not potential_matches:
        return None, {}

    best_match_name = None
    highest_wratio = -1
    highest_levenshtein_in_tie = -1

    for candidate_name in potential_matches:
        normalized_candidate = normalize_name(candidate_name)
        wratio_score = fuzz.WRatio(normalized_source, normalized_candidate)

        if wratio_score > highest_wratio:
            # Found a new best WRatio, update everything
            highest_wratio = wratio_score
            best_match_name = candidate_name
            highest_levenshtein_in_tie = fuzz.ratio(normalized_source, normalized_candidate)
        elif wratio_score == highest_wratio:
            # It's a tie in WRatio, use Levenshtein as a tie-breaker
            levenshtein_score = fuzz.ratio(normalized_source, normalized_candidate)
            if levenshtein_score > highest_levenshtein_in_tie:
                # This candidate wins the tie-break
                best_match_name = candidate_name
                highest_levenshtein_in_tie = levenshtein_score
            
    if not best_match_name:
        return None, {}

    # Calculate all scores for the best match found
    normalized_best_match = normalize_name(best_match_name)
    
    scores = calculate_text_similarities(normalized_source, normalized_best_match, nlp_model)
    scores["w_ratio"] = highest_wratio
    
    return best_match_name, scores

def main():
    """
    For each company in node_CompanyName.csv, find the best match in LinkedIn and Bloomberg data.
    """
    # 1. Setup Paths
    project_root = Path(__file__).resolve().parents[2]
    graph_path = project_root / "data" / "graph" / "node_CompanyName.csv"
    # Update data sources to use the separate Bloomberg and cleaned LinkedIn files
    bloomberg_source_path = project_root / "data" / "processed" / "Bloomberg_Companies.csv"
    linkedin_source_path = project_root / "data" / "processed" / "Cleaned_Linkedin_Companies.csv"
    output_path = project_root / "data" / "processed" / "Matches_Scores_Graph.csv"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. Load Data from new sources
    print("Loading data files...")
    try:
        graph_df = pd.read_csv(graph_path)
        bloomberg_df = pd.read_csv(bloomberg_source_path)
        linkedin_df = pd.read_csv(linkedin_source_path)
    except Exception as e:
        print(f"Error loading data files: {e}")
        return

    # Extract company lists from their respective dataframes
    bloomberg_companies = bloomberg_df.iloc[:, 1].dropna().unique() # Column B (index 1) is company name
    
    # Clean dirty values from LinkedIn data before creating the unique list
    linkedin_col_name = 'Linkedin_Name' # The column name is now fixed
    linkedin_data_slice = linkedin_df[linkedin_col_name]
    cleaned_linkedin_data = filter_dirty_values(linkedin_data_slice)
    linkedin_companies = cleaned_linkedin_data.dropna().unique()
    
    graph_companies = graph_df['companyNameText:string'].dropna().unique()
    
    print(f"Loaded {len(graph_companies)} graph nodes, {len(linkedin_companies)} LinkedIn companies (after cleaning), and {len(bloomberg_companies)} Bloomberg companies.")

    # 3. Load spaCy Model
    print("Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        print("Downloading spaCy model 'en_core_web_md'...")
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"])
        nlp = spacy.load("en_core_web_md")

    # 4. Build Indexes for fast lookup
    print("Building indexes for LinkedIn and Bloomberg data...")
    linkedin_index = build_word_index(linkedin_companies)
    bloomberg_index = build_word_index(bloomberg_companies)

    # --- Special Test Case (Currently Disabled) ---
    # The following block can be un-commented to run a detailed analysis on a specific list of names.
    # It finds all potential candidates, scores them, and saves the results to 'Special_Test_Bloomberg_Matches.csv'.
    """
    special_test_names = [
        "Minerals and Metals Group (MMG)", "MITSUI & CO. (AUSTRALIA) LTD.", 
        "Zashvin Pty. Ltd.", "Impress Energy  Limited", "Weather Investments II S.ar.l",
        "Vale Australia", "Vale S.A."
    ]
    print(f"\n--- Running special test for: {special_test_names} ---")
    
    special_test_results = []

    for test_graph_name in special_test_names:
        print(f"\n--- Testing: '{test_graph_name}' ---")
        
        normalized_test_name = normalize_name(test_graph_name)
        print(f"Normalized Name: '{normalized_test_name}'")

        words = normalized_test_name.split()
        potential_bloomberg_matches = set()
        for word in words:
            potential_bloomberg_matches.update(bloomberg_index.get(word, set()))
        
        print(f"Found {len(potential_bloomberg_matches)} potential Bloomberg candidates to score.")

        if potential_bloomberg_matches:
            for candidate_name in tqdm(list(potential_bloomberg_matches), desc=f"Scoring '{test_graph_name}' candidates"):
                normalized_candidate = normalize_name(candidate_name)
                
                set1 = set(normalized_test_name.split())
                set2 = set(normalized_candidate.split())
                intersection = len(set1.intersection(set2))
                union = len(set1.union(set2))
                jaccard_sim = intersection / union if union != 0 else 0.0

                no_space_source = normalized_test_name.replace(' ', '')
                no_space_match = normalized_candidate.replace(' ', '')
                no_space_exact = 1 if no_space_source == no_space_match else 0

                doc1 = nlp(normalized_test_name)
                doc2 = nlp(normalized_candidate)
                spacy_sim = doc1.similarity(doc2) if doc1.vector_norm and doc2.vector_norm else 0.0

                special_test_results.append({
                    "Graph_Name": test_graph_name,
                    "Normalized_Graph_Name": normalized_test_name,
                    "Bloomberg_Candidate_Name": candidate_name,
                    "Normalized_Candidate_Name": normalized_candidate,
                    "WRatio": fuzz.WRatio(normalized_test_name, normalized_candidate),
                    "Levenshtein_Ratio": fuzz.ratio(normalized_test_name, normalized_candidate),
                    "Jaccard_Similarity": jaccard_sim,
                    "Spacy_Similarity": spacy_sim,
                    "NoSpace_Exact_Match": no_space_exact
                })

    if special_test_results:
        special_test_df = pd.DataFrame(special_test_results)
        special_test_df.sort_values(by=["Graph_Name", "WRatio"], ascending=[True, False], inplace=True)
        
        special_test_output_path = output_path.parent / "Special_Test_Bloomberg_Matches.csv"
        special_test_df.to_csv(special_test_output_path, index=False)
        print(f"\nSaved special test results to {special_test_output_path}")
    else:
        print("\nNo potential Bloomberg candidates found for the special test names.")

    print("--- Special test finished. Continuing with main process... ---\n")
    """
    # --- End of Special Test Case ---


    # 5. Main Matching Loop
    all_results = []
    print("Finding best matches for each graph node company...")
    score_keys = ["w_ratio", "levenshtein_ratio", "jaccard_similarity", "spacy_similarity", "no_space_exact_match"] 
    for graph_name in tqdm(graph_companies, desc="Matching Graph Nodes"):
        
        # Find best match in LinkedIn
        linkedin_match, linkedin_scores = find_best_match(graph_name, linkedin_index, nlp)
        
        # Find best match in Bloomberg
        bloomberg_match, bloomberg_scores = find_best_match(graph_name, bloomberg_index, nlp)
        
        # Combine results in the desired order
        result_row = {"Graph_Company_Name": graph_name}
        
        # Add Bloomberg match and scores first
        result_row["Bloomberg_Match_Name"] = bloomberg_match
        for key in score_keys:
            result_row[f"Bloomberg_{key}"] = bloomberg_scores.get(key) if bloomberg_scores else None
            
        # Add LinkedIn match and scores second
        result_row["LinkedIn_Match_Name"] = linkedin_match
        for key in score_keys:
            result_row[f"LinkedIn_{key}"] = linkedin_scores.get(key) if linkedin_scores else None
            
        all_results.append(result_row)

    # 6. Save Output
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(output_path, index=False)
    print(f"Matching process complete. Results saved to {output_path}")

    # 7. Process and save perfect matches with new hierarchical criteria
    print("Processing and saving perfect matches with new criteria...")

    matched_nodes = set()
    bloomberg_matches_list = []
    linkedin_matches_list = []

    # --- Step 1: Bloomberg NoSpace Exact Match ---
    bloomberg_step1_matches = results_df[
        (results_df['Bloomberg_no_space_exact_match'] == 1) &
        (~results_df['Graph_Company_Name'].isin(matched_nodes))
    ]
    if not bloomberg_step1_matches.empty:
        bloomberg_matches_list.append(bloomberg_step1_matches)
        matched_nodes.update(bloomberg_step1_matches['Graph_Company_Name'])
    
    # --- Step 2: Bloomberg High-Confidence Match ---
    remaining_df = results_df[~results_df['Graph_Company_Name'].isin(matched_nodes)]
    bloomberg_step2_matches = remaining_df[
        (remaining_df['Bloomberg_w_ratio'] >= 95) &
        (remaining_df['Bloomberg_levenshtein_ratio'] >= 90) &
        (remaining_df['Bloomberg_jaccard_similarity'] >= 0.5) &
        (remaining_df['Bloomberg_spacy_similarity'] >= 0.5)
    ]
    if not bloomberg_step2_matches.empty:
        bloomberg_matches_list.append(bloomberg_step2_matches)
        matched_nodes.update(bloomberg_step2_matches['Graph_Company_Name'])

    # --- Step 3: LinkedIn NoSpace Exact Match (for remaining nodes) ---
    remaining_df = results_df[~results_df['Graph_Company_Name'].isin(matched_nodes)]
    linkedin_step3_matches = remaining_df[
        (remaining_df['LinkedIn_no_space_exact_match'] == 1)
    ]
    if not linkedin_step3_matches.empty:
        linkedin_matches_list.append(linkedin_step3_matches)
        matched_nodes.update(linkedin_step3_matches['Graph_Company_Name'])

    # --- Step 4: LinkedIn High-Confidence Match (for remaining nodes) ---
    remaining_df = results_df[~results_df['Graph_Company_Name'].isin(matched_nodes)]
    linkedin_step4_matches = remaining_df[
        (remaining_df['LinkedIn_w_ratio'] >= 95) &
        (remaining_df['LinkedIn_levenshtein_ratio'] >= 90) &
        (remaining_df['LinkedIn_jaccard_similarity'] >= 0.5) &
        (remaining_df['LinkedIn_spacy_similarity'] >= 0.5)
    ]
    if not linkedin_step4_matches.empty:
        linkedin_matches_list.append(linkedin_step4_matches)
        matched_nodes.update(linkedin_step4_matches['Graph_Company_Name'])

    # --- Process and save final Bloomberg matches ---
    if bloomberg_matches_list:
        final_bloomberg_matches = pd.concat(bloomberg_matches_list)
        bloomberg_company_col = bloomberg_df.columns[1]
        
        # Keep Graph_Company_Name during the merge
        merged_bloomberg = pd.merge(
            final_bloomberg_matches, # Use the full dataframe with Graph_Company_Name
            bloomberg_df,
            left_on='Bloomberg_Match_Name',
            right_on=bloomberg_company_col,
            how='inner'
        )
        
        # Select and reorder columns for clarity
        # Place Graph_Company_Name first, then the matched company's info
        final_bloomberg_df = merged_bloomberg.drop_duplicates(subset=['Graph_Company_Name', 'Bloomberg_Match_Name'])
        
        # Define desired output columns
        output_cols = ['Graph_Company_Name', 'Bloomberg_Match_Name']
        # Add original bloomberg columns, avoiding duplication of the match name column
        original_bloomberg_cols = [col for col in bloomberg_df.columns if col != bloomberg_company_col]
        output_cols.extend(original_bloomberg_cols)
        
        # # Add score columns for context -- REMOVED AS PER REQUEST
        # score_cols = [col for col in final_bloomberg_matches.columns if col.startswith('Bloomberg_')]
        # output_cols.extend(score_cols)

        # Reorder and select final columns, handling potential missing columns
        final_bloomberg_df = final_bloomberg_df[[col for col in output_cols if col in final_bloomberg_df.columns]]

        bloomberg_output_path = output_path.parent / "Perfect_Matches_Bloomberg.csv"
        final_bloomberg_df.to_csv(bloomberg_output_path, index=False)
        print(f"Saved {len(final_bloomberg_df)} perfect Bloomberg matches to {bloomberg_output_path}")
    else:
        print("No perfect Bloomberg matches found.")

    # --- Process and save final LinkedIn matches ---
    if linkedin_matches_list:
        final_linkedin_matches = pd.concat(linkedin_matches_list)
        
        # Keep Graph_Company_Name during the merge
        merged_linkedin = pd.merge(
            final_linkedin_matches, # Use the full dataframe
            linkedin_df,
            left_on='LinkedIn_Match_Name',
            right_on='Linkedin_Name',
            how='inner'
        )

        # Select and reorder columns
        final_linkedin_df = merged_linkedin.drop_duplicates(subset=['Graph_Company_Name', 'LinkedIn_Match_Name'])

        # Define desired output columns
        output_cols = ['Graph_Company_Name', 'LinkedIn_Match_Name']
        # Add original linkedin columns, avoiding duplication
        original_linkedin_cols = [col for col in linkedin_df.columns if col != 'LinkedIn_Match_Name' and col != 'Linkedin_Name']
        output_cols.extend(original_linkedin_cols)

        # # Add score columns for context -- REMOVED AS PER REQUEST
        # score_cols = [col for col in final_linkedin_matches.columns if col.startswith('LinkedIn_')]
        # output_cols.extend(score_cols)

        # Reorder and select final columns
        final_linkedin_df = final_linkedin_df[[col for col in output_cols if col in final_linkedin_df.columns]]

        linkedin_output_path = output_path.parent / "Perfect_Matches_Linkedin.csv"
        final_linkedin_df.to_csv(linkedin_output_path, index=False)
        print(f"Saved {len(final_linkedin_df)} perfect LinkedIn matches to {linkedin_output_path}")
    else:
        print("No perfect LinkedIn matches found.")


if __name__ == "__main__":
    main()