import pandas as pd
import spacy
from pathlib import Path
from fuzzywuzzy import fuzz
from tqdm import tqdm
import re
from collections import defaultdict

def normalize_name(name):
    """
    Cleans and normalizes a company name by:
    1. Converting to lowercase.
    2. Removing common company suffixes.
    3. Removing punctuation.
    4. Normalizing whitespace.
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
    Compares company names using an efficient blocking strategy before detailed similarity scoring.
    """
    # Setup paths
    project_root = Path(__file__).resolve().parents[2]
    linkedin_path = project_root / "data" / "raw" / "company" / "linkedin_unpickled" / "linkedin_mining_companies.csv"
    bloomberg_path = project_root / "data" / "processed" / "bloomberg_companies.csv"
    output_path = project_root / "data" / "processed" / "linkedin_bloomberg_name_matches_indexed.csv"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load data
    print("Loading data files...")
    try:
        linkedin_df = pd.read_csv(linkedin_path)
        bloomberg_df = pd.read_csv(bloomberg_path)
    except Exception as e:
        print(f"Error loading data files: {e}")
        return
    
    linkedin_companies = linkedin_df.iloc[:, 0].dropna().unique()
    bloomberg_companies = bloomberg_df.iloc[:, 1].dropna().unique()
    
    print(f"Loaded {len(linkedin_companies)} LinkedIn companies and {len(bloomberg_companies)} Bloomberg companies.")
    
    # --- Indexing/Blocking Strategy ---
    print("Building word index from Bloomberg companies for efficient lookup...")
    bloomberg_index = build_word_index(bloomberg_companies)
    
    # --- Generate Candidate Pairs ---
    print("Generating candidate pairs based on shared words...")
    candidate_pairs = set()
    for linkedin_name in tqdm(linkedin_companies, desc="Finding Candidates"):
        normalized_linkedin = normalize_name(linkedin_name)
        words = normalized_linkedin.split()
        
        # Find all potential matches from the index
        potential_matches = set()
        for word in words:
            potential_matches.update(bloomberg_index[word])
            
        # Create pairs for comparison
        for bloomberg_name in potential_matches:
            candidate_pairs.add((linkedin_name, bloomberg_name))
            
    print(f"Reduced {len(linkedin_companies) * len(bloomberg_companies):,} total combinations to {len(candidate_pairs):,} candidate pairs.")

    # Load spaCy model only if there are candidates to process
    if not candidate_pairs:
        print("No candidate pairs found. Exiting.")
        return
        
    print("Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        print("Downloading spaCy model...")
        import subprocess
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"])
        nlp = spacy.load("en_core_web_md")
    
    # --- Process only candidate pairs ---
    results = []
    print("Calculating detailed similarities for candidate pairs...")
    for linkedin_name_str, bloomberg_name_str in tqdm(candidate_pairs, desc="Comparing Candidates"):
        
        # Calculate various fuzzy match scores
        ratio = fuzz.ratio(linkedin_name_str, bloomberg_name_str)
        partial_ratio = fuzz.partial_ratio(linkedin_name_str, bloomberg_name_str)
        token_sort_ratio = fuzz.token_sort_ratio(linkedin_name_str, bloomberg_name_str)
        token_set_ratio = fuzz.token_set_ratio(linkedin_name_str, bloomberg_name_str)
        wratio = fuzz.WRatio(linkedin_name_str, bloomberg_name_str)
        
        # Calculate spaCy semantic similarity
        doc1 = nlp(linkedin_name_str)
        doc2 = nlp(bloomberg_name_str)
        spacy_similarity = doc1.similarity(doc2)
        
        results.append({
            "LinkedIn_Company": linkedin_name_str,
            "Bloomberg_Company": bloomberg_name_str,
            "Levenshtein_Ratio": ratio,
            "Partial_Ratio": partial_ratio,
            "Token_Sort_Ratio": token_sort_ratio,
            "Token_Set_Ratio": token_set_ratio,
            "WRatio": wratio,
            "Spacy_Semantic_Similarity": spacy_similarity
        })
    
    # Create and save DataFrame
    if not results:
        print("No similarities calculated. Output file will be empty.")
        # Create an empty df with correct columns to avoid errors
        results_df = pd.DataFrame(columns=["LinkedIn_Company", "Bloomberg_Company", "Levenshtein_Ratio", "Partial_Ratio", "Token_Sort_Ratio", "Token_Set_Ratio", "WRatio", "Spacy_Semantic_Similarity"])
    else:
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values(by=["WRatio", "Token_Set_Ratio", "Spacy_Semantic_Similarity"], ascending=False)
    
    results_df.to_csv(output_path, index=False)
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()