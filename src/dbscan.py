import re
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree, sort_graph_by_row_values
from sklearn.cluster import DBSCAN
from scipy.sparse import coo_matrix

INPUT  = "./data/processed/dbscaninput.csv"
OUTPUT = "./data/processed/Aggregation_with_constraints-5000km.csv"

# ---------------------------
# 1) 读数据 & 预处理
# ---------------------------
df_all = pd.read_csv(INPUT).fillna("")

def parse_to_set(text: str) -> set:
    """按逗号/分号切分为集合；统一小写去空。"""
    if not isinstance(text, str) or not text.strip():
        return set()
    return {t.strip().lower() for t in re.split(r"[;,]+", text) if t.strip()}

def normalize_name(name: str) -> str:
    """DEPOSIT_NAME 作为整体，不拆分；仅做去空&小写的规范化（保留逗号等原字符）。"""
    if not isinstance(name, str):
        return ""
    return name.strip().lower()

# 仅构造 COMMODITY_PRIMARY 的集合
df_all["COMMODITY_PRIMARY_SET"] = [parse_to_set(x) for x in df_all.get("COMMODITY_PRIMARY", "")]

# SYNONYMS 仍按逗号/分号切分
df_all["SYNONYMS_SET"] = [parse_to_set(x) for x in df_all.get("SYNONYMS", "")]

# DEPOSIT_NAME 作为单一整体 token（不拆分），并并入“名称集合”用于同名判断
name_tokens = df_all.get("DEPOSIT_NAME", "").astype(str).map(normalize_name)
df_all["NAME_SET"] = [
    (s.union({n}) if n else s)
    for s, n in zip(df_all["SYNONYMS_SET"], name_tokens)
]

# 只处理：SYNONYMS 或 DEPOSIT_NAME 至少有一个名字（即 NAME_SET 非空）且 COMMODITY_PRIMARY 非空
mask_eligible = (df_all["NAME_SET"].map(len) > 0) & (df_all["COMMODITY_PRIMARY_SET"].map(len) > 0)
df = df_all.loc[mask_eligible].copy()

if df.empty:
    raise ValueError("No eligible rows: NAME_SET and COMMODITY_PRIMARY are both required and non-empty.")

# ---------------------------
# 2) Location 候选（半径内邻居）
# ---------------------------
EARTH_R = 6371.0
eps_km  = 5000
eps_rad = eps_km / EARTH_R

coords_rad = np.radians(df[["LAT_GDA94", "LONG_GDA94"]].to_numpy())  # (lat, lon) in radians
tree = BallTree(coords_rad, metric="haversine")

# 半径内候选邻居：索引+距离（弧度）
neigh_idx_list, neigh_dist_list = tree.query_radius(coords_rad, r=eps_rad, return_distance=True, sort_results=False)

# ---------------------------
# 3) 先判“名称集合”交集（DEPOSIT_NAME 整体 + SYNONYMS），再判 COMMODITY_PRIMARY 交集
# ---------------------------
rows, cols, dists_km = [], [], []
name_sets = df["NAME_SET"].values
cprim     = df["COMMODITY_PRIMARY_SET"].values

for i in range(len(df)):
    si, ci = name_sets[i], cprim[i]
    idxs, dists_rad = neigh_idx_list[i], neigh_dist_list[i]

    for j, d_rad in zip(idxs, dists_rad):
        if i == j:
            continue
        # 1) 名称交集（DEPOSIT_NAME 作为整体已并入 NAME_SET）
        if si.isdisjoint(name_sets[j]):
            continue
        # 2) 主商品交集
        if ci.isdisjoint(cprim[j]):
            continue
        # 3) 位置已在半径内，保留真实距离
        rows.append(i)
        cols.append(j)
        dists_km.append(d_rad * EARTH_R)

# 稀疏距离矩阵（只包含满足 1/2 且在半径内的边）
n = len(df)
dist_sparse = coo_matrix((dists_km, (rows, cols)), shape=(n, n)).tocsr()
dist_sparse = sort_graph_by_row_values(dist_sparse, warn_when_not_sorted=False)

# ---------------------------
# 4) DBSCAN（预计算距离，单位=公里）
# ---------------------------
db = DBSCAN(eps=eps_km, min_samples=2, metric="precomputed")
labels = db.fit_predict(dist_sparse)

df["PROJECT_ID"] = labels
sizes = pd.Series(labels).value_counts()
df["PROJECT_SIZE"] = df["PROJECT_ID"].map(sizes)

# ---------------------------
# 5) 导出（保留原数据所有列 + 追加聚类列）
# ---------------------------
orig_cols = list(df_all.columns)
out_cols = orig_cols + [c for c in ["PROJECT_ID", "PROJECT_SIZE"] if c not in orig_cols]

df.sort_values(["PROJECT_ID","DEPOSIT_NAME"], na_position="last")[out_cols] \
  .to_csv(OUTPUT, index=False, encoding="utf-8")

print(f"Saved: {OUTPUT} (eps = {eps_km} km)")
print("Eligible rows:", len(df))
print("Cluster size distribution (PROJECT_ID -> count):")
print(df["PROJECT_ID"].value_counts().sort_index())
