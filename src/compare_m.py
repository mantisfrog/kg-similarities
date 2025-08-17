import re
import pandas as pd
import geopandas as gpd

DEPOSITS_CSV_PATH = './data/MineralDeposits.csv'
PROVINCES_SHP_PATH = './raw/116823_AGP_2018/ProvinceFullExtent.shp'
OUTPUT_CSV_PATH = './data/compare_Metallogenic.csv'

# ---------- 1) 读入矿床表 ----------
df = pd.read_csv(DEPOSITS_CSV_PATH)
orig_cols = df.columns.tolist()

# 安全处理：确保必要列存在
for col in ['PROVINCES', 'LONG_GDA94', 'LAT_GDA94']:
    if col not in df.columns:
        raise ValueError(f'Missing required column: {col}')

# ---------- 2) 从 PROVINCES 列抽取包含 "Metallogenic" 的那一项 ----------
def extract_metallogenic_token(text: str):
    if pd.isna(text):
        return pd.NA
    s = str(text)

    # 优先：严格匹配“被逗号包裹”的片段 , ...Metallogenic...
    m = re.search(r'(?i)(?<=,)\s*([^,]*metallogenic[^,]*)\s*(?=,)', s)
    if m:
        return m.group(1).strip()

    # 退而求其次：按逗号分割，找包含 metallogenic 的项（兼容在首/尾没有逗号的情况）
    parts = [p.strip() for p in s.split(',') if p.strip()]
    hits = [p for p in parts if re.search(r'(?i)metallogenic', p)]
    if not hits:
        return pd.NA
    # 若有多个，合并；也可改为 hits[0]
    return '; '.join(hits)

df['Metallogenic Province'] = df['PROVINCES'].apply(extract_metallogenic_token)

# ---------- 3) 读省份面层，仅保留 TYPE=metallogenic ----------
prov = gpd.read_file(PROVINCES_SHP_PATH)

# 规范 TYPE，筛选成矿省
type_norm = prov['TYPE'].astype(str).str.strip().str.lower()
met_gdf = prov[type_norm.eq('metallogenic')].copy()

# 仅保留必要字段，避免后续列名冲突
met_gdf = met_gdf[['NAME', 'geometry']].rename(columns={'NAME': 'NAME_MET'})

# ---------- 4) 把矿床点转为 GeoDataFrame（EPSG:4283） ----------
pts_gdf = gpd.GeoDataFrame(
    df.copy(),
    geometry=gpd.points_from_xy(df['LONG_GDA94'], df['LAT_GDA94']),
    crs='EPSG:4283'
)

# ---------- 5) 统一坐标系并空间连接 ----------
# 若省份图层有 CRS，按其 CRS 转换点；否则假定也是 EPSG:4283
if met_gdf.crs:
    pts_in_prov_crs = pts_gdf.to_crs(met_gdf.crs)
else:
    met_gdf = met_gdf.set_crs('EPSG:4283', allow_override=True)
    pts_in_prov_crs = pts_gdf

# 使用 sjoin 查找点所在的成矿省；用 'within' 避免边界多命中
joined = gpd.sjoin(pts_in_prov_crs, met_gdf, how='left', predicate='within')

# 如果有重复（极少数点与多个面相交），对每个点只取第一条
joined_first = (joined
                .reset_index()
                .sort_values(['index'])  # 保持原顺序
                .drop_duplicates(subset=['index'], keep='first')
                .set_index('index'))

# 回填到原 df（不带 geometry）
df_out = joined_first.drop(columns=['geometry']).copy()
df_out.rename(columns={'NAME_MET': 'Metallogenic Province FROM SHP'}, inplace=True)

# ---------- 6) 将两个新列放到表尾并输出 ----------
final_cols = orig_cols + [c for c in df_out.columns if c not in orig_cols and c != 'geometry']
df_out = df_out[final_cols]

df_out.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
print(f'Done. Saved to: {OUTPUT_CSV_PATH}')
