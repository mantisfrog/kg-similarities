#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fast & robust MetaPath2Vec training with weighted multi-metapath support (PyG 2.6.x)
- 单表 embedding（PyG 设计如此），保存时按 node_type 切片导出 per-type 向量。
- 按权重抽样 K 条路径/epoch + 每条路径限定最大 batch 数（CPU 友好）。
- 训练前校验 metapath 合法性；从边索引反推各类型节点数，避免越界。
- 训练后导出 .pt（dict: {node_type: Tensor}）与 .csv（结合 id_mappings）。
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pandas as pd
import torch
import torch.optim as optim
from tqdm import tqdm
from torch_geometric.nn.models import MetaPath2Vec

# ---- 项目内 import ----
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
from src import config

# ---------------- Hyperparams ----------------
EMBEDDING_DIM = int(os.environ.get("MP2V_DIM", 128))
WALK_LENGTH = int(os.environ.get("MP2V_WALK_LENGTH", 50))
CONTEXT_SIZE = int(os.environ.get("MP2V_CONTEXT_SIZE", 7))
WALKS_PER_NODE = int(os.environ.get("MP2V_WALKS_PER_NODE", 15))
NUM_NEGATIVE_SAMPLES = int(os.environ.get("MP2V_NEG", 5))
BATCH_SIZE = int(os.environ.get("MP2V_BATCH", 64))
LEARNING_RATE = float(os.environ.get("MP2V_LR", 0.01))
EPOCHS = int(os.environ.get("MP2V_EPOCHS", 50))
NUM_WORKERS = int(os.environ.get("MP2V_WORKERS", 0))  # CPU/WSL 推荐 0；Linux 可 1~2
SEED = int(os.environ.get("MP2V_SEED", 42))

SAMPLED_PATHS_PER_EPOCH = int(os.environ.get("MP2V_K", 20))
MAX_STEPS_PER_PATH = int(os.environ.get("MP2V_MAX_STEPS", 5000))

REPEAT_SCALE = float(os.environ.get("MP2V_REPEAT_SCALE", 10.0))
RELATION_TYPES = config.RELATION_TYPES
VERBOSE = True


# ---------------- Utilities ----------------
def set_seed(seed: int = 42):
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_schema_map(
    relation_types: Sequence[Tuple[str, str, str]]
) -> Dict[Tuple[str, str], str]:
    schema_map: Dict[Tuple[str, str], str] = {}
    for src, rel, dst in relation_types:
        r = rel.lower()
        schema_map[(src, dst)] = r
        schema_map[(dst, src)] = f"rev_{r}"
    return schema_map


def parse_metapath_string(
    path_string: str, schema_map: Dict[Tuple[str, str], str]
):
    nodes = path_string.split('>')
    parsed: List[List[str]] = []
    for i in range(len(nodes) - 1):
        s, d = nodes[i], nodes[i + 1]
        if (s, d) not in schema_map:
            raise ValueError(
                f"Invalid metapath hop: '{s}>{d}' in '{path_string}'. Check RELATION_TYPES."
            )
        parsed.append([s, schema_map[(s, d)], d])
    return parsed


def load_and_process_metapaths(
    cfg_path: str,
    schema_map: Dict[Tuple[str, str], str],
    repeat_scale: float = 1.0,
) -> List[List[Tuple[str, str, str]]]:
    with open(cfg_path, 'r', encoding='utf-8') as f:
        conf = json.load(f)
    all_paths: List[List[Tuple[str, str, str]]] = []
    print("Processing metapaths from simplified JSON config...")
    for path_group in conf.values():
        for path_string, w in path_group.items():
            try:
                steps = parse_metapath_string(path_string, schema_map)
            except ValueError as e:
                print(f" - Skip '{path_string}': {e}")
                continue
            weight = float(w)
            reps = max(1, int(round(weight * repeat_scale)))
            all_paths.extend([[tuple(s) for s in steps]] * reps)
            print(f" - Path '{path_string}' (weight={weight}, reps={reps})")
    return all_paths


