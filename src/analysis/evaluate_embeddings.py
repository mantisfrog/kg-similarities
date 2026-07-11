#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Evaluate MetaPath2Vec embeddings across runs.

What it does
- Loads one or more embedding runs (either .pt dict or *_embeddings.csv directory)
- Aligns with id_mappings and graph indices
- Computes lightweight link prediction metrics per relation:
  - ROC-AUC, Average Precision (AP)
  - Sampled Hits@K (approximate, using sampled candidates)
- Writes a CSV summary and prints a concise table

Usage examples
  python -m src.analysis.evaluate_embeddings \
    --run baseline src/feature/node_embeddings.pt \
    --max-pos 1500 --neg-per-pos 5 --hits-cands 200 --k 10

  python -m src.analysis.evaluate_embeddings \
    --run runA /path/to/expA/node_embeddings.pt \
    --run runB /path/to/expB/embeddings_csv \
    --relations OWNS,LOCATED_IN,HAS_COMMODITY,DOMICILED_IN --k 10 --out src/feature/emb_eval_results.csv

Notes
- Hits@K here is computed against a sampled candidate set (hits-cands) for speed.
- Ensure the id_mappings.pt used during training is available. The script
  will try: MP2V_ID_MAPS_PATH env, co-located with embeddings, then config path.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score

# Project imports
import sys
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
from src import config


# ----------------------------- Data classes -----------------------------
@dataclass
class RunSpec:
    name: str
    path: Path  # file (.pt) or directory (CSV dir)
    id_maps_path: Optional[Path] = None  # optional override


# ----------------------------- Utilities -----------------------------
def _load_embeddings(run: RunSpec) -> Dict[str, torch.Tensor]:
    """Load embeddings for a run.
    - If path is a .pt file: expect dict {node_type: Tensor[Ni, D]}
    - If path is a directory: read CSVs like '{Type}_embeddings.csv'
    Returns a dict of tensors (float32) keyed by node type.
    """
    p = run.path
    if p.is_file() and p.suffix == ".pt":
        obj = torch.load(p, weights_only=False)
        if not isinstance(obj, dict):
            raise ValueError(f"Expected dict in PT file, got {type(obj)} at {p}")
        out = {}
        for k, v in obj.items():
            if not isinstance(v, torch.Tensor):
                v = torch.tensor(np.asarray(v), dtype=torch.float32)
            out[k] = v.detach().float()
        return out

    if p.is_dir():
        tensors: Dict[str, torch.Tensor] = {}
        for csv_path in p.glob("*_embeddings.csv"):
            name = csv_path.name
            # Expect '{NodeType}_embeddings.csv'
            if not name.endswith("_embeddings.csv"):
                continue
            node_type = name[: -len("_embeddings.csv")]
            df = pd.read_csv(csv_path, index_col=0)
            # Store tensor; alignment handled later using id_maps
            tensors[node_type] = torch.tensor(df.values, dtype=torch.float32)
        if not tensors:
            raise FileNotFoundError(f"No '*_embeddings.csv' found under {p}")
        return tensors

    raise FileNotFoundError(f"Embeddings path not found or unsupported: {p}")


