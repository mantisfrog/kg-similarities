import pandas as pd
import spacy
from pathlib import Path
from fuzzywuzzy import fuzz
from tqdm import tqdm
import re
from collections import defaultdict
import numpy as np
import subprocess

def normalize_name(name):
    """
    Cleans and normalizes a company name by:
    1. Converting to lowercase.
    2. Replacing '&' with 'and'.
    3. Removing common company suffixes.
    4. Removing punctuation.
    5. Normalizing whitespace.
    """
    if not isinstance(name, str):
        return ""
    name = name.lower()
    # Replace '&' with 'and' before other processing
    name = name.replace('&', 'and')
    
    suffixes = [
        'pty ltd', 'p/l', 'proprietary limited', 'ltd', 'limited', 'nl', 
        'no liability', 'inc', 'incorporated', 'corp', 'corporation', 
        'plc', 'group', 'co', 'company', 'llc', 'llp', 'pty'
    ]
    suffix_pattern = r'\b(' + '|'.join(re.escape(s) for s in suffixes) + r')\b'
    name = re.sub(suffix_pattern, '', name)
    # Removed '&' from the character set as it has been replaced
    name = re.sub(r'[.,/-]', ' ', name)
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
            if word:
                index[word].add(original_name)
    return index

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
    highest_score = -1

    for candidate_name in potential_matches:
        normalized_candidate = normalize_name(candidate_name)
        score = fuzz.WRatio(normalized_source, normalized_candidate)
        if score > highest_score:
            highest_score = score
            best_match_name = candidate_name
            
    if not best_match_name:
        return None, {}

    # Calculate all scores for the best match found
    normalized_best_match = normalize_name(best_match_name)
    doc1 = nlp_model(normalized_source)
    doc2 = nlp_model(normalized_best_match)
    
    scores = {
        "WRatio": highest_score,
        "Levenshtein_Ratio": fuzz.ratio(normalized_source, normalized_best_match),
        "Partial_Ratio": fuzz.partial_ratio(normalized_source, normalized_best_match),
        "Token_Sort_Ratio": fuzz.token_sort_ratio(normalized_source, normalized_best_match),
        "Token_Set_Ratio": fuzz.token_set_ratio(normalized_source, normalized_best_match),
        "Spacy_Similarity": doc1.similarity(doc2) if doc1.vector_norm and doc2.vector_norm else 0.0
    }
    
    return best_match_name, scores

def main():
    """
    For each company in node_CompanyName.csv, find the best match in LinkedIn and Bloomberg data.
    """
    # 1. Setup Paths
    project_root = Path(__file__).resolve().parents[2]
    graph_path = project_root / "data" / "graph" / "node_CompanyName.csv"
    # The new single source for both Bloomberg and LinkedIn data
    combined_source_path = project_root / "data" / "processed" / "Bloomberg_Companies_with_Linkedin.csv"
    output_path = project_root / "data" / "processed" / "Matches_Scores_Graph.csv"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. Load Data from new sources
    print("Loading data files...")
    try:
        graph_df = pd.read_csv(graph_path)
        combined_df = pd.read_csv(combined_source_path)
    except Exception as e:
        print(f"Error loading data files: {e}")
        return

    # Extract company lists based on the new logic
    # Note: pandas iloc is 0-indexed, so row 2 is index 1, row 25205 is index 25204.
    # Row 25206 is index 25205, row 33116 is index 33115.
    bloomberg_companies = combined_df.iloc[1:25205, 1].dropna().unique() # Column B (index 1), Rows 2-25205
    
    # Clean dirty values from LinkedIn data before creating the unique list
    dirty_values = ["Minerals", "Mining Corp", "Minerals Corporation"]
    linkedin_data_slice = combined_df.iloc[25205:33116, 17] # Column R (index 17), Rows 25206-33116
    cleaned_linkedin_data = linkedin_data_slice[~linkedin_data_slice.isin(dirty_values)]
    linkedin_companies = cleaned_linkedin_data.dropna().unique()
    
    graph_companies = graph_df['companyNameText:string'].dropna().unique()
    
    print(f"Loaded {len(graph_companies)} graph nodes, {len(linkedin_companies)} LinkedIn companies (after cleaning), and {len(bloomberg_companies)} Bloomberg companies from the combined source file.")

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

    # 5. Main Matching Loop
    all_results = []
    print("Finding best matches for each graph node company...")
    for graph_name in tqdm(graph_companies, desc="Matching Graph Nodes"):
        
        # Find best match in LinkedIn
        linkedin_match, linkedin_scores = find_best_match(graph_name, linkedin_index, nlp)
        
        # Find best match in Bloomberg
        bloomberg_match, bloomberg_scores = find_best_match(graph_name, bloomberg_index, nlp)
        
        # Combine results in the desired order
        result_row = {"Graph_Company_Name": graph_name}
        
        # Add Bloomberg match and scores first
        result_row["Bloomberg_Match_Name"] = bloomberg_match
        for key, value in bloomberg_scores.items():
            result_row[f"Bloomberg_{key}"] = value
            
        # Add LinkedIn match and scores second
        result_row["LinkedIn_Match_Name"] = linkedin_match
        for key, value in linkedin_scores.items():
            result_row[f"LinkedIn_{key}"] = value
            
        all_results.append(result_row)

    # 6. Save Output
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(output_path, index=False)
    print(f"Matching process complete. Results saved to {output_path}")

if __name__ == "__main__":
    main()