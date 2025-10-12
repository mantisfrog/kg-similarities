from rapidfuzz import fuzz
from typing import Tuple, Optional, Set, Dict

def select_best_candidate(
    source_name: str,
    target_index: Dict[str, Set[str]],
    w_ratio_threshold: int = 80
) -> Tuple[Optional[str], float, float]:
    """
    Selects the best candidate from potential matches based on WRatio and Levenshtein ratio.

    A candidate is only considered if its WRatio score is above the threshold.
    Tie-breaking for identical WRatio scores is done using the Levenshtein ratio.

    Args:
        source_name: The normalized name to find a match for.
        target_index: A word index of the target company names for efficient lookup.
        w_ratio_threshold: The minimum WRatio score to be considered a candidate.

    Returns:
        A tuple containing:
        - The best matching normalized name (or None if no candidate meets the threshold).
        - The WRatio score of the best match (-1.0 if no candidate).
        - The Levenshtein ratio of the best match (-1.0 if no candidate).
    """
    words = source_name.split()
    potential_matches = set()
    for word in words:
        potential_matches.update(target_index.get(word, set()))

    if not potential_matches:
        return None, -1.0, -1.0

    best_match_normalized = None
    highest_w_ratio = -1.0
    highest_lev_for_best_w = -1.0

    for candidate_name in potential_matches:
        w_ratio = fuzz.WRatio(source_name, candidate_name)
        
        if w_ratio < w_ratio_threshold:
            continue

        lev_ratio = fuzz.ratio(source_name, candidate_name)

        # If current candidate's w_ratio is higher, it's the new best.
        # If w_ratio is the same, use levenshtein ratio to break the tie.
        if w_ratio > highest_w_ratio:
            highest_w_ratio = w_ratio
            highest_lev_for_best_w = lev_ratio
            best_match_normalized = candidate_name
        elif w_ratio == highest_w_ratio:
            if lev_ratio > highest_lev_for_best_w:
                highest_lev_for_best_w = lev_ratio
                best_match_normalized = candidate_name
    
    if best_match_normalized:
        return best_match_normalized, highest_w_ratio, highest_lev_for_best_w
    else:
        return None, -1.0, -1.0