def _try_load_id_maps_for_run(run: RunSpec, all_embeddings: Dict[str, torch.Tensor]):
    """Load id_mappings.pt matching the embeddings.
    Priority:
      1) run.id_maps_path if provided
      2) env MP2V_ID_MAPS_PATH
      3) sibling of embeddings file (same dir)
      4) inside embeddings dir (if path is dir)
      5) config.ID_MAPS_PATH
    Additionally validates rough shape match to embeddings.
    """
    candidates: List[Path] = []
    if run.id_maps_path:
        candidates.append(run.id_maps_path)
    env_p = os.environ.get("MP2V_ID_MAPS_PATH")
    if env_p:
        candidates.append(Path(env_p))
    if run.path.is_file():
        candidates.append(run.path.parent / "id_mappings.pt")
    if run.path.is_dir():
        candidates.append(run.path / "id_mappings.pt")
    candidates.append(config.ID_MAPS_PATH)

    tried: List[Tuple[Path, str]] = []
    for cand in candidates:
        if not cand or not cand.exists():
            continue
        try:
            id_maps = torch.load(cand, weights_only=False)
        except Exception as e:
            tried.append((cand, f"load_error:{e}"))
            continue
        # Basic shape sanity: if any overlapping type, lengths should match rows
        ok = True
        for t, Z in all_embeddings.items():
            if t in id_maps:
                try:
                    if len(id_maps[t]) != Z.shape[0]:
                        ok = False
                        break
                except Exception:
                    ok = False
                    break
        if ok:
            return id_maps, cand
        tried.append((cand, "shape_mismatch"))

    detail = ", ".join([f"{p}({why})" for p, why in tried])
    raise RuntimeError(
        "Could not find matching id_mappings.pt for embeddings. "
        f"Tried: {detail}. You can pass MP2V_ID_MAPS_PATH or place id_mappings.pt next to the embeddings."
    )