def validate_metapaths_against_graph(
    metapath_list: List[List[Tuple[str, str, str]]], data
) -> List[List[Tuple[str, str, str]]]:
    existing = set(data.edge_types)
    ok, bad = [], []
    for mp in metapath_list:
        if not mp:
            continue
        good = True
        for (s1, r1, d1), (s2, r2, d2) in zip(mp[:-1], mp[1:]):
            if (s1, r1, d1) not in existing:
                bad.append(("missing_edge", mp, (s1, r1, d1))); good=False; break
            if d1 != s2:
                bad.append(("type_mismatch", mp, (s1, r1, d1), (s2, r2, d2))); good=False; break
        if good and (mp[-1] not in existing):
            bad.append(("missing_edge", mp, mp[-1])); good=False
        if good:
            ok.append(mp)
    if bad:
        print(f"[warn] Dropped {len(bad)} metapaths. Examples:")
        for b in bad[:3]:
            print(" ->", b)
    return ok


def build_edge_index_dict(data):
    return {etype: data[etype].edge_index for etype in data.edge_types}


def infer_num_nodes_dict_from_edges(data) -> Dict[str, int]:
    max_idx = {nt: -1 for nt in data.node_types}
    for s, r, d in data.edge_types:
        ei = data[(s, r, d)].edge_index
        if ei.numel() == 0:
            continue
        max_idx[s] = max(max_idx[s], int(ei[0].max().item()))
        max_idx[d] = max(max_idx[d], int(ei[1].max().item()))
    return {
        nt: (m + 1 if m >= 0 else getattr(data[nt], 'num_nodes', 0))
        for nt, m in max_idx.items()
    }


def print_estimated_steps(data, metapaths: List[List[Tuple[str, str, str]]]):
    counts = {nt: getattr(data[nt], 'num_nodes', 0) for nt in data.node_types}
    total = 0
    for i, mp in enumerate(metapaths):
        start = mp[0][0]; n = counts.get(start, 0)
        steps = math.ceil(n * WALKS_PER_NODE / BATCH_SIZE)
        print(f"[{i:02d}] start={start:<18} nodes={n:<8} steps≈{steps}")
        total += steps
    print(f"≈ total steps per epoch (if all paths used): {total}")


def make_unique_paths_and_probs(metapaths: List[List[Tuple[str, str, str]]]):
    key_func = lambda mp: tuple(mp)
    ctr = Counter(key_func(mp) for mp in metapaths)
    unique_paths = [list(k) for k in ctr.keys()]
    weights = [float(v) for v in ctr.values()]
    s = sum(weights)
    probs = [w / s for w in weights]
    return unique_paths, probs


def _validate_num_nodes_dict_for_metapaths(num_nodes_dict: Dict[str, int],
                                           metapaths: List[List[Tuple[str, str, str]]]):
    needed = set()
    for mp in metapaths:
        for (s, _, d) in mp:
            needed.add(s); needed.add(d)
    missing = [t for t in sorted(needed) if int(num_nodes_dict.get(t, 0)) <= 0]
    if missing:
        raise ValueError(
            f"num_nodes_dict missing/zero for node types: {missing}. "
            "请检查 HeteroData 中这些类型是否有节点和相关边。"
        )


