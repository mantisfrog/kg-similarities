#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path
import math
import argparse
import torch
import pandas as pd
import numpy as np

from sklearn.decomposition import PCA

try:
    import umap
    HAS_UMAP = True
except Exception:
    HAS_UMAP = False

try:
    from sklearn.manifold import TSNE
    HAS_TSNE = True
except Exception:
    HAS_TSNE = False

import matplotlib.pyplot as plt
import torch.nn.functional as F

# ---- 项目内 import ----
project_root = Path(__file__).resolve().parents[2]
import sys
sys.path.append(str(project_root))
from src import config


def load_embeddings_and_idmaps():
    emb_path = Path(os.environ.get("MP2V_EMBEDDINGS_PATH", config.OUTPUT_EMBEDDINGS_PATH))
    idmap_path_env = "src/feature/id_mappings_subgraph.pt"
    idmap_path = Path(idmap_path_env) if idmap_path_env else Path(config.ID_MAPS_PATH)

    if not emb_path.exists():
        raise FileNotFoundError(f"Embeddings not found: {emb_path}")
    all_embeddings = torch.load(emb_path, weights_only=False)

    if not idmap_path.exists():
        # 兼容你在 subgraph 模式下可能把 idmap 存在 feature 目录的情况
        sub_path = config.FEATURE_DIR / "id_mappings_subgraph.pt"
        if sub_path.exists():
            idmap_path = sub_path
        else:
            raise FileNotFoundError(f"ID maps not found: {idmap_path}")

    id_maps = torch.load(idmap_path, weights_only=False)
    return all_embeddings, id_maps, emb_path, idmap_path


def assemble_matrix(all_embeddings, id_maps, keep_types=("Company", "Project")):
    rows = []
    metas = []
    for t in keep_types:
        if t not in all_embeddings:
            continue
        Z = all_embeddings[t]
        ids = id_maps.get(t)
        if ids is None or len(ids) != Z.shape[0]:
            # 回退到 CSV 索引重建
            csv_dir = Path(os.environ.get("MP2V_EMBEDDINGS_CSV_DIR", config.EMBEDDINGS_CSV_DIR))
            csv_path = csv_dir / f"{t}_embeddings.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path, index_col=0)
                if df.shape[0] == Z.shape[0]:
                    ids = pd.Series(df.index.tolist())
        if ids is None or len(ids) != Z.shape[0]:
            raise RuntimeError(f"ID map mismatch for {t}: got {len(ids) if ids is not None else 0} vs {Z.shape[0]}")

        rows.append(Z)
        metas.extend([(t, str(i)) for i in ids.to_numpy()])

    if not rows:
        raise RuntimeError(f"No embeddings found for types={keep_types}")

    X = torch.vstack(rows).detach().cpu()
    meta_df = pd.DataFrame(metas, columns=["node_type", "node_id"])
    return X, meta_df


