import pandas as pd
import geopandas as gpd

DEPOSITS_CSV_PATH = './src/data/MineralDeposits.csv'
PROVINCES_SHP_PATH = './src/raw/116823_AGP_2018/ProvinceFullExtent.shp'
OUTPUT_CSV_PATH = './src/data/Deposits_spatial.csv'

def process_deposits_with_provinces(deposits_path, provinces_path, output_path):
    """
    Load deposits (CSV) and provinces (shapefile), spatially join them,
    and write deposits annotated with province names by TYPE (igneous/metallogenic/sedimentary/tectonic).
    """
    try:
        # 1) Load data
        print("Step 1/5: Loading data...")
        deposits_df = pd.read_csv(deposits_path)
        provinces_gdf = gpd.read_file(provinces_path)
        print(f"Loaded {len(deposits_df)} deposits and {len(provinces_gdf)} province polygons.")

        # Stable key to merge back results later
        deposits_df['original_index'] = range(len(deposits_df))

        # 2) Build GeoDataFrame for deposits (GDA94 = EPSG:4283)
        print("Step 2/5: Building point geometries...")
        deposits_df.dropna(subset=['LONG_GDA94', 'LAT_GDA94'], inplace=True)
        deposits_gdf = gpd.GeoDataFrame(
            deposits_df,
            geometry=gpd.points_from_xy(deposits_df.LONG_GDA94, deposits_df.LAT_GDA94),
            crs="EPSG:4283"
        )

        # 3) Spatial join (ensure same CRS)
        print("Step 3/5: Performing spatial join (this may take a while)...")
        provinces_gdf = provinces_gdf.to_crs(deposits_gdf.crs)

        # --- 关键：TYPE 统一为小写，避免大小写不一致带来的漏匹配 ---
        if 'TYPE' in provinces_gdf.columns:
            provinces_gdf['TYPE'] = provinces_gdf['TYPE'].astype(str).str.strip().str.lower()
        else:
            raise KeyError("Shapefile 缺少 TYPE 字段")

        if 'NAME' not in provinces_gdf.columns:
            raise KeyError("Shapefile 缺少 NAME 字段")

        joined_gdf = gpd.sjoin(deposits_gdf, provinces_gdf, how='left', predicate='intersects')
        print("Spatial join done.")

        # 4) Pivot matched province names into columns by TYPE
        print("Step 4/5: Reshaping join results...")
        # 目标类型集（含 metallogenic），并指定最终列顺序
        target_types_order = ["igneous", "metallogenic", "sedimentary", "tectonic"]

        filtered_join = joined_gdf[joined_gdf['TYPE'].isin(target_types_order)]
        result_df = filtered_join[['original_index', 'NAME', 'TYPE']].drop_duplicates()

        province_info = (result_df
            .pivot_table(index='original_index', columns='TYPE', values='NAME', aggfunc='first')
            .reset_index()
        )

        # 确保四列都存在（即使某类在数据中不存在）
        for t in target_types_order:
            if t not in province_info.columns:
                province_info[t] = None

        # 5) Merge back and save
        print("Step 5/5: Merging and saving...")
        final_df = pd.merge(deposits_df, province_info, on='original_index', how='left')

        # 删除不需要的列（存在才删）
        columns_to_drop = ['original_index', 'ACCURACY_M', 'COMPANY_WEBSITES', 'DEPOSIT_MODEL']
        final_df.drop(columns=[c for c in columns_to_drop if c in final_df.columns], inplace=True)

        # 调整列顺序：把四个类型列放到表尾且顺序固定
        # 先把列名都转大写
        final_df.columns = [c.upper() for c in final_df.columns]
        # 目标顺序（大写）
        tail_cols = ["IGNEOUS", "METALLOGENIC", "SEDIMENTARY", "TECTONIC"]
        # 不在 tail 的列保持原顺序
        leading_cols = [c for c in final_df.columns if c not in tail_cols]
        final_df = final_df[leading_cols + tail_cols]

        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Done! Output saved to: {output_path}")

    except FileNotFoundError as e:
        print(f"Error: file not found - {e}. Check your paths.")
    except Exception as e:
        print(f"Error during processing: {e}")

if __name__ == "__main__":
    process_deposits_with_provinces(DEPOSITS_CSV_PATH, PROVINCES_SHP_PATH, OUTPUT_CSV_PATH)