# ---------------- Training ----------------
def train(data, metapaths: List[List[Tuple[str, str, str]]]):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\nUsing device: {device}")
    if not metapaths:
        raise ValueError("No metapaths to train on.")

    edge_index_dict = build_edge_index_dict(data)
    num_nodes_dict = infer_num_nodes_dict_from_edges(data)

    # 观测声明与推断的差异
    for nt in data.node_types:
        declared = getattr(data[nt], 'num_nodes', None)
        inferred = num_nodes_dict.get(nt, None)
        if declared is not None and inferred is not None and declared < inferred:
            print(f"[warn] {nt}: data.num_nodes={declared} < inferred_from_edges={inferred} -> will use inferred")

    _validate_num_nodes_dict_for_metapaths(num_nodes_dict, metapaths)

    node_type_counts = {nt: getattr(data[nt], 'num_nodes', 0) for nt in data.node_types}

    # CPU 友好：自动放大 MAX_STEPS_PER_PATH
    start_type = metapaths[0][0][0]
    est_steps = math.ceil(node_type_counts.get(start_type, 0) * WALKS_PER_NODE / BATCH_SIZE)
    auto_max_steps = max(MAX_STEPS_PER_PATH, int(est_steps * 1.2))
    if auto_max_steps != MAX_STEPS_PER_PATH:
        print(f"[auto] steps/epoch≈{est_steps}, raise MAX_STEPS_PER_PATH -> {auto_max_steps}")
    _MAX_STEPS_PER_PATH = auto_max_steps

    # 构造模型（PyG：始终一张 embedding 表 + 类型偏移；forward('<type>') 负责切片）
    model = MetaPath2Vec(
        edge_index_dict=edge_index_dict,
        embedding_dim=EMBEDDING_DIM,
        metapath=metapaths[0],
        walk_length=WALK_LENGTH,
        context_size=CONTEXT_SIZE,
        walks_per_node=WALKS_PER_NODE,
        num_negative_samples=NUM_NEGATIVE_SAMPLES,
        num_nodes_dict=num_nodes_dict,
        sparse=True,
    ).to(device)

    if VERBOSE:
        import torch_geometric
        print(f"[env] torch={torch.__version__}, torch_geometric={torch_geometric.__version__}")
        print(f"[env] node_types(all)={list(data.node_types)}")
        print(f"[env] num_nodes_dict={num_nodes_dict}")

        # 可切片的类型 = 有偏移的类型；仅这些能被 model('<type>') 调用
        available = list(getattr(model, "start", {}).keys())
        print(f"[env] sliceable_types(from model.start)={available}")

    optimizer = optim.SparseAdam(list(model.parameters()), lr=LEARNING_RATE)

    uniq_paths, probs = make_unique_paths_and_probs(metapaths)

    print("Starting training (weighted sampling of metapaths)...")
    epoch_pbar = tqdm(range(1, EPOCHS + 1), desc="Epochs", position=0)
    for epoch in epoch_pbar:
        model.train(); total_loss = 0.0; total_steps = 0

        K = min(SAMPLED_PATHS_PER_EPOCH, len(uniq_paths))
        sampled_idx = random.choices(range(len(uniq_paths)), weights=probs, k=K)

        path_estimates=[]; epoch_total_est=0
        for idx in sampled_idx:
            mp = uniq_paths[idx]; start_type = mp[0][0]
            n = node_type_counts.get(start_type, 0)
            est = math.ceil(n * WALKS_PER_NODE / BATCH_SIZE)
            est = min(est, _MAX_STEPS_PER_PATH)
            path_estimates.append(est); epoch_total_est += est

        epoch_steps_pbar = tqdm(total=epoch_total_est, desc=f"Epoch {epoch} Batches", leave=False, position=2)
        path_pbar = tqdm(sampled_idx, desc=f"Epoch {epoch} Paths", leave=False, position=1)

        for j, idx in enumerate(path_pbar):
            mp = uniq_paths[idx]
            path_str = ' > '.join([step[0] for step in mp] + [mp[-1][-1]])
            path_pbar.set_description(f"Path: {path_str[:40]}...")
            est_for_path = path_estimates[j]

            model.metapath = mp
            loader = model.loader(batch_size=BATCH_SIZE, shuffle=True, num_workers=NUM_WORKERS)
            steps = 0
            try:
                for pos_rw, neg_rw in loader:
                    optimizer.zero_grad()
                    loss = model.loss(pos_rw.to(device), neg_rw.to(device))
                    loss.backward(); optimizer.step()
                    total_loss += loss.item(); steps += 1; total_steps += 1
                    epoch_steps_pbar.update(1)
                    if steps >= _MAX_STEPS_PER_PATH: break
            except IndexError as e:
                start_type = mp[0][0] if mp else "UNKNOWN"
                try: start_idx_max = int(pos_rw[:, 0].max().item())
                except Exception: start_idx_max = "N/A"
                emb_size = model.embedding.weight.size(0)
                print(f"[error] IndexError on metapath={mp} start_type={start_type} "
                      f"start_max={start_idx_max} emb_size={emb_size} -> skip. Detail: {e}")
            finally:
                delta = steps - est_for_path
                if delta != 0:
                    epoch_steps_pbar.total += delta; epoch_steps_pbar.refresh()

        epoch_steps_pbar.close()
        avg_loss = total_loss / max(1, total_steps)
        epoch_pbar.set_postfix(loss=f"{avg_loss:.4f}", steps=total_steps)

    return model


