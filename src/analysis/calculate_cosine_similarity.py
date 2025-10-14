#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import torch
import torch.nn.functional as F
import pandas as pd
import sys
from pathlib import Path
import math

# Add project root to sys.path to allow imports from the 'src' directory
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
from src import config

# Default path for ID mappings generated during subgraph training
DEFAULT_SUB_ID_MAPS_PATH = config.FEATURE_DIR / "id_mappings_subgraph.pt"


def _id_maps_match_embeddings(id_maps: dict, all_embeddings: dict) -> bool:
    """
    Checks if the provided ID maps are consistent with the loaded embeddings.
    It compares the number of IDs for each node type with the number of embedding vectors.
    """
    try:
        # Ensure id_maps is a dictionary-like object
        items = id_maps.items()
    except AttributeError:
        return False
    
    for node_type, embeddings in all_embeddings.items():
        if node_type not in id_maps:
            continue
        try:
            # The number of embedding rows must match the number of IDs in the map
            if embeddings.shape[0] != len(id_maps[node_type]):
                return False
        except Exception:
            # Handle cases where id_maps[node_type] might not have a length
            return False
    return True


def load_matching_id_maps(all_embeddings: dict):
    """
    Loads the most suitable ID mapping file that corresponds to the embeddings.
    It searches in a prioritized order and selects the first file where the
    node counts match the embedding dimensions.
    
    Search Order:
      1. Path from MP2V_ID_MAPS_PATH environment variable.
      2. Default full-graph ID map path from config.
      3. Default subgraph ID map path.
    """
    candidates = []
    env_path = os.environ.get("MP2V_ID_MAPS_PATH")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(config.ID_MAPS_PATH)
    if DEFAULT_SUB_ID_MAPS_PATH not in candidates:
        candidates.append(DEFAULT_SUB_ID_MAPS_PATH)

    attempted = []
    for path in candidates:
        if not path or not path.exists():
            continue
        try:
            id_maps = torch.load(path, weights_only=False)
        except Exception as e:
            print(f"[warn] Failed to load ID maps from '{path}': {e}")
            continue
        
        # If counts match, this is the correct file
        if _id_maps_match_embeddings(id_maps, all_embeddings):
            print(f"[info] Using ID maps from '{path}'.")
            return id_maps, path
        attempted.append((path, id_maps))

    # If no perfect match is found, use the first valid file as a fallback
    if attempted:
        fallback_path, fallback_maps = attempted[0]
        print(f"[warn] Falling back to ID maps from '{fallback_path}', but row counts may mismatch.")
        return fallback_maps, fallback_path

    raise FileNotFoundError(
        "Could not find a usable ID maps file. "
        "Please set MP2V_ID_MAPS_PATH to the matching id_mappings file saved during training."
    )


