def get_match_status(w_ratio, levenshtein_ratio, secondary_scores):
    """
    Applies a set of rules to determine the match status based on similarity scores.

    Args:
        w_ratio (float): The weighted ratio score from rapidfuzz.
        levenshtein_ratio (float): The Levenshtein ratio score.
        secondary_scores (dict): A dictionary containing other similarity scores like
                                 'no_space_exact_match', 'au_removed_match',
                                 'jaccard_similarity', and 'spacy_similarity'.

    Returns:
        str: The determined match status, e.g., 'no_space_exact_match',
             'confident_score_match', or 'identified_candidates'.
    """
    if secondary_scores.get("no_space_exact_match") == 1:
        return "no_space_exact_match"
    if secondary_scores.get("au_removed_match") == 1:
        return "au_removed_match"
    if (w_ratio >= 95 and
            levenshtein_ratio >= 90 and
            secondary_scores.get("jaccard_similarity", 0) >= 0.5 and
            secondary_scores.get("spacy_similarity", 0) >= 0.5):
        return "confident_score_match"
    
    return "identified_candidates"