@torch.no_grad()
def save_embeddings(model: MetaPath2Vec, id_maps: Dict[str, pd.Series]):
    """只导出模型“可切片”的类型：即 model.start 里存在偏移的 node_type。"""
    model.eval()

    # 可切片类型（真正被建模的类型）
    start_dict = getattr(model, "start", None)
    if not start_dict:
        raise RuntimeError("model.start 为空，无法确定可导出的 node types。")
    node_types = list(start_dict.keys())

    # 记录哪些类型被跳过（例如：在 HeteroData 里有节点，但没出现在任何边上）
    all_known = set(getattr(model, "num_nodes_dict", {}).keys())
    skipped = sorted(list(all_known - set(node_types)))
    if skipped:
        print(f"[info] Skip types with no offsets (not in edges/metapaths): {skipped}")

    # 按类型调用 model('<type>') 得到切片向量
    all_embeddings = {}
    for nt in node_types:
        try:
            all_embeddings[nt] = model(nt).detach().cpu()
        except KeyError:
            # 极端情况下 start/end 缺键（防御性处理）
            print(f"[warn] '{nt}' missing in model.start; skip.")
        except Exception as e:
            print(f"[warn] Failed to slice embeddings for '{nt}': {e}")

    if not all_embeddings:
        raise RuntimeError("No embeddings were sliced; nothing to save.")

    # .pt 保存
    torch.save(all_embeddings, config.OUTPUT_EMBEDDINGS_PATH)
    print(f"\n[ok] Per-type node embeddings saved to '{config.OUTPUT_EMBEDDINGS_PATH}'")
    print(f"[ok] Saved types: {list(all_embeddings.keys())}")

    # .csv 保存
    out_dir = Path(config.EMBEDDINGS_CSV_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    print("Saving embeddings to CSV files...")
    for nt, Z_t in tqdm(all_embeddings.items(), desc="Saving Node Types"):
        Z = Z_t.numpy()
        if id_maps and nt in id_maps and hasattr(id_maps[nt], 'to_numpy'):
            ids = id_maps[nt].to_numpy()
        else:
            ids = pd.RangeIndex(Z.shape[0]).to_numpy()
        df = pd.DataFrame(Z, index=ids).add_prefix('dim_')
        df.index.name = f"{nt}_neo4j_id"
        (out_dir / f"{nt}_embeddings.csv").write_text(df.to_csv())


# ---------------- Main ----------------
if __name__ == "__main__":
    set_seed(SEED)

    if not os.path.exists(config.HETERO_DATA_PATH):
        print(f"Error: Graph data file not found at '{config.HETERO_DATA_PATH}'."); sys.exit(1)
    print("Loading graph data and ID mappings...")
    data = torch.load(config.HETERO_DATA_PATH, weights_only=False)
    id_maps = torch.load(config.ID_MAPS_PATH, weights_only=False) if os.path.exists(config.ID_MAPS_PATH) else None
    print("Data loaded successfully.")

    schema_lookup = build_schema_map(RELATION_TYPES)
    metapaths = load_and_process_metapaths(config.METAPATH_CONFIG_PATH, schema_lookup, repeat_scale=REPEAT_SCALE)
    if not metapaths: print("No valid metapaths from config. Exit."); sys.exit(1)

    metapaths = validate_metapaths_against_graph(metapaths, data)
    if not metapaths: print("All metapaths were invalid after validation. Exit."); sys.exit(1)
    print(f"Using {len(metapaths)} metapaths after weighting & validation.")

    print_estimated_steps(data, metapaths)

    model = train(data, metapaths)
    save_embeddings(model, id_maps)

    print("\nEmbedding generation process completed successfully.")
