#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Diagnose metapath first/second-hop coverage on your (sub)graph.
- Loads graph + metapaths.json
- (Optional) Rebuilds the same subgraph used for training via env flags
- Prints cov1/cov2 per unique metapath, sorted by weakest first
- Optional CSV export

Env flags (mimic your training):
  MP2V_SUBGRAPH=1|0
  MP2V_COMPANY_IDS_FILE=src/analysis/seed_companies.txt
  MP2V_TOPK_PROJECTS=100 (<=0 means ALL; see DIAG_STRICT_TOPK below)
  REPEAT_SCALE (default 10.0) only affects weight->replication (we dedup later)

Special flag:
  DIAG_STRICT_TOPK=-1
    If set to "-1", treat TOPK=-1 with the *old buggy semantics* (slice[:-1]),
    to mimic your previous training run exactly. Otherwise, TOPK<=0 means "ALL".

Optional:
  DIAG_OUT_CSV=1  -> write CSV to config.FEATURE_DIR / "metapath_coverage.csv"
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pandas as pd
import torch
from torch_geometric.data import HeteroData
from torch_geometric.utils import subgraph

# --- Project-internal Imports ---
# Add the project root to the system path to allow direct imports from 'src'
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
from src import config
from src.analysis.train_metapath2vec import (
    build_company_subgraph,
    dedup_metapaths,
    load_graph_and_metapaths,
    repeat_metapaths,
)

def diagnose_first_hop_coverage(
    data: HeteroData, uniq_paths: List[Tuple[str, str, str]]
) -> List[Tuple[Tuple, float, float | None]]:
    """
    Calculates the 1-hop and 2-hop coverage for a list of metapaths.

    Args:
        data: The HeteroData graph object.
        uniq_paths: A list of unique metapaths to diagnose.

    Returns:
        A list of tuples, where each tuple contains the metapath, its 1-hop
        coverage, and its 2-hop coverage. The list is sorted by coverage.
    """
    report = []
    # Create a dictionary for quick lookup of edge indices by edge type
    edges = {et: data[et].edge_index for et in data.edge_types}

    for mp in uniq_paths:
        # --- 1-Hop Coverage Calculation ---
        # cov1 = (nodes of source type that have an outgoing edge) / (total nodes of source type)
        s1, r1, d1 = mp[0]  # Source, relation, destination for the first hop
        ei = edges.get((s1, r1, d1))
        total = getattr(data[s1], 'num_nodes', 0)

        if ei is None or total == 0:
            cov1 = 0.0
        else:
            # Calculate the number of unique source nodes that participate in this edge type
            num_source_nodes_with_edge = ei[0].unique().numel()
            cov1 = num_source_nodes_with_edge / total

        # --- 2-Hop Coverage Calculation ---
        # cov2 = (nodes reached in hop1 that can start hop2) / (total unique nodes reached in hop1)
        cov2 = None
        if len(mp) >= 2:
            s2, r2, d2 = mp[1]  # Source, relation, destination for the second hop
            ei2 = edges.get((s2, r2, d2))

            if ei is not None and ei2 is not None:
                # Find the intersection of nodes that are destinations of hop 1 and sources of hop 2
                dest_nodes_hop1 = ei[1].unique()
                source_nodes_hop2 = ei2[0].unique()
                intersection_count = dest_nodes_hop1.intersect(source_nodes_hop2).numel()
                
                # Avoid division by zero if no nodes were reached in hop 1
                total_dest_nodes_hop1 = max(1, dest_nodes_hop1.numel())
                cov2 = intersection_count / total_dest_nodes_hop1

        report.append((mp, cov1, cov2))

    # Sort the report to show the weakest metapaths first (by cov1, then cov2)
    return sorted(report, key=lambda x: (x[1], x[2] if x[2] is not None else 0))


def main():
    """
    Main execution function to run the metapath diagnosis.
    """
    # --- Configuration from Environment Variables ---
    use_subgraph = os.environ.get("MP2V_SUBGRAPH") == "1"
    company_ids_file = os.environ.get("MP2V_COMPANY_IDS_FILE")
    top_k_projects = int(os.environ.get("MP2V_TOPK_PROJECTS", -1))
    repeat_scale = float(os.environ.get("REPEAT_SCALE", 10.0))
    strict_topk = os.environ.get("DIAG_STRICT_TOPK") == "-1"
    out_csv = os.environ.get("DIAG_OUT_CSV") == "1"

    # --- Load Data ---
    print("Loading graph and metapaths...")
    data, metapaths, id_map, rev_id_map = load_graph_and_metapaths()
    
    # --- Subgraph Creation (Optional) ---
    if use_subgraph:
        print(f"Building subgraph from seed companies in: {company_ids_file}")
        with open(company_ids_file, "r") as f:
            company_ids = [line.strip() for line in f if line.strip()]
        
        data, id_map, rev_id_map = build_company_subgraph(
            data, id_map, company_ids, top_k_projects, strict_topk
        )
        print("Subgraph built.")

    # --- Metapath Preparation ---
    # Deduplicate metapaths to diagnose each unique path only once
    uniq_paths = dedup_metapaths(metapaths)
    
    # --- Run Diagnosis ---
    print("Diagnosing metapath coverage...")
    report = diagnose_first_hop_coverage(data, uniq_paths)

    # --- Print Report to Console ---
    print("\n" + "=" * 80)
    print("Metapath Coverage Report (Sorted by Weakest First)")
    print("-" * 80)
    print(f"{'Metapath':<55} {'Coverage-1':<12} {'Coverage-2':<12}")
    print("-" * 80)

    for mp, cov1, cov2 in report:
        path_str = " > ".join([f"{s}-{r[:4]}->{d}" for s, r, d in mp])
        cov1_str = f"{cov1:.3f}"
        cov2_str = f"{cov2:.3f}" if cov2 is not None else "N/A"
        print(f"{path_str:<55} {cov1_str:<12} {cov2_str:<12}")
    print("=" * 80)

    # --- CSV Export (Optional) ---
    if out_csv:
        df_data = []
        for mp, cov1, cov2 in report:
            path_str = " > ".join([f"{s}-{r}->{d}" for s, r, d in mp])
            df_data.append({
                "metapath": path_str,
                "coverage_1": cov1,
                "coverage_2": cov2,
                "hops": len(mp)
            })
        
        df = pd.DataFrame(df_data)
        out_path = config.FEATURE_DIR / "metapath_coverage.csv"
        df.to_csv(out_path, index=False)
        print(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