def _normalize_all(emb: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    return {t: F.normalize(Z, p=2, dim=1) for t, Z in emb.items()}


def _score_pairs(
    Zs: Dict[str, torch.Tensor],
    src_type: str,
    dst_type: str,
    src_idx: torch.Tensor,
    dst_idx: torch.Tensor,
) -> torch.Tensor:
    """Dot-product scores (cosine if vectors are normalized)."""
    Zs_src = Zs[src_type]
    Zs_dst = Zs[dst_type]
    a = Zs_src.index_select(0, src_idx.long())
    b = Zs_dst.index_select(0, dst_idx.long())
    return (a * b).sum(dim=1)


def _sample_edges(ei: torch.Tensor, max_pos: int) -> torch.Tensor:
    E = ei.shape[1]
    if E <= max_pos:
        return ei
    idx = torch.randperm(E)[:max_pos]
    return ei[:, idx]


def _sample_negative_dst(
    num_dst: int,
    pos_dst: torch.Tensor,
    num_neg_per_pos: int,
) -> torch.Tensor:
    """Uniformly sample negatives per positive (no adjacency check for speed)."""
    n_pos = pos_dst.numel()
    neg = torch.randint(low=0, high=num_dst, size=(n_pos, num_neg_per_pos), dtype=torch.long)
    # Avoid trivial equality to the positive
    mask_same = neg.eq(pos_dst.view(-1, 1))
    if mask_same.any():
        neg[mask_same] = (neg[mask_same] + 1) % num_dst
    return neg


def _resolve_forward_etype(data, src: str, rel: str, dst: str):
    """Resolve actual edge type in data for a given (src, rel, dst).
    Prefers exact match, then case-insensitive (lowercased relation).
    Does not flip to reverse; evaluates only the forward edge.
    Returns a tuple (src, rel_in_data, dst) or None if not found.
    """
    if (src, rel, dst) in data.edge_types:
        return (src, rel, dst)
    rlow = rel.lower()
    if (src, rlow, dst) in data.edge_types:
        return (src, rlow, dst)
    return None


def evaluate_relation(
    emb: Dict[str, torch.Tensor],
    data,
    etype: Tuple[str, str, str],
    max_pos: int,
    num_neg_per_pos: int,
    hits_cands: int,
    k: int,
) -> Dict[str, float]:
    src, rel, dst = etype
    resolved = _resolve_forward_etype(data, src, rel, dst)
    if not resolved:
        return {"auc": np.nan, "ap": np.nan, "hits@k": np.nan, "n_pos": 0}
    src, rel, dst = resolved

    # Basic availability check
    if src not in emb or dst not in emb:
        return {"auc": np.nan, "ap": np.nan, "hits@k": np.nan, "n_pos": 0}

    ei = data[(src, rel, dst)].edge_index
    if ei.numel() == 0:
        return {"auc": np.nan, "ap": np.nan, "hits@k": np.nan, "n_pos": 0}

    # Subsample positives for speed
    ei_s = _sample_edges(ei, max_pos)
    pos_src = ei_s[0].long().contiguous()
    pos_dst = ei_s[1].long().contiguous()
    n_pos = pos_src.numel()

    # Negative sampling
    num_dst = getattr(data[dst], 'num_nodes', emb[dst].shape[0])
    neg_dst = _sample_negative_dst(num_dst, pos_dst, num_neg_per_pos)  # [n_pos, R]

    # Scores
    pos_scores = _score_pairs(emb, src, dst, pos_src, pos_dst)
    # For ROC/AP we flatten negatives
    neg_src_flat = pos_src.repeat_interleave(num_neg_per_pos)
    neg_dst_flat = neg_dst.view(-1)
    neg_scores = _score_pairs(emb, src, dst, neg_src_flat, neg_dst_flat)

    # Metrics: ROC-AUC and AP
    y_true = np.concatenate([np.ones_like(pos_scores.numpy()), np.zeros_like(neg_scores.numpy())])
    y_score = np.concatenate([pos_scores.numpy(), neg_scores.numpy()])
    try:
        auc = roc_auc_score(y_true, y_score)
    except Exception:
        auc = np.nan
    try:
        ap = average_precision_score(y_true, y_score)
    except Exception:
        ap = np.nan

    # Hits@K (sampled): for each positive (u,v), compare with sampled candidates
    # Build candidate destination set per positive
    # Use a fresh sample of candidates for hits, excluding the true dst if collides
    hits = []
    cand_per_pos = max(k, hits_cands)
    num_dst_total = num_dst
    for i in range(n_pos):
        u = pos_src[i].item()
        v = pos_dst[i].item()
        cands = torch.randint(low=0, high=num_dst_total, size=(cand_per_pos,), dtype=torch.long)
        # Ensure true v is included and unique
        if (cands == v).any():
            # ok, already present
            pass
        else:
            if cand_per_pos > 0:
                cands[0] = v
        # Compute scores for u against candidates
        uu = torch.full_like(cands, fill_value=u)
        scores = _score_pairs(emb, src, dst, uu, cands)
        # Rank descending
        ranks = torch.argsort(scores, descending=True)
        # Position where candidate equals v
        pos_in_rank = (cands[ranks] == v).nonzero(as_tuple=False)
        if pos_in_rank.numel() == 0:
            hits.append(0.0)
        else:
            r = int(pos_in_rank[0].item()) + 1  # 1-based rank
            hits.append(1.0 if r <= k else 0.0)
    hits_k = float(np.mean(hits)) if hits else float("nan")

    return {"auc": float(auc), "ap": float(ap), "hits@k": hits_k, "n_pos": int(n_pos)}


def select_relations(requested: Optional[Sequence[str]]) -> List[Tuple[str, str, str]]:
    """Filter relations by name; None -> a useful default subset."""
    rels = config.RELATION_TYPES
    if requested:
        names = {r.strip().upper() for r in requested}
        return [(s, r, d) for (s, r, d) in rels if r.upper() in names]
    # Default: commonly interesting signal-bearing relations
    keep = {"OWNS", "LOCATED_IN", "HAS_COMMODITY", "DOMICILED_IN", "CLASSIFIED_AS", "CATEGORISED_AS"}
    return [(s, r, d) for (s, r, d) in rels if r in keep]


def main(argv: Optional[Sequence[str]] = None):
    ap = argparse.ArgumentParser(description="Evaluate embeddings across runs")
    ap.add_argument("--run", nargs=2, action="append", metavar=("NAME", "PATH"), required=True,
                    help="Add a run: a name and a path to .pt or CSV directory. Repeatable.")
    ap.add_argument("--relations", type=str, default=None,
                    help="Comma-separated relation names to evaluate (e.g., OWNS,LOCATED_IN). Default uses a sensible subset.")
    ap.add_argument("--max-pos", type=int, default=1500, help="Max positive edges per relation.")
    ap.add_argument("--neg-per-pos", type=int, default=5, help="# negatives per positive for AUC/AP.")
    ap.add_argument("--hits-cands", type=int, default=200, help="Candidate negatives per positive for Hits@K.")
    ap.add_argument("--k", type=int, default=10, help="K for Hits@K.")
    ap.add_argument("--out", type=str, default=None, help="Optional CSV path to write results.")

    args = ap.parse_args(argv)

    # Parse runs
    runs: List[RunSpec] = []
    for name, path_str in args.run:
        runs.append(RunSpec(name=name, path=Path(path_str)))

    # Parse requested relations
    rel_filter = None
    if args.relations:
        rel_filter = [x.strip() for x in args.relations.split(",") if x.strip()]
    rels = select_relations(rel_filter)
    if not rels:
        print("No relations selected. Check --relations.")
        return

    # Load graph
    if not config.HETERO_DATA_PATH.exists():
        raise FileNotFoundError(f"Graph not found: {config.HETERO_DATA_PATH}")
    data = torch.load(config.HETERO_DATA_PATH, weights_only=False)

    rows = []
    for run in runs:
        emb_raw = _load_embeddings(run)
        id_maps, id_path = _try_load_id_maps_for_run(run, emb_raw)

        # When loading from CSVs, reorder rows to match id_maps so that indices align with graph
        emb_reordered: Dict[str, torch.Tensor] = {}
        for t, Z in emb_raw.items():
            if t in id_maps:
                # If Z rows already match id_maps length, assume consistent ordering for .pt
                # For CSVs, reindex by id_maps values where possible
                if isinstance(Z, torch.Tensor):
                    Zt = Z
                else:
                    Zt = torch.tensor(np.asarray(Z), dtype=torch.float32)

                N = Zt.shape[0]
                try:
                    m = id_maps[t]
                    # If Zt shape equals len(m), keep as is; else try to realign using CSV indices if provided
                    if N == len(m):
                        emb_reordered[t] = Zt
                    else:
                        raise ValueError("row_mismatch")
                except Exception:
                    # As a fallback, try to rebuild order via CSV index if available next to embeddings
                    # This is best-effort; if not possible, raise with guidance
                    raise RuntimeError(
                        f"Embedding rows for '{t}' do not match id_maps length. Ensure you pass the matching id_mappings.pt for run '{run.name}'."
                    )
            else:
                # Keep as is; may be unused type for selected relations
                emb_reordered[t] = Z

        # Normalize for cosine similarity
        emb = _normalize_all(emb_reordered)

        for et in rels:
            metrics = evaluate_relation(
                emb=emb,
                data=data,
                etype=et,
                max_pos=args.max_pos,
                num_neg_per_pos=args.neg_per_pos,
                hits_cands=args.hits_cands,
                k=args.k,
            )
            rows.append({
                "run": run.name,
                "src": et[0],
                "rel": et[1],
                "dst": et[2],
                "n_pos": metrics["n_pos"],
                "auc": metrics["auc"],
                "ap": metrics["ap"],
                f"hits@{args.k}": metrics["hits@k"],
            })

    df = pd.DataFrame(rows)
    # Compute macro means per run
    if not df.empty:
        grp = df.groupby("run")[["auc", "ap", f"hits@{args.k}"]].mean().reset_index()
        print("\nMacro averages by run:")
        print(grp.to_string(index=False))
        print("\nPer-relation metrics:")
        cols = ["run", "src", "rel", "dst", "n_pos", "auc", "ap", f"hits@{args.k}"]
        print(df[cols].to_string(index=False))

    # Write CSV if requested
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"\nSaved evaluation results to: {out_path}")


if __name__ == "__main__":
    main()