def run_similarity_analysis(node_type: str, all_embeddings: dict, id_maps: dict, id_a: str, id_b: str, top_k: int):
    """
    Performs pairwise similarity and Top-K similarity search for a given node type.
    """
    print(f"\n{'='*20} Analysis for Node Type: {node_type} {'='*20}")

    # Extract embeddings and ID map for the specified node type
    if node_type not in all_embeddings:
        print(f"Error: Could not find '{node_type}' embeddings in the loaded file.")
        return
    embeddings = all_embeddings[node_type]

    id_map = id_maps.get(node_type)
    if id_map is None or len(id_map) == 0:
        print(f"Error: Could not find a non-empty '{node_type}' ID map.")
        return

    # Handle cases where embedding rows and ID map length do not match
    if embeddings.shape[0] != len(id_map):
        print(f"[warn] Row count mismatch for {node_type}: embeddings={embeddings.shape[0]} vs id_map={len(id_map)}")
        csv_dir = Path(os.environ.get("MP2V_EMBEDDINGS_CSV_DIR", config.EMBEDDINGS_CSV_DIR))
        csv_path = csv_dir / f"{node_type}_embeddings.csv"
        
        # Attempt to rebuild the ID map from the corresponding CSV file as a fallback
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path, index_col=0)
            except Exception as e:
                print(f"[warn] Failed to rebuild ID map from '{csv_path}': {e}")
                return
            if df.shape[0] != embeddings.shape[0]:
                print(f"[warn] CSV row count mismatch for {node_type}: csv_rows={df.shape[0]} vs embeddings={embeddings.shape[0]}")
                print("Set MP2V_ID_MAPS_PATH to the matching id_mappings file saved during training.")
                return
            id_map = pd.Series(df.index.tolist())
            print(f"[info] Rebuilt '{node_type}' ID map from '{csv_path}'.")
        else:
            print("These embeddings were likely trained on a subgraph."
                  " Set MP2V_ID_MAPS_PATH to the matching id_mappings file saved during training.")
            return

    print(f"Loaded {embeddings.shape[0]} {node_type.lower()} embeddings with dim={embeddings.shape[1]}.")

    # Create a lookup from Neo4j ID to tensor index for fast access
    neo4j_ids = id_map.to_numpy()
    neo4j_to_idx = {neo4j_id: i for i, neo4j_id in enumerate(neo4j_ids)}

    # Normalize embeddings to unit vectors for efficient cosine similarity calculation (dot product)
    embeddings = F.normalize(embeddings, p=2, dim=1)

    # --- Example 1: Pairwise Similarity ---
    print(f"\n--- Example 1: Similarity between two {node_type.lower()}s ---")
    try:
        idx_A = neo4j_to_idx[id_a]
        idx_B = neo4j_to_idx[id_b]
    except KeyError as e:
        print(f"{node_type} ID not found in id_maps: {e}")
        return

    vec_A = embeddings[idx_A]
    vec_B = embeddings[idx_B]
    sim_AB = torch.dot(vec_A, vec_B).item()

    print(f"Neo4j ID for {node_type} A: {id_a}")
    print(f"Neo4j ID for {node_type} B: {id_b}")
    print(f"Cosine Similarity: {sim_AB:.4f}")

    # --- Example 2: Top-K Similarity Search ---
    print(f"\n--- Example 2: Find Top-{top_k} similar {node_type.lower()}s ---")
    try:
        target_idx = neo4j_to_idx[id_a]
    except KeyError as e:
        print(f"{node_type} ID not found in id_maps: {e}")
        return

    # Calculate cosine similarity between the target vector and all other vectors
    target_vec = embeddings[target_idx]
    sims = torch.mv(embeddings, target_vec)
    sims[target_idx] = -math.inf  # Exclude self from results

    # Get the top K results
    k = min(top_k, sims.shape[0] - 1)
    top_vals, top_inds = torch.topk(sims, k=k, largest=True, sorted=True)

    print(f"Finding entities most similar to {node_type} with Neo4j ID: {id_a}")
    for rank, (score, idx) in enumerate(zip(top_vals.tolist(), top_inds.tolist()), start=1):
        similar_id = neo4j_ids[idx]
        print(f"  - Rank {rank}: {node_type} ID {similar_id} (Similarity: {score:.4f})")


def main():
    """
    Main function to load data and run similarity analysis for companies and projects.
    """
    TOP_K = 5
    # Company IDs for pairwise comparison and Top-K search
    COMPANY_A_ID = "comp_2"
    COMPANY_B_ID = "comp_3"
    #
    # Project IDs for pairwise comparison and Top-K search
    PROJECT_A_ID = "project_2831"
    PROJECT_B_ID = "project_2411"
    #
    TOP_K = 5

    print("Loading embeddings and ID maps...")
    try:
        emb_path = Path(os.environ.get("MP2V_EMBEDDINGS_PATH", config.OUTPUT_EMBEDDINGS_PATH))
        all_embeddings = torch.load(emb_path, weights_only=False)
        id_maps, id_map_path = load_matching_id_maps(all_embeddings)
    except FileNotFoundError as e:
        print(f"Error: Could not find required file. {e}")
        print("Please ensure train_metapath2vec.py has been run successfully.")
        return

    # --- Run analysis for Companies ---
    run_similarity_analysis(
        node_type="Company",
        all_embeddings=all_embeddings,
        id_maps=id_maps,
        id_a=COMPANY_A_ID,
        id_b=COMPANY_B_ID,
        top_k=TOP_K
    )

    # --- Run analysis for Projects ---
    run_similarity_analysis(
        node_type="Project",
        all_embeddings=all_embeddings,
        id_maps=id_maps,
        id_a=PROJECT_A_ID,
        id_b=PROJECT_B_ID,
        top_k=TOP_K
    )


if __name__ == "__main__":
    main()
