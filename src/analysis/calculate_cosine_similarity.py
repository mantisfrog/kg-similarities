#!/usr/bin/env python
# -*- coding: utf-8 -*-

import torch
import torch.nn.functional as F
import pandas as pd
import sys
from pathlib import Path
import math

# ---- 项目内 import ----
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
from src import config


def calculate_similarity():
    """
    加载训练好的 embeddings 和 ID 映射，计算公司间的相似度（使用 per-type 的 Company 向量）。
    """
    # =================================================================
    # ---- 在这里设置你要查询的公司 ID ----
    #
    COMPANY_A_ID = "comp_5"   # <-- 修改这里
    COMPANY_B_ID = "comp_2"   # <-- 修改这里
    #
    # 示例 2 (Top-K) 使用的目标公司 ID
    TARGET_COMPANY_ID_FOR_TOP_K = "comp_5"  # <-- 修改这里
    TOP_K = 5  # 取前 K 个相似公司（不含自身）
    # =================================================================

    print("Loading embeddings and ID maps...")
    try:
        # 加载 embedding 文件（现在应为按类型的 dict，包含 'Company'）
        all_embeddings = torch.load(config.OUTPUT_EMBEDDINGS_PATH, weights_only=False)
        # 加载 ID 映射文件（按类型分别存放 Series）
        id_maps = torch.load(config.ID_MAPS_PATH, weights_only=False)
    except FileNotFoundError as e:
        print(f"Error: Could not find required file. {e}")
        print("Please ensure train_metapath2vec.py has been run successfully.")
        return

    # ---- 取 Company 的向量表 ----
    if isinstance(all_embeddings, dict) and ('Company' in all_embeddings):
        company_embeddings = all_embeddings['Company']  # [N_company, dim]
        print("Detected per-type embedding tables. Using 'Company' embeddings.")
    elif isinstance(all_embeddings, dict) and ('NODE' in all_embeddings):
        print("Found a single 'NODE' table. This script expects per-type embeddings.")
        print("Please re-run training script that saves per-type slices via model('<type>').")
        return
    else:
        print("Error: Could not find 'Company' embeddings in the loaded file.")
        return

    company_id_map = id_maps.get('Company')
    if company_id_map is None or len(company_id_map) == 0:
        print("Error: Could not find non-empty 'Company' ID map.")
        return

    if company_embeddings.shape[0] != len(company_id_map):
        print(f"[warn] Row count mismatch: embeddings={company_embeddings.shape[0]} vs id_map={len(company_id_map)}")
        # 若不一致，继续也许会索引错位；谨慎起见直接退出
        # 你也可以在这里做截断/对齐，但强烈建议先排查源头
        return

    print(f"Loaded {company_embeddings.shape[0]} company embeddings with dim={company_embeddings.shape[1]}.")
    print(f"Loaded {len(company_id_map)} company ID mappings.")

    # ---- 建 neo4j_id -> index 的查找表 ----
    company_neo4j_ids = company_id_map.to_numpy()  # 顺序应与 embeddings 行对齐
    neo4j_to_idx = {neo4j_id: i for i, neo4j_id in enumerate(company_neo4j_ids)}

    # ---- 归一化（更稳的余弦相似度）----
    # 对整张矩阵做 L2 归一化；目标向量同样归一化
    company_embeddings = F.normalize(company_embeddings, p=2, dim=1)

    # ================= Example 1 =================
    print("\n--- Example 1: Similarity between two companies ---")
    try:
        idx_A = neo4j_to_idx[COMPANY_A_ID]
        idx_B = neo4j_to_idx[COMPANY_B_ID]
    except KeyError as e:
        print(f"Company ID not found in id_maps: {e}")
        return

    vec_A = company_embeddings[idx_A]  # [dim]
    vec_B = company_embeddings[idx_B]  # [dim]
    # 归一化后，cosine 就是内积
    sim_AB = torch.dot(vec_A, vec_B).item()

    print(f"Neo4j ID for Company A: {COMPANY_A_ID}")
    print(f"Neo4j ID for Company B: {COMPANY_B_ID}")
    print(f"Cosine Similarity: {sim_AB:.4f}")

    # ================= Example 2 =================
    print("\n--- Example 2: Find Top-{} similar companies ---".format(TOP_K))
    try:
        target_idx = neo4j_to_idx[TARGET_COMPANY_ID_FOR_TOP_K]
    except KeyError as e:
        print(f"Company ID not found in id_maps: {e}")
        return

    target_vec = company_embeddings[target_idx]  # [dim]

    # 与所有公司计算相似度（归一化后 -> 直接矩阵-向量乘）
    # sims: [N_company]
    sims = torch.mv(company_embeddings, target_vec)

    # 排除自身
    sims[target_idx] = -math.inf

    # 取 Top-K
    k = min(TOP_K, sims.shape[0] - 1)
    top_vals, top_inds = torch.topk(sims, k=k, largest=True, sorted=True)

    print(f"Finding companies most similar to Company with Neo4j ID: {TARGET_COMPANY_ID_FOR_TOP_K}")
    for rank, (score, idx) in enumerate(zip(top_vals.tolist(), top_inds.tolist()), start=1):
        similar_company_id = company_neo4j_ids[idx]
        print(f"  - Rank {rank}: Company ID {similar_company_id} (Similarity: {score:.4f})")


if __name__ == "__main__":
    calculate_similarity()
