# This module provides utilities for normalizing company names by removing legal suffixes 
# and standardizing common terms. It helps in matching similar company names by stripping 
# irrelevant legal endings and unifying variations in spelling.

# Users can customize the normalization by modifying:
# - RAW_SUFFIXES: List of company legal suffixes to remove (e.g., 'ltd', 'inc', 'corp')
# - replacements: Dictionary for standardizing spelling and plurals in the normalize_name function
# - DIRTY_VALUES: List of specific company names to filter out as they cause matching issues

import re
from typing import List, Tuple

# List of common company legal suffixes.
RAW_SUFFIXES = [

    'co', 'company',
    'group',
    'holding', 'holdings',

    # AU
    'pty ltd', 'p/l', 'proprietary limited',
    'ltd', 'limited',
    'nl', 'n.l.', 'no liability',
    'Ltd/Australia', 'Limited/Australia',

    # US
    'inc', 'incorporated',
    'corp', 'corporation',
    'plc', 'llc', 'llp',
    'pty',

    # Europe
    'bv', 'b.v.',
    'sa', 's.a.',
    'gmbh', 'g.m.b.h.',
    'ag',
    'kk', 'k.k.',
    'gk', 'g.k.',
    'srl', 's.r.l.',
    'sarl', 's.a.r.l.',
    'spa', 's.p.a.',
    's de rl', 's. de r.l.',
    'oy', 'ab', 'as',

    # Latin AM
    'ltda',
    's de rl de cv', 's. de r.l. de c.v.',

    # Singapore
    'pte ltd', 'pte limited', 'pte',

    # Canada (British Columbia)
    'b c ltd', 'b c limited',

    # Limited partnership
    'l.p.', 'lp',

    # Peru
    'sac', 's.a.c.',

    # France
    'sas', 's.a.s.',
]


# List of dirty values that should be filtered out before processing
# Storing them in lowercase for case-insensitive comparison
DIRTY_VALUES = [
    "minerals", 
    "mining corp", 
    "group engineering pty ltd", 
    "minerals corporation",
]


# Splits a string into lowercase alphanumeric tokens.
def _tokenize(text: str) -> List[str]:
    return re.findall(r'[A-Za-z0-9]+', text.lower())

# Converts raw suffixes into token sequences, sorted by length for greedy matching.
def _build_suffix_sequences(raw_suffixes: List[str]) -> List[Tuple[str, ...]]:
    seqs = set()
    for s in raw_suffixes:
        tokens = tuple(_tokenize(s))
        if tokens:
            seqs.add(tokens)
    # Sort by token count descending, then by total character length descending.
    return sorted(seqs, key=lambda t: (-len(t), -sum(len(x) for x in t)))

# Pre-compiled and sorted suffix token sequences.
SUFFIX_SEQUENCES = _build_suffix_sequences(RAW_SUFFIXES)

# Iteratively removes trailing suffix tokens from a list.
def _strip_trailing_suffix_tokens(tokens: List[str]) -> List[str]:
    changed = True
    while changed and tokens:
        changed = False
        for seq in SUFFIX_SEQUENCES:
            n = len(seq)
            if n <= len(tokens) and tokens[-n:] == list(seq):
                tokens = tokens[:-n]
                changed = True
                break # Restart scan with the longest suffix after a removal.
    return tokens

def is_dirty_value(name: str) -> bool:
    if not isinstance(name, str):
        return False
    # Perform a case-insensitive and space-trimmed comparison
    return name.strip().lower() in DIRTY_VALUES

def filter_dirty_values(names_series):
    # Create a boolean mask for dirty values using a case-insensitive and space-trimmed check
    # .str.strip() removes leading/trailing whitespace
    # .str.lower() converts to lowercase
    # .isin() checks against the lowercase DIRTY_VALUES list
    is_dirty_mask = names_series.str.strip().str.lower().isin(DIRTY_VALUES)
    # Return the series where the mask is False (i.e., not dirty)
    return names_series[~is_dirty_mask]

# Main function to clean and normalize a company name.
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    
    # Standardize ampersand and case.
    name = name.lower().replace('&', 'and')

    # Tokenize and safely strip trailing suffixes.
    tokens = _tokenize(name)
    tokens = _strip_trailing_suffix_tokens(tokens)

    # Optional: Standardize spelling and plurals.
    # Use American English and singular forms to improve levenshtein matching.
    replacements = {
        'australia': 'au',
        'aluminium': 'aluminum',
        'sulphur': 'sulfur',
        'haematite': 'hematite',
        'resources': 'resource',
        'minerals': 'mineral',
        'steels': 'steel',
        'diamonds': 'diamond',
    }
    tokens = [replacements.get(tok, tok) for tok in tokens]

    return ' '.join(tokens)