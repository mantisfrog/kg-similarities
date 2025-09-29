# Calculate multiple similarity metrics between two text strings.

# Args:
#     text1: First text string
#     text2: Second text string
#     nlp_model: Optional spaCy model for semantic similarity
    
# Returns:
#     Dictionary with various similarity scores

import numpy as np
from rapidfuzz import fuzz

def calculate_text_similarities(text1: str, text2: str, nlp_model=None) -> dict:
    # Basic validation
    if not text1 or not text2:
        return {
            "w_ratio": 0,
            "levenshtein_ratio": 0,
            "jaccard_similarity": 0,
            "spacy_similarity": 0,
            "no_space_exact_match": 0
        }
        
    # Calculate fuzzy string similarity scores
    wratio_score = fuzz.WRatio(text1, text2)
    levenshtein_ratio = fuzz.ratio(text1, text2)
    
    # Calculate Jaccard similarity on word sets
    set1 = set(text1.split())
    set2 = set(text2.split())
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    jaccard_sim = intersection / union if union else 0.0
    
    # Calculate spaCy similarity if model provided
    spacy_sim = 0
    if nlp_model:
        doc1 = nlp_model(text1)
        doc2 = nlp_model(text2)
        if doc1.vector_norm and doc2.vector_norm:
            spacy_sim = doc1.similarity(doc2)
    
    # No-space exact match (binary)
    no_space_text1 = text1.replace(' ', '')
    no_space_text2 = text2.replace(' ', '')
    no_space_match = 1 if no_space_text1 == no_space_text2 else 0
    
    return {
        "w_ratio": wratio_score,
        "levenshtein_ratio": levenshtein_ratio,
        "jaccard_similarity": jaccard_sim,
        "spacy_similarity": spacy_sim,
        "no_space_exact_match": no_space_match
    }