def reduce_to_2d(X, method="auto", pca_dim=50, random_state=42):
    X_np = X.numpy()
    # 先 PCA 降到 50 维（常见 trick：提速、去噪）
    d = min(pca_dim, X_np.shape[1], X_np.shape[0]-1)
    if d >= 2:
        X_pca = PCA(n_components=d, random_state=random_state).fit_transform(X_np)
    else:
        X_pca = X_np

    # UMAP 优先（更擅长保持邻域结构），否则 t-SNE
    if (method == "umap" or method == "auto") and HAS_UMAP:
        reducer = umap.UMAP(n_neighbors=30, min_dist=0.1, n_components=2, random_state=random_state, metric="euclidean")
        Y = reducer.fit_transform(X_pca)
        used = "umap"
    elif (method == "tsne" or method == "auto") and HAS_TSNE:
        # 合理 perplexity：不超过 N/3
        N = X_pca.shape[0]
        perp = max(5, min(30, N // 3))
        reducer = TSNE(n_components=2, perplexity=perp, learning_rate="auto", init="pca", random_state=random_state)
        Y = reducer.fit_transform(X_pca)
        used = "tsne"
    else:
        # 兜底：直接取前两主成分
        Y = X_pca[:, :2]
        used = "pca2"
    return Y, used


def build_knn_edges(highdim_X, meta_df, topk_same=10, topk_cross=5, min_sim=0.45):
    """
    在高维空间（归一化后）做 cosine Top-K：
      - Company↔Company：每个 Company 连 topk_same 条
      - Project↔Project：每个 Project 连 topk_same 条
      - Company↔Project：每个 Company 连 topk_cross 条（和项目）
    返回 edges DataFrame: source_id, target_id, sim, edge_type
    """
    # 归一化
    Xn = F.normalize(highdim_X, p=2, dim=1)
    types = meta_df["node_type"].to_numpy()
    ids = meta_df["node_id"].to_numpy()

    # 索引切片
    c_idx = np.where(types == "Company")[0]
    p_idx = np.where(types == "Project")[0]

    edges = []

    def topk_block(I):
        # I 子集内部 TopK
        Xi = Xn[I]
        S = Xi @ Xi.T  # cosine sim
        np.fill_diagonal(S.numpy(), -math.inf)
        k = min(topk_same, len(I) - 1)
        if k <= 0:
            return
        vals, idxs = torch.topk(S, k=k, dim=1, largest=True, sorted=True)
        for row, (vs, js) in enumerate(zip(vals, idxs)):
            s_id = ids[I[row]]
            for v, j in zip(vs.tolist(), js.tolist()):
                if v < min_sim:
                    continue
                t_id = ids[I[j]]
                edges.append((s_id, t_id, float(v), f"{types[I[row]][:1]}2{types[I[j]][:1]}"))

    # Company↔Company
    if len(c_idx) > 1:
        topk_block(c_idx)

    # Project↔Project
    if len(p_idx) > 1:
        topk_block(p_idx)

    # Company ↔ Project（按 Company 找最近项目）
    if topk_cross > 0 and len(c_idx) > 0 and len(p_idx) > 0:
        Xc = Xn[c_idx]
        Xp = Xn[p_idx]
        S = Xc @ Xp.T
        k = min(topk_cross, len(p_idx))
        vals, idxs = torch.topk(S, k=k, dim=1, largest=True, sorted=True)
        for i, (vs, js) in enumerate(zip(vals, idxs)):
            s_id = ids[c_idx[i]]
            for v, j in zip(vs.tolist(), js.tolist()):
                if v < min_sim:
                    continue
                t_id = ids[p_idx[j]]
                edges.append((s_id, t_id, float(v), "C2P"))

    edge_df = pd.DataFrame(edges, columns=["source_id", "target_id", "sim", "edge_type"])
    return edge_df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["auto", "umap", "tsne", "pca2"], default="auto")
    parser.add_argument("--pca_dim", type=int, default=50)
    parser.add_argument("--topk_same", type=int, default=10)
    parser.add_argument("--topk_cross", type=int, default=5)
    parser.add_argument("--min_sim", type=float, default=0.45)
    parser.add_argument("--outdir", type=str, default=str(config.FEATURE_DIR / "viz"))
    args = parser.parse_args()

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_embeddings, id_maps, emb_path, idmap_path = load_embeddings_and_idmaps()
    X, meta_df = assemble_matrix(all_embeddings, id_maps, keep_types=("Company", "Project"))

    # 2D 降维
    Y, used = reduce_to_2d(X, method=args.method, pca_dim=args.pca_dim)
    meta_df["x"] = Y[:, 0]
    meta_df["y"] = Y[:, 1]

    # 保存点坐标
    nodes_csv = out_dir / "emb_2d_nodes.csv"
    meta_df.to_csv(nodes_csv, index=False)

    # 画散点（两次 scatter：Company 一次、Project 一次）
    plt.figure(figsize=(8, 6), dpi=160)
    mask_c = (meta_df["node_type"] == "Company").to_numpy()
    mask_p = (meta_df["node_type"] == "Project").to_numpy()
    plt.scatter(meta_df.loc[mask_c, "x"], meta_df.loc[mask_c, "y"], s=10, alpha=0.7, label="Company")
    plt.scatter(meta_df.loc[mask_p, "x"], meta_df.loc[mask_p, "y"], s=6, alpha=0.6, label="Project")
    plt.legend()
    plt.title(f"2D embedding ({used}) - Company & Project")
    plt.tight_layout()
    scatter_path = out_dir / "emb_2d_scatter.png"
    plt.savefig(scatter_path)

    # 构建高维相似度 kNN 边
    edge_df = build_knn_edges(X, meta_df, topk_same=args.topk_same, topk_cross=args.topk_cross, min_sim=args.min_sim)
    edges_csv = out_dir / "emb_knn_edges.csv"
    edge_df.to_csv(edges_csv, index=False)

    print(f"[ok] Saved:\n - nodes: {nodes_csv}\n - edges: {edges_csv}\n - scatter: {scatter_path}")
    print(f"[info] Embeddings: {emb_path}\n       ID maps:   {idmap_path}\n       Reduce:    {used}")


if __name__ == "__main__":
    main()
