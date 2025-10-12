# Builds an inverted index from words to a set of original company names.
# It enables fast retrieval of potential matches (avoiding full Cartesian
# product comparisons).

# Args:
#     company_list: List of company names to index
    
# Returns:
#     Dictionary mapping words to sets of company names containing those words

from collections import defaultdict
from src.utils.normalize_names import normalize_name

def build_word_index(company_list):
    index = defaultdict(set)
    for original_name in company_list:
        normalized = normalize_name(original_name)
        words = normalized.split()
        for word in words:
            if word: # Avoid empty strings
                index[word].add(original_name)
    return index
